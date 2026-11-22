#!/usr/bin/env python3
"""Split a release file into GitHub-safe chunks and restore it losslessly.

GitHub rejects files larger than 25 MB (and recommends keeping individual
files well below that).  A 20,000,000-byte chunk leaves enough headroom for
GitHub's counting method while keeping the number of parts small.

Examples:
    python tools/release_chunks.py split dist/BlockStartLauncher.exe --out dist
    python tools/release_chunks.py verify dist/BlockStartLauncher.exe.manifest.json
    python tools/release_chunks.py restore dist/BlockStartLauncher.exe.manifest.json \
        --dest C:/Temp/BlockStartLauncher.exe
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

CHUNK_SIZE = 20_000_000  # 20 MB, safely below GitHub's 25 MB limit


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def _part_name(name: str, index: int) -> str:
    return f"{name}.part{index:02d}"


def split_file(source: Path, out_dir: Path, chunk_size: int = CHUNK_SIZE) -> Path:
    source = source.resolve()
    out_dir = out_dir.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if chunk_size <= 0 or chunk_size >= 25 * 1024 * 1024:
        raise ValueError("chunk_size must be > 0 and below 25 MiB")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Remove old parts for this exact file so a shorter rebuild cannot leave
    # a stale tail that would be concatenated by the launcher.
    for old in out_dir.glob(source.name + ".part*"):
        old.unlink()

    parts = []
    with source.open("rb") as handle:
        index = 1
        while True:
            data = handle.read(chunk_size)
            if not data:
                break
            part = out_dir / _part_name(source.name, index)
            part.write_bytes(data)
            parts.append(
                {
                    "name": part.name,
                    "size": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
            index += 1

    if not parts:
        raise ValueError("source file is empty")

    manifest = {
        "format": "bsl-release-chunks",
        "version": 1,
        "name": source.name,
        "size": source.stat().st_size,
        "sha256": sha256_file(source),
        "chunk_size": chunk_size,
        "parts": parts,
    }
    manifest_path = out_dir / (source.name + ".manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"SPLIT {source.name} -> {len(parts)} parts")
    print(f"MANIFEST {manifest_path}")
    return manifest_path


def _load_manifest(manifest_path: Path) -> tuple[dict, Path]:
    manifest_path = manifest_path.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("format") != "bsl-release-chunks":
        raise ValueError("not a bsl-release-chunks manifest")
    return manifest, manifest_path.parent


def verify_manifest(manifest_path: Path, quiet: bool = False) -> bool:
    manifest, base_dir = _load_manifest(manifest_path)
    total = 0
    digest = hashlib.sha256()
    for info in manifest.get("parts", []):
        part = base_dir / info["name"]
        if not part.is_file():
            raise FileNotFoundError(part)
        if part.stat().st_size != info["size"]:
            raise ValueError(f"size mismatch: {part}")
        part_hash = sha256_file(part)
        if part_hash != info["sha256"]:
            raise ValueError(f"sha256 mismatch: {part}")
        with part.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
                total += len(block)
    if total != manifest["size"]:
        raise ValueError(f"total size mismatch: {total} != {manifest['size']}")
    if digest.hexdigest() != manifest["sha256"]:
        raise ValueError("assembled sha256 mismatch")
    if not quiet:
        print(f"VERIFY_OK {manifest['name']} {total} bytes {len(manifest['parts'])} parts")
    return True


def restore_file(manifest_path: Path, dest: Path, force: bool = False) -> Path:
    manifest, base_dir = _load_manifest(manifest_path)
    dest = dest.resolve()
    if dest.is_file() and not force:
        if dest.stat().st_size == manifest["size"] and sha256_file(dest) == manifest["sha256"]:
            print(f"ALREADY_PRESENT {dest}")
            return dest

    verify_manifest(manifest_path, quiet=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_name(dest.name + ".tmp")
    try:
        with temp.open("wb") as output:
            for info in manifest["parts"]:
                with (base_dir / info["name"]).open("rb") as source:
                    for block in iter(lambda: source.read(1024 * 1024), b""):
                        output.write(block)
        if temp.stat().st_size != manifest["size"]:
            raise ValueError("restored size mismatch")
        if sha256_file(temp) != manifest["sha256"]:
            raise ValueError("restored sha256 mismatch")
        os.replace(temp, dest)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass
    print(f"RESTORED {dest}")
    return dest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GitHub-safe release chunk tool")
    sub = parser.add_subparsers(dest="command", required=True)

    split = sub.add_parser("split", help="split a file and write a manifest")
    split.add_argument("source", type=Path)
    split.add_argument("--out", type=Path, default=None)
    split.add_argument("--chunk-size", type=int, default=CHUNK_SIZE)

    verify = sub.add_parser("verify", help="verify chunks against their manifest")
    verify.add_argument("manifest", type=Path)

    restore = sub.add_parser("restore", help="verify and restore the original file")
    restore.add_argument("manifest", type=Path)
    restore.add_argument("--dest", type=Path, required=True)
    restore.add_argument("--force", action="store_true")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "split":
            out = args.out if args.out is not None else args.source.parent
            split_file(args.source, out, args.chunk_size)
        elif args.command == "verify":
            verify_manifest(args.manifest)
        elif args.command == "restore":
            restore_file(args.manifest, args.dest, args.force)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
