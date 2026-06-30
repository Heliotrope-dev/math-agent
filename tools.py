"""
tools.py — 工具定义 + 工具实现

三个工具：
  - calculator      基于 SymPy 的符号计算 / 数值计算
  - formula_lookup  数学公式查询库
  - step_decomposer 解题步骤规划
"""

import sympy as sp

# ─────────────────────────────────────────
# 1. Tool schemas（OpenAI / Ollama 格式）
#    与 Anthropic 格式的区别：
#      Anthropic: {"name": ..., "input_schema": {...}}
#      Ollama:    {"type": "function", "function": {"name": ..., "parameters": {...}}}
# ─────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": (
                "Perform symbolic or numeric math using SymPy. "
                "Supports: evaluate, solve (equations), differentiate, integrate, simplify, limit, definite_integral. "
                "Always use this for any computation — never calculate mentally."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": (
                            "Math expression or equation in Python/SymPy syntax. "
                            "Examples: '2*x**2 + 3*x - 5', 'sin(x) + cos(x)', 'x**2 - 4 = 0'"
                        ),
                    },
                    "operation": {
                        "type": "string",
                        "enum": ["evaluate", "solve", "differentiate", "integrate", "simplify", "limit", "definite_integral"],
                        "description": (
                            "evaluate — compute/simplify value; "
                            "solve — find roots or solutions; "
                            "differentiate — compute derivative; "
                            "integrate — compute indefinite integral; "
                            "simplify — algebraic simplification; "
                            "limit — compute limit (use variable='x->0' format for limit point); "
                            "definite_integral — compute definite integral (expression='f(x), a, b')"
                        ),
                    },
                    "variable": {
                        "type": "string",
                        "description": "Variable symbol for solve/differentiate/integrate. Default: 'x'.",
                    },
                },
                "required": ["expression", "operation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "formula_lookup",
            "description": (
                "Retrieve relevant formulas and identities for a math topic. "
                "Use free-form natural language — e.g. '二次方程求根公式', 'chain rule for derivatives', '复变函数留数定理'. "
                "Call this before solving to confirm which formulas apply."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Natural language description of the math concept or formula needed. "
                            "Examples: '导数乘积法则', 'Pythagorean theorem', '留数定理', 'binomial probability'"
                        ),
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "step_decomposer",
            "description": (
                "Analyze a math problem and produce a structured solution roadmap. "
                "Call this first to plan the approach before computing."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "problem_type": {
                        "type": "string",
                        "description": (
                            "Problem category, e.g. 'quadratic equation', 'definite integral', "
                            "'Pythagorean theorem', 'conditional probability'."
                        ),
                    },
                    "problem": {
                        "type": "string",
                        "description": "The original problem statement.",
                    },
                },
                "required": ["problem_type", "problem"],
            },
        },
    },
]


# ─────────────────────────────────────────
# 2. 公式数据库
# ─────────────────────────────────────────

