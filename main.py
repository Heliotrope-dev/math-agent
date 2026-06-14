"""
main.py — CLI 入口

运行方式：
  export ANTHROPIC_API_KEY="sk-ant-..."
  python main.py
"""

import sys
from agent import MathAgent

_BANNER = """
╔══════════════════════════════════════════════════╗
║           🧮  Math Solver Agent                  ║
║   Powered by Claude claude-opus-4-8 + Tool Use            ║
╚══════════════════════════════════════════════════╝
支持题型：代数 · 几何 · 微积分 · 三角 · 概率统计

命令：help 查看示例，quit / exit / q 退出
"""

_EXAMPLES = """
📝 示例题目：
  1. 解方程：2x² + 5x - 3 = 0
  2. 求导：f(x) = x³·sin(x)
  3. 求不定积分：x² + 2x
  4. 直角三角形两直角边为 3 和 4，求斜边
  5. 求 f(x) = x³ - 6x² + 9x + 1 的极值点
  6. 一个袋中有 3 个红球和 5 个蓝球，不放回取 2 个，求两个都是红球的概率
"""


def main() -> None:
    print(_BANNER)
    agent = MathAgent()

    while True:
        try:
            problem = input("📌 输入数学题（或 help / quit）：").strip()

            if not problem:
                continue

            if problem.lower() in ("quit", "exit", "q"):
                print("\n再见！")
                break

            if problem.lower() == "help":
                print(_EXAMPLES)
                continue

            print("\n" + "─" * 52)
            solution = agent.solve(problem)
            print("\n📊 解题结果：\n")
            print(solution)
            print("─" * 52 + "\n")

        except KeyboardInterrupt:
            print("\n\n已中断，再见！")
            sys.exit(0)
        except Exception as exc:
            print(f"\n❌ 出错：{exc}\n")


if __name__ == "__main__":
    main()
