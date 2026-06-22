"""快速验证 mcp_server.py：用 MCP 官方 client SDK 连接 server，list tools 并实际调用一次。"""

import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    params = StdioServerParameters(command=sys.executable, args=["mcp_server.py"])

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("发现的工具：", [t.name for t in tools.tools])

            result = await session.call_tool(
                "calculator", {"expression": "x**2 - 4", "operation": "solve"}
            )
            print("\ncalculator(x**2 - 4, solve) →")
            print(result.content[0].text)

            result2 = await session.call_tool("formula_lookup", {"topic": "calculus"})
            print("\nformula_lookup(calculus) →")
            print(result2.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())
