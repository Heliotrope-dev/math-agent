# Math Agent

面向大学数学的 AI 学习平台，包含 AI 解题助手和 RAG 知识库问答两大功能模块。

线上地址：**[math.heliotrope.online](https://math.heliotrope.online)**

---

## 功能

**数学解题**
拍题识别（Gemini 原生多模态）、语音提问（Gemini 音频输入）、SymPy 精确符号计算、苏格拉底式引导模式、覆盖大一到大三 14 门课程、真流式输出、自然语言生成知识导图、错题本（LLM 自动总结成可读条目）、学习档案（薄弱环节追踪+针对性练习）、答案自纠错（详见下方）、对话历史持久化。

**知识库问答（RAG）**
PDF/TXT/Markdown 上传去重、Gemini 向量化 + ChromaDB 检索、带来源引用的回答、多轮对话。

---

## 项目结构

```
app.py                       # 入口：st.navigation 路由
_math_page.py                # 数学解题页：会话状态、主布局、Agent调用、UI渲染
agent.py                     # ReAct 循环 + 多模型路由 + 答案自纠错
tools.py                     # 五个工具（计算器 / 公式检索 / 步骤分解 / 画图 / 知识导图）+ 答案校验逻辑
mcp_server.py                # 把其中三个纯函数工具（计算器/公式检索/步骤分解）包装成标准 MCP Server
rag_formula_lookup.py        # formula_lookup 工具的语义检索实现
pages/2_知识库问答.py         # RAG 问答页
components/
  auth.py                    # 认证：注册/登录/token校验，对话历史+错题本持久化
  sidebar.py / ui_helpers.py # 侧边栏、全局 CSS（日间/暗色）
  rag_engine.py / rag_ingest.py  # RAGEngine、文档解析与扫描件OCR兜底
eval/run_verification_eval.py  # 量化"答案自纠错"效果的评测脚本
tests/                        # pytest：纯函数单测，不触网不调API
data/chroma_db/               # ChromaDB 本地持久化向量库
```

---

## 关键设计

- **手写 ReAct Agent，不用 LangChain**：`agent.py` 里一个显式 for 循环控制工具调用与终止，中间文字用 `_accumulated` 攒起来避免被下一轮覆盖。
- **答案自纠错**：每轮 `calculator` 结果收进"值池"，最终答案用 SymPy 做符号等价+数值容差比对，不一致触发一次重新核对（非无限重试），UI 显示验证状态。`eval/run_verification_eval.py` 用独立于被测代码的 SymPy oracle 跑 15 题 A/B 对比量化效果，也靠这个评测揪出过 `\boxed{}`/`\[...\]` 等格式的解析盲区。
- **对话历史压缩**：近 10 轮保留原文，更早的压缩成一条摘要 system 消息，零额外 LLM 调用。
- **五工具架构**：`calculator`（SymPy，白名单正则+黑名单拦截注入，独立进程池 15 秒超时防挂死）、`formula_lookup`（本地 embedding 语义检索）、`step_decomposer`（解题路线图）、`plot_function`（函数画图）、`draw_mindmap`（知识导图）。其中前三个不依赖 Streamlit session state，另外单独封装成了 `mcp_server.py`，可被 Claude Code / Claude Desktop 等任意 MCP host 直接调用；后两个要往页面里塞图/导图数据，暂不适合搬进通用 MCP 调用。
- **自定义认证**：不用 Supabase SDK，直接调 REST；PBKDF2-SHA256 密码哈希；登录失败锁定持久化在数据库（不是 session state，防绕过）。已知权衡：应用层邮箱过滤做隔离，未上 Supabase Auth 做真正的行级 RLS。
- **RAG 检索链路**：句子边界切分优先于硬切、多编码兼容、ChromaDB 按用户隔离（早期版本没做，见下）、扫描件走独立 OCR 调用（不复用带"数学助教"系统提示词的 solve()）。
- **单一供应商、原生多模态**：文字解题、拍题识别、语音转写、扫描件 OCR、向量嵌入五条链路全部走同一个 `GeminiFailoverClient`（`components/config.py`）——前四个用 `gemini-3.5-flash-lite` 的 `chat.completions.create`，图片走标准 `image_url` data URL，语音走 `input_audio` content part；嵌入用 `gemini-embedding-001` 的 `embeddings.create`，3072 维（原 `bge-m3` 是 1024 维，切换时知识库是空的，没有旧向量兼容问题）。一个 key、一个供应商，不用为每种输入类型或每个能力单独接一家。

---

## 值得一提的踩坑

- **RAG 知识库曾完全没有用户隔离**：不同账号会互相看到/检索到对方上传的私有文档，甚至能删除对方文件——交给独立 Agent 审查揪出，按 `user` 字段加隔离后修复，已用两个真实账号验证。
- **参考来源渲染存在存储型 XSS**，配合明文存储的登录 token 可被用于账号接管——同一轮审查发现，已加转义修复；同批还带出限流漏洞和一处遗留死代码。
- **登录锁定时区裸比较**：本地开发机（UTC+8）测试时锁定形同虚设，因为没显式带时区导致跟数据库 UTC 时间戳比较出错，VPS 恰好是 UTC 才没在生产暴露。
- **公式检索 RAG 静默退化成关键词匹配**：Ollama 反代 Host 头校验+缺失 embedding 模型两个问题叠加，功能实际失效了一个月却没有任何报错提示。
- **本地 Streamlit 版本与生产不一致**：本地 1.50 vs 生产 1.58，多个 `data-testid` 选择器在两版本间改名，"本地测试通过"曾是假象。
- **GitHub Actions 部署密钥迁移服务器后没同步更新**，静默失效一个多月，推到 main 的改动其实从未真正上线。
- 中文语义检索在早期把 LaTeX notation 一起塞进 embedding，被稀释到几乎搜不到——分离纯语义文本和展示层 notation 后修复，`demo_rag_comparison.py` 可复现对比效果。
- 暗色模式下 KaTeX 公式渲染成看不见的黑色（SVG 层级样式没被普通文字颜色规则覆盖到）；移动端原生侧边栏体验差，改成汉堡按钮+滑出遮罩层自实现。
- **两个项目共用一个 DeepSeek key，一个的日常调用能把另一个的额度耗光**：math-agent 和 finance-agent 共用同一个 DeepSeek 账号，math-agent 的日常调用把余额耗光，导致 finance-agent 新功能用不了。2026-08-26 做了五维度真实同题对比（金融判断/数学推理/代码/严格指令遵循/中文表达）后，把 math-agent 文字解题切到千问 qwen3.7-flash——千问全面不输，数学推理这一项还更强（DeepSeek 当时在预算内被截断算不完），价格不到 DeepSeek 一半，从根源上解决了资源争用。
- **SiliconFlow 账号欠费，拍题和语音同时下线**：2026-09-14 发现 SiliconFlow 余额不足，Qwen3-VL（拍题）和 SenseVoice（语音）两条链路同一时间失效，用户上传图片或录音会静默失败或收到"未配置"提示。没有再引入第三家专职视觉/语音供应商，而是全部并到已经在文字解题上验证过的 Gemini——它本身原生支持图片和音频输入，标准 `image_url`/`input_audio` content part 直接可用，一次改动同时补齐两条链路，不用再多维护一套供应商 key。向量嵌入当时评估觉得是数据迁移、没有一起切，但检查后发现知识库其实是空的（count=0），干脆一起切了，全项目彻底退出 SiliconFlow。
- **Gemini 流式工具调用丢失 thought_signature，两轮以上必炸**：真实复现——线上测「求导数：f(x) = x³+2x」，模型先调 `calculator`，第二轮请求直接 400 `INVALID_ARGUMENT`："Function call is missing a thought_signature"。根因是 `solve_stream` 把 tool_calls 从流式 delta 手动重建成新字典时只保留了 id/name/arguments，没保留 Gemini 专有的 `extra_content.google.thought_signature`——这个字段不在 OpenAI 协议里，openai SDK 的类型也没声明，只在 `model_extra` 里能挖到；不原样带回下一轮，Gemini 会因为"看不到上一次思考的签名"拒绝请求。顺带发现 Gemini 的 tool_call delta 一次性整个发完（不像 OpenAI 按 index 分片），`index` 恒为 `None`，用它当 accumulator 的 key 在真有并行工具调用时会把它们错误合并，改用 `id` 兜底区分。
- **Gemini embeddings 接口 batch 请求第一条 index 是 None**：跟上面 tool_call 的 index 是同一类坑——批量请求返回的 `data` 列表里，第一条 `index` 字段是 `None`，其余从 1 开始（0 去哪了不清楚，猜测是某层 JSON 序列化把值为 0 的字段当成"假值"吞掉了）。按 `index` 排序会直接因为 `None` 和 `int` 不能比较而报错；改成直接信任响应列表顺序等于输入顺序（这是 embeddings 接口的通行约定，也用真实批量请求验证过確实如此），不再排序。

---

## 技术栈

- **语言**：Python 3.11
- **框架**：Streamlit（多页面）
- **LLM**：Gemini gemini-3.5-flash-lite（文字/拍题/语音统一，原生多模态，2026-09-14 从千问+SiliconFlow 切换——SiliconFlow 账号欠费，Qwen3-VL 视觉与 SenseVoice 语音同时下线，索性三路都并到 Gemini 一家）
- **符号计算**：SymPy（ProcessPoolExecutor 隔离，15s 超时防挂死）
- **向量检索**：ChromaDB + Gemini `gemini-embedding-001`（3072 维）
- **数据库**：Supabase（PostgreSQL，直接 REST，对话历史/错题本/学习档案持久化）
- **测试/评测**：pytest（纯函数单测）+ 自建 eval 脚本（SymPy 独立 oracle 量化答案自纠错效果）
- **部署**：VPS 上 venv + systemd 直接跑（无 Docker），Nginx 反向代理 + Cloudflare CDN（Full Strict + Origin Certificate），GitHub Actions 在 push 到 main 后自动部署

---

MIT License

## Creators

- Heliotrope
- Claude Code
- Codex
