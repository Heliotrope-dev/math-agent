"""
app.py — 路由入口

Launch:
  streamlit run app.py
"""
import streamlit as st
from components.ui_helpers import _BASE_CSS

st.set_page_config(
    page_title="Math Solver",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS 在导航之前注入，前端永远不会看到未样式化的内容
st.markdown(_BASE_CSS, unsafe_allow_html=True)

# position="hidden" 彻底关闭 Streamlit 自动侧边栏导航，前端层面不渲染
pg = st.navigation(
    [
        st.Page("_math_page.py", title="数学解题", default=True),
        st.Page("pages/2_知识库问答.py", title="知识库问答"),
    ],
    position="hidden",
)
pg.run()
