# modules/calculator.py - 安全数学表达式计算器
import math
import re
import logging
import cmath
from typing import Optional, Union

logger = logging.getLogger("calculator")


class Calculator:
    """安全数学表达式计算器"""

    def __init__(self):
        # 扩展安全函数和常量
        self.safe_functions = {
            # 基础数学函数
            'sqrt': math.sqrt,
            'cbrt': lambda x: x ** (1 / 3),  # 立方根
            'sin': math.sin,
            'cos': math.cos,
            'tan': math.tan,
            'asin': math.asin,
            'acos': math.acos,
            'atan': math.atan,
            'log': math.log,
            'log10': math.log10,
            'log2': math.log2,
            'exp': math.exp,
            'abs': abs,
            'round': round,
            'ceil': math.ceil,
            'floor': math.floor,
            'factorial': math.factorial,

            # 双曲函数
            'sinh': math.sinh,
            'cosh': math.cosh,
            'tanh': math.tanh,

            # 统计函数
            'hypot': math.hypot,
            'gcd': math.gcd,
            'lcm': lambda a, b: abs(a * b) // math.gcd(a, b) if a and b else 0,

            # 常量
            'pi': math.pi,
            'e': math.e,
            'tau': math.tau,
            'inf': float('inf'),
            'nan': float('nan'),

            # 复数支持
            'phase': cmath.phase,
            'polar': cmath.polar,
            'rect': cmath.rect,
            'csqrt': cmath.sqrt,
            'complex': lambda a, b: complex(a, b)
        }

    def is_calculation_request(self, text: str) -> bool:
        """检测是否为计算请求"""
        if not text:
            return False

        # 检测计算请求的关键词
        calculation_keywords = [
            "计算", "算一下", "等于多少", "=?",
            "calculate", "compute", "what is", "=?"
        ]

        # 检测数学表达式模式
        math_patterns = [
            r"\d+\s*[-+*/%^]\s*\d+",
            r"^[-+*/%^]\s*\d+",
            r"sqrt\(.+\)",
            r"sin\(.+\)",
            r"log\(.+\)",
            r"\d+\s*=\s*\?",
            r"[\d.]+[+\-*/^][\d.]+",
            r"^[\d()+\-*/^.a-z]+$",
        ]

        # 检查关键词
        if any(keyword in text.lower() for keyword in calculation_keywords):
            return True

        # 检查数学模式
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in math_patterns):
            return True

        return False

    def safe_evaluate(
            self,
            expression: str
    ) -> Optional[Union[float, str]]:
        """安全评估数学表达式"""
        try:
            # 清理表达式 - 保留更多数学符号
            clean_expr = re.sub(r"[^0-9a-zA-Z.\-+*/^%()π\s,]", "", expression)

            # 保留必要空格，仅压缩多余空格
            clean_expr = re.sub(r"\s+", " ", clean_expr).strip()

            # 替换常见数学符号
            clean_expr = clean_expr.replace("π", "pi").replace("^", "**")

            # 验证表达式安全性
            if not self._validate_expression(clean_expr):
                logger.warning(f"检测到不安全表达式: {expression}")
                return None

            # 创建安全环境 - 修复变量引用问题
            safe_env = {
                # 基础数学函数
                'sqrt': math.sqrt,
                'cbrt': lambda x: x ** (1 / 3),
                'sin': math.sin,
                'cos': math.cos,
                'tan': math.tan,
                'asin': math.asin,
                'acos': math.acos,
                'atan': math.atan,
                'log': math.log,
                'log10': math.log10,
                'log2': math.log2,
                'exp': math.exp,
                'abs': abs,
                'round': round,
                'ceil': math.ceil,
                'floor': math.floor,
                'factorial': math.factorial,
                
                # 双曲函数
                'sinh': math.sinh,
                'cosh': math.cosh,
                'tanh': math.tanh,
                
                # 统计函数
                'hypot': math.hypot,
                'gcd': math.gcd,
                'lcm': lambda a, b: abs(a * b) // math.gcd(a, b) if a and b else 0,
                
                # 常量
                'pi': math.pi,
                'e': math.e,
                'tau': math.tau,
                'inf': float('inf'),
                'nan': float('nan'),
                
                # 复数支持
                'phase': cmath.phase,
                'polar': cmath.polar,
                'rect': cmath.rect,
                'csqrt': cmath.sqrt,
                'complex': lambda a, b: complex(a, b),
                
                # 安全基础
                '__builtins__': None
            }

            # 使用eval执行计算
            result = eval(clean_expr, safe_env)

            # 添加详细日志
            logger.info(f"计算表达式: {clean_expr}")
            result = eval(clean_expr, safe_env)
            logger.info(f"计算结果: {result}")

            # 处理特殊值
            if isinstance(result, (int, float)):
                if result == float('inf'):
                    return "无穷大"
                if result == float('-inf'):
                    return "负无穷大"
                if math.isnan(result):
                    return "未定义"
                # 修复整数处理：先判断类型再处理
                if isinstance(result, int):
                    return result
                elif result.is_integer():
                    return int(result)
                else:
                    return round(result, 4)

            # 处理复数结果
            if isinstance(result, complex):
                return f"{result.real:.4f}{result.imag:+.4f}i"

            return str(result)

        except ZeroDivisionError:
            return "除零错误"
        except ValueError as ve:
            logger.error(f"数学错误: {expression} - {str(ve)}")
            return "数学错误"
        except SyntaxError as se:
            logger.error(f"语法错误: {expression} - {str(se)}")
            return "语法错误"
        except TypeError as te:
            logger.error(f"类型错误: {expression} - {str(te)}")
            return "类型错误"
        except NameError as ne:
            logger.error(f"未定义名称: {expression} - {str(ne)}")
            return "未定义函数或变量"
        except Exception as e:
            logger.error(f"计算错误: {expression} - {str(e)}")
            logger.exception(f"计算错误详情: {expression}")  # 添加详细异常日志
            return None

    def _validate_expression(self, expr: str) -> bool:
        """验证表达式是否安全"""
        # 禁止危险关键字
        danger_keywords = ["__", "import", "open", "exec", "eval", "lambda", "class"]
        if any(keyword in expr.lower() for keyword in danger_keywords):
            return False

        # 检查括号平衡
        stack = []
        for char in expr:
            if char == '(':
                stack.append(char)
            elif char == ')':
                if not stack:
                    return False
                stack.pop()
        if stack:
            return False

        # 修复：函数名大小写不敏感验证
        func_calls = re.findall(r"([a-zA-Z]+)\(", expr)
        safe_funcs_lower = [name.lower() for name in self.safe_functions]
        
        for func in set(func_calls):
            if func.lower() not in safe_funcs_lower:
                return False

        return True


# 全局计算器实例（安全初始化）
try:
    calculator = Calculator()
    logger.info("✅ 计算器初始化成功")
    logger.info(f"支持函数: {list(calculator.safe_functions.keys())}")
except Exception as e:
    logger.critical(f"❌ 计算器初始化失败: {str(e)}")
    # 创建空实例避免后续崩溃
    calculator = type('DummyCalc', (), {'safe_evaluate': lambda x: "计算器故障"})()

# 确保全局变量存在
if 'calculator' not in globals():
    calculator = None

