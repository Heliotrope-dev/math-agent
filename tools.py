"""
tools.py — Tool definitions + implementations

Three tools:
  - calculator      SymPy-based symbolic/numeric computation
  - formula_lookup  Math formula reference library
  - step_decomposer Problem solving step planner
"""

import io
import re as _re
import base64
import logging
import sympy as sp
from concurrent.futures import ProcessPoolExecutor, TimeoutError as _FutTimeout

_log = logging.getLogger(__name__)

# ── 图像队列（per-thread，防止多用户共享进程时串用）─────────────────────────────
import threading as _threading
_tls = _threading.local()

def _pending_images() -> list:
    if not hasattr(_tls, "images"):
        _tls.images = []
    return _tls.images

def get_and_clear_pending_images() -> list[dict]:
    imgs = list(_pending_images())
    _pending_images().clear()
    return imgs


def compress_image(image_bytes: bytes, max_size: int = 800, quality: int = 85) -> bytes:
    """压缩图片以减少 token 与带宽；失败时降级返回原图而不中断流程。"""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        if max(w, h) > max_size:
            ratio = max_size / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return buf.getvalue()
    except Exception as e:
        _log.warning("图片压缩失败，使用原图：%s", e)
        return image_bytes

def _save_figure(fig, caption: str = "") -> str:
    try:
        import matplotlib.pyplot as plt
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode()
        _pending_images().append({"b64": b64, "caption": caption})
        return f"[图像已生成：{caption}]"
    except Exception as e:
        return f"[图像生成失败：{e}]"

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
            "name": "plot_function",
            "description": (
                "生成函数图像并展示给用户。讲解函数性质、展示曲线形态、比较多个函数时调用。"
                "适用：正弦/余弦/指数/对数/多项式/泰勒近似对比等一切需要可视化的情形。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expressions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Python/SymPy 语法的表达式列表，如 ['sin(x)', 'x - x**3/6']。支持多条曲线同时展示。",
                    },
                    "xmin": {"type": "number", "description": "x 轴最小值，默认 -10"},
                    "xmax": {"type": "number", "description": "x 轴最大值，默认 10"},
                    "ymin": {"type": "number", "description": "y 轴最小值（可选，不填自动）"},
                    "ymax": {"type": "number", "description": "y 轴最大值（可选，不填自动）"},
                    "title": {"type": "string", "description": "图像标题"},
                    "labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "每条曲线的图例名称（可选，与 expressions 一一对应）",
                    },
                },
                "required": ["expressions"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draw_mindmap",
            "description": (
                "生成知识点思维导图。讲解一个知识点的体系结构、概念关系、重要定理分类时调用。"
                "适用：知识框架梳理、知识点总结、概念对比分类。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "思维导图中心主题，如「泰勒展开」"},
                    "branches": {
                        "type": "array",
                        "description": "主要分支，每个分支包含 label（名称）和 children（子节点列表）",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string"},
                                "children": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["label"],
                        },
                    },
                },
                "required": ["title", "branches"],
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

# ── SymPy 安全沙箱 ────────────────────────────────────────────────────────────
# sympify() 内部走 eval；白名单过滤阻断注入路径
_SAFE_EXPR = _re.compile(r"^[0-9a-zA-Z\+\-\*/\^().,:=\s'<>\[\]!*$]+$")
_BANNED = ("__", "import", "lambda", "eval", "exec", "open", "os.", "sys.")

def _check_expr_safe(expr: str) -> "str | None":
    if len(expr) > 500:
        return "表达式过长（>500字符），请拆分后重试"
    low = expr.lower()
    if not _SAFE_EXPR.match(expr) or any(b in low for b in _BANNED):
        return "表达式包含不允许的字符或关键字，只支持纯数学表达式"
    return None

_CALC_POOL = ProcessPoolExecutor(max_workers=2)
_CALC_TIMEOUT = 15  # 秒


def _preprocess_expr(expression: str) -> str:
    """把用户手写的 ^ 幂运算符号替换成 Python/SymPy 的 **。"""
    return _re.sub(r'(?<=[\d)a-zA-Z])\^(?=[\d(\-a-zA-Z])', '**', expression)


def _calc_impl(expression: str, operation: str, variable: str) -> str:
    """在子进程中执行 SymPy 计算——只有进程能真正 kill 挂死的 SymPy。"""
    import sympy as sp
    expr_str = _preprocess_expr(expression)
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


