"""Minecraft Server List Ping (modern protocol) with no extra dependencies."""

import json
import re
import socket
import struct
import time


_PROTOCOL = 47
_MAX_PACKET = 2 * 1024 * 1024
_COLOR_CODE = re.compile("§.")


def _varint(value):
    value = int(value) & 0xFFFFFFFF
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _string(value):
    raw = value.encode("utf-8") if isinstance(value, str) else bytes(value)
    return _varint(len(raw)) + raw


def _read_varint(sock):
    value = 0
    shift = 0
    for _ in range(5):
        byte = sock.recv(1)
        if not byte:
            raise ConnectionError("服务器提前关闭了连接")
        value |= (byte[0] & 0x7F) << shift
        if not byte[0] & 0x80:
            return value
        shift += 7
    raise ValueError("服务器返回了无效的数据包")


def _read_exact(sock, size):
    chunks = []
    remaining = int(size)
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise ConnectionError("服务器提前关闭了连接")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _read_varint_bytes(data, offset):
    value = 0
    shift = 0
    for index in range(5):
        if offset + index >= len(data):
            raise ValueError("数据包不完整")
        byte = data[offset + index]
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, offset + index + 1
        shift += 7
    raise ValueError("数据包长度无效")


def _flatten_motd(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_flatten_motd(item) for item in value)
    if isinstance(value, dict):
        text = str(value.get("text") or "")
        extra = value.get("extra") or []
        return text + _flatten_motd(extra)
    return ""


def _clean_text(value):
    value = _COLOR_CODE.sub("", _flatten_motd(value))
    return value.replace("\n", " ").strip()


def parse_address(address, default_port=25565):
    text = str(address or "").strip()
    if not text:
        raise ValueError("没有填写服务器地址")
    for prefix in ("minecraft://", "mc://"):
        if text.lower().startswith(prefix):
            text = text[len(prefix):]
    text = text.strip().strip("/")
    if text.startswith("[") and "]" in text:
        host, rest = text[1:].split("]", 1)
        port = int(rest[1:]) if rest.startswith(":") and rest[1:].isdigit() else int(default_port)
        return host, port
    if text.count(":") == 1:
        host, possible = text.rsplit(":", 1)
        if possible.isdigit():
            return host, int(possible)
    return text, int(default_port)


def parse_status_payload(payload):
    packet_id, offset = _read_varint_bytes(payload, 0)
    if packet_id != 0:
        raise ValueError("服务器返回了非状态数据包")
    length, offset = _read_varint_bytes(payload, offset)
    if length <= 0 or offset + length > len(payload):
        raise ValueError("状态数据包长度无效")
    raw = payload[offset: offset + length].decode("utf-8", "replace")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("状态数据不是 JSON 对象")
    players = data.get("players") or {}
    version = data.get("version") or {}
    return {
        "version": str(version.get("name") or ""),
        "protocol": int(version.get("protocol") or 0),
        "players_online": int(players.get("online") or 0),
        "players_max": int(players.get("max") or 0),
        "motd": _clean_text(data.get("description") or ""),
        "favicon": str(data.get("favicon") or ""),
    }


def ping(address, port=None, timeout=3.5):
    """Return a JSON-friendly status dict; never raises for normal network errors."""
    started = time.perf_counter()
    try:
        host, resolved_port = parse_address(address, port or 25565)
        with socket.create_connection((host, resolved_port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            handshake = (
                _varint(0)
                + _varint(_PROTOCOL)
                + _string(host)
                + struct.pack(">H", resolved_port)
                + _varint(1)
            )
            sock.sendall(_varint(len(handshake)) + handshake)
            sock.sendall(_varint(1) + _varint(0))
            length = _read_varint(sock)
            if length <= 0 or length > _MAX_PACKET:
                raise ValueError("服务器返回的状态包过大")
            payload = _read_exact(sock, length)
            data = parse_status_payload(payload)
        latency = int((time.perf_counter() - started) * 1000)
        return {
            "ok": True,
            "host": host,
            "port": resolved_port,
            "latency_ms": max(1, latency),
            "error": "",
            **data,
        }
    except Exception as exc:
        return {
            "ok": False,
            "host": str(address or ""),
            "port": int(port or 25565),
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "error": str(exc) or exc.__class__.__name__,
        }
