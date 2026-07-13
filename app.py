"""
app.py — 路由入口

Launch:
  streamlit run app.py
"""
import streamlit as st
from components.ui_helpers import _BASE_CSS, _DARK_CSS

st.set_page_config(
    page_title="Math Solver",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 初始化 dark_mode（最早一次，后续 page 脚本里重复 init 无副作用）
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

# CSS 在导航之前注入，前端永远不会看到未样式化的内容
st.markdown(
    _BASE_CSS + (_DARK_CSS if st.session_state.dark_mode else ""),
    unsafe_allow_html=True,
)

# position="hidden" 彻底关闭 Streamlit 自动侧边栏导航，前端层面不渲染
pg = st.navigation(
    [
        st.Page("_math_page.py", title="数学解题", default=True),
        st.Page("pages/2_知识库问答.py", title="知识库问答"),
    ],
    position="hidden",
)
pg.run()
