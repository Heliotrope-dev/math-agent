"""tools.py 里"答案自纠错"相关纯函数的单元测试：LaTeX 归一化、答案解析、
数学等价比对。全部本地计算，不触网、不调用 LLM。
"""

from tools import (
    _normalize_latex,
    _clean_answer_text,
    _extract_calc_value,
    _to_value_set,
    _value_in_pool,
    answer_supported_by_calcs,
    answers_equivalent,
    _check_expr_safe,
    _preprocess_expr,
)


# ── _normalize_latex ─────────────────────────────────────────────────────────

def test_normalize_latex_boxed():
    assert _normalize_latex(r"\boxed{3}") == "3"


def test_normalize_latex_frac():
    assert _normalize_latex(r"\frac{1}{2}") == "(1)/(2)"


def test_normalize_latex_dfrac():
    assert _normalize_latex(r"\dfrac{a}{b}") == "(a)/(b)"


def test_normalize_latex_frac_short():
    assert _normalize_latex(r"\frac12") == "(1)/(2)"


def test_normalize_latex_nested_frac():
    # 分数里还有分数，需要反复替换到不再变化
    out = _normalize_latex(r"\frac{\frac{1}{2}}{3}")
    assert "frac" not in out


# ── _clean_answer_text ───────────────────────────────────────────────────────

def test_clean_answer_text_strips_prefix():
    assert _clean_answer_text("答案：3") == "3"
    assert _clean_answer_text("结果: -2") == "-2"


def test_clean_answer_text_strips_dollar_and_left_right():
    assert _clean_answer_text(r"$\left(3\right)$") == "(3)"


# ── _extract_calc_value ──────────────────────────────────────────────────────

def test_extract_calc_value_solve_result():
    out = _extract_calc_value("方程：x**2-4\n解：[2, -2]")
    assert out == "[2, -2]"


def test_extract_calc_value_strips_approx():
    out = _extract_calc_value("表达式：1/3\n化简：1/3\n数值结果：1/3 ≈ 0.333333333333333")
    assert out.strip() == "1/3"


def test_extract_calc_value_strips_integration_constant():
    out = _extract_calc_value(r"∫ (x) dx = x**2/2 + C")
    assert out.strip() == "x**2/2"


# ── _to_value_set ────────────────────────────────────────────────────────────

def test_to_value_set_single():
    vals = _to_value_set("3")
    assert len(vals) == 1


def test_to_value_set_multi_comma_separated():
    vals = _to_value_set("[2, -2]")
    assert len(vals) == 2


def test_to_value_set_strips_var_eq_prefix():
    vals = _to_value_set("x=2, x=-2")
    assert len(vals) == 2


def test_to_value_set_parse_failure_returns_none():
    # 注意：sympy 的隐式乘法解析器会把中文字符当成符号变量相乘，不会报错
    # （比如"这不是"会被解析成 这*不*是），所以这里用真正语法非法的输入。
    assert _to_value_set("(((") is None


# ── _value_in_pool ────────────────────────────────────────────────────────────

def test_value_in_pool_symbolic_match():
    import sympy as sp
    x = sp.sympify("1/3")
    pool = [sp.sympify("2/6")]
    assert _value_in_pool(x, pool)


def test_value_in_pool_numeric_tolerance():
    import sympy as sp
    v = sp.sympify("0.1 + 0.2")
    pool = [sp.sympify("0.3")]
    assert _value_in_pool(v, pool, tol=1e-6)


def test_value_in_pool_no_match():
    import sympy as sp
    v = sp.sympify("5")
    pool = [sp.sympify("3"), sp.sympify("-3")]
    assert not _value_in_pool(v, pool)


# ── answer_supported_by_calcs（核心：答案自纠错的判定逻辑）─────────────────────

def test_answer_supported_single_calc():
    calc_results = ["表达式：2+3*4\n化简：14\n数值结果：14"]
    assert answer_supported_by_calcs("14", calc_results)


def test_answer_supported_mismatch_triggers_correction():
    # 模型抄错了最终答案：calculator 算出 14，但写成 15
    calc_results = ["表达式：2+3*4\n化简：14\n数值结果：14"]
    assert not answer_supported_by_calcs("15", calc_results)


def test_answer_supported_multi_calc_pool():
    # 二次方程两个根分两次单独 evaluate 调用——不能只看最后一次
    calc_results = [
        "表达式：2\n化简：2\n数值结果：2",
        "表达式：-2\n化简：-2\n数值结果：-2",
    ]
    assert answer_supported_by_calcs("[2, -2]", calc_results)


def test_answer_supported_boxed_and_frac_latex():
    calc_results = ["表达式：1/2\n化简：1/2\n数值结果：0.5"]
    assert answer_supported_by_calcs(r"\boxed{\frac{1}{2}}", calc_results)


def test_answer_supported_no_calc_results():
    assert not answer_supported_by_calcs("14", [])


def test_answer_supported_unparseable_answer():
    calc_results = ["表达式：2+3*4\n化简：14\n数值结果：14"]
    assert not answer_supported_by_calcs("(((", calc_results)


def test_answers_equivalent_single_result():
    assert answers_equivalent("14", "表达式：2+3*4\n化简：14\n数值结果：14")
    assert not answers_equivalent("15", "表达式：2+3*4\n化简：14\n数值结果：14")


# ── _check_expr_safe（沙箱白名单）────────────────────────────────────────────

def test_check_expr_safe_allows_plain_math():
    assert _check_expr_safe("2*x**2 + 3*x - 5") is None


def test_check_expr_safe_rejects_banned_keyword():
    assert _check_expr_safe("__import__('os')") is not None
    assert _check_expr_safe("eval('1')") is not None
    assert _check_expr_safe("os.system('ls')") is not None


def test_check_expr_safe_rejects_too_long():
    assert _check_expr_safe("x+" * 300) is not None


# ── _preprocess_expr（^ → **）──────────────────────────────────────────────

def test_preprocess_expr_caret_to_power():
    assert _preprocess_expr("x^2") == "x**2"


def test_preprocess_expr_leaves_existing_power_alone():
    assert _preprocess_expr("x**2") == "x**2"
