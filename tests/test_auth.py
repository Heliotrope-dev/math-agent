"""components/auth.py 单元测试：PBKDF2 密码哈希（纯本地，不触网）。"""

from components.auth import _hash_pw, _check_pw


def test_hash_verify_roundtrip():
    stored = _hash_pw("s3cret-密码!")
    assert "$" in stored  # salt$hash 格式
    assert _check_pw("s3cret-密码!", stored)


def test_wrong_pw_rejected():
    stored = _hash_pw("correct-horse")
    assert not _check_pw("wrong-password", stored)
