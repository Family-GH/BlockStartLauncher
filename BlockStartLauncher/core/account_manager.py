import hashlib
import json
import os
import sys
import time
import uuid as uuid_lib
from urllib.parse import urlparse

import requests

import config
from core import secure_store

DEVICE_CODE_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode"
TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
XBL_URL = "https://user.auth.xboxlive.com/user/authenticate"
XSTS_URL = "https://xsts.auth.xboxlive.com/xsts/authorize"
MC_LOGIN_URL = "https://api.minecraftservices.com/authentication/login_with_xbox"
MC_PROFILE_URL = "https://api.minecraftservices.com/minecraft/profile"
SCOPE = "XboxLive.SignIn XboxLive.offline_access"


def accounts_path():
    return os.path.join(config.base_dir(), "accounts.json")


def _read_account_file(path):
    raw = secure_store.read_json(path)
    if raw is None:
        return None
    if isinstance(raw, dict) and raw.get("format") == secure_store.FORMAT:
        payload = secure_store.open_payload(raw)
        if not isinstance(payload, list):
            raise ValueError("decrypted accounts root is not a list")
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    raise ValueError("accounts root is not a list")


def _load():
    path = accounts_path()
    try:
        if not os.path.isfile(path):
            return []
        accounts = _read_account_file(path)
    except Exception:
        accounts = None
    if accounts is not None:
        # Older builds wrote accounts.json as plain text.  Migrate it to the
        # DPAPI envelope as soon as it is read successfully.
        if accounts and _is_plaintext(path):
            try:
                _save(accounts)
            except Exception:
                pass
        return accounts
    # A corrupted or foreign-user file must never be silently replaced by an
    # empty list: try the previous good copy first.
    backup = path + ".bak"
    try:
        if os.path.isfile(backup):
            accounts = _read_account_file(backup)
            if accounts is not None:
                return accounts
    except Exception:
        pass
    return []


def _is_plaintext(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            raw = json.load(handle)
        return isinstance(raw, list)
    except Exception:
        return False


def _save(accounts):
    path = accounts_path()
    secure_store.write_envelope(path, list(accounts))
    # write_envelope keeps the previous file as .bak.  On the first migration
    # that previous file is the old plaintext list, so do not leave credentials
    # (or player names) lying around in a second file.
    backup = path + ".bak"
    try:
        if os.path.isfile(backup) and not secure_store.is_envelope(backup):
            os.remove(backup)
    except Exception:
        pass
    # If an old build left a plaintext accounts.json beside the exe, remove it
    # now that the encrypted copy in LOCALAPPDATA is safely written.
    if getattr(sys, "frozen", False):
        legacy = os.path.join(config.executable_dir(), "accounts.json")
        if os.path.normcase(os.path.abspath(legacy)) != os.path.normcase(os.path.abspath(path)):
            for stale in (legacy, legacy + ".bak"):
                try:
                    if os.path.isfile(stale):
                        os.remove(stale)
                except Exception:
                    pass


def list_accounts():
    return sorted(_load(), key=lambda item: item.get("created") or 0)


def _find(account_id):
    for account in _load():
        if account.get("id") == account_id:
            return account
    return None


def add_offline(username):
    name = str(username or "").strip() or config.DEFAULT_USERNAME
    name = name[:16]
    digest = hashlib.md5(("OfflinePlayer:" + name).encode("utf-8")).digest()
    account_id = str(uuid_lib.UUID(bytes=digest))
    account = {
        "id": account_id,
        "username": name,
        "uuid": account_id,
        "type": "offline",
        "token": "0",
        "refresh_token": "",
        "expires_at": 0,
        "created": time.time(),
    }
    accounts = [item for item in _load() if item.get("id") != account_id]
    accounts.append(account)
    _save(accounts)
    return account


def add_microsoft(account):
    accounts = [item for item in _load() if item.get("id") != account.get("id")]
    accounts.append(account)
    _save(accounts)
    return account


def remove(account_id):
    accounts = [item for item in _load() if item.get("id") != account_id]
    _save(accounts)


def _client_id(value=None):
    client_id = str(value or config.MS_CLIENT_ID or "").strip()
    if not client_id:
        raise RuntimeError("请先在设置页填写 Azure client_id")
    return client_id


def start_device_flow(client_id=None):
    client_id = _client_id(client_id)
    response = requests.post(
        DEVICE_CODE_URL,
        data={"client_id": client_id, "scope": SCOPE},
        timeout=30,
        headers={"User-Agent": config.USER_AGENT},
    )
    if response.status_code != 200:
        raise RuntimeError(f"获取设备代码失败：HTTP {response.status_code}")
    data = response.json()
    return {
        "device_code": data.get("device_code", ""),
        "user_code": data.get("user_code", ""),
        "verification_uri": data.get("verification_uri") or data.get("verification_url") or "",
        "expires_in": int(data.get("expires_in") or 900),
        "interval": max(1, int(data.get("interval") or 5)),
    }


def poll_device_token(flow, client_id=None, cancel=None, status_cb=None):
    client_id = _client_id(client_id)
    deadline = time.time() + int(flow.get("expires_in") or 900)
    interval = max(1, int(flow.get("interval") or 5))
    while time.time() < deadline:
        if cancel and cancel():
            raise RuntimeError("微软登录已取消")
        response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": client_id,
                "device_code": flow.get("device_code", ""),
            },
            timeout=30,
            headers={"User-Agent": config.USER_AGENT},
        )
        if response.status_code == 200:
            return response.json()
        try:
            data = response.json()
        except Exception:
            data = {}
        error = str(data.get("error") or "")
        if error == "authorization_pending":
            if status_cb:
                status_cb("等待浏览器中完成微软登录")
            time.sleep(interval)
            continue
        if error == "slow_down":
            interval += 5
            time.sleep(interval)
            continue
        description = data.get("error_description") or error or f"HTTP {response.status_code}"
        raise RuntimeError("微软登录失败：" + str(description))
    raise RuntimeError("设备代码已过期，请重新登录")


