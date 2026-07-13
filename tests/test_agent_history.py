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


def test_extract_final_answer_bracket_delimiter():
    # 模型经常写 LaTeX 的 \[ \] 显示公式定界符而不是约定的 $$——语义等价，
    # 之前的正则只认 $$，会把这种情况判成"没有最终答案"，自纠错悄悄
    # 跳过校验。eval/run_verification_eval.py 真实跑数据集时发现的。
    text = "过程...\n最终答案：\n\\[\n\\boxed{14}\n\\]"
    assert _extract_final_answer(text) == "\\boxed{14}"


def test_extract_final_answer_prefers_last_block_mixed_delimiters():
    text = "草稿 \\[x^2\\] 之后 $$15$$"
    assert _extract_final_answer(text) == "15"


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
    assert route_model("求导数", image_bytes=None) == "deepseek-v4-flash"


def test_route_model_with_image_no_vision_key(monkeypatch):
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
    assert route_model("拍题", image_bytes=b"fake") == "deepseek-v4-flash"


def test_route_model_with_image_and_vision_key(monkeypatch):
    monkeypatch.setenv("SILICONFLOW_API_KEY", "fake-key")
    assert route_model("拍题", image_bytes=b"fake") != "deepseek-v4-flash"


# ── solve_stream 纠错分支（mock API 流式响应，不联网）───────────────────────────
# 真实API调用测试过主路径（真流式+多轮工具调用+verified状态都正常），但三次
# 真实调用模型都答对了，没能实测到"纠错"这条分支——用mock强制触发一次，
# 覆盖这个当时没能现场验证的盲区。

def _stream_chunk(content=None, tool_calls=None):
    from unittest.mock import MagicMock
    delta = MagicMock()
    delta.content = content
    delta.tool_calls = tool_calls
    choice = MagicMock()
    choice.delta = delta
    chunk = MagicMock()
    chunk.choices = [choice]
    return chunk


def _stream_tool_call_delta(index, id_=None, name=None, arguments=None):
    from unittest.mock import MagicMock
    tcd = MagicMock()
    tcd.index = index
    tcd.id = id_
    fn = MagicMock()
    fn.name = name
    fn.arguments = arguments
    tcd.function = fn
    return tcd


def test_solve_stream_triggers_visible_correction_on_calc_mismatch(monkeypatch):
    """模拟：第一轮模型调用calculator算出3+4=7，第二轮却写出跟计算结果对不上
    的答案8——应该触发纠错、把修正说明可见地追加进流式输出、状态标为
    corrected；第三轮（重试）给出跟calculator结果一致的修正答案。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key-for-mock-test")
    agent = MathAgent(model="deepseek-v4-flash")

    calls = {"n": 0}

    def fake_create(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return iter([
                _stream_chunk(tool_calls=[_stream_tool_call_delta(0, id_="call_1", name="calculator", arguments="")]),
                _stream_chunk(tool_calls=[_stream_tool_call_delta(
                    0, arguments='{"expression": "3+4", "operation": "evaluate"}')]),
            ])
        elif calls["n"] == 2:
            return iter([
                _stream_chunk(content="计算结果是"),
                _stream_chunk(content="$$8$$"),
            ])
        else:
            return iter([
                _stream_chunk(content="重新检查后，正确答案是"),
                _stream_chunk(content="$$7$$"),
            ])

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)

    collected = []
    for chunk in agent.solve_stream("3加4等于几"):
        d = chunk.choices[0].delta.content
        if d:
            collected.append(d)
    full_text = "".join(collected)

    assert calls["n"] == 3
    assert agent.last_verification == "corrected"
    assert agent.pre_correction_answer is not None
    assert "8" in agent.pre_correction_answer
    # 修正说明必须是可见流出来的，不能悄悄换掉
    assert "重新核对" in full_text
    assert "8" in full_text
    assert "7" in full_text


def test_solve_stream_marks_unresolved_when_correction_still_mismatches(monkeypatch):
    """模拟纠错重试后依然跟calculator结果对不上——不应该无限重试，第二次
    就要标记 unresolved，并在输出里可见地警告用户。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key-for-mock-test")
    agent = MathAgent(model="deepseek-v4-flash")

    calls = {"n": 0}

    def fake_create(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return iter([
                _stream_chunk(tool_calls=[_stream_tool_call_delta(0, id_="call_1", name="calculator", arguments="")]),
                _stream_chunk(tool_calls=[_stream_tool_call_delta(
                    0, arguments='{"expression": "3+4", "operation": "evaluate"}')]),
            ])
        elif calls["n"] == 2:
            return iter([_stream_chunk(content="答案是$$8$$")])
        else:
            # 重试后依然写错（跟calculator算出的7对不上）
            return iter([_stream_chunk(content="确认后答案是$$9$$")])

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)

    collected = []
    for chunk in agent.solve_stream("3加4等于几"):
        d = chunk.choices[0].delta.content
        if d:
            collected.append(d)
    full_text = "".join(collected)

    assert calls["n"] == 3  # 只重试一次，不会无限循环
    assert agent.last_verification == "unresolved"
    assert "没能通过自动核实" in full_text
