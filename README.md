---
title: Math Solver Agent
emoji: 🧮
colorFrom: purple
colorTo: indigo
sdk: docker
pinned: false
license: mit
---

# 🧮 Math Agent — AI 大学数学助教

> 面向大学数学学习的全栈 AI 应用。用户系统 + 多模态解题 + 学习追踪，独立设计并实现。

**线上地址**：Hugging Face Spaces（Docker 部署）  
**技术栈**：Python · Streamlit · Supabase · OpenAI-compatible API · SymPy · KaTeX

---

## 项目概览

这是一个面向大学数学学习场景的 AI 助教应用，覆盖大一到大三共 13 门数学课程。核心功能包括：

- 多工具协作解题（ReAct Agentic Loop）
- 拍题 OCR / 语音输入 / 文件上传
- 用户注册登录 + 学习数据持久化
- 错题本、学习档案、知识点标签
- 苏格拉底引导模式（不直接给答案）
- 微信风格 UI，支持深色模式和移动端

---

## 技术亮点

### 1. 自实现 ReAct Agentic Loop（无框架依赖）

**不使用 LangChain / LlamaIndex**，在 `agent.py` 中手动实现完整的 Agentic Loop：

```
while iteration < MAX_ITER:
    response = LLM(messages, tools)
    if finish_reason == "tool_calls":
        执行工具 → 追加结果到 messages → 继续循环
    else:
        返回最终答案
```

设计细节：
- `finish_reason == "tool_calls"` 时收集同轮输出文字（防止模型中间思考被丢弃）
- 工具调用 JSON 解析降级：先 `json.loads`，失败则 `raw_decode` 处理尾部多余内容
- 迭代超限后追加 user 消息强制模型收束，而不是直接截断
- 支持 `on_tool_call` 回调，实时推送工具状态到 UI

### 2. 多模型动态切换

根据输入类型自动选择模型：

| 场景 | 模型 | API |
|------|------|-----|
| 文字解题（默认） | DeepSeek Chat | DeepSeek API |
| 拍题 OCR + 解答 | Qwen3-VL-30B | SiliconFlow |
| 用户手动切换 | Qwen3-VL-8B/32B 等 | SiliconFlow |

视觉模式下图片先压缩（PIL → JPEG 80%，最长边≤768px）再 base64 编码发送，减少 token 消耗。

### 3. 用户系统（无三方 Auth SDK）

**直接用 Supabase REST API + Python requests 实现**，不依赖 `supabase` 包：

- 密码 PBKDF2-SHA256（100k 次迭代 + 随机 salt），兼容旧版 SHA-256 自动迁移
- 7 天免登录 Token（服务端 `sessions` 表）+ URL query param 持久化
- localStorage + sessionStorage 双重保险：关闭浏览器后自动恢复登录，同时防止过期 Token 触发无限 reload 死循环
- 登录频率限制：5 次错误锁定 60 秒

```python
# 核心 token 验证流程
def _validate_token(token: str):
    rows = _sb_get("sessions", {
        "token": f"eq.{token}",
        "expires_at": f"gt.{datetime.now().isoformat()}",
        "select": "email"
    })
    return rows[0]["email"] if rows else None
```

### 4. 数学公式渲染

Streamlit 内置 MathJax 对复杂 LaTeX（`aligned` 环境、中文混排）渲染不稳定，通过 `_cv1.html()` 向父 frame 注入 **KaTeX 0.16.11**：

- `auto-render` 扩展自动处理 `$$...$$` / `$...$` / `\[...\]` / `\(...\)`
- `MutationObserver` 监听 Streamlit 每次重渲染后自动重新 render
- 深色模式下额外覆盖 KaTeX + MathJax 3（`mjx-container`）颜色变量

### 5. 学习数据追踪

```
user_topics 表：email, course, topic, visit_count, last_visited
wrong_book  表：email, question, saved_at, image_b64
sessions    表：token, email, expires_at
users       表：email, password_hash
```

- 每次提问知识点 tag 自动写入 `user_topics`，`visit_count >= 2` 标记为薄弱点
- 侧边栏「学习档案」展示最近学习记录 + 薄弱点快捷入口
- 错题本支持图片题目（存 base64）

### 6. 三工具 + SymPy 精确计算

```
step_decomposer  → 题型分析，规划解题路线
formula_lookup   → 公式库检索（8 主题 / 60+ 条）
calculator       → SymPy 符号引擎
                    solve / differentiate / integrate
                    limit / definite_integral / evaluate
```

SymPy 符号计算避免浮点误差，`limit` / `definite_integral` 原生支持。

### 7. 移动端适配

- 侧边栏改为 `position: fixed` 覆盖层 + CSS `transform` 滑入动画
- JS 注入 ☰ 汉堡按钮，点击展开，遮罩点击关闭
- 深色模式 CSS 通过 `_cv1.html()` 写入父 frame `<head>`，绕过 Streamlit React 重渲染覆盖

---

## 架构图

```
浏览器
  │
  ├─ Streamlit (app.py)                        ← 微信风格 UI / 登录 / 路由
  │    ├─ 用户系统 ─── Supabase REST API       ← users / sessions / wrong_book / user_topics
  │    └─ MathAgent (agent.py)                 ← ReAct Agentic Loop
  │         ├─ DeepSeek API  (文字解题)
  │         ├─ SiliconFlow   (视觉 / VL 模型)
  │         └─ Tools (tools.py)
  │               ├─ step_decomposer
  │               ├─ formula_lookup
  │               └─ calculator ── SymPy
  │
  └─ KaTeX (CDN, JS 注入)                      ← 数学公式渲染
```

---

## 核心文件

| 文件 | 说明 |
|------|------|
| `app.py` | Streamlit UI 主文件，含登录、聊天、学习追踪、CSS/JS 注入 |
| `agent.py` | ReAct Agentic Loop，多模型路由，视觉/引导/解题三模式 |
| `tools.py` | 工具定义（JSON Schema）+ SymPy 计算引擎 + 公式库 |
| `rag_formula_lookup.py` | RAG 版公式检索（nomic-embed-text + 余弦相似度） |
| `mcp_server.py` | FastMCP 包装，可注册进 Claude Code / Claude Desktop |
| `Dockerfile` | HuggingFace Spaces Docker 部署配置 |

---

## 设计决策

**为什么不用 LangChain？**  
手动实现 Agentic Loop 代码量不大（< 100 行核心逻辑），但能完全控制工具调用行为、错误处理、中间文字收集等细节；框架反而增加不可预期的行为和调试难度。

**为什么不用 Supabase Python SDK？**  
SDK 在 Streamlit Cloud 环境偶有连接池问题，直接用 `requests` 封装 REST 接口更轻量可控，认证逻辑也更透明。

**为什么注入 KaTeX 而不依赖 Streamlit 内置 MathJax？**  
Streamlit 的 MathJax 对含 `&=` 对齐的多行公式（如 `aligned` 环境）在特定场景下不稳定；KaTeX 渲染速度更快，且通过 MutationObserver 可以在每次 Streamlit 重渲染后自动补充渲染。

---

*Built with Claude Code · 2026*
