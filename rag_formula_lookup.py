"""
rag_formula_lookup.py — formula_lookup 的 RAG 版本

tools.py 里的 _run_formula_lookup 是关键字查字典：必须先猜中 topic 这个 enum
（algebra / calculus / ...）才能拿到对应公式，题目原文用不上。

这版用 RAG 替换"查字典"：
  1. 把 _FORMULAS 拆成一条条 (name, formula) 文档块（chunking）
  2. 用本地 Ollama embedding 模型把每条文档和用户的题目都向量化（embedding）
  3. 余弦相似度检索 top-k 最相关的公式（retrieval）
  4. 把检索结果拼进 prompt，交给本地 qwen3.5:9b 生成针对该题的解答（generation）

可以直接用任意自然语言题目描述查询，不需要知道 topic 是什么——
这是和原版 dict 查表最大的区别。
"""

import math
import os

import requests

from tools import _FORMULAS

_base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_URL = _base + "/api"
EMBED_MODEL = "nomic-embed-text"
GEN_MODEL = os.environ.get("MATH_AGENT_MODEL", "qwen3.5:9b")

# 调试发现：nomic-embed-text 对"中文 query vs 英文公式 notation"跨语言匹配很弱
# （英文 query 测试时 Product Rule 能排进前 5，中文 query 完全检索不到）。
# 给每条公式加一句中文语义描述，作为跨语言检索的语义锚点。
_DESCRIPTIONS: dict[str, str] = {
    "Quadratic Formula": "解二次方程 ax²+bx+c=0 的求根公式",
    "Difference of Squares": "两数平方差的因式分解",
    "Perfect Square": "完全平方公式展开",
    "Sum / Diff of Cubes": "两数立方和或立方差的因式分解",
    "Log Rules": "对数运算的乘除幂运算法则",
    "Exponent Rules": "指数幂运算法则",
    "Pythagorean Theorem": "直角三角形斜边与两直角边的关系",
    "Circle": "圆的面积和周长公式",
    "Triangle Area": "三角形面积计算公式",
    "Sphere": "球的体积和表面积公式",
    "Cylinder": "圆柱体的体积和侧面积公式",
    "Distance Formula": "平面上两点间距离的计算公式",
    "Midpoint Formula": "平面上两点连线中点坐标公式",
    "Heron's Formula": "已知三边长求三角形面积的公式",
    "Power Rule (deriv)": "幂函数求导法则",
    "Product Rule": "两个函数相乘之后求导的法则",
    "Quotient Rule": "两个函数相除之后求导的法则",
    "Chain Rule": "复合函数求导的链式法则",
    "Power Rule (integ)": "幂函数的不定积分公式",
    "Fundamental Theorem": "定积分与原函数的关系，微积分基本定理",
    "Common Derivatives": "常见函数（正弦、指数、对数）的导数",
    "L'Hôpital's Rule": "求 0/0 或 ∞/∞ 型极限的洛必达法则",
    "Pythagorean Identity": "正弦和余弦的平方和恒等式",
    "Angle Addition": "两角之和的正弦余弦展开公式",
    "Double Angle": "二倍角的正弦余弦公式",
    "Law of Sines": "三角形边长与角的正弦比例关系",
    "Law of Cosines": "三角形边长与角的余弦关系，推广的勾股定理",
    "SOH-CAH-TOA": "直角三角形中正弦余弦正切的定义",
    "Mean / Variance": "数据的平均值与方差计算",
    "Binomial": "二项分布的概率计算公式",
    "Combinations": "组合数的计算公式",
    "Bayes' Theorem": "条件概率的贝叶斯公式",
    "Normal Distribution": "正态分布的概率密度函数",
    "Euclidean Algorithm": "求最大公约数的欧几里得算法",
    "Fermat's Little Thm": "素数模运算下的费马小定理",
    "Euler's Theorem": "欧拉定理，费马小定理的推广",
    "Fundamental Thm Arith": "算术基本定理，整数的素因数分解唯一性",
    # complex analysis
    "C-R Equations":           "柯西黎曼方程，判断复变函数解析性的充要条件",
    "Cauchy Integral Formula":  "柯西积分公式，用围道积分求解析函数值",
    "Residue Theorem":          "留数定理，利用极点留数计算围道积分",
    "First-Order Pole Residue": "一阶极点留数的计算方法",
    "Laurent Series":           "复变函数在环形域上的洛朗级数展开",
    "Taylor Series (complex)":  "复变函数在圆形收敛域内的泰勒展开",
    "Liouville's Theorem":      "刘维尔定理，有界整函数为常数",
    "Fundamental Thm (Alg)":    "代数基本定理，非常数多项式在复数域有根",
    # numerical analysis
    "Lagrange Interpolation":   "拉格朗日插值多项式构造公式",
    "Newton Interpolation":     "牛顿插值多项式，基于差商构造",
    "Divided Difference":       "差商的定义和递推计算",
    "Composite Trapezoidal":    "复化梯形公式，数值积分方法",
    "Composite Simpson":        "复化辛普森公式，数值积分精度更高",
    "Newton's Method":          "牛顿迭代法求方程近似根",
    "Gaussian Elimination":     "高斯消去法求解线性方程组",
    "Bisection Method":         "二分法求方程根",
    "Error Estimate (Trap)":    "复化梯形公式的截断误差估计",
    "Error Estimate (Simp)":    "复化辛普森公式的截断误差估计",
}


