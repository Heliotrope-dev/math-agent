"""agent.py 里跟对话历史管理相关的纯函数测试：轮次裁剪、消息截断、
长对话压缩摘要、最终答案提取。全部本地计算，不发起任何 API 调用。
"""

from agent import MathAgent, _extract_final_answer, route_model, _MAX_HISTORY_TURNS, _MAX_MSG_CHARS


def _turn(i):
    return [
        {"role": "user", "content": f"问题{i}"},
        {"role": "assistant", "content": f"回答{i}"},
    ]


# ── _extract_final_answer ────────────────────────────────────────────────────

def test_extract_final_answer_basic():
    assert _extract_final_answer("过程...\n$$14$$") == "14"


def test_extract_final_answer_takes_last_block():
    # 按格式约定最终答案应该是最后一个 $$ $$ 块——防止正文里出现的公式被误当成答案
    text = "推导过程 $$x^2$$ 继续...\n最终答案 $$15$$"
    assert _extract_final_answer(text) == "15"


def test_extract_final_answer_none_when_absent():
    assert _extract_final_answer("这段话里没有双美元符号公式") is None


# ── _msg_len / _truncate_msg ─────────────────────────────────────────────────

def test_msg_len_string_content():
    assert MathAgent._msg_len({"role": "user", "content": "abc"}) == 3


def test_msg_len_multimodal_content_estimated():
    # 图片消息 content 是 list，不是 str，用固定估算值而不是 len()（len(list)会严重低估token数）
    m = {"role": "user", "content": [{"type": "text", "text": "x"}]}
    assert MathAgent._msg_len(m) == 4000


def test_truncate_msg_under_limit_unchanged():
    m = {"role": "user", "content": "short"}
    assert MathAgent._truncate_msg(m) == m


def test_truncate_msg_over_limit_truncated():
    long_content = "a" * (_MAX_MSG_CHARS + 500)
    m = {"role": "user", "content": long_content}
    out = MathAgent._truncate_msg(m)
    assert len(out["content"]) < len(long_content)
    assert out["content"].startswith("a" * 100)
    assert "已截断" in out["content"]


def test_truncate_msg_does_not_mutate_original():
    long_content = "a" * (_MAX_MSG_CHARS + 500)
    m = {"role": "user", "content": long_content}
    MathAgent._truncate_msg(m)
    assert m["content"] == long_content  # 原字典不能被就地改掉


# ── _trim_history ─────────────────────────────────────────────────────────────

def test_trim_history_keeps_all_when_short():
    history = _turn(1) + _turn(2)
    assert MathAgent._trim_history(history) == history


def test_trim_history_caps_at_max_turns():
    history = []
    for i in range(_MAX_HISTORY_TURNS + 5):
        history.extend(_turn(i))
    trimmed = MathAgent._trim_history(history)
    # 每轮 user+assistant 两条，裁完应该正好是 _MAX_HISTORY_TURNS 轮
    assert len(trimmed) == _MAX_HISTORY_TURNS * 2
    # 保留的应该是最近的几轮，不是最早的
    assert trimmed[0]["content"] == f"问题{5}"


def test_trim_history_drops_leading_orphan_assistant_message():
    # 历史以 assistant 消息开头（没有配对的user）时会被静默丢弃——只有
    # user 消息才会把缓冲区结算进 turns。生产环境里 messages 列表总是
    # 以 user 消息开始（_math_page.py 里第一条 append 永远是用户消息），
    # 这个分支实际不会触发，这里只是把当前行为钉死，防止以后改坏。
    history = [{"role": "assistant", "content": "无头回复"}] + _turn(1)
    trimmed = MathAgent._trim_history(history)
    assert trimmed == _turn(1)


# ── _compress_history ─────────────────────────────────────────────────────────

def test_compress_history_short_passthrough():
    history = _turn(1)
    assert MathAgent._compress_history(history) == history


def test_compress_history_summarizes_dropped_turns():
    history = []
    for i in range(_MAX_HISTORY_TURNS + 5):
        history.extend(_turn(i))
    compressed = MathAgent._compress_history(history)
    # 最前面应该多出一条 system 摘要消息
    assert compressed[0]["role"] == "system"
    assert "摘要" in compressed[0]["content"]
    # 摘要之后紧跟着最近保留的轮次
    assert compressed[1]["content"] == f"问题{5}"


def test_compress_history_summary_capped_at_2000_chars():
    history = []
    for i in range(200):
        history.extend(_turn(i))
    compressed = MathAgent._compress_history(history)
    assert len(compressed[0]["content"]) <= 2000


# ── route_model ───────────────────────────────────────────────────────────────

def test_route_model_no_image_returns_default():
    assert route_model("求导数", image_bytes=None) == "deepseek-chat"


def test_route_model_with_image_no_vision_key(monkeypatch):
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
    assert route_model("拍题", image_bytes=b"fake") == "deepseek-chat"


def test_route_model_with_image_and_vision_key(monkeypatch):
    monkeypatch.setenv("SILICONFLOW_API_KEY", "fake-key")
    assert route_model("拍题", image_bytes=b"fake") != "deepseek-chat"
