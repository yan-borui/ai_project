# tests/test_stream.py - 流式响应测试
import time
import requests

API_ENDPOINT = "http://localhost:8000/generate"

# 测试数据
with open("../data/test_prompts.txt", "r", encoding="utf-8") as f:
    test_prompts = [line.strip() for line in f.readlines() if line.strip()]


def test_stream_response(prompt: str):
    print(f"\n测试提示: '{prompt[:30]}...'")
    print("=" * 50)

    try:
        # 发送请求
        response = requests.post(
            API_ENDPOINT,
            json={
                "prompt": prompt,
                "temperature": 0.8,
                "max_tokens": 300
            },
            stream=True,
            timeout=30
        )

        # 检查响应状态
        if response.status_code != 200:
            print(f"错误: {response.status_code} - {response.text}")
            return

        print("流式响应开始:")
        content_buffer = ""

        # 统一处理所有流式响应
        for chunk in response.iter_content(chunk_size=None):
            if chunk:
                text = chunk.decode('utf-8')
                print(text, end='', flush=True)
                content_buffer += text
                time.sleep(0.05)  # 微小延迟使输出更平滑

        print("\n流式响应结束")
        print(f"接收内容长度: {len(content_buffer)} 字符")

    except Exception as e:
        print(f"\n测试失败: {str(e)}")


if __name__ == "__main__":
    for prompt in test_prompts:
        test_stream_response(prompt)
        time.sleep(1)  # 请求间暂停