def embed(text: str) -> list[float]:
    resp = requests.post(f"{OLLAMA_URL}/embeddings", json={"model": EMBED_MODEL, "prompt": text}, timeout=10)
    resp.raise_for_status()
    return resp.json()["embedding"]


def cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


def build_index() -> list[dict]:
    """把公式库拆成文档块，并逐条 embedding（chunking + embedding）。"""
    docs = []
    for topic, formulas in _FORMULAS.items():
        for name, formula in formulas.items():
            desc = _DESCRIPTIONS.get(name, "")
            # embed_text 只放中文语义描述，用于检索匹配；
            # text 是连同公式 notation 的完整内容，用于返回/拼进生成 prompt。
            # 调试发现：把公式 notation 混进 embedding 文本会被大量 unicode 符号稀释掉中文语义信号，
            # 导致检索效果显著变差 —— 检索文本和返回内容分开存，是更标准的 RAG 做法。
            embed_text = f"{name}：{desc}"
            text = f"{name}（{desc}）: {formula}"
            docs.append({
                "topic": topic,
                "name": name,
                "text": text,
                "vector": embed(embed_text),
            })
    return docs


def retrieve(query: str, docs: list[dict], top_k: int = 3) -> list[dict]:
    """检索：query embedding 和每条文档做余弦相似度，取 top_k。"""
    q_vec = embed(query)
    scored = [(cosine_sim(q_vec, d["vector"]), d) for d in docs]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in scored[:top_k]]


def generate(query: str, retrieved: list[dict]) -> str:
    """生成：把检索到的公式拼进 prompt，交给本地 qwen 模型作答。"""
    context = "\n".join(f"- {d['name']}: {d['text'].split(': ', 1)[1]}" for d in retrieved)
    prompt = (
        f"已知以下公式可能与题目相关：\n{context}\n\n"
        f"题目：{query}\n\n"
        "请基于上面提供的公式，给出解题思路（不需要算出最终数值，只说明用哪个公式、怎么用）。"
    )
    resp = requests.post(
        f"{OLLAMA_URL}/generate",
        json={"model": GEN_MODEL, "prompt": prompt, "stream": False},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["response"]


if __name__ == "__main__":
    print("正在为公式库建立向量索引...")
    index = build_index()
    print(f"索引完成，共 {len(index)} 条公式。\n")

    query = "两个函数相乘之后再求导，应该怎么算？"
    print(f"题目（注意：没有提供 topic，是纯自然语言）：{query}\n")

    hits = retrieve(query, index, top_k=3)
    print("检索到最相关的公式：")
    for h in hits:
        print(f"  [{h['topic']}] {h['name']}")

    print("\n模型生成的解题思路：\n")
    print(generate(query, hits))
