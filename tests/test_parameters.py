# tests/test_parameters.py - 参数对比测试
import requests
import json
import time

API_ENDPOINT = "http://localhost:8000/compare"

# 加载测试提示词
with open("../data/test_prompts.txt", "r", encoding="utf-8") as f:
    test_prompts = [line.strip() for line in f.readlines() if line.strip()]

# 测试用例
test_cases = [
    {"prompt": prompt, "temperature": 0.7, "max_tokens": 200}
    for prompt in test_prompts[:100]  # 测试前100条
]


def run_test():
    results = []

    for i, test in enumerate(test_cases, 1):
        print(f"\n测试 #{i}/{len(test_cases)}: {test['prompt'][:30]}...")

        start_time = time.time()

        try:
            response = requests.post(
                API_ENDPOINT,
                json=test,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                duration = time.time() - start_time

                # 记录结果
                test_result = {
                    "prompt": test["prompt"],
                    "status": "success",
                    "duration": round(duration, 2),
                    "low_temp_length": len(result["low_temp"]),
                    "high_temp_length": len(result["high_temp"]),
                    "analysis": result["analysis"]
                }

                print(f"✓ 成功 | 耗时: {duration:.2f}s")
                print(f"  分析: {result['analysis'][:100]}...")

            else:
                test_result = {
                    "prompt": test["prompt"],
                    "status": f"error_{response.status_code}",
                    "error": response.text[:200]
                }
                print(f"✗ 错误: {response.status_code} - {response.text[:50]}")

        except Exception as e:
            test_result = {
                "prompt": test["prompt"],
                "status": "exception",
                "error": str(e)
            }
            print(f"✗ 异常: {str(e)}")

        results.append(test_result)
        time.sleep(0.5)  # 避免速率限制

    # 保存结果
    with open("parameter_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 打印摘要
    success_count = sum(1 for r in results if r["status"] == "success")
    print(f"\n测试完成: {success_count}/{len(results)} 成功")


if __name__ == "__main__":
    run_test()
