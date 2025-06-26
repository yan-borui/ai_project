# modules/preprocessing.py - 输入预处理
import re
import logging
from . import calculator

logger = logging.getLogger("preprocessing")

# 敏感词库 - 可扩展
SENSITIVE_WORDS = [
    "暴力", "色情", "毒品", "赌博", "诈骗", "恐怖主义",
    "仇恨言论", "自杀", "自残", "儿童色情",
    "暴恐", "反动", "邪教", "枪支", "爆炸物",
    "violence", "porn", "drugs", "gambling", "scam",
    "terrorism", "hate speech", "suicide", "self-harm",
    "child abuse", "weapon", "explosive", "extremism"
]


# 创建 Trie 树结构
class TrieNode:
    __slots__ = ['children', 'is_end']

    def __init__(self):
        self.children = {}
        self.is_end = False


class SensitiveWordFilter:
    def __init__(self, word_list):
        self.root = TrieNode()
        self.build_trie(word_list)

    def build_trie(self, words):
        """构建 Trie 树"""
        for word in words:
            node = self.root
            for char in word:
                if char not in node.children:
                    node.children[char] = TrieNode()
                node = node.children[char]
            node.is_end = True

    def filter_text(self, text):
        """过滤文本中的敏感词"""
        if not text:
            return text

        # 转换为小写用于匹配（保留原始大小写）
        lower_text = text.lower()
        n = len(text)
        result = []
        i = 0

        while i < n:
            found = False
            node = self.root
            j = i
            matched_end = -1

            # 查找最长匹配
            while j < n and lower_text[j] in node.children:
                node = node.children[lower_text[j]]
                if node.is_end:
                    matched_end = j
                j += 1

            # 如果找到匹配
            if matched_end >= i:
                # 替换敏感词
                result.append("***")
                i = matched_end + 1
                found = True
                logger.debug(f"过滤敏感词: {text[i:matched_end + 1]}")

            if not found:
                # 添加非敏感词字符
                result.append(text[i])
                i += 1

        return "".join(result)


# 初始化敏感词过滤器
sensitive_filter = SensitiveWordFilter(SENSITIVE_WORDS)


def sanitize_input(text: str) -> str:
    """清理用户输入"""
    if not text or not isinstance(text, str):
        return ""

    try:
        # 记录原始输入
        original = text[:100] + "..." if len(text) > 100 else text

        # 1. 敏感词过滤
        clean_text = sensitive_filter.filter_text(text)

        # 2. 移除潜在危险字符
        clean_text = re.sub(r"[<>{}|\\^~\[\]]", "", clean_text)

        # 3. 标准化空格
        clean_text = re.sub(r"\s+", " ", clean_text).strip()

        # 记录变化
        if clean_text != text:
            logger.info(f"输入清理: '{original}' -> '{clean_text[:100]}...'")

        return clean_text

    except Exception as e:
        logger.error(f"输入清理失败: {str(e)}")
        return text


def detect_injection(text: str) -> bool:
    """检测潜在指令注入"""
    if not text:
        return False

    # 豁免我们自己的功能命令
    allowed_prefixes = ["calc:", "map:", "kb:"]
    if any(text.startswith(prefix) for prefix in allowed_prefixes):
        return False

    # 添加数学表达式白名单
    if calculator and calculator.calculator.is_calculation_request(text):
        return False

    injection_patterns = [
        "忽略之前", "作为AI", "系统提示", "角色扮演",
        "忘记指令", "突破限制", "扮演角色", "忽略以上",
        "previous instructions", "as an AI", "system prompt", "role play",
        "forget instructions", "bypass restrictions", "play a role"
    ]

    text_lower = text.lower()

    # 检查注入模式
    if any(pattern in text_lower for pattern in injection_patterns):
        return True

    # 检查可疑的编码模式
    if re.search(r"\\x[0-9a-f]{2}", text_lower):
        return True

    # 检查多重括号（可能试图覆盖系统提示）
    if text_lower.count("(") > 3 and text_lower.count(")") > 3:
        return True

    return False
