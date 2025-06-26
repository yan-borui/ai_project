# modules/output_validation.py - 输出验证
import json
import re
import logging
from pydantic import BaseModel, ValidationError

logger = logging.getLogger("output_validation")


# 输出JSON Schema
class OutputSchema(BaseModel):
    response: str
    reasoning: str = None
    sources: list[str] = []


def validate_output(output: str) -> str:
    """输出校验与格式化"""
    if not output:
        return ""

    # 尝试1: 解析为JSON
    try:
        data = json.loads(output)
        validated = OutputSchema(**data)
        logger.debug("输出成功验证为JSON")
        return json.dumps(validated.dict(), ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, ValidationError):
        pass

    # 尝试2: 类似JSON的结构（宽松模式）
    if re.search(r'{.*}', output):
        try:
            # 提取最可能JSON部分
            match = re.search(r'({.*})', output, re.DOTALL)
            if match:
                json_part = match.group(1)
                data = json.loads(json_part)
                validated = OutputSchema(**data)
                logger.debug("输出成功验证为类似JSON结构")
                return json.dumps(validated.dict(), ensure_ascii=False, indent=2)
        except:
            pass

    # 非JSON输出的清理
    logger.debug("输出为非JSON格式，进行清理")

    # 1. 移除控制字符
    clean_output = re.sub(r'[\x00-\x1F]', '', output)

    # 2. 移除潜在危险内容
    clean_output = re.sub(r'<script.*?>.*?</script>', '', clean_output, flags=re.IGNORECASE)

    # 3. 截断超长输出
    if len(clean_output) > 2000:
        clean_output = clean_output[:2000] + "... [输出截断]"

    return clean_output
