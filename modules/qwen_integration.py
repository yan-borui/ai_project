# modules/qwen_integration.py
import json
import logging
import httpx
import re

logger = logging.getLogger("qwen_integration")

QWEN_API_BASE = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"


# 禁用流式响应，返回完整结果
async def async_get_completion_qwen(prompt: str, temperature: float, max_tokens: int, api_key: str,
                                    client: httpx.AsyncClient) -> str:
    url = QWEN_API_BASE
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-DashScope-SSE": "disable"
    }
    payload = {
        "model": "qwen-turbo",
        "input": {
            "messages": [
                {"role": "user", "content": prompt}
            ]
        },
        "parameters": {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "result_format": "text"
        }
    }

    try:
        response = await client.post(url, headers=headers, json=payload, timeout=120.0)
        response.raise_for_status()
        data = response.json()
        if "output" in data and "text" in data["output"]:
            return data["output"]["text"]
        elif "output" in data and "choices" in data["output"]:
            return data["output"]["choices"][0]["message"]["content"]
        else:
            logger.error(f"无法解析Qwen响应: {data}")
            return f"错误: 无法解析API响应 - {str(data)[:200]}"
    except Exception as e:
        logger.exception("Qwen API调用异常")
        return f"错误: {str(e)}"


def clean_stream_line(line: str) -> str:
    """
    清理流式响应中的单行数据，去除id、event等标签以及HTTP_STATUS/200等无关内容。
    返回纯净的文本。
    """
    # 去除 id:数字 和 event:result:HTTP_STATUS/200 等标签
    line = re.sub(r'id:\d+', '', line)
    line = re.sub(r'event:[^ ]+', '', line)
    line = line.replace(":HTTP_STATUS/200", "")
    # line = line.replace(':', '')
    # 去除多余的空白符
    line = line.strip()

    # 清理后如果是空字符串则返回空
    return line


# 启用流式响应，返回异步生成器
async def async_get_completion_qwen_stream(prompt: str, temperature: float, max_tokens: int, api_key: str):
    async with httpx.AsyncClient(timeout=120.0) as client:
        url = QWEN_API_BASE
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-DashScope-SSE": "enable"  # 明确启用流式响应
        }
        payload = {
            "model": "qwen-turbo",
            "input": {
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            },
            "parameters": {
                "temperature": temperature,
                "max_tokens": max_tokens,
                "result_format": "text",
                "incremental_output": True
            }
        }

        try:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()

                logger.debug(f"Qwen响应头: {response.headers}")

                buffer = ""

                async for line_bytes in response.aiter_lines():
                    line = line_bytes.strip()
                    if not line:
                        continue

                    logger.debug(f"原始响应行: {line}")

                    # SSE格式行通常以 data: 开头
                    if line.startswith("data:"):
                        data_str = line[len("data:"):].strip()
                        if data_str == "[DONE]":
                            break

                        # 清理多余标签
                        cleaned_line = clean_stream_line(data_str)

                        if not cleaned_line:
                            continue

                        # 尝试解析JSON数据
                        try:
                            event_data = json.loads(cleaned_line)
                            if "output" in event_data and "text" in event_data["output"]:
                                text_chunk = event_data["output"]["text"]
                            elif "choices" in event_data and len(event_data["choices"]) > 0:
                                text_chunk = event_data["choices"][0]["message"]["content"]
                            else:
                                logger.warning(f"无法解析的JSON响应内容: {event_data}")
                                text_chunk = ""

                            if text_chunk:
                                # 拼接缓存，yield完整内容
                                buffer += text_chunk
                                yield text_chunk
                        except json.JSONDecodeError:
                            # 如果不是JSON，直接当作纯文本输出
                            yield cleaned_line

                    # 处理JSON格式直接响应（偶尔可能出现）
                    elif line.startswith("{") or line.startswith("["):
                        try:
                            data = json.loads(line)
                            if "output" in data and "text" in data["output"]:
                                yield data["output"]["text"]
                            elif "choices" in data and len(data["choices"]) > 0:
                                yield data["choices"][0]["message"]["content"]
                            else:
                                logger.warning(f"无法解析的JSON响应: {data}")
                        except json.JSONDecodeError:
                            logger.warning(f"JSON解析失败: {line}")
                            yield line

                    # 其它纯文本直接输出
                    else:
                        cleaned_line = clean_stream_line(line)
                        if cleaned_line:
                            yield cleaned_line

        except Exception as e:
            logger.exception("Qwen流式API调用异常")
            yield f"[错误: {str(e)}]"
