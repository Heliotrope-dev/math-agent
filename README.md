# Math Agent

面向大学数学学习的 AI 助手：将解题、符号计算、知识检索与学习记录放进一条可追溯的学习流程。

在线体验：[math.heliotrope.online](https://math.heliotrope.online)

## 它能做什么

- 解答高等数学、线性代数、概率论、数理统计、常微分方程等大学数学问题
- 支持文字、图片和语音提问，并以分步骤讲解为主，而非只给最终答案
- 用 SymPy 进行精确符号计算与结果校验；发现结果不一致时进行一次受控复核
- 生成函数图像、解题路线与知识导图，帮助理解而不只是完成一道题
- 提供个人错题本、学习档案与针对性练习建议
- 上传 PDF、TXT、Markdown 建立私有知识库，并在回答中标注来源

## 为什么这样设计

模型擅长解释和引导，但不应独自承担可验证的数学计算。因此项目将职责拆开：

- AI 负责理解题意、规划步骤、解释推导与组织表达。
- SymPy 负责精确计算、符号等价和数值容差校验。
- 检索系统只从用户自己的知识库中取回资料，并附带来源。

这让回答既更像老师，也更容易核验。计算或检索无法确认时，系统应该明确说明边界，而不是补全一个看似合理的答案。

## 核心架构

```text
用户输入（文本 / 图片 / 语音）
            |
            v
      Math Agent 编排层
       /       |        \
      v        v         v
  SymPy 计算  公式检索   图像 / 知识导图
       \       |        /
        v      v       v
     校验与一次受控复核
            |
            v
      流式讲解与学习记录
```

| 模块 | 职责 |
| --- | --- |
| `agent.py` | 模型路由、工具调用循环、流式输出与结果复核 |
| `tools.py` | 安全的 SymPy 计算、公式检索、步骤拆解、作图、知识导图 |
| `components/rag_engine.py` | ChromaDB 私有知识库检索 |
| `components/rag_ingest.py` | 文档解析、切分与扫描件 OCR 兜底 |
| `components/auth.py` | 账户、对话历史、错题本与学习档案持久化 |
| `mcp_server.py` | 将纯函数数学工具暴露为 MCP Server |

## 技术栈

- Python 3.11、Streamlit
- Gemini：文字、图片、语音与嵌入
- SymPy：确定性符号计算与答案校验
- ChromaDB：按用户隔离的知识库检索
- Supabase：账户与学习数据持久化

## 本地运行

```bash
git clone https://github.com/Heliotrope-dev/math-agent.git
cd math-agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

在 `.streamlit/secrets.toml` 配置自己的模型与数据库凭据。该文件只保留在本地或部署环境，绝不提交到仓库。

## 项目原则

- 优先帮助理解，而不是把作业答案直接交出去。
- 可由程序验证的结论，交给程序验证。
- 用户上传的资料按账户隔离；引用只来自当前用户可访问的资料。
- 失败、信息不足或无法验证时如实说明，不伪造来源或结论。

## License

MIT
