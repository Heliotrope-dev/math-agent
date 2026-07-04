"""Supabase REST helpers + user authentication."""

import hashlib
import os
import secrets as _secrets
from datetime import datetime, timedelta

import requests

_SB_URL = (
    os.environ.get("SUPABASE_URL", "").rstrip("/") + "/rest/v1"
    if os.environ.get("SUPABASE_URL")
    else ""
)
_SB_KEY = os.environ.get("SUPABASE_KEY", "")
_SB_HDR = {
    "apikey": _SB_KEY,
    "Authorization": f"Bearer {_SB_KEY}",
    "Content-Type": "application/json",
}

_TOKEN_DAYS = 7


# ── Supabase REST（直接用 requests，无需 supabase 包）────────────────────────

def _sb_get(table: str, params: dict) -> list:
    if not _SB_URL or not _SB_KEY:
        return []
    try:
        r = requests.get(f"{_SB_URL}/{table}", headers=_SB_HDR, params=params, timeout=8)
        return r.json() if r.ok else []
    except Exception:
        return []


def _sb_post(table: str, data):
    if not _SB_URL or not _SB_KEY:
        return
    try:
        requests.post(f"{_SB_URL}/{table}", headers=_SB_HDR, json=data, timeout=8)
    except Exception:
        pass


def _sb_delete(table: str, params: dict):
    if not _SB_URL or not _SB_KEY:
        return
    try:
        requests.delete(f"{_SB_URL}/{table}", headers=_SB_HDR, params=params, timeout=8)
    except Exception:
        pass


def _sb_patch(table: str, data: dict, params: dict):
    if not _SB_URL or not _SB_KEY:
        return
    try:
        requests.patch(f"{_SB_URL}/{table}", headers=_SB_HDR, json=data, params=params, timeout=8)
    except Exception:
        pass


# ── 学习记录（user_topics 表）────────────────────────────────────────────────

def _track_topic(email: str, course: str, topic: str):
    if not email:
        return
    existing = _sb_get("user_topics", {
        "user_email": f"eq.{email}", "topic": f"eq.{topic}", "select": "id,visit_count"
    })
    if existing:
        _sb_patch("user_topics",
                  {"visit_count": existing[0]["visit_count"] + 1,
                   "last_visited": datetime.now().isoformat()},
                  {"user_email": f"eq.{email}", "topic": f"eq.{topic}"})
    else:
        _sb_post("user_topics", {
            "user_email": email, "course": course, "topic": topic,
            "visit_count": 1, "last_visited": datetime.now().isoformat(),
        })


def _load_user_profile(email: str) -> dict:
    if not email:
        return {}
    rows = _sb_get("user_topics", {
        "user_email": f"eq.{email}", "select": "course,topic,visit_count,last_visited",
        "order": "visit_count.desc", "limit": "30",
    })
    if not rows:
        return {}
    weak   = [r for r in rows if r["visit_count"] >= 2][:6]
    recent = sorted(rows, key=lambda r: r.get("last_visited") or "", reverse=True)[:5]
    return {"weak": weak, "recent": recent, "all": rows}


# ── 用户管理（登录注册 + 7天免登录）──────────────────────────────────────────

def _hash_pw(pw: str) -> str:
    salt = _secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100000)
    return f"{salt}${h.hex()}"


def _check_pw(pw: str, stored: str) -> bool:
    try:
        salt, h = stored.split("$", 1)
        return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100000).hex() == h
    except Exception:
        return hashlib.sha256(pw.encode()).hexdigest() == stored


def _user_exists(email: str) -> bool:
    return len(_sb_get("users", {"email": f"eq.{email}", "select": "email"})) > 0


def _check_user(email: str, pw: str) -> bool:
    rows = _sb_get("users", {
        "email": f"eq.{email}", "select": "email,password_hash"
    })
    if not rows:
        return False
    stored = rows[0]["password_hash"]
    # 新格式 PBKDF2
    try:
        salt, h = stored.split("$", 1)
        if hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100000).hex() == h:
            return True
    except Exception:
        pass
    # 旧格式 SHA256 无盐 — 验证通过后自动升级
    if hashlib.sha256(pw.encode()).hexdigest() == stored:
        new_salt = os.urandom(16).hex()
        new_hash = hashlib.pbkdf2_hmac("sha256", pw.encode(), new_salt.encode(), 100000).hex()
        _sb_patch("users", {"password_hash": f"{new_salt}${new_hash}"}, {"email": f"eq.{email}"})
        return True
    return False


def _register_user(email: str, pw_hash: str):
    _sb_post("users", {"email": email, "password_hash": pw_hash})


def _create_token(email: str) -> str:
    token = _secrets.token_urlsafe(32)
    now = datetime.now()
    exp = (now + timedelta(days=_TOKEN_DAYS)).isoformat()
    _sb_delete("sessions", {"email": f"eq.{email}", "expires_at": f"lt.{now.isoformat()}"})
    _sb_post("sessions", {"token": token, "email": email, "expires_at": exp})
    return token


def _validate_token(token: str):
    rows = _sb_get("sessions", {
        "token": f"eq.{token}", "expires_at": f"gt.{datetime.now().isoformat()}", "select": "email"
    })
    return rows[0]["email"] if rows else None


def _invalidate_token(token: str):
    _sb_delete("sessions", {"token": f"eq.{token}"})


# ── 错题本持久化（Supabase REST）─────────────────────────────────────────────

def _load_wrong_book(email: str) -> list:
    if not email:
        return []
    return _sb_get("wrong_book", {"email": f"eq.{email}", "select": "*", "order": "id"})


def _save_wrong_book(email: str, wb: list):
    if not email:
        return
    rows = [
        {
            "email": email,
            "question": item["question"],
            "saved_at": item.get("saved_at", ""),
            "image_b64": item.get("image_b64", ""),
        }
        for item in wb
    ] if wb else []
    backup = []
    try:
        backup = _load_wrong_book(email)
    except Exception:
        pass
    deleted = False
    try:
        _sb_delete("wrong_book", {"email": f"eq.{email}"})
        deleted = True
        if rows:
            _sb_post("wrong_book", rows)
    except Exception:
        # 只有 delete 成功但 insert 失败时才需要恢复，避免二次 delete 导致数据双重丢失
        if deleted and backup:
            try:
                _sb_post("wrong_book", [
                    {"email": email, "question": x["question"],
                     "saved_at": x.get("saved_at", ""), "image_b64": x.get("image_b64", "")}
                    for x in backup
                ])
            except Exception:
                pass