def _xsts_error_message(code):
    return {
        "2148916233": "该微软账户尚未创建 Xbox 账户，请先登录 xbox.com 创建。",
        "2148916235": "该账户所在地区不支持 Xbox Live。",
        "2148916238": "该账户被判定为未成年人账户，需要加入家庭组后才能登录。",
    }.get(str(code), f"Xbox 认证失败（XErr {code}）")


def _exchange_ms_token(access_token, refresh_token):
    xbl_response = requests.post(
        XBL_URL,
        json={
            "Properties": {"AuthMethod": "RPS", "SiteName": "user.auth.xboxlive.com", "RpsTicket": "d=" + access_token},
            "RelyingParty": "http://auth.xboxlive.com",
            "TokenType": "JWT",
        },
        timeout=30,
        headers={"User-Agent": config.USER_AGENT},
    )
    if xbl_response.status_code != 200:
        raise RuntimeError(f"Xbox Live 认证失败：HTTP {xbl_response.status_code}")
    xbl_data = xbl_response.json()
    xbl_token = xbl_data.get("Token", "")
    claims = (xbl_data.get("DisplayClaims") or {}).get("xui") or [{}]
    user_hash = claims[0].get("uhs", "")

    xsts_response = requests.post(
        XSTS_URL,
        json={
            "Properties": {"SandboxId": "RETAIL", "UserTokens": [xbl_token]},
            "RelyingParty": "rp://api.minecraftservices.com/",
            "TokenType": "JWT",
        },
        timeout=30,
        headers={"User-Agent": config.USER_AGENT},
    )
    if xsts_response.status_code == 401:
        try:
            data = xsts_response.json()
        except Exception:
            data = {}
        raise RuntimeError(_xsts_error_message(data.get("XErr", "")))
    if xsts_response.status_code != 200:
        raise RuntimeError(f"XSTS 授权失败：HTTP {xsts_response.status_code}")
    xsts_token = xsts_response.json().get("Token", "")

    mc_response = requests.post(
        MC_LOGIN_URL,
        json={"identityToken": f"XBL3.0 x={user_hash};{xsts_token}"},
        timeout=30,
        headers={"User-Agent": config.USER_AGENT},
    )
    if mc_response.status_code != 200:
        raise RuntimeError(f"Minecraft 令牌交换失败：HTTP {mc_response.status_code}")
    mc_data = mc_response.json()
    mc_token = mc_data.get("access_token", "")
    expires_in = int(mc_data.get("expires_in") or 86400)

    profile = requests.get(
        MC_PROFILE_URL,
        headers={"Authorization": "Bearer " + mc_token, "User-Agent": config.USER_AGENT},
        timeout=30,
    )
    if profile.status_code == 404:
        raise RuntimeError("该微软账户未拥有 Minecraft: Java Edition")
    if profile.status_code != 200:
        raise RuntimeError(f"获取 Minecraft 档案失败：HTTP {profile.status_code}")
    profile_data = profile.json()
    raw_uuid = str(profile_data.get("id") or "")
    try:
        account_uuid = str(uuid_lib.UUID(raw_uuid))
    except Exception:
        account_uuid = raw_uuid

    return {
        "id": account_uuid,
        "username": profile_data.get("name") or "Player",
        "uuid": account_uuid,
        "type": "msa",
        "token": mc_token,
        "refresh_token": refresh_token,
        "expires_at": time.time() + expires_in - 120,
        "created": time.time(),
    }


def complete_login(token_response):
    access_token = token_response.get("access_token", "")
    refresh_token = token_response.get("refresh_token", "")
    if not access_token:
        raise RuntimeError("微软登录响应缺少 access_token")
    account = _exchange_ms_token(access_token, refresh_token)
    add_microsoft(account)
    return account


