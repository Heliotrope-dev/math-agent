---
title: Math Solver Agent
emoji: 🧮
colorFrom: purple
colorTo: indigo
sdk: streamlit
sdk_version: 1.50.0
app_file: app.py
pinned: false
license: mit
---

# 🧮 Math Solver Agent

> 完全离线的 AI 数学解题系统 — 无需 OpenAI / DeepSeek API，本地运行。
>
> 独立设计并实现，无框架依赖，手动实现完整 ReAct Agentic Loop。

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![Gradio](https://img.shields.io/badge/Web%20UI-Gradio-orange)](https://gradio.app)
[![Ollama](https://img.shields.io/badge/LLM-Ollama%20qwen3.5%3A9b-green)](https://ollama.ai)
[![MCP](https://img.shields.io/badge/Protocol-MCP-purple)](https://modelcontextprotocol.io)

---

## 核心亮点

| 技术点 | 实现方式 |
|--------|---------|
| **ReAct Agentic Loop** | 手动实现 while 循环：LLM → tool_calls → 执行 → 追加结果 → 循环 |
| **Tool Use / Function Calling** | 三工具设计：规划 → 检索 → 计算，结构化解题 |
| **RAG 语义检索** | nomic-embed-text 向量化公式库，余弦相似度检索，无需预知 topic |
| **本地 LLM** | 支持 qwen3.5:9b via Ollama，完全离线，零 API 成本 |
| **SymPy 符号计算** | 精确无浮点误差，支持求导/积分/极限/解方程 |
| **MCP Server** | FastMCP 包装三个工具，可直接集成进 Claude Code / Claude Desktop |
| **Web UI** | Gradio 界面，实时显示 Agent 工具调用追踪 |

---

## Architecture / 架构

```
┌─────────────────────────────────────────────────────────────────┐
│  用户输入（CLI / Web UI）                                        │
└──────────────────────┬──────────────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  MathAgent — ReAct Agentic Loop  (agent.py)                     │
│                                                                  │
│  LLM (qwen3.5:9b via Ollama  或  DeepSeek API)                  │
│    ├─ finish_reason == "tool_calls"  →  执行工具  →  循环        │
│    └─ finish_reason == "stop"        →  返回最终答案             │
│                                                                  │
│  MAX_ITERATIONS = 12  （防止无限循环）                           │
│  支持多轮对话 history                                            │
└──────┬──────────────────────┬──────────────────────┬────────────┘
       ▼                      ▼                      ▼
┌─────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│step_decomposer│  │  formula_lookup  │    │     calculator      │
│ 分析题型     │  │  公式库检索       │    │  SymPy 符号引擎      │
│ 生成解题路线图│  │  8 个主题 / 60+条│    │  evaluate / solve   │
└─────────────┘  │  RAG 语义检索版   │    │  differentiate      │
                  │  (nomic-embed-text│    │  integrate          │
                  │   + 余弦相似度)   │    │  limit  ← NEW       │
                  └──────────────────┘    │  definite_integral  │
                                          └─────────────────────┘
```

**公式库主题（formula_lookup）：**
```
algebra · geometry · calculus · trigonometry · statistics · number_theory
complex_analysis (复变函数)  ← NEW
numerical_analysis (数值分析) ← NEW
```

---

## Quick Start / 快速开始

### 方式 1：本地 Ollama（推荐，完全离线）

```bash
# 前置条件：安装 Ollama 并拉取模型
ollama pull qwen3.5:9b
ollama pull nomic-embed-text

# 安装依赖
pip install openai sympy gradio requests

# 启动 Web UI
USE_LOCAL=1 python app.py
# → 访问 http://localhost:7860

# 或使用 CLI
python main.py --local
```

### 方式 2：DeepSeek API

```bash
pip install openai sympy gradio

export DEEPSEEK_API_KEY="sk-..."   # 从 platform.deepseek.com 获取

python app.py          # Web UI
python main.py         # CLI
```

### 方式 3：注册进 Claude Code（MCP）

```bash
pip install "mcp[cli]"
claude mcp add math-agent -- python mcp_server.py
# 之后在 Claude Code 里可以直接调用 calculator / formula_lookup / step_decomposer
```

---

## Web UI 界面

```
┌─────────────────────────────────┬────────────────────────────┐
│  🤖 对话区                       │  模式切换                  │
│                                 │  ☑ 本地 Ollama（离线）     │
│  用户: 解方程 2x²+5x-3=0        │                            │
│  AI: 这是标准二次方程...         │  🔧 Agent 工具调用追踪     │
│       x = 1/2 或 x = -3        │  ─────────────────────    │
│                                 │  🔧 调用: step_decomposer  │
│  [输入框]  [发送] [清空]         │     参数: {quadratic...}   │
│                                 │  🔧 调用: formula_lookup   │
│  📝 示例: 求导 f(x)=x³·sin(x)  │     参数: {algebra}        │
│           查公式: 留数定理       │  🔧 调用: calculator       │
│           ∫₀¹ x² dx            │     结果: [1/2, -3]       │
└─────────────────────────────────┴────────────────────────────┘
```

---

## Example / 运行示例

```
📌 输入数学题：解方程 2x² + 5x - 3 = 0

🤔 Agent 思考中...（本地 qwen3.5:9b）

🔧 调用工具：step_decomposer
   参数：{'problem_type': 'quadratic equation', 'problem': '...'}
   结果：🔍 题型分析 | 类型：二次方程 | 1.整理...

🔧 调用工具：formula_lookup
   参数：{'topic': 'algebra'}
   结果：📐 ALGEBRA 常用公式 | • Quadratic Formula...

🔧 调用工具：calculator
   参数：{'expression': '2*x**2 + 5*x - 3', 'operation': 'solve'}
   结果：方程：2*x**2 + 5*x - 3 | 解：[1/2, -3]

📊 解题结果：

**解题思路**：标准二次方程，使用求根公式
**分步解答**：
  1. 识别系数：a=2, b=5, c=-3
  2. 代入公式：x = (-5 ± √(25+24)) / 4 = (-5 ± 7) / 4
  3. 求解：x₁ = 1/2，x₂ = -3

**最终答案：x = 1/2 或 x = -3**
```

---

## 新增功能（极限 & 定积分）

```python
# 极限：variable 使用 "x->0" 格式
calculator(expression="sin(x)/x", operation="limit", variable="x->0")
# → lim(x->0) (sin(x)/x) = 1

# 定积分：expression 格式为 "f(x), 下界, 上界"
calculator(expression="x**2, 0, 1", operation="definite_integral")
# → ∫[0,1] (x²) dx = 1/3 ≈ 0.3333
```

---

## RAG 版 formula_lookup

`tools.py` 里的 `formula_lookup` 需要指定 topic（固定 enum）。
`rag_formula_lookup.py` 用本地向量检索替代关键字匹配：

```
公式库 (60+ 条) → 每条加中文语义描述 → nomic-embed-text 向量化 → 存索引
用户题目（自然语言，不需要 topic）→ embedding → 余弦相似度 → top-k → qwen 生成解题思路
```

> **调试记录**：直接把公式符号混进 embedding 文本，中文 query 跨语言匹配很差；
> 把"检索文本"（纯中文语义描述）和"返回内容"（公式本体）分开存，检索准确率显著提升。

```bash
ollama pull nomic-embed-text
python rag_formula_lookup.py
```

---

## MCP Server

`mcp_server.py` 用 FastMCP 把三个工具包装成标准 MCP Server：
- schema 从 Python 类型注解 + docstring 自动生成
- 任何 MCP host（Claude Code / Claude Desktop / Cursor）零配置发现并调用
- `test_mcp_client.py` 用官方 SDK 验证 server 正常工作

```bash
mcp dev mcp_server.py        # MCP Inspector 调试
claude mcp add math-agent -- python mcp_server.py   # 注册进 Claude Code
```

---

## Files / 文件说明

```
app.py                ← Gradio Web UI（推荐入口）
main.py               ← CLI 入口（支持 --local 本地模式）
agent.py              ← ReAct Agentic Loop，支持 Ollama / DeepSeek 双模式
tools.py              ← 工具定义（JSON Schema）+ SymPy 实现 + 公式库
rag_formula_lookup.py ← RAG 语义检索版 formula_lookup（nomic-embed-text）
mcp_server.py         ← FastMCP Server 包装
test_mcp_client.py    ← MCP client 集成测试
```

---

## Key Design Decisions

- **无 LangChain / 无框架** — Agentic Loop 手动实现，清晰展示 tool_calls → 执行 → 追加 → 循环的完整机制
- **本地优先** — 默认支持 Ollama qwen3.5:9b，零成本、无隐私风险；DeepSeek 作为云端备选
- **RAG 检索/生成分离** — embedding 文本用纯中文描述（语义锚点），返回内容用完整公式，解决跨语言检索问题
- **MCP 协议** — 工具写一次，多个 AI host 共享，符合 2025 年后 AI 工具生态趋势
- **SymPy 精确计算** — 符号计算避免浮点误差，limit/definite_integral 原生支持

---

*Built with Claude Code · 2026*
