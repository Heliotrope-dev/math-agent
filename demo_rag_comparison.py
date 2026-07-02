"""
demo_rag_comparison.py — 面试演示用：复现"公式 notation 混入 embedding 导致中文检索失效"的 bug 与修复

跑两套索引：
  混合版（bug 复现）：embedding 文本 = 公式名 + 中文描述 + 完整 notation 混在一起
  分离版（实际修复）：embedding 文本 = 纯中文语义描述（rag_formula_lookup.py 现在的做法）
用同一个中文自然语言题目去检索，对比 Top-5 排名和相似度分数。
"""

from rag_formula_lookup import _DESCRIPTIONS, cosine_sim, embed
from tools import _FORMULAS

QUERIES = [
    "两个函数相乘之后再求导，应该怎么算？",   # 应命中 Product Rule
    "已知三角形三条边的长度，怎么求面积？",     # 应命中 Heron's Formula
]


def build_index(mixed: bool) -> list[dict]:
    docs = []
    for topic, formulas in _FORMULAS.items():
        for name, formula in formulas.items():
            desc = _DESCRIPTIONS.get(name, "")
            if mixed:
                embed_text = f"{name}（{desc}）: {formula}"  # bug版：notation混进embedding
            else:
                embed_text = f"{name}：{desc}"               # 修复版：纯中文语义描述
            docs.append({"topic": topic, "name": name, "vector": embed(embed_text)})
    return docs


def retrieve(query: str, docs: list[dict], top_k: int = 5):
    q_vec = embed(query)
    scored = [(cosine_sim(q_vec, d["vector"]), d["name"]) for d in docs]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]


def main():
    print("正在分别构建【混合版】和【分离版】两套向量索引...\n")
    mixed_index = build_index(mixed=True)
    clean_index = build_index(mixed=False)

    for query in QUERIES:
        print("=" * 60)
        print(f"题目（纯中文自然语言，不带 topic）：{query}\n")

        print("❌ 混合版（公式notation混入embedding）Top-5：")
        for score, name in retrieve(query, mixed_index):
            print(f"   {score:.4f}  {name}")

        print("\n✅ 分离版（纯中文语义描述embedding，现在的实现）Top-5：")
        for score, name in retrieve(query, clean_index):
            print(f"   {score:.4f}  {name}")
        print()


if __name__ == "__main__":
    main()
