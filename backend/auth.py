import hashlib
import json
import os
import secrets
from typing import Dict, List, Optional

USERS_FILE = "./users.json"
_sessions: Dict[str, str] = {}  # token -> username


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _load() -> Dict:
    if not os.path.exists(USERS_FILE):
        default = {
            "rvoyat": {
                "password": _hash("rvoyat"),
                "role": "admin",
                "default_ambito": None,
            }
        }
        _save(default)
        return default
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(users: Dict) -> None:
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def login(username: str, password: str) -> Optional[str]:
    users = _load()
    user = users.get(username)
    if not user or user["password"] != _hash(password):
        return None
    token = secrets.token_hex(32)
    _sessions[token] = username
    return token


def logout(token: str) -> None:
    _sessions.pop(token, None)


def get_user(token: str) -> Optional[Dict]:
    username = _sessions.get(token)
    if not username:
        return None
    users = _load()
    u = users.get(username)
    if not u:
        return None
    return {"username": username, "role": u["role"], "default_ambito": u.get("default_ambito"), "theme": u.get("theme", "dark")}


def list_users() -> List[Dict]:
    users = _load()
    return [
        {"username": k, "role": v["role"], "default_ambito": v.get("default_ambito"), "theme": v.get("theme", "dark")}
        for k, v in users.items()
    ]


def create_user(username: str, password: str, role: str) -> bool:
    users = _load()
    if username in users:
        return False
    users[username] = {"password": _hash(password), "role": role, "default_ambito": None, "theme": "dark"}
    _save(users)
    return True


def update_user(username: str, password: Optional[str] = None,
                role: Optional[str] = None, default_ambito: Optional[str] = None,
                theme: Optional[str] = None) -> bool:
    users = _load()
    if username not in users:
        return False
    if password is not None:
        users[username]["password"] = _hash(password)
    if role is not None:
        users[username]["role"] = role
    if default_ambito is not None:
        users[username]["default_ambito"] = default_ambito if default_ambito != "" else None
    if theme is not None and theme in ("dark", "light"):
        users[username]["theme"] = theme
    _save(users)
    return True


def delete_user(username: str) -> bool:
    users = _load()
    if username not in users:
        return False
    del users[username]
    for t in [t for t, u in list(_sessions.items()) if u == username]:
        _sessions.pop(t, None)
    _save(users)
    return True
