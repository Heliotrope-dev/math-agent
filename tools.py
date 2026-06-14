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
                "Supports: evaluate, solve (equations), differentiate, integrate, simplify. "
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
                        "enum": ["evaluate", "solve", "differentiate", "integrate", "simplify"],
                        "description": (
                            "evaluate — compute/simplify value; "
                            "solve — find roots or solutions; "
                            "differentiate — compute derivative; "
                            "integrate — compute indefinite integral; "
                            "simplify — algebraic simplification"
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
                "Call this before solving to confirm which formulas apply."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "enum": [
                            "algebra",
                            "geometry",
                            "calculus",
                            "trigonometry",
                            "statistics",
                            "number_theory",
                        ],
                        "description": "Math topic to look up.",
                    }
                },
                "required": ["topic"],
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

        else:
            return f"未知操作：{operation}"

    except Exception as exc:
        return (
            f"计算出错：{exc}\n"
            "提示：请使用 Python/SymPy 语法，例如用 x**2 代替 x²，用 * 表示乘法。"
        )


def _run_formula_lookup(topic: str) -> str:
    """从公式库中检索指定主题的公式。"""
    formulas = _FORMULAS.get(topic, {})
    if not formulas:
        return f"未找到主题 '{topic}' 的公式。"

    lines = [f"📐 {topic.upper()} 常用公式", "=" * 44]
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
        return _run_formula_lookup(topic=tool_input["topic"])
    elif tool_name == "step_decomposer":
        return _run_step_decomposer(
            problem_type=tool_input["problem_type"],
            problem=tool_input["problem"],
        )
    else:
        return f"未知工具：{tool_name}"
