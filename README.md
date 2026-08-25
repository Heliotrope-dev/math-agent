# Math Agent

面向大学数学的 AI 学习平台，包含 AI 解题助手和 RAG 知识库问答两大功能模块。

线上地址：**[math.heliotrope.online](https://math.heliotrope.online)**

---

## 功能

**数学解题**
拍题识别（Qwen3-VL）、语音提问（SenseVoice）、SymPy 精确符号计算、苏格拉底式引导模式、覆盖大一到大三 13 门课程、真流式输出、自然语言生成知识导图、错题本（LLM 自动总结成可读条目）、学习档案（薄弱环节追踪+针对性练习）、答案自纠错（详见下方）、对话历史持久化。

**知识库问答（RAG）**
PDF/TXT/Markdown 上传去重、BAAI/bge-m3 向量化 + ChromaDB 检索、带来源引用的回答、多轮对话。

---

## 项目结构

```
app.py                       # 入口：st.navigation 路由
_math_page.py                # 数学解题页：会话状态、主布局、Agent调用、UI渲染
agent.py                     # ReAct 循环 + 多模型路由 + 答案自纠错
tools.py                     # 三个工具（计算器 / 公式检索 / 步骤分解）+ 答案校验逻辑
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
- **三工具架构**：`calculator`（SymPy，白名单正则+黑名单拦截注入，独立进程池 15 秒超时防挂死）、`formula_lookup`（本地 embedding 语义检索）、`step_decomposer`（解题路线图）。
- **自定义认证**：不用 Supabase SDK，直接调 REST；PBKDF2-SHA256 密码哈希；登录失败锁定持久化在数据库（不是 session state，防绕过）。已知权衡：应用层邮箱过滤做隔离，未上 Supabase Auth 做真正的行级 RLS。
- **RAG 检索链路**：句子边界切分优先于硬切、多编码兼容、ChromaDB 按用户隔离（早期版本没做，见下）、扫描件走独立 OCR 调用（不复用带"数学助教"系统提示词的 solve()）。

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

---

## 技术栈

- **语言**：Python 3.11
- **框架**：Streamlit（多页面）
- **LLM**：DeepSeek API（文字）/ SiliconFlow Qwen3-VL（视觉）/ SenseVoice（语音）
- **符号计算**：SymPy（ProcessPoolExecutor 隔离，15s 超时防挂死）
- **向量检索**：ChromaDB + BAAI/bge-m3（SiliconFlow Embeddings）
- **数据库**：Supabase（PostgreSQL，直接 REST，对话历史/错题本/学习档案持久化）
- **测试/评测**：pytest（纯函数单测）+ 自建 eval 脚本（SymPy 独立 oracle 量化答案自纠错效果）
- **部署**：VPS + Nginx 反向代理 + Cloudflare CDN（Full Strict + Origin Certificate）+ systemd，GitHub Actions 在 push 到 main 后自动部署

---

MIT License
