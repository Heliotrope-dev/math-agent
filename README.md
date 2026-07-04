# Math Agent

面向大学数学的 AI 解题助手，支持文字、拍题、语音三种提问方式，自带学习记录和错题本。

线上地址：**[math.heliotrope.online](https://math.heliotrope.online)**

---

## 功能

- **拍题识别**：拍照或上传图片，Qwen3-VL 识别题目并逐步解答
- **语音提问**：说出题目，SenseVoice 转文字后直接求解
- **符号计算**：SymPy 精确求解微积分、线性代数、方程，无浮点误差
- **引导模式**：苏格拉底式教学，AI 提问引导而非直接给答案
- **课程入口**：覆盖大一到大三 13 门数学课，按知识点系统学习
- **错题本**：解题后一键收藏，支持随机复习
- **学习档案**：记录访问过的知识点，标记薄弱环节（访问 ≥2 次）

---

## 项目结构

```
app.py                  # 入口：路由、会话管理、主布局
agent.py                # ReAct 循环 + 多模型路由
tools.py                # 三个工具：计算器 / 公式检索 / 步骤分解
components/
  auth.py               # 认证：注册 / 登录 / token 校验 / 错题本持久化
  sidebar.py            # 侧边栏全部 UI
  config.py             # 常量 + 密钥读取
  ui_helpers.py         # 全局 CSS（日间 / 暗色两套）
```

---

## 设计细节

### 1. 手写 ReAct Agent，不用 LangChain

Agent 核心是 `agent.py` 里一个 `for` 循环，每轮调用一次 LLM，检查 `finish_reason` 决定继续还是返回：

```python
for iteration in range(self.max_iterations):
    response = self.client.chat.completions.create(
        model=self.model, tools=tools, messages=messages
    )
    finish_reason = response.choices[0].finish_reason

    if finish_reason != "tool_calls":
        # 最终回复，拼上之前轮次积累的文本
        final = msg.content or "（无输出）"
        if _accumulated:
            final = "\n\n".join(_accumulated) + "\n\n" + final
        return final

    # 工具调用轮：执行工具，结果写回 messages，继续循环
    if msg.content:
        _accumulated.append(msg.content)   # 保存中间文字，避免被下轮覆盖
    for tc in msg.tool_calls:
        result = execute_tool(tc.function.name, args)
        messages.append({"role": "tool", "content": result})
```

`_accumulated` 列表解决了一个实际问题：模型在工具调用轮有时会输出中间推导文字，直接进下一轮就丢了。把它攒起来拼到最终回复前面，解题过程才完整。

工具调用失败时有降级：捕获 400/502 错误后关掉 `tools` 参数，退化成普通对话继续跑，而不是直接报错中断。

---

### 2. 对话历史压缩

长对话会撑爆 context window，但直接截断会让模型忘记前文。`_compress_history()` 的做法：

- 保留最近 10 轮原文（`_trim_history`，从后往前数完整的 user+assistant 对）
- 更早的轮次提取摘要，压缩成一条 `system` 消息插在最前面

```python
summary = "（以下是早前对话的摘要，供参考）\n" + "\n".join(lines[-40:])
return [{"role": "system", "content": summary[:2000]}] + recent
```

不需要额外一次 LLM 调用，纯字符串截取，延迟为零。

---

### 3. 三工具架构

| 工具 | 实现 | 作用 |
|---|---|---|
| `calculator` | SymPy | 精确符号计算：求导、积分、极限、解方程、行列式 |
| `formula_lookup` | 字符串匹配 + 相似度 | 从 60+ 公式库中检索相关定理 |
| `step_decomposer` | LLM 推理 | 题型识别，生成解题路线图 |

`calculator` 调用 SymPy 而非让模型心算，避免数值错误。工具生成的图像（matplotlib）存入线程本地队列 `threading.local()`，避免多用户请求在同一进程里串用：

```python
_tls = threading.local()

def _pending_images() -> list:
    if not hasattr(_tls, "images"):
        _tls.images = []
    return _tls.images
```

---

### 4. 自定义认证，直接调 Supabase REST

没有用 Supabase Python SDK，所有操作都是 `requests.post/get/patch/delete` 直接打 REST API。减少一个依赖，错误栈也更干净。

密码哈希用 PBKDF2-SHA256（Python 标准库 `hashlib`）：

```python
def _hash_pw(pw: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 260000)
    return salt + ":" + h.hex()
```

登录 token 写入 `st.query_params` 和 `localStorage` 双份，关闭浏览器后重新打开也能自动恢复会话（7 天有效期）。

---

### 5. Streamlit 主题注入

Streamlit 不支持运行时切换主题，`config.toml` 只在启动时生效。暗色模式的做法：

用 `streamlit.components.v1.html()` 向父页面 `<head>` 注入 `<style>` 标签，同时挂一个 `MutationObserver`，每次 Streamlit rerender 后重新执行覆盖：

```javascript
var s = doc.createElement('style');
s.id = '_dm_override_css';
doc.head.appendChild(s);

function apply() {
    s.textContent = CSS;
    // 对顽固元素用 inline setProperty，优先级高于所有外部样式
    var inp = doc.querySelector('[data-testid="stChatInputContainer"]');
    if (inp) inp.style.setProperty('background', '#16162A', 'important');
}

new MutationObserver(function(muts) {
    if (muts.some(m => m.addedNodes.length > 0))
        setTimeout(apply, 30);
}).observe(doc.body, { childList: true, subtree: true });
```

`_cv1.html()` 渲染在 iframe 里，通过 `window.parent.document` 操作父页面 DOM，绕过 Streamlit 的组件 CSS 作用域。

---

### 6. KaTeX 替代内置 MathJax

Streamlit 内置 MathJax 在流式输出时会和 markdown 解析冲突，导致公式闪烁或渲染失败。改成手动加载 KaTeX：动态插入 `<script>` 标签，加载完成后挂 `MutationObserver`，每次 DOM 变化后 debounce 250ms 重新 render。同样通过 `window.parent.document` 注入到父页面，公式渲染在整个应用范围内生效。

---

## 踩过的坑

开发过程中遇到的几个有代表性的问题，记录在这里。

**httpx.Client 共享连接池导致请求冻结**

`httpx.Client` 最初放在模块级别，所有 `MathAgent` 实例共享同一个连接池。在并发场景下一个请求阻塞会拖住其余所有请求。改成每个 `MathAgent.__init__` 里独立创建自己的 client 实例解决。

**过期 token 触发无限刷新循环**

登录 token 同时存在 `localStorage` 和 URL query params 两个地方。7 天过期后，校验失败只清了其中一处，另一处继续触发自动登录，页面陷入无限 reload。修复：校验失败后同步清除两处，并在 JS 端加 `sessionStorage` 标志位防止重复触发。

**语音输入返回空输出**

语音识别的结果通常很短（几个字），触发了模型路由里"短文本用轻量视觉模型"的逻辑，但视觉模型在没有图片时返回空内容。修复：路由逻辑改为只在有图片时才切换视觉模型，纯文字一律走 DeepSeek。

**KaTeX 公式在 Streamlit rerender 后消失**

Streamlit 每次交互都用 React virtual-DOM diff 替换容器内容，KaTeX 渲染的节点跟着被清掉。用 `MutationObserver` 监听 `<body>` 变化，每次 DOM 更新后 debounce 250ms 重新调用 `renderMathInElement`，公式稳定渲染。

**nginx 反代端口配错**

部署后语音识别一直 pending，以为是 SiliconFlow API 问题，排查了半天。最后发现 nginx 配的是 8501，Streamlit 实际跑在 8502，请求根本没到应用层。

**Fable 5 子 Agent 在 VPS 上直接改文件**

OpenClaw 的 Fable 5 子 Agent 会直接 SSH 到 VPS 修改文件但不提交，导致 `git pull` 每次报本地有未提交改动而失败，服务停留在旧版本。每次需要手动 `git checkout -- . && git pull` 恢复。长期方案是把 GitHub Actions 部署脚本改成 `git reset --hard origin/main`。

---

## 技术栈

- **语言**：Python 3.11
- **框架**：Streamlit
- **LLM**：DeepSeek API（文字）/ SiliconFlow Qwen3-VL（视觉）/ SenseVoice（语音）
- **符号计算**：SymPy
- **数据库**：Supabase（PostgreSQL，直接 REST）
- **部署**：VPS + Nginx 反向代理 + systemd + GitHub Actions 自动部署

---

MIT License