def _run_calculator(expression: str, operation: str, variable: str = "x") -> str:
    """SymPy 符号计算引擎（带安全检查 + 进程超时）。"""
    err = _check_expr_safe(expression)
    if err:
        return f"计算被拒绝：{err}"
    try:
        fut = _CALC_POOL.submit(_calc_impl, expression, operation, variable)
        return fut.result(timeout=_CALC_TIMEOUT)
    except _FutTimeout:
        return (f"计算超时（>{_CALC_TIMEOUT}s），表达式可能过于复杂，"
                "请简化后重试，或改用数值方法")
    except Exception as exc:
        return (
            f"计算出错：{exc}\n"
            "提示：请使用 Python/SymPy 语法，例如用 x**2 代替 x²，用 * 表示乘法。"
        )


# ── 答案验证：判断模型最终答案与 calculator 的计算结果是否数学等价 ────────────
# 用于抓一类常见的 LLM 失误——工具算对了，但抄到最终答案时抄错/漏负号/约分错。
from sympy.parsing.sympy_parser import (
    parse_expr as _parse_expr,
    standard_transformations as _std_transforms,
    implicit_multiplication_application as _implicit_mul,
)
_LOOSE_TRANSFORMS = _std_transforms + (_implicit_mul,)

_LATEX_STRIP = _re.compile(r'\$+|\\\(|\\\)|\\\[|\\\]|\\left|\\right|\\,|\\;|\\quad|\\qquad|\\!')
_LATEX_TIMES = _re.compile(r'\\(?:times|cdot)')  # \times / \cdot → 乘号，不是能直接删掉的装饰符
_ANSWER_PREFIX = _re.compile(r'^(答案|结果|即|解得?)\s*[:：]?\s*')
_BRACED_POW = _re.compile(r'\^\{([^{}]+)\}')  # x^{3} → x**(3)，普通^正则要求指数紧跟数字/字母，遇到花括号包裹的指数会漏
_BOXED_RE = _re.compile(r'\\boxed\s*\{(.*)\}\s*$', _re.DOTALL)
_FRAC_RE = _re.compile(r'\\[cd]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}')
_FRAC_SHORT_RE = _re.compile(r'\\[cd]?frac\s*(\w)\s*(\w)')  # \frac12 简写（无花括号，各一个字符）
_TEXT_MACRO_RE = _re.compile(r'\\text\s*\{([^{}]*)\}')  # \text{或} 这类注释性文字宏，拆包留内容


def _normalize_latex(s: str) -> str:
    """把常见的 LaTeX 数学宏转成 sympy 能读的形式：\\boxed{} 拆包，\\frac{a}{b} / \\frac12 → (a)/(b)，
    \\text{...} 拆包留文字内容（模型常用 \\boxed{x=2 \\text{或} x=-2} 这种写法把多解并成一个框）。"""
    s = s.strip()
    m = _BOXED_RE.match(s)
    if m:
        s = m.group(1).strip()
    s = _TEXT_MACRO_RE.sub(r'\1', s)
    s = _LATEX_TIMES.sub('*', s)  # \times/\cdot 是乘号，不能直接删掉（会变成两个数字挨在一起）
    s = _BRACED_POW.sub(r'**(\1)', s)
    prev = None
    while prev != s:  # \frac 可能嵌套（如分数里还有分数），反复替换到不再变化
        prev = s
        s = _FRAC_RE.sub(r'(\1)/(\2)', s)
        s = _FRAC_SHORT_RE.sub(r'(\1)/(\2)', s)
    return s


def _clean_answer_text(s: str) -> str:
    """去除 LaTeX 宏/包裹符号、"答案："前缀，剩下待拆分/sympify 的核心内容。"""
    s = _normalize_latex(s)
    s = _LATEX_STRIP.sub('', s).strip()
    s = _ANSWER_PREFIX.sub('', s).strip()
    return s.strip()


def _extract_calc_value(tool_result: str) -> str:
    """从 calculator 格式化输出（如 "解：[2, -2]" / "数值结果：3.0"）里抠出真正的结果片段。

    取最后一行、最后一个 分隔符（：/:/=）之后的内容；'≈' 之后的近似值丢弃，优先用精确值；
    不定积分的任意常数 "+ C" 去掉（注意：这只是文本层面处理，不代表已严谨判断反导函数等价）。
    """
    lines = [ln for ln in tool_result.strip().splitlines() if ln.strip()]
    if not lines:
        return tool_result.strip()
    last_line = lines[-1]
    if '≈' in last_line:
        last_line = last_line.split('≈', 1)[0]
    sep_idx = max((last_line.rfind(sep) for sep in ('：', ':', '=')), default=-1)
    if sep_idx != -1:
        last_line = last_line[sep_idx + 1:]
    last_line = _re.sub(r'\+\s*[Cc]\s*$', '', last_line)
    return last_line.strip()