_FORMULAS: dict[str, dict[str, str]] = {
    "algebra": {
        "Quadratic Formula":    "x = (-b ± √(b²-4ac)) / 2a  （ax² + bx + c = 0）",
        "Difference of Squares":"a² - b² = (a+b)(a-b)",
        "Perfect Square":       "(a±b)² = a² ± 2ab + b²",
        "Sum / Diff of Cubes":  "a³ ± b³ = (a±b)(a²∓ab+b²)",
        "Log Rules":            "log(ab)=loga+logb, log(a/b)=loga-logb, log(aⁿ)=n·loga",
        "Exponent Rules":       "aᵐ·aⁿ=aᵐ⁺ⁿ, (aᵐ)ⁿ=aᵐⁿ, a⁰=1, a⁻ⁿ=1/aⁿ",
    },
    "geometry": {
        "Pythagorean Theorem":  "c² = a² + b²  （c 为斜边）",
        "Circle":               "Area = πr²,  Circumference = 2πr",
        "Triangle Area":        "A = ½ × base × height",
        "Sphere":               "Volume = (4/3)πr³,  Surface = 4πr²",
        "Cylinder":             "Volume = πr²h,  Lateral Surface = 2πrh",
        "Distance Formula":     "d = √((x₂-x₁)² + (y₂-y₁)²)",
        "Midpoint Formula":     "M = ((x₁+x₂)/2, (y₁+y₂)/2)",
        "Heron's Formula":      "A = √(s(s-a)(s-b)(s-c)), s=(a+b+c)/2",
    },
    "calculus": {
        "Power Rule (deriv)":   "d/dx[xⁿ] = n·xⁿ⁻¹",
        "Product Rule":         "(fg)' = f'g + fg'",
        "Quotient Rule":        "(f/g)' = (f'g - fg') / g²",
        "Chain Rule":           "d/dx[f(g(x))] = f'(g(x)) · g'(x)",
        "Power Rule (integ)":   "∫xⁿ dx = xⁿ⁺¹/(n+1) + C  (n ≠ -1)",
        "Fundamental Theorem":  "∫[a,b] f(x)dx = F(b) - F(a), F' = f",
        "Common Derivatives":   "d/dx[sin x]=cos x, d/dx[eˣ]=eˣ, d/dx[ln x]=1/x",
        "L'Hôpital's Rule":     "lim f/g = lim f'/g'  (0/0 或 ∞/∞ 型)",
    },
    "trigonometry": {
        "Pythagorean Identity": "sin²x + cos²x = 1",
        "Angle Addition":       "sin(A+B)=sinA·cosB+cosA·sinB, cos(A+B)=cosA·cosB-sinA·sinB",
        "Double Angle":         "sin2x=2sinx·cosx, cos2x=cos²x-sin²x=1-2sin²x",
        "Law of Sines":         "a/sinA = b/sinB = c/sinC",
        "Law of Cosines":       "c² = a² + b² - 2ab·cosC",
        "SOH-CAH-TOA":          "sin=对/斜, cos=邻/斜, tan=对/邻",
    },
    "statistics": {
        "Mean / Variance":      "μ = Σxᵢ/n,  σ² = Σ(xᵢ-μ)²/n",
        "Binomial":             "P(X=k) = C(n,k)·pᵏ·(1-p)ⁿ⁻ᵏ",
        "Combinations":         "C(n,k) = n! / (k!(n-k)!)",
        "Bayes' Theorem":       "P(A|B) = P(B|A)·P(A) / P(B)",
        "Normal Distribution":  "f(x) = (1/σ√2π)·exp(-(x-μ)²/2σ²)",
    },
    "number_theory": {
        "Euclidean Algorithm":  "gcd(a,b) = gcd(b, a mod b)",
        "Fermat's Little Thm":  "aᵖ ≡ a (mod p)  对素数 p",
        "Euler's Theorem":      "aᵠ⁽ⁿ⁾ ≡ 1 (mod n)  当 gcd(a,n)=1",
        "Fundamental Thm Arith":"每个 >1 的整数可唯一分解为素数之积",
    },
    "complex_analysis": {
        "C-R Equations":          "∂u/∂x = ∂v/∂y,  ∂u/∂y = -∂v/∂x  （解析函数的充要条件）",
        "Cauchy Integral Formula": "f(z₀) = (1/2πi) ∮ f(z)/(z-z₀) dz",
        "Residue Theorem":         "∮ f(z)dz = 2πi · Σ Res[f, zₖ]",
        "First-Order Pole Residue":"Res[f, z₀] = lim(z→z₀) (z-z₀)·f(z)",
        "Laurent Series":          "f(z) = Σ aₙ(z-z₀)ⁿ，n从-∞到+∞",
        "Taylor Series (complex)": "f(z) = Σ f⁽ⁿ⁾(z₀)/n! · (z-z₀)ⁿ，收敛域内",
        "Liouville's Theorem":     "有界整函数必为常数",
        "Fundamental Thm (Alg)":   "非常数多项式在ℂ上至少有一个零点",
    },
    "numerical_analysis": {
        "Lagrange Interpolation":  "Lₙ(x) = Σ yₖ·∏(x-xⱼ)/(xₖ-xⱼ)，j≠k",
        "Newton Interpolation":    "N(x) = f[x₀] + f[x₀,x₁](x-x₀) + f[x₀,x₁,x₂](x-x₀)(x-x₁)+…",
        "Divided Difference":      "f[x₀,x₁] = (f(x₁)-f(x₀))/(x₁-x₀)，高阶类似",
        "Composite Trapezoidal":   "Tₙ = h/2·[f(x₀) + 2Σf(xₖ) + f(xₙ)]，h=(b-a)/n",
        "Composite Simpson":       "Sₙ = h/3·[f(x₀)+4f(x₁)+2f(x₂)+…+4f(xₙ₋₁)+f(xₙ)]",
        "Newton's Method":         "xₙ₊₁ = xₙ - f(xₙ)/f'(xₙ)，二阶收敛",
        "Gaussian Elimination":    "对增广矩阵[A|b]做行变换化为上三角，再回代",
        "Bisection Method":        "若f(a)·f(b)<0，取中点c=(a+b)/2，缩小区间",
        "Error Estimate (Trap)":   "|Eₙ| ≤ (b-a)³/(12n²) · max|f''(x)|",
        "Error Estimate (Simp)":   "|Eₙ| ≤ (b-a)⁵/(180n⁴) · max|f⁽⁴⁾(x)|",
    },
}

