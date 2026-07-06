"""
main.py — CLI entry point

Usage:
  DeepSeek mode: export DEEPSEEK_API_KEY="sk-..."  &&  python main.py
  Local Ollama:  python main.py --local             (no API Key needed)
"""

import sys
from agent import MathAgent

_BANNER = """
╔══════════════════════════════════════════════════╗
║           🧮  Math Solver Agent                  ║
╚══════════════════════════════════════════════════╝
支持：代数 · 几何 · 微积分 · 三角 · 概率统计 · 复变函数 · 数值分析
"""

_EXAMPLES = """
📝 示例题目：
  1. 解方程：2x² + 5x - 3 = 0
  2. 求导：f(x) = x³·sin(x)
  3. 求不定积分：x² + 2x
  4. 定积分：x**2, 0, 1（即 ∫₀¹ x² dx）
  5. 极限：sin(x)/x，x→0（输入 variable=x->0）
  6. 查公式：复变函数柯西积分公式
  7. 直角三角形两直角边为 3 和 4，求斜边
  8. 复变函数 f(z)=z² 是否解析
  9. 用复化梯形公式（n=4）计算 ∫₀¹ eˣ dx
"""


def main() -> None:
    use_local = "--local" in sys.argv or "-l" in sys.argv
    agent = MathAgent(use_local=use_local)
    mode = "本地 qwen3.5:9b（离线）" if use_local else "DeepSeek API"
    print(_BANNER)
    print(f"  模式：{mode}")
    print("  命令：help 查看示例，quit / exit / q 退出，clear 清空对话历史\n")

    history = []

    while True:
        try:
            problem = input("📌 输入数学题（或 help / quit / clear）：").strip()

            if not problem:
                continue
            if problem.lower() in ("quit", "exit", "q"):
                print("\n再见！")
                break
            if problem.lower() == "help":
                print(_EXAMPLES)
                continue
            if problem.lower() == "clear":
                history.clear()
                print("✅ 对话历史已清空\n")
                continue

            print("\n" + "─" * 52)
            solution = agent.solve(problem, history=history)
            print("\n📊 解题结果：\n")
            print(solution)
            print("─" * 52 + "\n")

            history.append({"role": "user",      "content": f"请解题：{problem}"})
            history.append({"role": "assistant",  "content": solution})
            history = agent._trim_history(history)

        except KeyboardInterrupt:
            print("\n\n已中断，再见！")
            sys.exit(0)
        except Exception as exc:
            print(f"\n❌ 出错：{exc}\n")


if __name__ == "__main__":
    main()