def _to_value_set(s: str) -> "list | None":
    """把一段文本解析成一组 SymPy 值（支持逗号分隔的多解、"或"/"和"/or/and 分隔的
    多解、[] 包裹的列表）。解析失败返回 None。

    每个解可能带"x=""f'(x)=""2+3*4="这类前缀——不管前缀是变量名、函数记号
    还是完整重述的算式，真正要验证的都是最后一个"="后面的值，统一取
    最后一个"="之后的部分（没有"="就保留原样）。
    """
    s = _clean_answer_text(s).strip('[]{}')
    parts = [p.strip() for p in _re.split(r'[,;，；]|或|和|(?:\s+(?:or|and)\s+)', s) if p.strip()]
    if not parts:
        return None
    values = []
    for p in parts:
        eq_idx = p.rfind('=')
        if eq_idx != -1:
            p = p[eq_idx + 1:].strip()
        try:
            values.append(_parse_expr(_preprocess_expr(p), transformations=_LOOSE_TRANSFORMS))
        except Exception:
            return None
    return values


def _value_in_pool(v, pool: list, tol: float = 1e-6) -> bool:
    """v 是否在 pool 里有等价的值（先试符号相等，再退化到数值容差）。"""
    for p in pool:
        try:
            if sp.simplify(v - p) == 0:
                return True
        except Exception:
            pass
        try:
            if abs(complex(sp.N(v)) - complex(sp.N(p))) < tol:
                return True
        except Exception:
            pass
    return False


def answer_supported_by_calcs(parsed_answer: str, calc_results: list, tol: float = 1e-6) -> bool:
    """判断最终答案里的每一个值，是否都能在这一轮所有 calculator 调用结果里找到依据。

    不是只对比"最后一次调用"——模型经常分几次单独算（比如二次方程两个根分两次
    evaluate），只看最后一次会把正确答案误判成不一致。这里把这一轮所有 calculator
    结果汇总成一个"值池"，最终答案里的每个值只要能在池子里找到匹配就算通过。
    找不到 calculator 记录、或最终答案解析失败，一律判为"无法验证"（不通过）。
    """
    answer_vals = _to_value_set(parsed_answer)
    if not answer_vals:
        return False
    pool = []
    for r in calc_results:
        vals = _to_value_set(_extract_calc_value(r))
        if vals:
            pool.extend(vals)
    if not pool:
        return False
    return all(_value_in_pool(v, pool, tol) for v in answer_vals)


def answers_equivalent(parsed_answer: str, tool_result: str, tol: float = 1e-6) -> bool:
    """判断模型最终答案与单次 calculator 结果是否数学等价（answer_supported_by_calcs 的单值版本）。"""
    return answer_supported_by_calcs(parsed_answer, [tool_result], tol)


# RAG 懒加载索引（首次调用时构建，需要 Ollama 在线；失败后 5 分钟重试）
import time as _time
_rag_index: "list[dict] | None" = None
_rag_available: "bool | None" = None
_rag_next_retry: float = 0
_rag_lock = _threading.Lock()  # build_index 耗时数十秒，加锁防止多用户并发重复构建


def _get_rag_index() -> "list[dict] | None":
    global _rag_index, _rag_available, _rag_next_retry
    # 快路径不加锁；慢路径（构建）持锁并二次检查
    if _rag_index is not None:
        return _rag_index
    if _rag_available is False and _time.time() < _rag_next_retry:
        return None
    with _rag_lock:
        if _rag_index is not None:
            return _rag_index
        if _rag_available is False and _time.time() < _rag_next_retry:
            return None
        try:
            from rag_formula_lookup import build_index
            _rag_index = build_index()
            _rag_available = True
            _rag_next_retry = 0
            return _rag_index
        except Exception:
            _rag_available = False
            _rag_next_retry = _time.time() + 300  # 5 分钟后重试
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
# 4. 可视化工具实现
# ─────────────────────────────────────────

