# tests/test_amap.py - 高德地图API测试（控制台输出版）
import requests
import json
import time
import logging
from datetime import datetime
import sys

# 配置控制台日志输出
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout  # 输出到控制台
)
logger = logging.getLogger("amap_test")

# API配置
API_ENDPOINT = "http://localhost:8000/map"

# 40条测试数据（直接嵌入在脚本中）
TEST_PROMTPS = [
    # 地理编码测试
    "map:geocode 北京市海淀区中关村",
    "map:geocode 上海市浦东新区陆家嘴",
    "map:geocode 广州市天河区珠江新城",
    "map:geocode 深圳市南山区腾讯大厦",
    "map:geocode 杭州市西湖区阿里巴巴西溪园区",
    "map:geocode 成都市武侯区天府软件园",
    "map:geocode 南京市鼓楼区南京大学",
    "map:geocode 武汉市洪山区华中科技大学",
    "map:geocode 西安市雁塔区大雁塔",
    "map:geocode 重庆市渝中区解放碑",

    # 逆地理编码测试
    "map:reverse 116.397428,39.90923",  # 北京
    "map:reverse 121.499718,31.239703",  # 上海
    "map:reverse 113.323568,23.114155",  # 广州
    "map:reverse 114.066112,22.548515",  # 深圳
    "map:reverse 120.210792,30.246026",  # 杭州
    "map:reverse 104.067923,30.679943",  # 成都
    "map:reverse 118.778074,32.057236",  # 南京
    "map:reverse 114.436868,30.510615",  # 武汉
    "map:reverse 108.946465,34.347269",  # 西安
    "map:reverse 106.576677,29.556468",  # 重庆

    # 地点搜索测试
    "map:search 餐厅 北京",
    "map:search 酒店 上海",
    "map:search 医院 广州",
    "map:search 加油站 深圳",
    "map:search 银行 杭州",
    "map:search 学校 成都",
    "map:search 电影院 南京",
    "map:search 超市 武汉",
    "map:search 公园 西安",
    "map:search 地铁站 重庆",

    # 错误测试
    "map:geocode 不存在的地址12345",
    "map:reverse 200,200",  # 无效坐标
    "map:search @#$%^&* 无效城市",  # 特殊字符
    "map:geocode",  # 缺少参数
    "map:reverse 116.397428",  # 不完整坐标
    "map:unknown_command 测试数据",  # 未知命令
    "map:search 特殊!字符@地点#",  # 特殊字符
    "map:geocode 东京都千代田区",  # 国外地址
    "map:reverse 139.691706,35.689487",  # 东京坐标
    "map:search Starbucks 纽约"  # 国外搜索
]


def run_amap_test():
    """执行高德地图API测试（控制台输出详细结果）"""
    print("\n" + "=" * 60)
    print("开始高德地图API测试")
    print(f"测试端点: {API_ENDPOINT}")
    print(f"测试数量: {len(TEST_PROMTPS)}")
    print("=" * 60)

    results = []
    success_count = 0
    error_count = 0

    for i, prompt in enumerate(TEST_PROMTPS, 1):
        # 打印测试标题
        print(f"\n{'=' * 50}")
        print(f"测试 #{i}/{len(TEST_PROMTPS)}: {prompt}")
        print(f"{'-' * 50}")

        start_time = time.time()
        response = None

        try:
            # 发送POST请求
            print(f"发送请求: {prompt}")
            response = requests.post(
                API_ENDPOINT,
                json={"prompt": prompt},
                timeout=15
            )

            # 记录结果
            result = {
                "prompt": prompt,
                "status": response.status_code,
                "latency": round(time.time() - start_time, 3),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            # 打印响应详情
            print(f"响应状态: {response.status_code}")
            print(f"响应时间: {result['latency']}秒")

            if response.status_code == 200:
                json_response = response.json()
                result["response"] = json_response
                success_count += 1

                # 格式化打印响应内容
                print("响应内容:")
                if "error" in json_response:
                    print(f"  错误信息: {json_response['error']}")
                else:
                    for key, value in json_response.items():
                        if isinstance(value, dict):
                            print(f"  {key}:")
                            for subkey, subvalue in value.items():
                                print(f"    {subkey}: {subvalue}")
                        elif isinstance(value, list):
                            print(f"  {key}:")
                            for i, item in enumerate(value, 1):
                                if isinstance(item, dict):
                                    print(f"    结果 #{i}:")
                                    for k, v in item.items():
                                        print(f"      {k}: {v}")
                                else:
                                    print(f"    {item}")
                        else:
                            print(f"  {key}: {value}")

                print("✓ 测试成功")
            else:
                result["error"] = response.text[:500]
                error_count += 1
                print(f"响应内容: {response.text[:500]}")
                print("✗ 测试失败")

        except requests.exceptions.Timeout:
            result = {
                "prompt": prompt,
                "status": "timeout",
                "error": "请求超时",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            error_count += 1
            print("✗ 请求超时")
        except Exception as e:
            result = {
                "prompt": prompt,
                "status": "exception",
                "error": str(e),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            error_count += 1
            print(f"✗ 发生异常: {str(e)}")

        results.append(result)
        time.sleep(0.3)  # 避免速率限制

    # 打印最终报告
    print("\n" + "=" * 60)
    print("测试完成!")
    print(f"成功: {success_count}")
    print(f"失败: {error_count}")
    print("=" * 60)

    # 保存结果到文件
    with open("amap_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"详细结果已保存到: amap_test_results.json")


if __name__ == "__main__":
    run_amap_test()
