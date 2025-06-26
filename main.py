# main.py - 主应用入口
import os
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from dotenv import load_dotenv
from pydantic import BaseModel
import httpx
from contextlib import asynccontextmanager
from pathlib import Path
from modules import preprocessing, llm_integration, output_validation, qwen_integration, amap_integration, \
    knowledge_base
from modules.calculator import calculator as calc_instance


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="app.log",
    filemode="a"
)
logger = logging.getLogger("main")

# 加载环境变量
load_dotenv()
API_KEY = os.getenv("DEEPSEEK_API_KEY")
QWEN_API_KEY = os.getenv("QWEN_API_KEY")
if not API_KEY:
    logger.error("API密钥未配置！请在.env文件中设置DEEPSEEK_API_KEY")
    raise RuntimeError("API密钥未配置")

# 获取项目根目录
BASE_DIR = Path(__file__).parent


# 创建FastAPI应用
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    model_path = BASE_DIR / "local_models" / "all-MiniLM-L6-v2"
    try:
        # 确保目录存在
        (BASE_DIR / "local_models").mkdir(exist_ok=True, parents=True)
        (BASE_DIR / "knowledge_documents").mkdir(exist_ok=True, parents=True)

        # 模型路径
        model_path = BASE_DIR / "local_models" / "all-MiniLM-L6-v2"

        # 索引路径
        index_path = BASE_DIR / "knowledge_index.idx"
        documents_dir = BASE_DIR / "knowledge_documents"

        # 初始化知识库
        logger.info("正在初始化知识库...")
        knowledge_base.knowledge_base = knowledge_base.KnowledgeBase(str(model_path))

        # 如果索引文件存在则加载，否则构建新索引
        if index_path.exists():
            knowledge_base.knowledge_base.load_index(str(index_path))
            logger.info("知识库索引加载完成")
        elif any(documents_dir.iterdir()):  # 文档目录不为空
            knowledge_base.knowledge_base.build_index(str(documents_dir))
            knowledge_base.knowledge_base.save_index(str(index_path))
            logger.info("知识库索引构建并保存完成")
        else:
            logger.warning("未找到知识库索引文件或文档目录为空")
    except Exception as e:
        logger.error(f"知识库初始化失败: {str(e)}")
        # 创建空知识库继续运行
        knowledge_base.knowledge_base = knowledge_base.KnowledgeBase(str(model_path))
        logger.warning("创建空知识库继续运行")

    yield

    # 关闭时清理资源
    logger.info("清理知识库资源...")
    if hasattr(knowledge_base, 'knowledge_base') and knowledge_base.knowledge_base:
        knowledge_base.knowledge_base.release()


app = FastAPI(
    title="LLM API 后端服务",
    description="大语言模型API集成系统",
    version="1.0",
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan
)


# 数据模型定义
class UserInput(BaseModel):
    prompt: str
    temperature: float = 0.7
    max_tokens: int = 500
    provider: str = "deepseek"
    function: str = "llm"


class ComparisonResult(BaseModel):
    low_temp: str
    high_temp: str
    analysis: str


# 流式响应端点
@app.post("/generate", summary="流式响应生成")
async def generate_stream(input: UserInput):
    try:
        raw_prompt = input.prompt.strip()
        parts = raw_prompt.split(maxsplit=1)
        first_word = parts[0].lower()
        actual_prompt = parts[1] if len(parts) > 1 else ""

        if first_word == "qwen":
            if not QWEN_API_KEY:
                raise HTTPException(500, "Qwen API Key未配置")
            clean_prompt = preprocessing.sanitize_input(actual_prompt)
            if preprocessing.detect_injection(clean_prompt):
                raise HTTPException(403, "检测到潜在安全威胁")

            stream_generator = qwen_integration.async_get_completion_qwen_stream(
                prompt=clean_prompt,
                temperature=input.temperature,
                max_tokens=input.max_tokens,
                api_key=QWEN_API_KEY
            )
            return StreamingResponse(stream_generator, media_type="text/event-stream")

        else:
            # 默认调用 DeepSeek
            clean_prompt = preprocessing.sanitize_input(raw_prompt)  # 整个输入作为prompt

            if preprocessing.detect_injection(clean_prompt):
                logger.warning(f"检测到指令注入: {clean_prompt[:50]}")
                raise HTTPException(403, "检测到潜在安全威胁")

            stream_generator = llm_integration.generate_stream_response(
                prompt=clean_prompt,
                temperature=input.temperature,
                max_tokens=input.max_tokens,
                api_key=API_KEY
            )
            return StreamingResponse(stream_generator, media_type="text/event-stream")

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception("生成过程中出错")
        raise HTTPException(500, "生成失败") from e