def _run_plot_function(expressions, xmin=-10, xmax=10, ymin=None, ymax=None,
                       title="", labels=None) -> str:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        # 课本风格：白底黑线，简洁学术风
        plt.rcParams.update({
            # matplotlib 自己扫描字体文件时，VPS 上装的 Noto Sans CJK 那个
            # .ttc 合集文件只被它认成"Noto Sans CJK JP"这一个名字（尽管同一个
            # 文件里也有SC/TC/KR的字形），配置里写"DejaVu Sans"/"Arial Unicode
            # MS"/"sans-serif"这几个名字都对不上，实际用的还是matplotlib自带的
            # DejaVu Sans——这个字体压根不含中文字形，所有中文都会画成方块
            # （日文变体的字形集完整覆盖常用简体中文字符，不影响可读性）。
            "font.family": ["Noto Sans CJK JP", "DejaVu Sans", "sans-serif"],
            "axes.unicode_minus": False,
            "axes.facecolor": "white",
            "figure.facecolor": "white",
            "axes.edgecolor": "#333333",
            "grid.color": "#cccccc",
            "grid.linewidth": 0.5,
        })

        fig, ax = plt.subplots(figsize=(9, 5.5))

        # 多条曲线用实线/虚线/点划线区分，颜色只用深色系
        line_styles = ["-", "--", "-.", ":"]
        colors = ["#1a1a1a", "#2255aa", "#cc2200", "#228833", "#aa44bb"]
        x_sym = sp.Symbol("x")
        x_arr = np.linspace(float(xmin), float(xmax), 2000)

        for i, expr_str in enumerate(expressions):
            try:
                sym_expr = sp.sympify(expr_str.replace("^", "**"))
                fn = sp.lambdify(x_sym, sym_expr, "numpy")
                y_arr = np.array(fn(x_arr), dtype=complex)
                y_arr = np.real(y_arr)
                y_arr[np.abs(y_arr) > 1e5] = np.nan
                lbl = (labels[i] if labels and i < len(labels)
                       else f"$y = {sp.latex(sym_expr)}$")
                ax.plot(x_arr, y_arr,
                        color=colors[i % len(colors)],
                        linestyle=line_styles[i % len(line_styles)],
                        lw=1.8, label=lbl)
            except Exception as e:
                ax.text(0.05, 0.95 - i * 0.07, f"解析失败: {expr_str}",
                        transform=ax.transAxes, fontsize=9, color="red")

        ax.axhline(0, color="black", lw=0.8)
        ax.axvline(0, color="black", lw=0.8)
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.6)
        if ymin is not None and ymax is not None:
            ax.set_ylim(float(ymin), float(ymax))
        if len(expressions) > 1 or (labels and labels[0]):
            ax.legend(fontsize=10, frameon=True, framealpha=0.9,
                      edgecolor="#aaaaaa", fancybox=False)
        if title:
            ax.set_title(title, fontsize=12, fontweight="bold",
                         color="#111111", pad=10, loc="left")
        ax.set_xlabel("$x$", fontsize=11)
        ax.set_ylabel("$y$", fontsize=11)
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        return _save_figure(fig, title or "函数图像")
    except Exception as e:
        return f"[plot_function 错误：{e}]"


