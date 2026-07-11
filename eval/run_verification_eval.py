"""eval/run_verification_eval.py — 量化"答案自纠错"功能的实际效果。

对每道题分别用"自纠错开启（当前默认行为）"和"自纠错关闭（monkeypatch掉
判定函数，模拟没有这个功能时的效果）"各跑一次真实 API 调用，比较模型
最终答案与 sympy 独立算出的标准答案是否一致，输出准确率对比。

题目的标准答案全部由 sympy 直接计算（不经过 tools.py 的 calculator 工具），
跟被测代码互相独立，避免"用同一套代码出题又用同一套代码判题"的自证明问题。

跑法：
  python3 eval/run_verification_eval.py

输出：eval/results_<timestamp>.json（逐题原始结果）+ 终端打印的汇总统计。
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_secrets():
    import toml
    path = os.path.join(os.path.dirname(__file__), "..", ".streamlit", "secrets.toml")
    try:
        secrets = toml.load(path)
        for k, v in secrets.items():
            if isinstance(v, str) and k not in os.environ:
                os.environ[k] = v
    except Exception as e:
        print(f"（未加载 secrets.toml：{e}，将依赖已有环境变量）")


_load_secrets()

import sympy as sp

import agent as agent_module
from agent import MathAgent, _extract_final_answer
from tools import _to_value_set, _value_in_pool, answer_supported_by_calcs as _real_verifier

x = sp.Symbol("x")

# ── 题目集：(自然语言题目, sympy标准答案值列表) ──────────────────────────────
# 刻意混入几道容易"工具算对、最终答案抄错/漏代入"的题（比如要求代入具体点
# 求导数值、多解方程），这类题正是自纠错设计要抓的失误模式。
PROBLEMS = [
    ("求 2 + 3*4 的值", [sp.sympify("14")]),
    ("求方程 x**2 - 4 = 0 的所有实数解", [sp.sympify("2"), sp.sympify("-2")]),
    ("求函数 f(x) = x**3 - 3*x 的导数", [sp.diff(x**3 - 3 * x, x)]),
    ("求 x**2 的不定积分（结果不用写 +C）", [sp.integrate(x**2, x)]),
    ("求极限 lim(x->0) sin(x)/x", [sp.limit(sp.sin(x) / x, x, 0)]),
    ("求定积分 ∫[0,1] x**2 dx", [sp.integrate(x**2, (x, 0, 1))]),
    ("化简 (x**2 - 1)/(x - 1)", [sp.simplify((x**2 - 1) / (x - 1))]),
    ("求方程 2*x - 6 = 0 的解", [sp.sympify("3")]),
    ("求函数 f(x) = sin(x)*cos(x) 的导数", [sp.diff(sp.sin(x) * sp.cos(x), x)]),
    ("求函数 f(x) = x**3 在 x=2 处的导数值（不是导函数，是代入x=2后的具体数值）",
     [sp.diff(x**3, x).subs(x, 2)]),
    ("求方程 x**2 - 5*x + 6 = 0 的所有解", [sp.sympify("2"), sp.sympify("3")]),
    ("求 e**x 的不定积分（结果不用写 +C）", [sp.exp(x)]),
    ("求定积分 ∫[0,pi] sin(x) dx", [sp.integrate(sp.sin(x), (x, 0, sp.pi))]),
    ("求函数 f(x) = ln(x) 的导数", [sp.diff(sp.log(x), x)]),
    ("求函数 f(x) = 2*x**2 - 8*x + 3 在 x=3 处的导数值（代入具体数值）",
     [sp.diff(2 * x**2 - 8 * x + 3, x).subs(x, 3)]),
]


def _grade_against(response_text: str, expected: list) -> bool:
    """从模型输出里提取最终答案（复用生产代码同一套 $$ 提取逻辑——这是
    "怎么知道答案对不对"必经的同一道工序，不是被测对象本身），跟 sympy
    独立算出的标准答案比对是否等价。"""
    parsed = _extract_final_answer(response_text)
    if not parsed:
        return False
    vals = _to_value_set(parsed)
    if not vals:
        return False
    if len(vals) != len(expected):
        return False
    remaining = list(expected)
    for v in vals:
        match = next((e for e in remaining if _value_in_pool(v, [e])), None)
        if match is None:
            return False
        remaining.remove(match)
    return True


def _run_one(agent: MathAgent, problem: str) -> str:
    try:
        result = agent.solve(problem)
        if hasattr(result, "__iter__") and not isinstance(result, str):
            result = "".join(c.choices[0].delta.content or "" for c in result)
        return result or ""
    except Exception as e:
        return f"[调用出错: {e}]"


def main():
    results = []
    with MathAgent(use_local=False) as agent:
        for i, (problem, expected) in enumerate(PROBLEMS, 1):
            print(f"\n[{i}/{len(PROBLEMS)}] {problem}")

            # ── 自纠错开启（默认行为，不动代码）──
            t0 = time.time()
            out_on = _run_one(agent, problem)
            ok_on = _grade_against(out_on, expected)
            dt_on = time.time() - t0
            print(f"  验证开启: {'✓' if ok_on else '✗'}  ({dt_on:.1f}s)")

            # ── 自纠错关闭（monkeypatch判定函数恒True，模拟没有这个功能）──
            agent_module.answer_supported_by_calcs = lambda *a, **k: True
            t0 = time.time()
            out_off = _run_one(agent, problem)
            ok_off = _grade_against(out_off, expected)
            dt_off = time.time() - t0
            agent_module.answer_supported_by_calcs = _real_verifier  # 恢复
            print(f"  验证关闭: {'✓' if ok_off else '✗'}  ({dt_off:.1f}s)")

            results.append({
                "problem": problem,
                "expected": [str(e) for e in expected],
                "verify_on": {"correct": ok_on, "seconds": round(dt_on, 1), "output": out_on},
                "verify_off": {"correct": ok_off, "seconds": round(dt_off, 1), "output": out_off},
            })

    n = len(results)
    acc_on = sum(r["verify_on"]["correct"] for r in results) / n
    acc_off = sum(r["verify_off"]["correct"] for r in results) / n
    flipped_to_correct = [r["problem"] for r in results
                           if r["verify_on"]["correct"] and not r["verify_off"]["correct"]]
    flipped_to_wrong = [r["problem"] for r in results
                         if not r["verify_on"]["correct"] and r["verify_off"]["correct"]]

    print("\n" + "=" * 60)
    print(f"题目数: {n}")
    print(f"验证开启准确率: {acc_on*100:.1f}%  ({sum(r['verify_on']['correct'] for r in results)}/{n})")
    print(f"验证关闭准确率: {acc_off*100:.1f}%  ({sum(r['verify_off']['correct'] for r in results)}/{n})")
    print(f"验证把错的救回来的题: {len(flipped_to_correct)}")
    for p in flipped_to_correct:
        print(f"  - {p}")
    if flipped_to_wrong:
        print(f"验证关闭反而更对的题（值得关注）: {len(flipped_to_wrong)}")
        for p in flipped_to_wrong:
            print(f"  - {p}")
    print("=" * 60)

    out_path = os.path.join(os.path.dirname(__file__), f"results_{int(time.time())}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "n": n, "acc_on": acc_on, "acc_off": acc_off,
            "flipped_to_correct": flipped_to_correct,
            "flipped_to_wrong": flipped_to_wrong,
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n详细结果已写入 {out_path}")


if __name__ == "__main__":
    main()
