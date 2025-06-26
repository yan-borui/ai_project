import gradio as gr
import requests
import time
import sys
import os
import logging
import json
from pathlib import Path

# 设置项目根目录路径
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

# 配置API端点
API_URL = "http://localhost:8000/generate"
COMPARE_URL = "http://localhost:8000/compare"
HEALTH_URL = "http://localhost:8000/health"

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="gui.log",
    filemode="w"
)
logger = logging.getLogger("gradio_gui")

def generate_response(prompt, temperature, max_tokens, provider):
    """处理流式响应生成"""
      # 根据选择的provider添加前缀
    if provider == "qwen":
        formatted_prompt = f"qwen {prompt}"  # 添加qwen前缀
    else:
        formatted_prompt = prompt  # DeepSeek不需要前缀

    logger.info(f"开始请求: prompt='{formatted_prompt[:50]}...', temp={temperature}, tokens={max_tokens}, provider={provider}")
    
    try:
        # 构建请求
        response = requests.post(
            API_URL,
            json={
                "prompt": formatted_prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "provider": provider
            },
            stream=True,
            timeout=60
        )
        
        # 检查响应状态
        if response.status_code != 200:
            error_msg = f"API错误: {response.status_code} - {response.text[:200]}"
            logger.error(error_msg)
            yield error_msg
            return
        
        logger.info(f"收到响应: 状态码={response.status_code}")
        
        # 处理流式响应
        full_response = ""
        for chunk in response.iter_content(chunk_size=None):
            if chunk:
                try:
                    # 直接解码为UTF-8
                    text = chunk.decode('utf-8', errors='replace')
                    full_response += text
                    yield full_response
                except Exception as e:
                    error = f"\n解码错误: {str(e)}"
                    logger.error(error)
                    yield error
        
        logger.info(f"请求完成, 总长度={len(full_response)}字符")
            
    except Exception as e:
        error = f"请求失败: {str(e)}"
        logger.exception(error)
        yield error