def _run_draw_mindmap(title: str, branches: list) -> str:
    """课本风格层级树状思维导图：白底黑线，矩形框，从左到右层级展开。"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches

        plt.rcParams.update({
            # matplotlib 自己扫描字体文件时，VPS 上装的 Noto Sans CJK 那个
            # .ttc 合集文件只被它认成"Noto Sans CJK JP"这一个名字（尽管同一个
            # 文件里也有SC/TC/KR的字形），配置里写"DejaVu Sans"/"Arial Unicode
            # MS"/"sans-serif"这几个名字都对不上，实际用的还是matplotlib自带的
            # DejaVu Sans——这个字体压根不含中文字形，所有中文都会画成方块
            # （日文变体的字形集完整覆盖常用简体中文字符，不影响可读性）。
            "font.family": ["Noto Sans CJK JP", "DejaVu Sans", "sans-serif"],
            "axes.unicode_minus": False,
        })

        # ── 布局计算（从左到右：根 → 分支 → 子节点）────────────────────────
        # 统计总行数（每个子节点占一行，分支至少占一行）
        rows_per_branch = [max(1, len(b.get("children", []))) for b in branches]
        total_rows = max(sum(rows_per_branch), 1)

        ROW_H  = 0.7   # 每行高度
        COL_W  = 3.2   # 每列宽度
        BOX_W  = 2.8   # 文字框宽
        BOX_H  = 0.45  # 文字框高
        FIG_H  = max(5.0, total_rows * ROW_H + 1.5)
        FIG_W  = 12.0

        fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        ax.axis("off")

        # 坐标系：x = 列，y 从上到下
        ax.set_xlim(-0.5, FIG_W)
        ax.set_ylim(-FIG_H, 0.5)

        def draw_box(ax, cx, cy, text, is_root=False, is_branch=False):
            """画矩形框 + 文字，返回框的左右中心坐标。"""
            fc = "#1a1a2e" if is_root else ("#e8eef7" if is_branch else "white")
            ec = "#1a1a2e" if is_root else "#555577"
            tc = "white" if is_root else "#111111"
            lw = 1.8 if is_branch else 1.0
            rect = patches.FancyBboxPatch(
                (cx - BOX_W / 2, cy - BOX_H / 2), BOX_W, BOX_H,
                boxstyle="square,pad=0.05",
                facecolor=fc, edgecolor=ec, linewidth=lw, zorder=4,
            )
            ax.add_patch(rect)
            ax.text(cx, cy, text, ha="center", va="center",
                    fontsize=9.5 if is_root else (9.0 if is_branch else 8.5),
                    color=tc, fontweight="bold" if (is_root or is_branch) else "normal",
                    zorder=5, clip_on=True)
            return (cx - BOX_W / 2, cy), (cx + BOX_W / 2, cy)  # left, right mid-points

        def hline(ax, x0, x1, y):
            ax.plot([x0, x1], [y, y], color="#777788", lw=0.9, zorder=3)

        def vline(ax, x, y0, y1):
            ax.plot([x, x], [y0, y1], color="#777788", lw=0.9, zorder=3)

        # ── 根节点（居中纵向）────────────────────────────────────────────────
        root_x = 1.8
        root_cy = -FIG_H / 2
        draw_box(ax, root_x, root_cy, title, is_root=True)
        root_right_x = root_x + BOX_W / 2

        # ── 分支 + 子节点 ────────────────────────────────────────────────────
        branch_x   = root_x + COL_W
        child_x    = branch_x + COL_W

        # 计算每个分支的纵向中心 y
        cursor = -1.0  # 从顶部开始
        branch_centers = []
        for rb in rows_per_branch:
            span = rb * ROW_H
            branch_centers.append(cursor - span / 2)
            cursor -= span

        # 根节点垂直线连到所有分支
        if branch_centers:
            y_top    = branch_centers[0]
            y_bottom = branch_centers[-1]
            vline(ax, root_right_x + 0.3, y_top, y_bottom)

        for bi, (branch, bcy) in enumerate(zip(branches, branch_centers)):
            # 根 → 分支 水平连线
            hline(ax, root_right_x + 0.3, branch_x - BOX_W / 2, bcy)

            draw_box(ax, branch_x, bcy, branch.get("label", ""), is_branch=True)
            branch_right_x = branch_x + BOX_W / 2

            children = branch.get("children", [])
            if not children:
                continue

            # 子节点纵向排列
            rb = rows_per_branch[bi]
            top_cy = bcy + (rb - 1) / 2 * ROW_H
            child_ys = [top_cy - j * ROW_H for j in range(len(children))]

            # 分支 → 子节点 垂直线
            if len(children) > 1:
                vline(ax, branch_right_x + 0.3, child_ys[0], child_ys[-1])

            for child_text, ccy in zip(children, child_ys):
                hline(ax, branch_right_x + 0.3, child_x - BOX_W / 2, ccy)
                draw_box(ax, child_x, ccy, child_text)

        # 标题
        ax.text(FIG_W / 2, -0.1, title + "  知识框架",
                ha="center", va="bottom", fontsize=11,
                fontweight="bold", color="#1a1a2e")

        fig.tight_layout(pad=0.5)
        return _save_figure(fig, f"{title} 知识框架")
    except Exception as e:
        return f"[draw_mindmap 错误：{e}]"


# ─────────────────────────────────────────
# 5. 统一分发入口（供 agent.py 调用）
# ─────────────────────────────────────────

def execute_tool(tool_name: str, tool_input: dict) -> str:
    """将工具调用请求分发到对应实现。"""
    if not isinstance(tool_input, dict):
        return f"[参数格式错误：期望 JSON 对象，收到 {type(tool_input).__name__}]"
    if tool_name == "calculator":
        if "expression" not in tool_input or "operation" not in tool_input:
            return "[calculator 缺少必填参数 expression/operation，请重新调用并提供完整参数]"
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
    elif tool_name == "plot_function":
        return _run_plot_function(
            expressions=tool_input.get("expressions", [tool_input.get("expression", "x")]),
            xmin=tool_input.get("xmin", -10),
            xmax=tool_input.get("xmax", 10),
            ymin=tool_input.get("ymin"),
            ymax=tool_input.get("ymax"),
            title=tool_input.get("title", ""),
            labels=tool_input.get("labels"),
        )
    elif tool_name == "draw_mindmap":
        return _run_draw_mindmap(
            title=tool_input.get("title", ""),
            branches=tool_input.get("branches", []),
        )
    else:
        return f"未知工具：{tool_name}"
