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
- **错题本**：解题后一键收藏，随时随机复习
- **学习档案**：记录访问过的知识点，标记薄弱环节

---

## 技术栈

**后端 / 推理**
- Python 3.11 + Streamlit
- 自实现 ReAct Agent（不依赖 LangChain），手写工具调用循环
- DeepSeek API（文字解题）+ SiliconFlow（视觉/语音）
- SymPy 符号引擎 + 60+ 公式的 RAG 检索

**认证 / 数据**
- Supabase REST API 直接调用（不用 SDK），PBKDF2-SHA256 密码哈希
- 7 天免登录 token，localStorage + URL 双重持久化

**前端 / UI**
- KaTeX 数学渲染（通过 MutationObserver 注入，绕过 Streamlit 组件作用域）
- 暗色模式：JS 动态注入 CSS + `setProperty` 强制覆盖 Streamlit 主题
- 手机端：自定义汉堡菜单 + 侧边栏滑出覆盖层，隐藏 Streamlit 原生 UI

**部署**
- VPS（Ubuntu）+ Nginx 反向代理 + systemd 进程管理
- GitHub Actions 自动部署到生产

---

## 项目结构

```
app.py                  # 入口：路由、会话管理、主布局
agent.py                # ReAct 循环 + 多模型路由
tools.py                # 三个工具：计算器 / 公式检索 / 步骤分解
components/
  auth.py               # 认证：注册 / 登录 / token / 错题本
  sidebar.py            # 侧边栏全部内容
  config.py             # 常量 + 密钥读取
  ui_helpers.py         # 全局 CSS（日间 / 暗色）
```

---

## 几个有意思的实现细节

**为什么不用 LangChain**：自己写 ReAct 循环大概 80 行，调试起来每一步都看得清楚。用框架反而多了一层黑箱。

**Streamlit 暗色模式的坑**：Streamlit 不支持运行时切换主题，每次 rerun 都会重新应用 config.toml 的颜色。解决方案是用 `streamlit.components.v1` 向父页面 `<head>` 注入 `<style>` 标签，同时用 MutationObserver 监听 Streamlit rerender，用 JS `setProperty('important')` 强制覆盖 inline 样式。

**KaTeX 替代 MathJax**：Streamlit 内置 MathJax 在流式输出时会跟 markdown 解析冲突，改成手动加载 KaTeX 并在每次 DOM 变化后重新 render，公式显示稳定很多。

**Supabase 不用 SDK**：直接 `requests.post()` 调 REST API，减少一个依赖，错误也更容易定位。

---

MIT License