def refresh(account_id, client_id=None):
    account = _find(account_id)
    if not account:
        raise RuntimeError("账户不存在")
    if account.get("type") == "offline":
        return account
    refresh_token = account.get("refresh_token") or ""
    if not refresh_token:
        raise RuntimeError("登录状态已失效，请重新登录")
    client_id = _client_id(client_id)
    response = requests.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": SCOPE,
        },
        timeout=30,
        headers={"User-Agent": config.USER_AGENT},
    )
    if response.status_code != 200:
        raise RuntimeError("刷新微软令牌失败，请重新登录")
    data = response.json()
    refreshed = _exchange_ms_token(data.get("access_token", ""), data.get("refresh_token") or refresh_token)
    refreshed["created"] = account.get("created") or time.time()
    add_microsoft(refreshed)
    return refreshed


def get_launch_options(account_id, client_id=None):
    account = _find(account_id)
    if not account:
        raise RuntimeError("账户不存在，请重新选择账户")
    if account.get("type") == "offline":
        return {
            "username": account.get("username") or config.DEFAULT_USERNAME,
            "uuid": account.get("uuid") or "",
            "token": "0",
            "user_type": "legacy",
        }
    expires_at = float(account.get("expires_at") or 0)
    if expires_at and expires_at < time.time() + 60:
        account = refresh(account_id, client_id)
    return {
        "username": account.get("username") or config.DEFAULT_USERNAME,
        "uuid": account.get("uuid") or "",
        "token": account.get("token") or "",
        "user_type": "msa",
    }


def _error_detail(response):
    try:
        data = response.json()
    except Exception:
        data = {}
    detail = data.get("errorMessage") or data.get("error") or data.get("message")
    if detail:
        return str(detail)
    if response.status_code == 401:
        return "登录已过期，请重新登录微软账户"
    if response.status_code == 403:
        return "当前账户无权执行此操作"
    return f"HTTP {response.status_code}"


def _authorized(account_id, client_id=None):
    account = _find(account_id)
    if not account:
        raise RuntimeError("账户不存在，请重新选择账户")
    if account.get("type") == "offline":
        raise RuntimeError("离线账户没有官方皮肤和披风，请先登录微软账户")
    expires_at = float(account.get("expires_at") or 0)
    if expires_at and expires_at < time.time() + 60:
        account = refresh(account_id, client_id)
    return account


def _authorized_request(account, method, url, client_id=None, **kwargs):
    headers = dict(kwargs.pop("headers", {}))
    headers["Authorization"] = "Bearer " + (account.get("token") or "")
    headers["User-Agent"] = config.USER_AGENT
    response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
    if response.status_code == 401:
        account = refresh(account["id"], client_id)
        headers["Authorization"] = "Bearer " + (account.get("token") or "")
        response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
    if response.status_code not in (200, 201, 202, 204):
        raise RuntimeError("Minecraft 服务返回：" + _error_detail(response))
    return response


def get_profile(account_id, client_id=None):
    account = _authorized(account_id, client_id)
    response = _authorized_request(account, "GET", MC_PROFILE_URL, client_id)
    if response.status_code == 204:
        return {}
    try:
        data = response.json()
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("name", account.get("username") or "")
    data.setdefault("id", account.get("uuid") or "")
    return data


def validate_skin_bytes(data):
    if not data or len(data) > 2 * 1024 * 1024:
        raise RuntimeError("皮肤文件为空或超过 2 MB")
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError("皮肤必须是 PNG 图片")
    if len(data) < 24:
        raise RuntimeError("皮肤 PNG 数据不完整")
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    if (width, height) not in ((64, 64), (64, 32)):
        raise RuntimeError("皮肤尺寸必须是 64×64 或 64×32 像素")


def upload_skin(account_id, file_path, variant="classic", client_id=None):
    with open(file_path, "rb") as handle:
        data = handle.read()
    validate_skin_bytes(data)
    variant = "slim" if str(variant).lower() == "slim" else "classic"
    account = _authorized(account_id, client_id)
    response = _authorized_request(
        account,
        "POST",
        MC_PROFILE_URL + "/skins",
        client_id,
        data={"variant": variant},
        files={"file": (os.path.basename(file_path) or "skin.png", data, "image/png")},
    )
    try:
        return response.json()
    except Exception:
        return {}


def reset_skin(account_id, client_id=None):
    account = _authorized(account_id, client_id)
    _authorized_request(account, "DELETE", MC_PROFILE_URL + "/skins/active", client_id)
    return True


def set_cape(account_id, cape_id="", client_id=None):
    account = _authorized(account_id, client_id)
    if cape_id:
        _authorized_request(
            account, "PUT", MC_PROFILE_URL + "/capes/active", client_id, json={"capeId": cape_id}
        )
    else:
        _authorized_request(account, "DELETE", MC_PROFILE_URL + "/capes/active", client_id)
    return True


def download_texture(url):
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in ("http", "https") or parsed.netloc.lower() != "textures.minecraft.net":
        raise RuntimeError("皮肤资源地址不受信任")
    response = requests.get(url, timeout=20, headers={"User-Agent": config.USER_AGENT})
    if response.status_code != 200:
        raise RuntimeError(f"下载皮肤资源失败：HTTP {response.status_code}")
    if len(response.content) > 2 * 1024 * 1024:
        raise RuntimeError("皮肤资源过大")
    return response.content

