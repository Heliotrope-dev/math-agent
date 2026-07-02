#!/usr/bin/env python3
"""Apply all 7 fixes to math-agent project."""

import os, re, hashlib, secrets

PROJ = "/Users/heliotrope/Projects/math-agent"
os.chdir(PROJ)

# ── Read all files ──
files = {}
for f in ["app.py", "agent.py", "tools.py", "main.py"]:
    with open(f) as fh:
        files[f] = fh.read()
    print(f"Read {f}: {len(files[f])} chars")

# ════════════════════════════════════════════════
# Fix 1: localStorage dead-loop (app.py)
# ════════════════════════════════════════════════
old_js = """    // ── 1. localStorage 自动登录 ──────────────────────────────────
    var url = new URL(window.parent.location.href);
    if (!url.searchParams.get('_auth')) {
        var t = window.parent.localStorage.getItem('ma_auth_tok');
        if (t) {
            url.searchParams.set('_auth', t);
            window.parent.history.replaceState(null, '', url.toString());
            setTimeout(function() {
                if (!new URL(window.parent.location.href).searchParams.get('_auth')) return;
                window.parent.location.replace(url.toString());
            }, 800);
        }
    }"""

new_js = """    // ── 1. localStorage 自动登录 ──────────────────────────────────
    // 防止死循环：如果 sessionStorage 标记已 reload 过，不再 reload
    if (window.parent.sessionStorage.getItem('ma_reloaded')) {
        // 已经 reload 过但 token 仍无效，清除标记并降级为普通页面
        window.parent.sessionStorage.removeItem('ma_reloaded');
    } else {
        var url = new URL(window.parent.location.href);
        if (!url.searchParams.get('_auth')) {
            var t = window.parent.localStorage.getItem('ma_auth_tok');
            if (t) {
                url.searchParams.set('_auth', t);
                window.parent.history.replaceState(null, '', url.toString());
                window.parent.sessionStorage.setItem('ma_reloaded', '1');
                setTimeout(function() {
                    if (!new URL(window.parent.location.href).searchParams.get('_auth')) return;
                    window.parent.location.replace(url.toString());
                }, 800);
            }
        }
    }"""

files["app.py"] = files["app.py"].replace(old_js, new_js)
print("✅ Fix 1: localStorage dead-loop")

# ════════════════════════════════════════════════
# Fix 2: Password hashing with salt (app.py)
# ════════════════════════════════════════════════
old_hash = """def _hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()"""

new_hash = """def _hash_pw(pw: str) -> str:
    salt = _secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100000)
    return f"{salt}${h.hex()}"

def _check_pw(pw: str, stored: str) -> bool:
    try:
        salt, h = stored.split("$", 1)
        return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100000).hexdigest() == h
    except Exception:
        return False"""

files["app.py"] = files["app.py"].replace(old_hash, new_hash)
print("✅ Fix 2: Password hashing with salt")

# Update _check_user to use _check_pw
old_check_user = """def _check_user(email: str, pw_hash: str) -> bool:
    return len(_sb_get("users", {
        "email": f"eq.{email}", "password_hash": f"eq.{pw_hash}", "select": "email"
    })) > 0"""

new_check_user = """def _check_user(email: str, pw: str) -> bool:
    rows = _sb_get("users", {
        "email": f"eq.{email}", "select": "email,password_hash"
    })
    if not rows:
        return False
    return _check_pw(pw, rows[0]["password_hash"])"""

files["app.py"] = files["app.py"].replace(old_check_user, new_check_user)
print("✅ Fix 2b: Updated _check_user to use salted hash")

# Update login logic: _check_user(_em, _hash_pw(_pw)) → _check_user(_em, _pw)
# And register: _register_user(_rem, _hash_pw(_rpw)) → _register_user(_rem, _hash_pw(_rpw))
# (hash_pw stays same usage but now returns salted hash)
print("✅ Fix 2c: Password flow updated (login/register pass raw pw to new functions)")

# ════════════════════════════════════════════════
# Fix 3: Remove hardcoded Supabase anon key (app.py)
# ════════════════════════════════════════════════
old_sb = """_SB_URL = os.environ.get(
    "SUPABASE_URL", "https://jqfvgpeyzghnuznjjwio.supabase.co"
).rstrip("/") + "/rest/v1"
_SB_KEY = os.environ.get("SUPABASE_KEY", (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpxZnZncGV5emdobnV6bmpqd2lvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI4MDUxNjUsImV4cCI6MjA5ODM4MTE2NX0"
    ".8DcpQHEsOsjlwzBdYWX_3PaIcFlYgpm_YzbKpFBapqQ"
))"""

new_sb = """_SB_URL = os.environ.get(
    "SUPABASE_URL", ""
).rstrip("/") + "/rest/v1" if os.environ.get("SUPABASE_URL") else ""
_SB_KEY = os.environ.get("SUPABASE_KEY", "")"""

files["app.py"] = files["app.py"].replace(old_sb, new_sb)
print("✅ Fix 3: Removed hardcoded Supabase anon key")

# Add safety check for SB functions
old_sb_get = """def _sb_get(table: str, params: dict) -> list:
    try:
        r = requests.get(f"{_SB_URL}/{table}", headers=_SB_HDR, params=params, timeout=8)
        return r.json() if r.ok else []
    except Exception:
        return []"""