# 参数对比端点
@app.post("/compare", summary="参数对比")
async def compare_parameters(input: UserInput):
    try:
        # 使用 provider 参数确定模型，而不是解析输入
        provider = input.provider.lower()
        raw_prompt = input.prompt.strip()
        
        # 移除模型前缀（如果存在）
        if raw_prompt.startswith("qwen ") or raw_prompt.startswith("deepseek "):
            parts = raw_prompt.split(maxsplit=1)
            actual_prompt = parts[1] if len(parts) > 1 else ""
        else:
            actual_prompt = raw_prompt

        async with httpx.AsyncClient(timeout=120.0) as client:
            if provider == "qwen":
                if not QWEN_API_KEY:
                    raise HTTPException(500, "Qwen API Key未配置")
                clean_prompt = preprocessing.sanitize_input(actual_prompt)
                if preprocessing.detect_injection(clean_prompt):
                    raise HTTPException(403, "检测到潜在安全威胁")

                low_temp = await qwen_integration.async_get_completion_qwen(
                    prompt=clean_prompt,
                    temperature=0.7,
                    max_tokens=input.max_tokens,
                    api_key=QWEN_API_KEY,
                    client=client
                )
                high_temp = await qwen_integration.async_get_completion_qwen(
                    prompt=clean_prompt,
                    temperature=1.2,
                    max_tokens=input.max_tokens,
                    api_key=QWEN_API_KEY,
                    client=client
                )

            else:
                clean_prompt = preprocessing.sanitize_input(actual_prompt)

                if preprocessing.detect_injection(clean_prompt):
                    logger.warning(f"检测到指令注入: {clean_prompt[:50]}")
                    raise HTTPException(403, "检测到潜在安全威胁")

                low_temp = await llm_integration.async_get_completion(
                    prompt=clean_prompt,
                    temperature=0.7,
                    max_tokens=input.max_tokens,
                    api_key=API_KEY,
                    client=client
                )
                high_temp = await llm_integration.async_get_completion(
                    prompt=clean_prompt,
                    temperature=1.2,
                    max_tokens=input.max_tokens,
                    api_key=API_KEY,
                    client=client
                )

        analysis = f"温度参数对比分析 (0.7 vs 1.2):\n"
        analysis += f"保守输出 (0.7): {low_temp[:100]}...\n"
        analysis += f"创意输出 (1.2): {high_temp[:100]}...\n"
        analysis += f"主要差异: {abs(len(low_temp) - len(high_temp))}字符长度差"

        valid_low = output_validation.validate_output(low_temp)
        valid_high = output_validation.validate_output(high_temp)

        return ComparisonResult(
            low_temp=valid_low,
            high_temp=valid_high,
            analysis=analysis
        )

    except Exception as e:
        logger.exception("参数对比过程中出错")
        raise HTTPException(500, "参数对比失败") from e


# 添加计算器端点
@app.post("/calculate")
async def calculate(input: UserInput):
    """数学计算端点 - 最终修复版"""
    try:
        # 确保计算器实例已初始化
        if not calc_instance:
            raise HTTPException(500, "计算器未初始化")
        
        # 新增：处理 calc: 前缀
        if input.prompt.startswith("calc:"):
            expression = input.prompt[5:].strip()  # 移除前缀
        else:
            expression = input.prompt
        
        # 添加详细日志
        logger.info(f"计算请求: {expression}")
        
        # 直接使用prompt作为表达式
        result = calc_instance.safe_evaluate(expression)
        
        return {"result": result}
    
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception("计算过程中出错")
        return JSONResponse(
            status_code=500,
            content={"error": f"计算失败: {str(e)}"}
        )