def compare_responses(prompt, max_tokens, provider):
    """处理参数对比 - 修复模型切换问题"""
    logger.info(f"开始对比请求: prompt='{prompt[:50]}...', tokens={max_tokens}, provider={provider}")
    
    try:
        response = requests.post(
            COMPARE_URL,
            json={
                "prompt": prompt,
                "max_tokens": max_tokens,
                "provider": provider  # 确保传递provider参数
            },
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            logger.info("对比请求成功完成")
            return [
                data.get("low_temp", "无结果"),
                data.get("high_temp", "无结果"),
                data.get("analysis", "无分析结果")
            ]
        else:
            error_msg = f"API错误: {response.status_code} - {response.text[:200]}"
            logger.error(error_msg)
            return ["错误", "错误", error_msg]
    
    except Exception as e:
        error = f"请求失败: {str(e)}"
        logger.exception(error)
        return ["错误", "错误", error]
    
def calculate_expression(expression):
    """处理计算器请求"""
    try:
        # 添加超时和空表达式处理
        if not expression.strip():
            return "请输入表达式"
        
        response = requests.post(
            "http://localhost:8000/calculate",
            json={"prompt": f"calc:{expression}"},
            timeout=10
        )
        
        # 增强错误处理
        if response.status_code == 200:
            return response.json().get("result", "无结果")
        elif response.status_code == 403:
            return "安全验证失败"
        else:
            return f"API错误: {response.status_code}"
            
    except requests.exceptions.Timeout:
        return "请求超时"
    except Exception as e:
        return f"请求失败: {str(e)}"

def map_service(command):
    """处理地图服务请求 - 改进版"""
    try:
        # 确保命令有map:前缀
        if not command.startswith("map:"):
            command = "map:" + command

        response = requests.post(
            "http://localhost:8000/map",
            json={"prompt": command},
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # 格式化输出
            formatted = []
            
            if "help" in data:
                formatted.append("🗺️ 地图服务使用说明")
                formatted.append("="*30)
                formatted.extend(data["commands"])
                return "\n".join(formatted)
            
            if "error" in data:
                return f"❌ 错误: {data['error']}"
            
            # 根据不同类型格式化输出
            if "type" in data:
                formatted.append(f"🔍 {data['type']}")
                formatted.append("="*30)
            
            if "查询" in data:
                formatted.append(f"🔎 查询内容: {data['查询']}")
            
            # 处理地址解析结果
            if "地址" in data:
                formatted.extend([
                    f"🏠 详细地址: {data['地址']}",
                    f"📍 坐标位置: {data.get('坐标', '未知')}",
                    f"🗺️ 行政区划: {data.get('省份', '')}{data.get('城市', '')}{data.get('区域', '')}",
                    ""
                ])
            
            # 处理坐标解析结果
            if "街道" in data:
                formatted.extend([
                    f"🏠 详细地址: {data['地址']}",
                    f"📍 坐标位置: {data['查询']}",
                    f"🗺️ 行政区划: {data['省份']} → {data['城市']} → {data['区域']}",
                    f"🏘️ 街道信息: {data['街道']}",
                    ""
                ])
            
            # 处理地点搜索结果
            if "结果" in data:
                formatted.append(f"🔍 搜索关键词: {data['关键词']}")
                formatted.append(f"🌆 搜索范围: {data['范围']}")
                formatted.append(f"📊 找到 {data['结果数量']} 个结果:")
                formatted.append("")
                
                for i, result in enumerate(data["结果"], 1):
                    for key, value in result.items():
                        formatted.append(f"⭐ {key}:")
                        for k, v in value.items():
                            formatted.append(f"   - {k}: {v}")
                        formatted.append("")
            
            return "\n".join(formatted) if formatted else "无结果"
        
        return f"API错误: {response.status_code}"
    
    except Exception as e:
        return f"请求失败: {str(e)}"

def knowledge_base_search(query):
    """处理知识库查询"""
    try:
        # 确保查询有kb:前缀
        if not query.startswith("kb:"):
            query = "kb:" + query
            
        response = requests.post(
            "http://localhost:8000/knowledge_base",
            json={"prompt": query},
            timeout=15
        )
        if response.status_code == 200:
            data = response.json().get("results", [])
            # 转换为Dataframe格式
            return [[
                item["content"],
                item["source"],
                item["score"]
            ] for item in data]
        return []
    except Exception as e:
        return []

def check_health():
    """检查后端服务状态"""
    try:
        response = requests.get(HEALTH_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            # 更新为新的响应格式
            status = "✅ 服务运行正常\n"
            status += f"模型: {data.get('model', '未知')}\n"
            status += f"状态: {data.get('status', '未知')}"
            return status
        return f"⚠️ 服务异常: {response.status_code}"
    except Exception as e:
        return f"❌ 服务不可达: {str(e)}"

# 创建Gradio界面
with gr.Blocks(
    title="LLM对话系统",
    theme=gr.themes.Soft(),
    css="""
    .output-box {
        font-family: 'Microsoft YaHei', 'PingFang SC', 'SimHei', sans-serif;
        font-size: 16px;
        line-height: 1.6;
        white-space: pre-wrap;
        overflow-y: auto;
        background-color: #f9f9f9;
        border-radius: 8px;
        padding: 15px;
        min-height: 300px;
    }
    .input-box {
        font-size: 16px;
        padding: 12px;
        font-family: 'Microsoft YaHei', 'PingFang SC', 'SimHei', sans-serif;
    }
    .model-status {
        background-color: #e6f7ff;
        border: 1px solid #91d5ff;
        border-radius: 6px;
        padding: 10px;
        margin-bottom: 15px;
    }
    """
) as demo:
    gr.Markdown("# 🧠 LLM智能对话系统")
    gr.Markdown("基于DeepSeek和通义千问大模型的对话应用")
    
    with gr.Tab("💬 对话生成"):
        with gr.Row(equal_height=False):
            # 左侧输入面板
            with gr.Column(scale=5):
                with gr.Group():
                    prompt_input = gr.Textbox(
                        label="输入提示",
                        placeholder="请输入您的问题或指令...",
                        lines=5,
                        max_lines=10,
                        elem_classes=["input-box"]
                    )
                    
                    with gr.Row():
                        provider_select = gr.Radio(
                            ["deepseek", "qwen"],
                            value="deepseek",
                            label="模型选择",
                            info="选择使用的大模型"
                        )
                        
                    with gr.Row():
                        temperature_slider = gr.Slider(
                            0.1, 2.0, value=0.7, 
                            label="创造力 (temperature)",
                            info="值越高，回答越有创意",
                            step=0.1
                        )
                        tokens_slider = gr.Slider(
                            100, 2000, value=500, step=100,
                            label="最大长度 (max_tokens)",
                            info="控制回答的最大长度"
                        )
                    
                    # 当前模型状态显示
                    model_status = gr.Textbox(
                        label="当前模型状态",
                        value="DeepSeek (默认)",
                        interactive=False,
                        elem_classes=["model-status"]
                    )
                    
                    # 当模型选择变化时更新状态
                    def update_model_status(provider):
                        model_name = "DeepSeek" if provider == "deepseek" else "Qwen"
                        return f"已选择: {model_name} 模型"
                        
                    provider_select.change(
                        fn=update_model_status,
                        inputs=provider_select,
                        outputs=model_status
                    )
                    
                    submit_btn = gr.Button("🚀 生成回答", variant="primary", size="lg")
            
            # 右侧输出面板
            with gr.Column(scale=5):
                output_area = gr.Textbox(
                    label="模型输出",
                    interactive=False,
                    lines=15,
                    show_copy_button=True,
                    elem_classes=["output-box"],
                    autoscroll=True
                )
        
        # 连接交互
        submit_btn.click(
            fn=generate_response,
            inputs=[prompt_input, temperature_slider, tokens_slider, provider_select],
            outputs=output_area
        )

    with gr.Tab("🧮 计算器"):
        with gr.Row():
            with gr.Column():
                calc_input = gr.Textbox(
                    label="数学表达式",
                    placeholder="输入计算表达式，如: 2+3*sin(pi/2)",
                    elem_classes=["input-box"]
                )
                calc_btn = gr.Button("计算", variant="primary")
                calc_output = gr.Textbox(
                    label="计算结果",
                    interactive=False,
                    elem_classes=["output-box"]
                )
        
        calc_btn.click(
            fn=calculate_expression,
            inputs=calc_input,
            outputs=calc_output
        )

    with gr.Tab("🗺️ 地图服务"):
        with gr.Row():
            with gr.Column():
                map_input = gr.Textbox(
                    label="地图指令",
                    placeholder="输入地图指令，如: geocode 北京市海淀区中关村 // search 餐厅 北京 // reverse 116.397428,39.90923",
                    lines=3,
                    elem_classes=["input-box"]
                )
                map_btn = gr.Button("执行", variant="primary")
                # 修改这里：将 gr.JSON() 改为 gr.Textbox()
                map_output = gr.Textbox(  # 修改这一行
                    label="地图结果",
                    interactive=False,
                    lines=10,  # 增加行数以显示更多内容
                    elem_classes=["output-box"]
                )
        
        map_btn.click(
            fn=map_service,
            inputs=map_input,
            outputs=map_output
        )

    with gr.Tab("📚 知识库"):
        with gr.Row():
            with gr.Column():
                kb_input = gr.Textbox(
                    label="查询内容",
                    placeholder="输入知识库查询内容",
                    elem_classes=["input-box"]
                )
                kb_btn = gr.Button("搜索", variant="primary")
                kb_output = gr.Dataframe(
                    label="搜索结果",
                    headers=["内容", "来源", "相关性"],
                    datatype=["str", "str", "number"],
                    interactive=False,
                    elem_classes=["output-box"]
                )
        
        kb_btn.click(
            fn=knowledge_base_search,
            inputs=kb_input,
            outputs=kb_output
        )
    
    with gr.Tab("🔍 参数对比"):
        with gr.Row():
            with gr.Column(scale=1):
                with gr.Group():
                    compare_prompt = gr.Textbox(
                        label="输入提示", 
                        placeholder="请输入要对比的内容...",
                        lines=3,
                        elem_classes=["input-box"]
                    )
                    
                    with gr.Row():
                        compare_provider = gr.Radio(
                            ["deepseek", "qwen"],
                            value="deepseek",
                            label="模型选择"
                        )
                        compare_tokens = gr.Slider(
                            100, 2000, value=300, step=100,
                            label="最大长度"
                        )
                    
                    compare_btn = gr.Button("🔬 执行对比", variant="primary")
            
            with gr.Column(scale=1):
                with gr.Group():
                    low_temp_output = gr.Textbox(
                        label="低温输出 (0.7)", 
                        lines=6, 
                        interactive=False,
                        elem_classes=["output-box"]
                    )
                    high_temp_output = gr.Textbox(
                        label="高温输出 (1.2)", 
                        lines=6, 
                        interactive=False,
                        elem_classes=["output-box"]
                    )
                    analysis_output = gr.Textbox(
                        label="对比分析", 
                        lines=4, 
                        interactive=False,
                        elem_classes=["output-box"]
                    )
        
        # 连接交互
        compare_btn.click(
            fn=compare_responses,
            inputs=[compare_prompt, compare_tokens, compare_provider],
            outputs=[low_temp_output, high_temp_output, analysis_output]
        )
    
    with gr.Tab("ℹ️ 系统信息"):
        with gr.Row():
            with gr.Column(scale=1):
                with gr.Group():
                    gr.Markdown("### 系统状态")
                    status = gr.Textbox(
                        label="API状态", 
                        value="未连接", 
                        interactive=False,
                        elem_classes=["output-box"]
                    )
                
                    # 健康检查按钮
                    check_btn = gr.Button("🔄 检查服务状态")
                    check_btn.click(
                        fn=check_health,
                        outputs=status
                    )
        
            with gr.Column(scale=2):
                with gr.Group():
                    gr.Markdown("### 模型信息")
                    
                    # 创建模型状态显示组件
                    deepseek_status = gr.Markdown("**DeepSeek模型**:\n- 状态: 正常")
                    qwen_status = gr.Markdown("**Qwen模型**:\n- 状态: 正常")
                    
                    # 定义更新模型状态的函数
                    def update_model_status():
                        """更新模型状态显示"""
                        try:
                            response = requests.get(HEALTH_URL, timeout=5)
                            if response.status_code == 200:
                                data = response.json()
                                # 简化显示，因为后端只返回基本状态
                                return f"**服务状态**: ✅ 正常\n**当前模型**: {data.get('model', '未知')}"
                            return "**服务状态**: ⚠️ 异常"
                        except Exception as e:
                            return "**服务状态**: ❌ 不可达"
                    
                    # # 页面加载时更新模型状态(不需要，暂且注释掉)
                    # demo.load(
                    #     fn=update_model_status,
                    #     inputs=None,
                    #     outputs=[deepseek_status, qwen_status],
                    #     queue=False
                    # )


# 启动界面
if __name__ == "__main__":
    # 打印配置信息
    print("=" * 50)
    print("LLM对话系统GUI")
    print("=" * 50)
    print(f"后端API地址: {API_URL}")
    print(f"对比API地址: {COMPARE_URL}")
    print(f"健康检查地址: {HEALTH_URL}")
    print("\n请确保后端服务正在运行 (python main.py)")
    print("=" * 50)
    
    # 启动GUI
    print("启动Gradio界面...")
    print(f"请访问: http://localhost:7860")
    print("=" * 50)
    
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_error=True,
        debug=True
    )