# 解题步骤模板（按题型匹配）
_STEP_TEMPLATES: dict[str, list[str]] = {
    "equation": [
        "1. 整理方程，移项化简",
        "2. 识别方程类型（线性 / 二次 / 高次 / 超越方程）",
        "3. 选择求解方法（因式分解 / 求根公式 / 换元 / 数值法）",
        "4. 求解未知量",
        "5. 代回原方程验证",
    ],
    "geometry": [
        "1. 画出几何图形，标注已知量",
        "2. 确定目标量",
        "3. 查找适用公式（面积 / 体积 / 距离 / 勾股定理等）",
        "4. 代入计算",
        "5. 检查单位，判断结果合理性",
    ],
    "calculus": [
        "1. 分析函数结构（复合 / 乘积 / 商式）",
        "2. 确定适用规则（链式法则 / 乘积法则 / 换元积分…）",
        "3. 逐步推导",
        "4. 化简结果",
        "5. 可选：代入特殊值验证",
    ],
    "statistics": [
        "1. 明确随机事件与样本空间",
        "2. 判断概率模型（古典 / 二项 / 正态…）",
        "3. 列出计算公式",
        "4. 代入数值计算",
        "5. 检查概率和是否为 1",
    ],
    "complex_analysis": [
        "1. 写出 f(z) = u(x,y) + iv(x,y)，分离实部虚部",
        "2. 验证柯西-黎曼方程（判断解析性）",
        "3. 确定奇点（极点 / 本性奇点）及其阶数",
        "4. 计算留数（一阶极点用极限公式；高阶用导数公式）",
        "5. 用留数定理或柯西积分公式计算围道积分",
    ],
    "numerical": [
        "1. 确定问题类型（插值 / 数值积分 / 方程求根 / 线性方程组）",
        "2. 选择算法（拉格朗日/牛顿插值；梯形/Simpson；牛顿迭代/二分；高斯消去）",
        "3. 建立差商表或节点函数值表",
        "4. 代入公式计算",
        "5. 估计误差，判断精度是否满足要求",
    ],
    "default": [
        "1. 识别题型，提取关键信息",
        "2. 选择数学方法",
        "3. 建立方程 / 模型",
        "4. 逐步求解",
        "5. 验证答案合理性",
    ],
}


# ─────────────────────────────────────────
# 3. 工具实现
# ─────────────────────────────────────────

