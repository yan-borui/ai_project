# modules/llm_integration.py - LLM API集成
# modules/llm_integration.py - LLM API集成
import logging
import time
import os
import httpx
import asyncio
from openai import OpenAI, APITimeoutError, RateLimitError

logger = logging.getLogger("llm_integration")

# 使用DeepSeek专属API端点
DEEPSEEK_API_BASE = "https://api.deepseek.com/v1"


def create_openai_client(api_key: str):
    """创建OpenAI客户端，正确处理DeepSeek API设置"""
    # 获取代理配置
    proxy_url = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY") or \
                os.getenv("https_proxy") or os.getenv("http_proxy")

    # 创建自定义HTTP客户端
    timeout = httpx.Timeout(120.0)

    # 正确配置代理
    transport = None
    if proxy_url:
        logger.info(f"使用代理: {proxy_url}")
        transport = httpx.HTTPTransport(proxy=proxy_url, trust_env=False)

    http_client = httpx.Client(
        transport=transport,
        trust_env=False,
        timeout=timeout
    )

    return OpenAI(
        api_key=api_key,
        base_url=DEEPSEEK_API_BASE,
        http_client=http_client,
        timeout=timeout,
        max_retries=0
    )


# 添加异步API调用方法
async def async_get_completion(
        prompt: str,
        temperature: float,
        max_tokens: int,
        api_key: str,
        client: httpx.AsyncClient
) -> str:
    """异步获取完整的API响应"""
    retries = 0
    max_retries = 3
    result = None

    # DeepSeek API端点
    url = f"{DEEPSEEK_API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    while retries <= max_retries:
        try:
            logger.info(f"开始异步API请求: {prompt[:50]}... (重试 {retries}/{max_retries})")
            start_time = time.time()

            # 直接使用httpx进行异步调用
            response = await client.post(
                url,
                headers=headers,
                json=payload,
                timeout=120.0
            )

            # 检查响应状态
            if response.status_code != 200:
                error_msg = f"API错误: {response.status_code} - {response.text[:200]}"
                logger.error(error_msg)
                raise Exception(error_msg)

            data = response.json()
            duration = time.time() - start_time
            logger.info(f"API请求完成, 耗时: {duration:.2f}秒")
            result = data["choices"][0]["message"]["content"]
            break

        except (RateLimitError, APITimeoutError) as e:
            # 指数退避策略
            wait_time = min((2 ** retries) * 5, 60)  # 最大60秒
            logger.warning(f"{type(e).__name__}错误, 等待 {wait_time}秒后重试...")
            await asyncio.sleep(wait_time)
            retries += 1

            if retries > max_retries:
                logger.error("超过最大重试次数")
                result = "错误: API请求失败，请稍后再试"
                break

        except Exception as e:
            logger.exception("API调用出错")
            result = f"生成失败: {str(e)}"
            break

    return result


def generate_stream_response(prompt: str, temperature: float, max_tokens: int, api_key: str):
    """生成流式响应（打字机效果）"""
    retries = 0
    max_retries = 2

    while retries <= max_retries:
        client = None
        try:
            client = create_openai_client(api_key)
            logger.info(f"开始流式API请求: {prompt[:50]}... (重试 {retries}/{max_retries})")
            start_time = time.time()

            # 流式API调用
            stream = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )

            # 逐块生成响应
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

            duration = time.time() - start_time
            logger.info(f"流式请求完成, 耗时: {duration:.2f}秒")
            break

        except (RateLimitError, APITimeoutError) as e:
            # 指数退避策略
            wait_time = min((2 ** retries) * 5, 30)  # 最小5秒，最大30秒
            logger.warning(f"{type(e).__name__}错误, 等待 {wait_time}秒后重试...")
            time.sleep(wait_time)
            retries += 1

            if retries > max_retries:
                logger.error("超过最大重试次数")
                yield "[错误: API请求失败，请稍后再试]"
                break

        except Exception as e:
            logger.exception("流式生成出错")
            yield f"[生成出错: {str(e)}]"
            break

        finally:
            # 安全关闭客户端连接
            if client:
                try:
                    client._client.close()
                except Exception as e:
                    logger.warning(f"关闭客户端时出错: {str(e)}")


def get_completion(prompt: str, temperature: float, max_tokens: int, api_key: str) -> str:
    """获取完整的API响应"""
    retries = 0
    max_retries = 2
    result = None

    while retries <= max_retries:
        client = None
        try:
            client = create_openai_client(api_key)
            logger.info(f"开始API请求: {prompt[:50]}... (重试 {retries}/{max_retries})")
            start_time = time.time()

            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )

            duration = time.time() - start_time
            logger.info(f"API请求完成, 耗时: {duration:.2f}秒")
            result = response.choices[0].message.content
            break

        except (RateLimitError, APITimeoutError) as e:
            # 指数退避策略
            wait_time = min((2 ** retries) * 5, 30)
            logger.warning(f"{type(e).__name__}错误, 等待 {wait_time}秒后重试...")
            time.sleep(wait_time)
            retries += 1

            if retries > max_retries:
                logger.error("超过最大重试次数")
                result = "错误: API请求失败，请稍后再试"
                break

        except Exception as e:
            logger.exception("API调用出错")
            result = f"生成失败: {str(e)}"
            break

        finally:
            # 安全关闭客户端连接
            if client:
                try:
                    client._client.close()
                except Exception as e:
                    logger.warning(f"关闭客户端时出错: {str(e)}")

    return result
