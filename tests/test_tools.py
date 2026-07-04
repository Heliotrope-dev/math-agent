"""tools.py 单元测试：calculator 各操作 + formula_lookup 降级路径。"""

import tools
from tools import _run_calculator, _run_formula_lookup


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