def _run_calculator(expression: str, operation: str, variable: str = "x") -> str:
    """SymPy 符号计算引擎。"""
    # 预处理：将 ^ 替换为 **（用户常犯的写法）
    expr_str = expression.replace("^", "**")

    try:
        var = sp.Symbol(variable)

        if operation == "evaluate":
            expr = sp.sympify(expr_str)
            simplified = sp.simplify(expr)
            numeric = sp.N(simplified)
            return f"表达式：{expression}\n化简：{simplified}\n数值结果：{numeric}"

        elif operation == "solve":
            if "=" in expr_str:
                lhs, rhs = expr_str.split("=", 1)
                equation = sp.Eq(sp.sympify(lhs.strip()), sp.sympify(rhs.strip()))
            else:
                equation = sp.sympify(expr_str)
            solutions = sp.solve(equation, var)
            return f"方程：{expression}\n解：{solutions}"

        elif operation == "differentiate":
            expr = sp.sympify(expr_str)
            deriv = sp.simplify(sp.diff(expr, var))
            return f"f({variable}) = {expression}\nf'({variable}) = {deriv}"

        elif operation == "integrate":
            expr = sp.sympify(expr_str)
            result = sp.integrate(expr, var)
            return f"∫ ({expression}) d{variable} = {result} + C"

        elif operation == "simplify":
            expr = sp.sympify(expr_str)
            simplified = sp.simplify(expr)
            return f"原式：{expression}\n化简结果：{simplified}"

        elif operation == "limit":
            if "->" in variable:
                var_name, point_str = variable.split("->", 1)
                var_sym = sp.Symbol(var_name.strip())
                point = sp.sympify(point_str.strip())
            else:
                var_sym = sp.Symbol(variable)
                point = sp.sympify("0")
            expr = sp.sympify(expr_str)
            result = sp.limit(expr, var_sym, point)
            return f"lim({variable}) ({expression}) = {result}"

        elif operation == "definite_integral":
            parts = [p.strip() for p in expr_str.split(",")]
            if len(parts) == 3:
                expr = sp.sympify(parts[0])
                a, b = sp.sympify(parts[1]), sp.sympify(parts[2])
                result = sp.integrate(expr, (var, a, b))
                numeric = sp.N(result)
                return f"∫[{parts[1]},{parts[2]}] ({parts[0]}) d{variable} = {result} ≈ {numeric}"
            else:
                return "definite_integral 格式：'expression, lower, upper'，例如 'x**2, 0, 1'"

        else:
            return f"未知操作：{operation}"

    except Exception as exc:
        return (
            f"计算出错：{exc}\n"
            "提示：请使用 Python/SymPy 语法，例如用 x**2 代替 x²，用 * 表示乘法。"
        )


# RAG 懒加载索引（首次调用时构建，需要 Ollama 在线）
_rag_index: "list[dict] | None" = None
_rag_available: "bool | None" = None


def _get_rag_index():
    global _rag_index, _rag_available
    if _rag_available is False:
        return None
    if _rag_index is not None:
        return _rag_index
    try:
        from rag_formula_lookup import build_index
        _rag_index = build_index()
        _rag_available = True
        return _rag_index
    except Exception:
        _rag_available = False
        return None


# 关键词 → 主题映射（扩展版，用于 RAG 不可用时的 fallback）
_KW_MAP: dict[str, str] = {
    # algebra
    "algebra": "algebra", "代数": "algebra", "方程": "algebra", "二次": "algebra",
    "因式": "algebra", "对数": "algebra", "log": "algebra", "指数": "algebra",
    "求根": "algebra", "根号": "algebra", "展开": "algebra",
    # geometry
    "geometry": "geometry", "几何": "geometry", "面积": "geometry", "体积": "geometry",
    "距离": "geometry", "三角形": "geometry", "圆": "geometry", "勾股": "geometry",
    "球": "geometry", "圆柱": "geometry", "中点": "geometry",
    # calculus
    "calculus": "calculus", "微积分": "calculus", "导数": "calculus", "微分": "calculus",
    "积分": "calculus", "极限": "calculus", "limit": "calculus", "derivative": "calculus",
    "integral": "calculus", "洛必达": "calculus", "链式": "calculus", "乘积法则": "calculus",
    "商式": "calculus", "不定积分": "calculus", "定积分": "calculus", "微积分基本": "calculus",
    # trigonometry
    "trigonometry": "trigonometry", "三角函数": "trigonometry", "sin": "trigonometry",
    "cos": "trigonometry", "tan": "trigonometry", "正弦": "trigonometry", "余弦": "trigonometry",
    "倍角": "trigonometry", "和角": "trigonometry", "正切": "trigonometry",
    # statistics
    "statistics": "statistics", "统计": "statistics", "概率": "statistics",
    "probability": "statistics", "贝叶斯": "statistics", "正态": "statistics",
    "distribution": "statistics", "方差": "statistics", "二项": "statistics",
    "组合数": "statistics",
    # number theory
    "number_theory": "number_theory", "数论": "number_theory", "素数": "number_theory",
    "质数": "number_theory", "欧拉": "number_theory", "gcd": "number_theory",
    "费马": "number_theory", "最大公约数": "number_theory",
    # complex analysis
    "complex_analysis": "complex_analysis", "复变": "complex_analysis", "留数": "complex_analysis",
    "柯西": "complex_analysis", "解析函数": "complex_analysis", "cauchy": "complex_analysis",
    "residue": "complex_analysis", "洛朗": "complex_analysis", "极点": "complex_analysis",
    "围道": "complex_analysis",
    # numerical analysis
    "numerical_analysis": "numerical_analysis", "数值分析": "numerical_analysis",
    "插值": "numerical_analysis", "梯形": "numerical_analysis", "simpson": "numerical_analysis",
    "辛普森": "numerical_analysis", "牛顿迭代": "numerical_analysis", "二分法": "numerical_analysis",
    "高斯消去": "numerical_analysis", "拉格朗日": "numerical_analysis", "差商": "numerical_analysis",
}