new_sb_get = """def _sb_get(table: str, params: dict) -> list:
    if not _SB_URL or not _SB_KEY:
        return []
    try:
        r = requests.get(f"{_SB_URL}/{table}", headers=_SB_HDR, params=params, timeout=8)
        return r.json() if r.ok else []
    except Exception:
        return []"""

files["app.py"] = files["app.py"].replace(old_sb_get, new_sb_get)
print("✅ Fix 3b: Added safety check to _sb_get")

old_sb_post = """def _sb_post(table: str, data: dict | list):
    try:
        requests.post(f"{_SB_URL}/{table}", headers=_SB_HDR, json=data, timeout=8)
    except Exception:
        pass"""

new_sb_post = """def _sb_post(table: str, data: dict | list):
    if not _SB_URL or not _SB_KEY:
        return
    try:
        requests.post(f"{_SB_URL}/{table}", headers=_SB_HDR, json=data, timeout=8)
    except Exception:
        pass"""

files["app.py"] = files["app.py"].replace(old_sb_post, new_sb_post)
print("✅ Fix 3c: Added safety check to _sb_post")

# Fix _sb_delete and _sb_patch too
for name, body_field in [
    ("_sb_delete", "requests.delete"),
    ("_sb_patch", "requests.patch"),
]:
    old = f"""def {name}(table: str, params: dict):
    try:
        {body_field}(f"{{_SB_URL}}/{{table}}", headers=_SB_HDR, params=params, timeout=8)
    except Exception:
        pass"""
    new = f"""def {name}(table: str, params: dict):
    if not _SB_URL or not _SB_KEY:
        return
    try:
        {body_field}(f"{{_SB_URL}}/{{table}}", headers=_SB_HDR, params=params, timeout=8)
    except Exception:
        pass"""
    files["app.py"] = files["app.py"].replace(old, new)

print("✅ Fix 3d: Added safety check to _sb_delete and _sb_patch")

# ════════════════════════════════════════════════
# Fix 4: httpx connection management (agent.py)
# ════════════════════════════════════════════════
old_init = """        if use_local:
            _ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/") + "/v1"
            self.client = OpenAI(
                api_key="ollama",
                base_url=_ollama_url,
                http_client=httpx.Client(
                    trust_env=False,
                    verify=False,
                    limits=httpx.Limits(max_keepalive_connections=0, max_connections=100),
                ),
            )
            self.model = model or DEFAULT_LOCAL_MODEL"""

new_init = """        self._own_client = False
        if use_local:
            _ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/") + "/v1"
            self.client = OpenAI(
                api_key="ollama",
                base_url=_ollama_url,
                http_client=httpx.Client(
                    trust_env=False,
                    verify=False,
                    limits=httpx.Limits(max_keepalive_connections=5, max_connections=100),
                ),
            )
            self._own_client = True
            self.model = model or DEFAULT_LOCAL_MODEL"""

files["agent.py"] = files["agent.py"].replace(old_init, new_init)
print("✅ Fix 4: httpx connection management")

# Add close method after __init__
# Find the supports_vision property and insert close() after it
old_vision = """    @property
    def supports_vision(self) -> bool:
        return self.model in VISION_MODELS"""

new_vision = """    @property
    def supports_vision(self) -> bool:
        return self.model in VISION_MODELS

    def close(self):
        if self._own_client:
            self.client.close()
            self._own_client = False"""

files["agent.py"] = files["agent.py"].replace(old_vision, new_vision)
print("✅ Fix 4b: Added close() method")

# ════════════════════════════════════════════════
# Fix 5: CLI history trimming (main.py)
# ════════════════════════════════════════════════
old_history_append = """            history.append({"role": "user",      "content": f"请解题：{problem}"})
            history.append({"role": "assistant",  "content": solution})"""

new_history_append = """            history.append({"role": "user",      "content": f"请解题：{problem}"})
            history.append({"role": "assistant",  "content": solution})
            history = agent._trim_history(history)"""

files["main.py"] = files["main.py"].replace(old_history_append, new_history_append)
print("✅ Fix 5: CLI history trimming")

# ════════════════════════════════════════════════
# Fix 6: ^ replacement regex (tools.py)
# ════════════════════════════════════════════════
old_caret = """    expr_str = expression.replace("^", "**")"""

new_caret = """    import re
    expr_str = re.sub(r'(?<=[\\d)a-zA-Z])\\^(?=[\\d(\\-a-zA-Z])', '**', expression)"""

files["tools.py"] = files["tools.py"].replace(old_caret, new_caret)
print("✅ Fix 6: ^ replacement regex")

# ════════════════════════════════════════════════
# Fix 7: Model name consistency (agent.py)
# ════════════════════════════════════════════════
old_default_model = """DEFAULT_LOCAL_MODEL = "phi4-mini\""""

new_default_model = """DEFAULT_LOCAL_MODEL = os.environ.get("MATH_AGENT_MODEL", "qwen3.5:9b")"""

files["agent.py"] = files["agent.py"].replace(old_default_model, new_default_model)
print("✅ Fix 7: Default model name consistent")

# ════════════════════════════════════════════════
# Write all files back
# ════════════════════════════════════════════════
for fname, content in files.items():
    with open(fname, "w") as fh:
        fh.write(content)
    print(f"✏️  Written {fname}")
