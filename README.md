# LLM智能对话系统

这是一个功能全面的LLM智能对话系统，集成了DeepSeek和通义千问大模型，并提供了多种实用工具功能。

## 功能概述

### 核心功能
- **对话生成**：支持DeepSeek和通义千问大模型
- **参数对比**：比较不同温度参数下的模型输出
- **计算器**：执行数学表达式计算
- **地图服务**：提供地理编码、逆地理编码和地点搜索
- **知识库**：从本地文档构建知识索引并支持语义搜索
- **系统监控**：显示API状态和服务健康信息

### 技术亮点
- 流式响应生成（打字机效果）
- 多模型支持（DeepSeek/Qwen）
- 敏感词过滤和输入安全验证
- 知识库语义搜索
- 参数对比分析
- 响应输出验证

## 安装与运行

### 前置要求
- Python 3.10+
- Git LFS

### 安装步骤
1. 浅克隆仓库（需安装Git LFS）：
```bash
git clone --depth 1 https://github.com/yan-borui/ai_project.git
cd ai_project
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

### 启动服务
1. 启动后端API：
```bash
python main.py
```

2. 启动前端GUI：
```bash
python gradio_gui.py
```

3. 访问Web界面：
```
http://localhost:7860
```

## 使用指南

### 对话生成
1. 在"对话生成"标签页输入提示
2. 选择模型（DeepSeek或Qwen）
3. 调整创造力和最大长度参数
4. 点击"生成回答"按钮

### 计算器
1. 在"计算器"标签页输入数学表达式
2. 点击"计算"按钮查看结果
3. 支持函数：sin, cos, log, sqrt等
4. 支持常量：pi, e, inf等

### 地图服务
1. 在"地图服务"标签页输入指令：
   - `geocode 地址`：地址转坐标
   - `reverse 经度,纬度`：坐标转地址
   - `search 关键词 城市`：地点搜索
2. 点击"执行"按钮查看结果

### 知识库
1. 将文档放入`knowledge_documents`目录
2. 在"知识库"标签页输入查询
3. 点击"搜索"按钮查看结果
4. 支持文件类型：PDF, TXT, DOCX

### 参数对比
1. 在"参数对比"标签页输入提示
2. 选择模型和最大长度
3. 点击"执行对比"按钮
4. 查看低温(0.7)和高温(1.2)输出对比

## 项目结构

```
llm-dialogue-system/
├── gradio_gui.py          # 前端界面
├── main.py                # 后端主程序
├── requirements.txt       # 依赖列表
├── .env                   # 环境变量配置
├── modules/
│   ├── amap_integration.py   # 高德地图集成
│   ├── calculator.py         # 计算器模块
│   ├── knowledge_base.py     # 知识库管理
│   ├── llm_integration.py    # DeepSeek集成
│   ├── output_validation.py  # 输出验证
│   ├── preprocessing.py      # 输入预处理
│   └── qwen_integration.py   # 通义千问集成
└── knowledge_documents/   # 知识库文档存储
```

## 配置选项

### 知识库配置
- 文档目录：`knowledge_documents/`
- 索引文件：`knowledge_index.idx`
- 支持格式：PDF, TXT, DOCX

## 常见问题

### 服务启动失败
1. 检查API密钥是否在.env文件中正确设置
2. 确保端口8000和7860未被占用
3. 检查Python版本是否为3.10+

### 地图服务不工作
1. 确保已申请高德地图API密钥
2. 检查AMAP_API_KEY是否在.env中设置
3. 验证网络连接是否正常

### 知识库无结果
1. 确保文档已放入`knowledge_documents/`目录
2. 检查文档格式是否支持（PDF/TXT/DOCX）
3. 尝试重建知识库索引

## 贡献指南

欢迎贡献！请遵循以下步骤：
1. Fork项目仓库
2. 创建特性分支（`git checkout -b feature/AmazingFeature`）
3. 提交更改（`git commit -m 'Add some AmazingFeature'`）
4. 推送到分支（`git push origin feature/AmazingFeature`）
5. 提交Pull Request

## 许可证

本项目采用 [MIT 许可证](LICENSE)