def _run_formula_lookup(query: str) -> str:
    """从公式库中检索与 query 相关的公式（先 RAG，再关键词 fallback）。"""
    # ── RAG 路径（需要 Ollama 在线）──────────────────────────────
    index = _get_rag_index()
    if index:
        try:
            from rag_formula_lookup import retrieve
            hits = retrieve(query, index, top_k=5)
            lines = [f"📐 公式检索：{query}", "=" * 44]
            for d in hits:
                lines.append(f"\n• {d['name']}  [{d['topic']}]")
                formula_part = d["text"].split(": ", 1)[-1]
                lines.append(f"  {formula_part}")
            return "\n".join(lines)
        except Exception:
            pass

    # ── Fallback：关键词匹配（不需要 Ollama）──────────────────────
    query_lower = query.lower()
    matched_topics: list[str] = []
    for kw, topic in _KW_MAP.items():
        if kw in query_lower and topic not in matched_topics:
            matched_topics.append(topic)

    if not matched_topics:
        # 最后兜底：返回 algebra + calculus 基础公式
        matched_topics = ["algebra", "calculus"]

    lines = [f"📐 公式检索：{query}", "=" * 44]
    for topic in matched_topics:
        formulas = _FORMULAS.get(topic, {})
        lines.append(f"\n【{topic.upper()}】")
        for name, formula in formulas.items():
            lines.append(f"\n• {name}")
            lines.append(f"  {formula}")
    return "\n".join(lines)


def _run_step_decomposer(problem_type: str, problem: str) -> str:
    """根据题型生成结构化解题路线图。"""
    key = "default"
    pt_lower = problem_type.lower()

    if any(w in pt_lower for w in ["equation", "方程", "solve", "root"]):
        key = "equation"
    elif any(w in pt_lower for w in ["geometry", "几何", "area", "面积", "volume", "体积",
                                      "distance", "距离", "triangle", "circle", "圆"]):
        key = "geometry"
    elif any(w in pt_lower for w in ["calculus", "微积分", "derivative", "导数",
                                      "integral", "积分", "limit", "极限"]):
        key = "calculus"
    elif any(w in pt_lower for w in ["statistics", "统计", "probability", "概率", "distribution"]):
        key = "statistics"
    elif any(w in pt_lower for w in ["complex", "复变", "residue", "留数", "cauchy", "analytic", "解析"]):
        key = "complex_analysis"
    elif any(w in pt_lower for w in ["numerical", "数值", "interpolat", "插值", "trapezoidal", "梯形", "bisection"]):
        key = "numerical"

    steps = "\n".join(_STEP_TEMPLATES[key])
    return (
        f"🔍 题型分析\n"
        f"类型：{problem_type}\n"
        f"题目：{problem}\n\n"
        f"📋 解题路线：\n{steps}"
    )


# ─────────────────────────────────────────
# 4. 统一分发入口（供 agent.py 调用）
# ─────────────────────────────────────────

def execute_tool(tool_name: str, tool_input: dict) -> str:
    """将 Claude 的 tool_use 请求分发到对应实现。"""
    if tool_name == "calculator":
        return _run_calculator(
            expression=tool_input["expression"],
            operation=tool_input["operation"],
            variable=tool_input.get("variable", "x"),
        )
    elif tool_name == "formula_lookup":
        return _run_formula_lookup(query=tool_input.get("query") or tool_input.get("topic", ""))
    elif tool_name == "step_decomposer":
        return _run_step_decomposer(
            problem_type=tool_input["problem_type"],
            problem=tool_input["problem"],
        )
    else:
        return f"未知工具：{tool_name}"
