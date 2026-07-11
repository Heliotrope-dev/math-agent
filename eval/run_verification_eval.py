"""eval/run_verification_eval.py — 量化"答案自纠错"功能的实际效果。

第一版方法论有两个问题（15题跑出来开启/关闭准确率完全一样，明显不对）：
  1. 样本量太小（15题），一道题的胜负翻转就能让总数完全抵消。
  2. 用两次独立重跑（开启一次、关闭一次）来对比——这两次是各自独立的
     API 调用，LLM 采样本身的随机性就会造成"关闭"那次偶然更准/更差，
     跟纠错功能有没有效果根本没关系，噪音混进了信号里。

这一版改成：只跑一次（纠错功能开启，也就是真实线上的默认行为），
用 agent.last_verification / agent.pre_correction_answer 直接读"这一轮
纠错到底有没有触发、触发前的原始答案是什么"，在同一次调用内部对比
"触发纠错前 vs 纠错后"，不再需要靠对比两次独立重跑来间接推断，排除了
采样噪音这个混淆变量。同时把题目换成更多需要多次 calculator 调用再
综合成一个最终答案的多步题（这类题模型更容易"算对但抄错/漏抄"），
简单题基本不会触发纠错，题目太简单会让这个功能没有用武之地。

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

from agent import MathAgent, _extract_final_answer
from tools import _to_value_set, _value_in_pool

x, y = sp.symbols("x y")

# ── 题目集：(自然语言题目, sympy标准答案值列表) ──────────────────────────────
# 前15道是简单单步题（原有的，保留作为基线对照）；后15道是刻意设计的多步题，
# 需要模型做多次 calculator 调用（求导+求解+代入多个点+综合），这类题
# 更容易出现"工具算对、最终写答案时漏抄/抄错/挑错值"的情况——正是自纠错
# 设计要抓的失误模式，简单题基本不会触发。
_f1 = x**3 - 3 * x**2
PROBLEMS = [
    # ── 简单单步题（基线）──
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

    # ── 多步题：需要多次 calculator 调用再综合成一个答案 ──
    ("求函数 f(x) = x**3 - 6*x**2 + 11*x - 6 的所有实数零点",
     sorted(sp.solve(x**3 - 6 * x**2 + 11 * x - 6, x), key=str)),
    ("求函数 f(x) = x**3 - 3*x**2 在区间[-1, 3]上的最大值（先求导找临界点，"
     "再比较临界点和端点的函数值）",
     [max(_f1.subs(x, v) for v in [-1, 0, 2, 3])]),
    ("求函数 f(x) = x**3 - 3*x**2 在区间[-1, 3]上的最小值（先求导找临界点，"
     "再比较临界点和端点的函数值）",
     [min(_f1.subs(x, v) for v in [-1, 0, 2, 3])]),
    ("求曲线 y = x**2 和 y = 2*x 的交点的所有x坐标",
     sorted(sp.solve(sp.Eq(x**2, 2 * x), x), key=str)),
    ("求函数 f(x) = x**4 - 4*x**2 所有导数为零的点对应的x坐标",
     sorted(sp.solve(sp.diff(x**4 - 4 * x**2, x), x), key=str)),
    ("解方程组：x + y = 5，x - y = 1，求 x 和 y 的值",
     list(sp.linsolve([x + y - 5, x - y - 1], [x, y]))[0]),
    ("将 (x-1)*(x-2)*(x-3) 展开成多项式，求其中 x**2 项的系数",
     [sp.Poly(sp.expand((x - 1) * (x - 2) * (x - 3)), x).coeff_monomial(x**2)]),
    ("求函数 f(x) = x**2 - 4*x + 3 与x轴交点的所有x坐标",
     sorted(sp.solve(x**2 - 4 * x + 3, x), key=str)),
    ("求函数 f(x) = 2*x**3 - 9*x**2 + 12*x 的所有极值点对应的函数值（先求导求临界点，"
     "再代入原函数）",
     sorted({(2 * x**3 - 9 * x**2 + 12 * x).subs(x, v)
             for v in sp.solve(sp.diff(2 * x**3 - 9 * x**2 + 12 * x, x), x)}, key=str)),
    ("求方程 2*sin(x) = 1 在 [0, 2*pi] 区间内的所有解",
     sorted(sp.solveset(sp.Eq(2 * sp.sin(x), 1), x, sp.Interval(0, 2 * sp.pi)), key=str)),
    ("求函数 y = ln(x) - x 的极大值（先求导找临界点，再代回原函数求函数值）",
     [(sp.log(x) - x).subs(x, sp.solve(sp.diff(sp.log(x) - x, x), x)[0])]),
    ("求圆 x**2+y**2=25 与直线 y=x+1 的交点的所有x坐标",
     sorted(sp.solve(sp.Eq(x**2 + (x + 1)**2, 25), x), key=str)),
    ("求函数 f(x) = x**3 - 6*x**2 + 9*x 的所有极值点对应的函数值之和（先求导求临界点，"
     "代入原函数，再把这些值加起来）",
     [sum({(x**3 - 6 * x**2 + 9 * x).subs(x, v)
           for v in sp.solve(sp.diff(x**3 - 6 * x**2 + 9 * x, x), x)})]),
    ("求函数 f(x) = x**4 - 8*x**2 + 3 所有导数为零的点对应的x坐标",
     sorted(sp.solve(sp.diff(x**4 - 8 * x**2 + 3, x), x), key=str)),
    ("求方程 x**3 - 2*x**2 - 5*x + 6 = 0 的所有实数解",
     sorted(sp.solve(x**3 - 2 * x**2 - 5 * x + 6, x), key=str)),
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


def main():
    results = []
    with MathAgent(use_local=False) as agent:
        for i, (problem, expected) in enumerate(PROBLEMS, 1):
            print(f"\n[{i}/{len(PROBLEMS)}] {problem}")
            t0 = time.time()
            try:
                final = agent.solve(problem)
            except Exception as e:
                final = f"[调用出错: {e}]"
            dt = time.time() - t0

            verification = agent.last_verification
            final_correct = _grade_against(final, expected)
            pre_correct = None
            if verification == "corrected" and agent.pre_correction_answer:
                pre_correct = _grade_against(agent.pre_correction_answer, expected)

            tag = f"验证={verification or '未触发'}"
            if pre_correct is not None:
                tag += f"  纠错前{'✓' if pre_correct else '✗'}→纠错后{'✓' if final_correct else '✗'}"
            print(f"  最终答案: {'✓' if final_correct else '✗'}  {tag}  ({dt:.1f}s)")

            results.append({
                "problem": problem,
                "expected": [str(e) for e in expected],
                "verification": verification,
                "final_correct": final_correct,
                "pre_correction_correct": pre_correct,
                "seconds": round(dt, 1),
                "output": final,
                "pre_correction_output": agent.pre_correction_answer,
            })

    n = len(results)
    n_correct = sum(r["final_correct"] for r in results)
    triggered = [r for r in results if r["verification"] == "corrected"]
    fixed = [r for r in triggered if r["pre_correction_correct"] is False and r["final_correct"] is True]
    broke = [r for r in triggered if r["pre_correction_correct"] is True and r["final_correct"] is False]
    unnecessary = [r for r in triggered if r["pre_correction_correct"] is True and r["final_correct"] is True]
    still_wrong = [r for r in triggered if r["pre_correction_correct"] is False and r["final_correct"] is False]

    print("\n" + "=" * 60)
    print(f"题目数: {n}")
    print(f"最终答案准确率: {n_correct/n*100:.1f}%  ({n_correct}/{n})")
    print(f"纠错触发次数: {len(triggered)}/{n}")
    if triggered:
        print(f"  其中：纠错前错→纠错后对（真正救回来）: {len(fixed)}")
        for r in fixed:
            print(f"    - {r['problem']}")
        print(f"  纠错前对→纠错后错（误伤，反而改错了）: {len(broke)}")
        for r in broke:
            print(f"    - {r['problem']}")
        print(f"  纠错前对→纠错后仍对（触发了但没必要，多花一轮）: {len(unnecessary)}")
        print(f"  纠错前错→纠错后仍错（没救回来）: {len(still_wrong)}")
    print("=" * 60)

    out_path = os.path.join(os.path.dirname(__file__), f"results_{int(time.time())}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "n": n, "n_correct": n_correct,
            "n_triggered": len(triggered), "n_fixed": len(fixed),
            "n_broke": len(broke), "n_unnecessary": len(unnecessary),
            "n_still_wrong": len(still_wrong),
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n详细结果已写入 {out_path}")


if __name__ == "__main__":
    main()
