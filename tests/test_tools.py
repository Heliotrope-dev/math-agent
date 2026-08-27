"""tools.py 单元测试：calculator 各操作 + formula_lookup 降级路径
（原有部分），加上 LaTeX 归一化/表达式白名单校验（今晚新补的部分）。
"""

import tools
from tools import _run_calculator, _run_formula_lookup


# ── calculator / formula_lookup（原有测试）───────────────────────────────

def test_eval_basic():
    out = _run_calculator("2+3*4", "evaluate")
    assert "14" in out


def test_solve_quadratic():
    out = _run_calculator("x**2-4", "solve")
    assert "2" in out and "-2" in out


def test_differentiate():
    out = _run_calculator("x**3", "differentiate")
    assert "3" in out  # x**3 的导数 3*x**2


def test_bad_expr_no_crash():
    out = _run_calculator("this is (( not math", "evaluate")
    assert isinstance(out, str)
    assert "计算出错" in out


def test_formula_fallback(monkeypatch):
    # 强制 RAG 不可用（且处于重试冷却期），必须走关键词 fallback
    monkeypatch.setattr(tools, "_rag_index", None)
    monkeypatch.setattr(tools, "_rag_available", False)
    monkeypatch.setattr(tools, "_rag_next_retry", float("inf"))
    out = _run_formula_lookup("求导数的乘积法则")
    assert isinstance(out, str)
    assert out.strip()


# ── _normalize_latex（今晚新补）───────────────────────────────────────────

def test_normalize_latex_simple_frac():
    assert tools._normalize_latex(r"\frac{1}{2}") == "(1)/(2)"


def test_normalize_latex_nested_frac():
    """分数里还有分数——while循环改成了for循环封顶50次，嵌套2层
    远低于上限，展开结果必须跟改动前完全一样。"""
    assert tools._normalize_latex(r"\frac{\frac{a}{b}}{c}") == "((a)/(b))/(c)"


def test_normalize_latex_boxed_unwrap():
    assert tools._normalize_latex(r"\boxed{x = 2}") == "x = 2"


def test_normalize_latex_iteration_cap_terminates():
    """极端构造的深层嵌套（超过50层）不应该让函数失控跑很久——
    只要能在合理时间内返回（不抛异常、不卡死）就算通过，不要求
    完全展开到底（这正是加上限的设计取舍：牺牲极端情况下的完整
    展开，换取任何输入都能有限时间内返回）。"""
    import time

    deep = "a"
    for _ in range(80):
        deep = r"\frac{" + deep + "}{1}"
    t0 = time.perf_counter()
    result = tools._normalize_latex(deep)
    elapsed = time.perf_counter() - t0
    assert isinstance(result, str)
    assert elapsed < 5, f"80层嵌套花了{elapsed:.2f}s，看起来上限没生效"


# ── fix_latex ─────────────────────────────────────────────────────────────

def test_fix_latex_bracket_to_dollar():
    assert tools.fix_latex(r"\(x+1\)") == "$x+1$"


def test_fix_latex_display_bracket_to_double_dollar():
    result = tools.fix_latex(r"\[x^2 + 1\]")
    assert "$$x^2 + 1$$" in result


def test_fix_latex_strips_stray_html_tags():
    result = tools.fix_latex("答案是 5 </div>")
    assert "</div>" not in result


def test_fix_latex_fixes_odd_double_dollar_count():
    result = tools.fix_latex("$$x=1")
    assert result.count("$$") % 2 == 0


# ── _check_expr_safe ────────────────────────────────────────────────────

def test_check_expr_safe_accepts_normal_math():
    assert tools._check_expr_safe("2*x**2 + 3*x - 5") is None
    assert tools._check_expr_safe("sin(x) + cos(x)") is None


def test_check_expr_safe_rejects_dunder():
    # 双下划线本身就不在_SAFE_EXPR白名单字符集里，__import__这类写法
    # 在正则这一关就会被挡下，不需要走到_BANNED关键字检测那一步。
    msg = tools._check_expr_safe("__import__('os').system('ls')")
    assert msg is not None


def test_check_expr_safe_rejects_banned_keywords():
    for payload in ("eval(1)", "exec('x')", "open('/etc/passwd')", "lambda x: x"):
        assert tools._check_expr_safe(payload) is not None, f"{payload!r} 应该被拒绝"


def test_check_expr_safe_rejects_too_long():
    assert tools._check_expr_safe("x+" * 300) is not None
