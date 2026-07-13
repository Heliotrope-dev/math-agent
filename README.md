# Math Agent

面向大学数学的 AI 学习平台，包含 AI 解题助手和 RAG 知识库问答两大功能模块。

线上地址：**[math.heliotrope.online](https://math.heliotrope.online)**

---

## 功能

### 数学解题
- **拍题识别**：拍照或上传图片，Qwen3-VL 识别题目并逐步解答
- **语音提问**：说出题目，SenseVoice 转文字后直接求解
- **符号计算**：SymPy 精确求解微积分、线性代数、方程，无浮点误差
- **引导模式**：苏格拉底式教学，AI 提问引导而非直接给答案
- **课程入口**：覆盖大一到大三 13 门数学课，按知识点系统学习
- **真流式输出**：逐字显示解题过程，非等全部生成完再一次性渲染；答案校验不一致时以可见的"重新核对"提示追加纠正，不是悄悄改答案
- **知识导图**：自然语言描述知识点结构，生成卡片式 HTML 知识框架（非 LaTeX/图片，纯 Unicode 数学符号，主题切换/刷新页面都能正常显示）
- **错题本**：解题后一键收藏，LLM 自动总结成"[学科] 知识点：完整题目"（不是存用户当时的简短指代，比如拍题时说的"第六题"，刷新后自己都看不懂当时问的是什么），支持随机复习，侧边栏按学科自动分组
- **学习档案**：记录访问过的知识点，标记薄弱环节（访问 ≥2 次），一键生成针对性练习题（只出题不解答）
- **答案自纠错**：SymPy 交叉验证最终答案和工具计算结果，不一致自动触发一次重新核对，UI 显示验证状态（详见下方设计细节）
- **对话持久化**：历史消息 + 图片存 Supabase，刷新页面不丢失；老用户再次打开显示"欢迎回来"个性化提示（上次学到哪、待复习错题数），新用户仍是示例题引导

### 知识库问答（RAG）
- **文档上传**：支持 PDF / TXT / Markdown，同名文件自动去重
- **语义检索**：BAAI/bge-m3 向量化，ChromaDB 余弦相似度检索
- **带引用回答**：DeepSeek 基于检索结果生成答案，附文件名 + 页码来源
- **多轮对话**：保留最近 5 轮历史，上下文连贯

---

## 项目结构

```
app.py                      # 入口：st.navigation 路由，只做这一件事
_math_page.py                # 数学解题页：会话状态、主布局、Agent调用、UI渲染
agent.py                    # ReAct 循环 + 多模型路由 + 答案自纠错
tools.py                    # 三个工具（计算器 / 公式检索 / 步骤分解）+ 答案校验逻辑
pages/
  2_知识库问答.py             # RAG 问答页（Streamlit 多页面）
components/
  auth.py                   # 认证：注册 / 登录（含失败锁定）/ token 校验 /
                             #   对话历史 + 错题本持久化（Supabase REST）
  sidebar.py                # 侧边栏全部 UI
  config.py                 # 常量 + 密钥读取
  ui_helpers.py             # 全局 CSS（日间 / 暗色两套）
  rag_engine.py             # RAGEngine：向量化 / ChromaDB / DeepSeek 生成
  rag_ingest.py             # 文档解析、句子边界切分、扫描件OCR兜底
eval/
  run_verification_eval.py  # 量化"答案自纠错"效果的评测脚本（见下文）
tests/                       # pytest：纯函数单测，不触网不调API
data/
  chroma_db/                # ChromaDB 本地持久化向量库
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

### 3. 答案自纠错（SymPy 交叉验证 + 一次重新核对）

LLM 常见失误不是"算错"，是"算对了但抄错最终答案"——`calculator` 工具明明返回了正确结果，模型总结的时候手滑写错/漏负号/漏代入具体数值。这个机制专门抓这一类。

**怎么做的**：一轮对话里每次 `calculator` 调用的结果都收集进一个"值池"（不是只看最后一次——很多题模型会把多个解分开单独算）。模型给出最终答案（`$$...$$` 或 `\[...\]` 包裹）后，用 SymPy 把答案里的每个值和值池逐一做符号等价 + 数值容差比对；对不上就把"这跟你算出的结果不一致，请重新核对"追加一轮，最多补一次（不是无限重试）：

```python
if _calc_results and not _verify_attempted:
    parsed = _extract_final_answer(final)
    if parsed and not answer_supported_by_calcs(parsed, _calc_results):
        _verify_attempted = True
        self.last_verification = "corrected"
        messages.append(msg)
        messages.append({"role": "user", "content": f"检查一下：你最终写的答案是「{parsed}」，但这跟你用 calculator 算出的结果对不上……"})
        continue
    elif parsed:
        self.last_verification = "verified"
return final
```

`self.last_verification`（`None` 无法验证 / `"verified"` 核对一致 / `"corrected"` 发现偏差已修正）暴露给 UI，气泡下面会显示对应提示，纠错不再是黑箱。

**量化效果**：`eval/run_verification_eval.py` 用 SymPy 独立算 15 道题的标准答案（跟被测代码完全无关的第二套计算路径，避免"自己出题自己判题"），对每道题分别跑"验证开启/关闭"两个变体，比较最终答案是否正确。跑这个脚本时顺带抓到了几个真实的解析盲区并修复：模型有时用 LaTeX 的 `\[...\]` 而不是约定的 `$$...$$`、多解答案写成 `\boxed{x=2 \text{或} x=-2}` 塞进一个框、导数答案带 `f'(x)=` 函数记号前缀——这几种格式之前会让校验逻辑直接判定"无法验证"，不是真的验证失败。

```
python3 eval/run_verification_eval.py
```

---

### 4. 三工具架构

| 工具 | 实现 | 作用 |
|---|---|---|
| `calculator` | SymPy | 精确符号计算：求导、积分、极限、解方程、行列式 |
| `formula_lookup` | 字符串匹配 + 相似度 | 从 60+ 公式库中检索相关定理 |
| `step_decomposer` | LLM 推理 | 题型识别，生成解题路线图 |

`calculator` 调用 SymPy 而非让模型心算，避免数值错误。表达式先过一层白名单正则 + 危险关键字黑名单（阻断 `sympify` 内部 `eval` 的注入路径），再丢进独立的 `ProcessPoolExecutor` 子进程执行，15 秒超时强制杀死——sympy 某些输入会导致计算挂死，只有整个进程被杀才能真正回收。

工具生成的图像（matplotlib）存入线程本地队列 `threading.local()`，避免多用户请求在同一进程里串用：

```python
_tls = threading.local()

def _pending_images() -> list:
    if not hasattr(_tls, "images"):
        _tls.images = []
    return _tls.images
```

---

### 5. 自定义认证，直接调 Supabase REST

没有用 Supabase Python SDK，所有操作都是 `requests.post/get/patch/delete` 直接打 REST API。减少一个依赖，错误栈也更干净。

密码哈希用 PBKDF2-SHA256（Python 标准库 `hashlib`）：

```python
def _hash_pw(pw: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 260000)
    return salt + ":" + h.hex()
```

登录 token 写入 `st.query_params` 和 `localStorage` 双份，关闭浏览器后重新打开也能自动恢复会话（7 天有效期）。

失败次数/锁定时间持久化在 `users` 表（`failed_attempts`/`locked_until` 列，连续 5 次错误锁 60 秒），不是存在 `st.session_state` 里——那样换个隐身窗口就能绕开，起不到防暴力破解的作用。这里踩过一个真实的时区坑：第一版直接用不带时区的 `datetime.now()` 跟数据库时间比，在非 UTC 的机器上测试直接失效（本地时间被当 UTC 存进数据库，一比"未来 60 秒"就成了"8 小时前"）；VPS 本身是 UTC 所以生产环境测不出这个问题，改成显式 `datetime.now(timezone.utc)`，不依赖宿主机时区。

**已知的安全权衡**：鉴权是自己写的邮箱密码逻辑，不是 Supabase Auth，所以 Supabase 完全不知道"是谁在发请求"——RLS 策略目前是 `using(true) with check(true))`（放行 anon key 的全部读写），真正的行级隔离靠应用层的 `email=eq.X` 过滤实现，不是数据库层强制的。这是有意识的权衡（开发速度 vs. 纵深防御），anon key 只存在 VPS 环境变量里、不进 git 仓库；下一步计划迁移到 Supabase Auth 做真正的按用户 RLS。

---

### 6. Streamlit 主题注入

Streamlit 不支持运行时切换主题，`config.toml` 只在启动时生效。暗色模式的做法：

用 `streamlit.components.v1.html()` 向父页面 `<head>` 注入 `<style>` 标签，同时挂一个 `MutationObserver`，每次 Streamlit rerender 后重新执行覆盖：

```javascript
var s = doc.createElement('style');
s.id = '_dm_override_css';
doc.head.appendChild(s);

function apply() {
    s.textContent = CSS;
    // 对顽固元素用 inline setProperty，优先级高于所有外部样式
    var inp = doc.querySelector('[data-testid="stChatInput"]');
    if (inp) inp.style.setProperty('background', '#16162A', 'important');
}

new MutationObserver(function(muts) {
    if (muts.some(m => m.addedNodes.length > 0))
        setTimeout(apply, 30);
}).observe(doc.body, { childList: true, subtree: true });
```

`_cv1.html()` 渲染在 iframe 里，通过 `window.parent.document` 操作父页面 DOM，绕过 Streamlit 的组件 CSS 作用域。

---

### 7. RAG 知识库：不依赖框架，每步显式实现

知识库问答没有使用 LangChain / LlamaIndex，检索和生成的每一步都是显式代码，方便调试和定制。

**切分策略**：按句子边界（`。！？!?\n`）优先断句，单句超长时再按窗口硬切，默认 500 字 / 50 字重叠。相比按字符数盲切，保留了更完整的语义单元。

**编码兼容**：TXT/Markdown 文件依次尝试 utf-8 → gb18030 → latin-1，兼容中文文档常见的 GBK 编码问题。

**向量化**：BAAI/bge-m3（SiliconFlow），按批次（16 条）请求，对接口返回乱序的情况按 `index` 字段排序后再拼接。

**向量库**：ChromaDB 本地持久化，余弦相似度，同名文档先删后写实现去重覆盖，不会出现重复 chunk 干扰检索。

**惰性客户端**：`RAGEngine` 被 `@st.cache_resource` 长期缓存，DeepSeek client 在 `__init__` 里不创建，改为每次使用时对比当前 key 是否变化，变了则重建，保证 key 配置后即生效。

**扫描件 OCR 兜底**：图片型 PDF（没有可提取文字层）会逐页渲染成图片，走视觉模型识别文字。这里特意不用 `MathAgent.solve()`，直接裸调 API——`solve()` 固定带着"你是数学助教"系统提示词，塞一张非数学的扫描件（比如简历）进去，模型会回复"未找到数学题"，完全无视"识别文字"这个指令。`MathAgent.solve()` 只适合"数学解题"这一个场景，其它视觉/文本任务（OCR、摘要总结）都要绕开它走独立的 API 调用。

---

### 8. KaTeX 替代内置 MathJax

Streamlit 内置 MathJax 在流式输出时会和 markdown 解析冲突，导致公式闪烁或渲染失败。改成手动加载 KaTeX：动态插入 `<script>` 标签，加载完成后挂 `MutationObserver`，每次 DOM 变化后 debounce 250ms 重新 render。同样通过 `window.parent.document` 注入到父页面，公式渲染在整个应用范围内生效。

---

## 踩过的坑

开发过程中遇到的几个有代表性的问题，记录在这里。

**函数图像里中文全变方块，换了字体后又变形**

`plot_function` 用 matplotlib 画图，中文字体配置踩了两层坑（思维导图工具
`draw_mindmap` 早期也是同一套 matplotlib 方案，后来因为另一个问题——见下面
"知识导图用 HTML 渲染，LaTeX 语法会原样显示成文字"——整体换成了 HTML/CSS 卡片
布局，不再有字体问题，这里的字体坑现在只影响 `plot_function`）：
1. VPS 上装的是 Google Noto 那种多语言合集字体（一个 `.ttc` 文件里塞了 SC/TC/JP/KR
   好几种字形），但 matplotlib 自己扫描字体文件时只认出了"Noto Sans CJK JP"这一个
   名字，配置里写的字体名全对不上，实际用的是 matplotlib 自带的 DejaVu Sans——
   不含任何中文字形，所有中文都画成方块。
2. 改成显式指定"Noto Sans CJK JP"后中文能显示了，但反馈"字有点变形，一眼就能
   看出来不对"——Han unification 导致的：中日双方汉字共享同一个 Unicode 码位，
   但具体笔画在两种印刷传统里不完全一样，用日文字形集画中文，母语读者一眼能
   看出不自然。

最终方案：`apt install fonts-wqy-microhei`（WenQuanYi 微米黑，专门的简体中文
字体，不是多语言合集，没有字形选错的问题）。**装完字体后还有一步容易漏**：
matplotlib 会把扫描到的字体列表缓存在 `~/.cache/matplotlib/fontlist-*.json`，
新装的字体不会自动生效，得删掉这个缓存文件让它重新扫描。VPS 迁移/重建时这个
apt 包和清缓存这一步都要记得配置。

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

**验证徽标挂了很久没人发现**

答案校验的 UI 提示曾经靠 `contextlib.redirect_stdout(buf)` 抓 `solve()` 执行期间的 stdout 输出去正则解析——但 `solve()` 内部的日志走的是 `logging` 模块（默认输出到 stderr），从没 `print()` 过东西到 stdout，`buf` 实际永远是空字符串。徽标函数因此恒返回 `None`，在生产环境从没真正显示过，但因为它"不报错、只是不显示"，一直没被发现。改成让 `solve()` 把验证结果记到实例属性上，UI 直接读，不再靠猜内容格式的正则表达式。**教训：靠字符串正则解析另一段代码的输出去判断状态，比直接让那段代码把状态显式传出来更脆弱，出问题时往往还是沉默失败，不会报错。**

**Streamlit testid 不能凭记忆/教程写**

CSS 选择器里用的 `data-testid` 在 Streamlit 版本之间会改名（`stChatInputContainer` 实际上从没存在过，真实的是 `stChatInput`；`stPills` 实际是 `stButtonGroup`）。拿不准就去 `venv/lib/*/site-packages/streamlit/static/static/js/*.js` 里 grep 真实字符串，不要凭旧教程或者上一个版本的记忆写选择器。

**同一个系统提示词坑踩了三次**

`MathAgent.solve()` 固定带着"你是数学助教"系统提示词，且非首轮输入会被强制拼上"请解题："前缀。这套设计对"解题"这个场景是对的，但先后在三个不相关的场景里被误用去做别的事：通用图片 OCR（把简历图片当数学题，回复"未找到"）、把简短对话总结成错题本条目（被"请解题："带偏，输出变成分步解题格式而不是一行摘要）。每次都是详细读了报错/异常输出才定位到根因。**教训：新功能要调用 agent 时先问一句"这是不是解题"，不是的话直接绕开 `solve()`，裸调 OpenAI 客户端。**

**答案自纠错的解析盲区，靠真实评测数据集才挖出来**

自己读代码审查时以为这套校验逻辑没问题（单元测试也全过），真正跑 `eval/run_verification_eval.py` 对着 15 道题、30 次真实 API 调用做 A/B 对比时才发现：模型经常用 LaTeX 的 `\[...\]` 显示公式定界符而不是约定的 `$$...$$`（提取正则只认后者）、把多解答案写成 `\boxed{x=2 \text{或} x=-2}`（`\text{}` 宏没拆包、也没按"或"字拆分成两个解）、导数答案带 `f'(x)=` 函数记号前缀（前缀正则只认单变量 `x=`）。这几种格式都是模型本身答案正确、纯粹是提取/解析层跟不上模型的真实输出多样性，静态审查代码逻辑很难想到要覆盖这些格式，跑真实数据才暴露出来。**教训：校验/评测类功能，光看代码逻辑没问题不够，要拿真实模型输出（不是自己拍脑袋编的样例）跑一遍。**

**登录锁定的时区裸比较，本地测试立刻炸穿**

把失败次数/锁定时间存进数据库后，第一版用不带时区的 `datetime.now()` 直接跟 Supabase 返回的 `timestamptz` 字符串比较——在本地开发机（UTC+8）上测，"未来60秒"的锁定时间写进去之后，读出来跟本地时钟一比直接变成"8小时前"，锁定形同虚设，账号连错5次立刻又能登录。VPS 本身时区是 UTC，所以这个 bug 在生产环境完全测不出来。改成显式 `datetime.now(timezone.utc)`，不依赖宿主机时区设置。**教训：任何要跟数据库时间戳比较的代码，"我的机器测着是对的"不代表在所有时区下都对，涉及时间比较必须显式带时区。**

**知识导图用 HTML 渲染，LaTeX 语法会原样显示成文字**

`draw_mindmap` 从 matplotlib 改成 HTML/CSS 卡片布局后，模型仍然习惯性地在
分支文字里写 `\frac{2}{\frac{1}{a}+\frac{1}{b}}`、`\leq` 这类 LaTeX 命令——
但这段内容是通过 `unsafe_allow_html=True` 直接注入的 HTML 字符串，不会经过
Streamlit 原生的 KaTeX 自动渲染管线，LaTeX 命令原样显示成文字。没有去改渲染
管线本身（风险更高），而是反过来约束源头：把工具的 schema 描述改成明确要求
"纯 Unicode 数学符号（√、∞、≤、≥、∮、∑），禁止 LaTeX 命令语法"，模型照着新
描述生成的内容就不会再触发这个问题。

**JS 语法错误会让整段 `<script>` "看似部署了、实则从没跑起来过"**

`components.v1.html()` 渲染在独立 iframe 里，脚本外层包着 `try{...}catch(e){}`，
本以为出错也只是被静默吞掉。但排查一处"自动登录/息屏后自动重连"完全不生效的
问题时发现：脚本里有一个多余的 `}`，提前把外层 IIFE 闭合，导致后面缺一个配对
的 `)`——这是**解析期**语法错误，不是运行期异常，整个 `<script>` 标签直接编译
失败，`try{}catch(e){}` 本身也在失败范围内，从来没执行过一行代码。用
`node --check` 把 `_math_page.py` 里所有 `<script>...</script>` 块整段抠出来
单独过一遍语法检查，才批量揪出这个和另一个类似的问题。**教训：iframe 里的
`try{}catch(e){}` 只能兜运行期异常，兜不住语法错误；组件脚本改完最好用
`node --check` 过一遍语法，不要只靠人眼数括号。**

**内联样式一旦用 `!important` 设过，后面同名 CSS 规则改了也没用**

暗色模式下汉堡按钮样式最初是 JS 判断当前主题后用
`el.style.setProperty('background', ..., 'important')` 设置的。这个内联
`!important` 一旦生效，会永久盖过后面任何外部样式表的同名 `!important`
规则——哪怕之后把 CSS 改对了、把判断条件改对了，只要这行内联样式先跑过一次，
再怎么改 CSS 都不会生效，因为浏览器压根不会拿它跟内联样式比。而且这段 JS 只
在组件 iframe 首次挂载时执行一次（用 `if (doc.getElementById(...)) return`
判重），Streamlit 每次 rerun 都会重新挂载这个 iframe，判重逻辑导致它连"首次
挂载"的执行时机都经常错过。改成完全交给 CSS：深色规则的源码顺序排在浅色规则
后面，同选择器同优先级下源码靠后天然生效，不需要 JS 探测主题、也不会被残留的
内联样式卡死。**教训：能用 CSS 解决的主题切换/样式覆盖，尽量别用 JS 设
`!important` 内联样式兜底——一旦设过就很难再被任何后续 CSS 修正。**

**"文字被裁剪"很多时候其实是"被别的元素挡住了"**

排查侧边栏邮箱、分组标题显示不全的问题时，最初沿用了项目里一贯的思路——
以为又是容器高度锁死、内容被裁掉。但实际起一份跟生产环境版本一致的本地
Streamlit 服务、登录后量了真实 DOM 的 `getBoundingClientRect()` 才发现：
文字自己的盒子高度是完整的，是下面挨得太近的按钮的白底圆角框直接盖住了
文字下半截，视觉上跟"裁剪"很像但机制完全不同——`overflow:hidden`类的修复
思路对这种情况完全无效。**教训：视觉上"看起来像被裁剪"不代表就是裁剪，
条件允许时应该直接测量真实元素的边界矩形而不是照搬上一次类似问题的诊断。**

**本地 Streamlit 版本没对齐生产，测出来的"正常"是假象**

本地 `pip install streamlit` 装出来的是 1.50.0，因为系统自带的是 Python
3.9，而 Streamlit 1.51+ 要求 3.10+，pip 会默默选择"能装的最新版"而不是报错
提醒版本被限制了。VPS 上实际跑的是 1.58.0——版本差出 8 个小版本，`st.chat_
input` 的 `accept_audio` 参数、多个 `data-testid` 命名（`element-container`
→`stElementContainer`、`stChatInputInstructions` 整个消失）在两个版本之间
都变了，本地测试"看起来没问题"其实只是没跑到那条代码路径就报错退出了。
用 Homebrew 装了一个独立的 Python 3.12，配出跟生产完全一致的 1.58.0 venv
后，才测出好几个此前一直没被发现的失效选择器。**教训：本地测试环境的库
版本要跟生产对齐，尤其是像 Streamlit 这种内部 DOM 结构会随版本变化、又没有
公开稳定 API 保证的框架——版本不对齐时"测试通过"不代表任何事。**

---

## 技术栈

- **语言**：Python 3.11
- **框架**：Streamlit（多页面）
- **LLM**：DeepSeek API（文字）/ SiliconFlow Qwen3-VL（视觉）/ SenseVoice（语音）
- **符号计算**：SymPy（ProcessPoolExecutor 隔离，15s 超时防挂死）
- **向量检索**：ChromaDB + BAAI/bge-m3（SiliconFlow Embeddings）
- **数据库**：Supabase（PostgreSQL，直接 REST，对话历史/错题本/学习档案持久化）
- **测试/评测**：pytest（纯函数单测）+ 自建 eval 脚本（SymPy 独立 oracle 量化答案自纠错效果）
- **部署**：VPS + Nginx 反向代理 + Cloudflare CDN（Full Strict + Origin Certificate）+ systemd

---

MIT License
