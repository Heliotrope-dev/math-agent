"""Supabase REST helpers + user authentication."""

import hashlib
import os
import secrets as _secrets
from datetime import datetime, timedelta, timezone

import requests

_TOKEN_DAYS = 7


# ── Supabase REST（直接用 requests，无需 supabase 包）────────────────────────

def _sb_url() -> str:
    url = os.environ.get("SUPABASE_URL", "")
    return url.rstrip("/") + "/rest/v1" if url else ""

def _sb_headers() -> dict:
    key = os.environ.get("SUPABASE_KEY", "")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

def _sb_ready() -> bool:
    return bool(_sb_url() and os.environ.get("SUPABASE_KEY"))


def _sb_get(table: str, params: dict) -> list:
    if not _sb_ready():
        return []
    try:
        r = requests.get(f"{_sb_url()}/{table}", headers=_sb_headers(), params=params, timeout=8)
        return r.json() if r.ok else []
    except Exception:
        return []


def _sb_post(table: str, data) -> bool:
    if not _sb_ready():
        return False
    try:
        r = requests.post(f"{_sb_url()}/{table}", headers=_sb_headers(), json=data, timeout=8)
        return r.ok
    except Exception:
        return False


def _sb_upsert(table: str, data, on_conflict: str) -> bool:
    """插入或更新（按 on_conflict 指定的唯一约束判断冲突）。
    比"先查存不存在再决定insert/update"更省一次往返，也天然幂等——
    同样的行重复提交不会报唯一约束冲突，也不会产生重复行。
    """
    if not _sb_ready():
        return False
    try:
        headers = {**_sb_headers(), "Prefer": "resolution=merge-duplicates"}
        r = requests.post(
            f"{_sb_url()}/{table}", headers=headers, json=data,
            params={"on_conflict": on_conflict}, timeout=8,
        )
        return r.ok
    except Exception:
        return False


def _sb_delete(table: str, params: dict) -> bool:
    if not _sb_ready():
        return False
    try:
        r = requests.delete(f"{_sb_url()}/{table}", headers=_sb_headers(), params=params, timeout=8)
        return r.ok
    except Exception:
        return False


def _sb_patch(table: str, data: dict, params: dict) -> bool:
    if not _sb_ready():
        return False
    try:
        r = requests.patch(f"{_sb_url()}/{table}", headers=_sb_headers(), json=data, params=params, timeout=8)
        return r.ok
    except Exception:
        return False


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
        computed = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100000).hex()
        return _secrets.compare_digest(computed, h)
    except Exception:
        computed = hashlib.sha256(pw.encode()).hexdigest()
        return _secrets.compare_digest(computed, stored)


def _user_exists(email: str) -> bool:
    return len(_sb_get("users", {"email": f"eq.{email}", "select": "email"})) > 0


_LOCKOUT_THRESHOLD = 5
_LOCKOUT_SECONDS = 60


