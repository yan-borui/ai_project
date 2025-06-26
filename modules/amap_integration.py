# modules/amap_integration.py - 高德地图API集成
import os
import logging
import httpx
from typing import Dict, List, Optional
import re

logger = logging.getLogger("amap_integration")

# 高德地图API配置
AMAP_API_BASE = "https://restapi.amap.com/v3"


def get_amap_key():
    """延迟获取API密钥，确保.env已加载"""
    return os.getenv("AMAP_API_KEY")


class AMapService:
    @staticmethod
    async def geocode(address: str) -> Optional[Dict]:
        """地理编码：地址转坐标"""
        amap_api_key = get_amap_key()
        if not amap_api_key:
            return {"error": "地图服务配置错误：请设置AMAP_API_KEY环境变量"}

        url = f"{AMAP_API_BASE}/geocode/geo"
        params = {
            "key": amap_api_key,
            "address": address,
            "output": "JSON"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                if data["status"] == "1" and data["geocodes"]:
                    location = data["geocodes"][0]["location"].split(",")
                    # 格式化输出
                    return {
                        "type": "geocode",
                        "query": address,
                        "result": {
                            "formatted_address": data["geocodes"][0].get("formatted_address", "未知"),
                            "province": data["geocodes"][0].get("province", "未知"),
                            "city": data["geocodes"][0].get("city", "未知"),
                            "district": data["geocodes"][0].get("district", "未知"),
                            "longitude": float(location[0]),
                            "latitude": float(location[1])
                        }
                    }
                return {"error": f"未找到与'{address}'相关的位置信息"}
        except Exception as e:
            logger.error(f"地理编码失败: {str(e)}")
            return {"error": f"地图服务暂时不可用，请稍后再试 ({str(e)})"}

    @staticmethod
    async def reverse_geocode(lng: float, lat: float) -> Optional[Dict]:
        """逆地理编码：坐标转地址"""
        amap_api_key = get_amap_key()
        if not amap_api_key:
            return {"error": "地图服务配置错误：请设置AMAP_API_KEY环境变量"}

        url = f"{AMAP_API_BASE}/geocode/regeo"
        params = {
            "key": amap_api_key,
            "location": f"{lng},{lat}",
            "extensions": "base",
            "output": "JSON"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                if data["status"] == "1":
                    address = data["regeocode"]["addressComponent"]
                    # 格式化输出
                    return {
                        "type": "reverse_geocode",
                        "query": f"{lng},{lat}",
                        "result": {
                            "formatted_address": data["regeocode"].get("formatted_address", "未知"),
                            "country": address.get("country", "未知"),
                            "province": address.get("province", "未知"),
                            "city": address.get("city", address.get("province", "未知")),
                            "district": address.get("district", "未知"),
                            "township": address.get("township", "未知"),
                            "street": f"{address['streetNumber'].get('street', '')} {address['streetNumber'].get('number', '')}".strip()
                        }
                    }
                return {"error": f"未找到坐标({lng},{lat})对应的地址信息"}
        except Exception as e:
            logger.error(f"逆地理编码失败: {str(e)}")
            return {"error": f"地图服务暂时不可用，请稍后再试 ({str(e)})"}

    @staticmethod
    async def search_poi(keyword: str, city: str = "") -> Optional[Dict]:
        """地点搜索"""
        amap_api_key = get_amap_key()
        if not amap_api_key:
            return {"error": "地图服务配置错误：请设置AMAP_API_KEY环境变量"}

        url = f"{AMAP_API_BASE}/place/text"
        params = {
            "key": amap_api_key,
            "keywords": keyword,
            "city": city,
            "output": "JSON"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                if data["status"] == "1" and data["pois"]:
                    # 格式化结果
                    results = []
                    for poi in data["pois"][:5]:  # 最多返回5个结果
                        location = poi["location"].split(",")
                        results.append({
                            "name": poi.get("name", "未知地点"),
                            "address": poi.get("address", "未知地址"),
                            "longitude": float(location[0]),
                            "latitude": float(location[1]),
                            "type": poi.get("type", "未知类型"),
                            "distance": f"{int(poi.get('distance', 0))}米" if poi.get("distance") else "未知距离"
                        })
                    
                    return {
                        "type": "poi_search",
                        "query": keyword,
                        "city": city if city else "全国范围",
                        "count": len(results),
                        "results": results
                    }
                return {"error": f"未找到与'{keyword}'相关的地点"}
        except Exception as e:
            logger.error(f"地点搜索失败: {str(e)}")
            return {"error": f"地图服务暂时不可用，请稍后再试 ({str(e)})"}

    @staticmethod
    def parse_map_command(prompt: str) -> Dict:
        """解析地图指令 - 改进版"""
        logger.info(f"解析地图指令: {prompt}")
        
        # 清理指令
        clean_prompt = prompt.replace("map:", "").strip()
        if not clean_prompt:
            return {"type": "help"}
        
        # 识别指令类型
        command_types = {
            "geocode": "地理编码",
            "reverse": "逆地理编码",
            "search": "地点搜索"
        }
        
        # 尝试匹配指令类型
        command_type = None
        for cmd in command_types:
            if clean_prompt.lower().startswith(cmd):
                command_type = cmd
                break
        
        if not command_type:
            # 自动识别指令类型
            if "坐标" in clean_prompt or "位置" in clean_prompt or "定位" in clean_prompt:
                return {"type": "reverse", "message": "请提供坐标信息，例如：116.397428,39.90923"}
            elif "搜索" in clean_prompt or "查找" in clean_prompt or "查询" in clean_prompt:
                return {"type": "search", "message": "请提供搜索关键词和城市（可选），例如：餐厅 北京"}
            else:
                return {"type": "geocode", "message": "请提供地址信息，例如：北京市海淀区中关村"}
        
        # 提取参数
        arguments = clean_prompt[len(command_type):].strip()
        
        if command_type == "geocode":
            if not arguments:
                return {"type": "error", "message": "请提供地址信息，例如：北京市海淀区中关村"}
            return {"type": "geocode", "address": arguments}
        
        elif command_type == "reverse":
            if not arguments:
                return {"type": "error", "message": "请提供坐标信息，例如：116.397428,39.90923"}
            
            # 尝试提取坐标
            coord_pattern = r"(-?\d+\.\d+)[,，\s]+(-?\d+\.\d+)"
            match = re.search(coord_pattern, arguments)
            if match:
                try:
                    lng = float(match.group(1))
                    lat = float(match.group(2))
                    return {"type": "reverse", "lng": lng, "lat": lat}
                except:
                    pass
            
            return {"type": "error", "message": "坐标格式错误，请使用'经度,纬度'格式"}
        
        elif command_type == "search":
            if not arguments:
                return {"type": "error", "message": "请提供搜索关键词，例如：餐厅"}
            
            # 分离关键词和城市
            parts = arguments.split(maxsplit=1)
            keyword = parts[0]
            city = parts[1] if len(parts) > 1 else ""
            
            return {"type": "search", "keyword": keyword, "city": city}
        
        return {"type": "help"}