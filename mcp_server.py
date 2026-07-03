"""
mcp_server.py — 把 math-agent 的三个工具包装成标准 MCP Server。

对比 tools.py 里的 TOOL_DEFINITIONS（手写 OpenAI/Ollama 格式的 JSON Schema）：
FastMCP 直接从函数签名 + docstring 自动生成 schema，任何 MCP host
（Claude Code / Claude Desktop / Cursor）都能直接发现并调用这三个工具，
不需要为每个 host 各写一套 glue code。

运行方式：
  调试: mcp dev mcp_server.py        # 打开 MCP Inspector
  注册进 Claude Code: claude mcp add math-agent -- <venv-python> mcp_server.py
"""

from mcp.server.fastmcp import FastMCP

from tools import _run_calculator, _run_formula_lookup, _run_step_decomposer

mcp = FastMCP("math-agent")


@mcp.tool()
def calculator(expression: str, operation: str, variable: str = "x") -> str:
    """基于 SymPy 的符号/数值计算。operation: evaluate / solve / differentiate / integrate / simplify。"""
    return _run_calculator(expression, operation, variable)


@mcp.tool()
def formula_lookup(query: str) -> str:
    """查询数学公式库。query: algebra / geometry / calculus / trigonometry / statistics / number_theory。"""
    return _run_formula_lookup(query)


@mcp.tool()
def step_decomposer(problem_type: str, problem: str) -> str:
    """为一道数学题生成结构化解题路线图。"""
    return _run_step_decomposer(problem_type, problem)


if __name__ == "__main__":
    mcp.run()