def _check_user(email: str, pw: str) -> tuple:
    """返回 (是否登录成功, 失败时的提示信息)。

    失败次数/锁定时间持久化在 users 表的 failed_attempts/locked_until 列——
    之前是存在 st.session_state 里的，换个隐身窗口/清一下cookie就能绕开
    5次锁定，起不到实际防暴力破解的作用。
    """
    rows = _sb_get("users", {
        "email": f"eq.{email}",
        "select": "email,password_hash,failed_attempts,locked_until",
    })
    if not rows:
        return False, "邮箱或密码不正确"
    row = rows[0]

    locked_until = row.get("locked_until")
    if locked_until:
        try:
            # 显式用带时区的UTC比较——本地测试时踩过坑：写入用
            # datetime.now()（无时区），Postgres 把它当UTC存，但如果运行的
            # 机器本地时区不是UTC（比如开发机是UTC+8），"未来60秒"写进去
            # 后读出来对着本地时钟一比就成了"8小时前"，锁定形同虚设。
            # VPS本身是UTC所以之前没测出来，这里改成不依赖宿主机时区。
            lu = datetime.fromisoformat(locked_until.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            if now < lu:
                wait = int((lu - now).total_seconds()) + 1
                return False, f"密码错误次数过多，请等待 {wait} 秒后重试"
        except Exception:
            pass

    stored = row["password_hash"]
    ok = False
    upgrade_hash = None
    # 新格式 PBKDF2
    try:
        salt, h = stored.split("$", 1)
        computed = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100000).hex()
        ok = _secrets.compare_digest(computed, h)
    except Exception:
        pass
    # 旧格式 SHA256 无盐 — 验证通过后自动升级
    if not ok and _secrets.compare_digest(hashlib.sha256(pw.encode()).hexdigest(), stored):
        ok = True
        new_salt = os.urandom(16).hex()
        upgrade_hash = f"{new_salt}${hashlib.pbkdf2_hmac('sha256', pw.encode(), new_salt.encode(), 100000).hex()}"

    if ok:
        patch = {"failed_attempts": 0, "locked_until": None}
        if upgrade_hash:
            patch["password_hash"] = upgrade_hash
        _sb_patch("users", patch, {"email": f"eq.{email}"})
        return True, ""

    attempts = (row.get("failed_attempts") or 0) + 1
    if attempts >= _LOCKOUT_THRESHOLD:
        locked_at = (datetime.now(timezone.utc) + timedelta(seconds=_LOCKOUT_SECONDS)).isoformat()
        _sb_patch("users", {"failed_attempts": 0, "locked_until": locked_at}, {"email": f"eq.{email}"})
        return False, f"密码连续错误{_LOCKOUT_THRESHOLD}次，请等待{_LOCKOUT_SECONDS}秒后重试"
    _sb_patch("users", {"failed_attempts": attempts}, {"email": f"eq.{email}"})
    return False, f"邮箱或密码不正确（还有 {_LOCKOUT_THRESHOLD - attempts} 次机会）"


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


# ── 对话历史持久化（Supabase REST）───────────────────────────────────────────
# image_b64 存的是已经压缩过的缩略图（compress_image 处理过，单张几十到
# 一百多KB），个人使用量级不会让表明显膨胀，用户明确要求上传的图片以后
# 还能点开看，所以存。

def _save_message(email: str, role: str, content: str, image_b64: str = "") -> bool:
    if not email or not content:
        return False
    payload = {"email": email, "role": role, "content": content}
    if image_b64:
        payload["image_b64"] = image_b64
    return _sb_post("chat_messages", payload)


def _load_recent_messages(email: str, limit: int = 20) -> list:
    if not email:
        return []
    rows = _sb_get("chat_messages", {
        "email": f"eq.{email}", "select": "role,content,image_b64",
        "order": "created_at.desc", "limit": str(limit),
    })
    return list(reversed(rows))


def _delete_messages(email: str) -> bool:
    """只删 chat_messages（对话历史），不碰 wrong_book 表。"""
    if not email:
        return False
    return _sb_delete("chat_messages", {"email": f"eq.{email}"})


# ── 错题本持久化（Supabase REST）─────────────────────────────────────────────

def _load_wrong_book(email: str) -> list:
    if not email:
        return []
    return _sb_get("wrong_book", {"email": f"eq.{email}", "select": "*", "order": "id"})


def _save_wrong_book(email: str, wb: list) -> bool:
    """差量删除 + 全量upsert：表上有 (email,question) 唯一约束，upsert天然幂等。

    之前insert那一半是"先查一遍现有的，本地算出哪些是新的再insert"——如果
    _load_wrong_book 因为网络抖动返回了空列表（不代表真的没有），会把所有
    条目都误判成"新的"重新insert一遍，产生重复行。现在改成每次都把当前
    wb整个列表做upsert（有唯一约束兜底，重复提交只是覆盖同一行，不会
    再产生重复），从根上消除这个窗口。
    """
    if not email:
        return False
    existing = _load_wrong_book(email)
    existing_qs = {r["question"] for r in existing}
    new_qs = {item["question"] for item in wb} if wb else set()

    # 精确删除已移除的条目（按 question 精确匹配，不影响其他条目）
    for q in existing_qs - new_qs:
        _sb_delete("wrong_book", {"email": f"eq.{email}", "question": f"eq.{q}"})

    # image_b64 仅存 session_state，不写库，避免表结构不匹配
    if wb:
        rows = [
            {"email": email, "question": item["question"],
             "saved_at": item.get("saved_at", "")}
            for item in wb
        ]
        return _sb_upsert("wrong_book", rows, on_conflict="email,question")
    return True