# 添加地图服务端点
@app.post("/map")
async def map_service(input: UserInput):
    """地图服务端点 - 改进版"""
    try:
        # 解析地图指令
        command = amap_integration.AMapService.parse_map_command(input.prompt)
        
        # 处理不同类型的命令
        if command["type"] == "geocode":
            result = await amap_integration.AMapService.geocode(command["address"])
            return format_map_result(result)
        
        elif command["type"] == "reverse":
            result = await amap_integration.AMapService.reverse_geocode(
                command["lng"], command["lat"]
            )
            return format_map_result(result)
        
        elif command["type"] == "search":
            result = await amap_integration.AMapService.search_poi(
                command["keyword"], command["city"]
            )
            return format_map_result(result)
        
        elif command["type"] == "error":
            return {"error": command["message"]}
        
        else:
            return {
                "help": "地图服务使用说明",
                "commands": [
                    "map:geocode <地址> - 地址转坐标（例如：map:geocode 北京市海淀区中关村）",
                    "map:reverse <经度>,<纬度> - 坐标转地址（例如：map:reverse 116.397428,39.90923）",
                    "map:search <关键词> [城市] - 搜索地点（例如：map:search 餐厅 北京）"
                ]
            }

    except Exception as e:
        logger.exception("地图服务过程中出错")
        return {"error": f"地图服务失败: {str(e)}"}


def format_map_result(result: dict) -> dict:
    """格式化地图服务结果"""
    if "error" in result:
        return result
    
    # 根据不同结果类型格式化输出
    if result["type"] == "geocode":
        res = result["result"]
        return {
            "type": "地址解析结果",
            "查询": result["query"],
            "地址": res["formatted_address"],
            "省份": res["province"],
            "城市": res["city"],
            "区域": res["district"],
            "坐标": f"经度: {res['longitude']}, 纬度: {res['latitude']}"
        }
    
    elif result["type"] == "reverse_geocode":
        res = result["result"]
        return {
            "type": "坐标解析结果",
            "查询": result["query"],
            "地址": res["formatted_address"],
            "国家": res["country"],
            "省份": res["province"],
            "城市": res["city"],
            "区域": res["district"],
            "街道": res["street"]
        }
    
    elif result["type"] == "poi_search":
        results = []
        for i, poi in enumerate(result["results"], 1):
            results.append({
                f"结果 {i}": {
                    "名称": poi["name"],
                    "地址": poi["address"],
                    "坐标": f"经度: {poi['longitude']}, 纬度: {poi['latitude']}",
                    "类型": poi["type"],
                    "距离": poi["distance"]
                }
            })
        
        return {
            "type": "地点搜索结果",
            "关键词": result["query"],
            "范围": result["city"],
            "结果数量": result["count"],
            "结果": results
        }
    
    return result


# 添加知识库端点
@app.post("/knowledge_base")
async def knowledge_base_search(input: UserInput):
    """知识库检索端点"""
    try:
        # 移除可能的命令前缀
        query = input.prompt.replace("kb:", "").strip()

        # 检索知识库
        results = knowledge_base.knowledge_base.search(query, top_k=3)

        # 格式化结果
        formatted_results = []
        for content, meta, score in results:
            formatted_results.append({
                "content": content[:500] + "..." if len(content) > 500 else content,
                "source": meta.get("source", "未知"),
                "page": meta.get("page", 0),
                "score": round(score, 3)
            })

        return {"results": formatted_results}

    except Exception as e:
        logger.exception("知识库检索过程中出错")
        raise HTTPException(500, "知识库检索失败") from e



# 修改安全中间件
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """全局安全中间件"""
    try:
        # 只检查POST请求
        if request.method == "POST":
            # 获取请求体
            body_bytes = await request.body()
            body_str = body_bytes.decode("utf-8")

            # 检查是否是我们允许的功能命令
            allowed_prefixes = ["calc:", "map:", "kb:"]
            if any(body_str.startswith(prefix) for prefix in allowed_prefixes):
                # 放行允许的命令
                request._body = body_bytes
                return await call_next(request)

            # 指令注入防护
            if preprocessing.detect_injection(body_str):
                logger.warning(f"中间件检测到注入: {body_str[:100]}")
                return JSONResponse(
                    status_code=403,
                    content={"error": "检测到潜在安全威胁"}
                )

            # 将body放回请求中（因为已经读取过）
            request._body = body_bytes

        return await call_next(request)

    except Exception:
        logger.exception("安全中间件出错")
        return JSONResponse(
            status_code=500,
            content={"error": "服务器内部错误"}
        )


# 健康检查端点
@app.get("/health")
def health_check():
    """服务健康检查"""
    return {"status": "healthy", "model": "deepseek-chat"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
