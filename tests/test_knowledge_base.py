import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from modules import knowledge_base


def run_tests():
    # 构建模型路径
    model_path = root_dir / "local_models" / "all-MiniLM-L6-v2"

    # 确保模型目录存在
    model_path.parent.mkdir(exist_ok=True, parents=True)

    # 初始化知识库
    try:
        kb = knowledge_base.KnowledgeBase(model_name=str(model_path))
        print(f"成功加载模型: {model_path}")
    except Exception as e:
        print(f"模型加载失败: {str(e)}")
        print(f"请将模型下载到: {model_path}")
        return

    # 确保文档目录存在
    doc_dir = root_dir / "knowledge_documents"
    doc_dir.mkdir(exist_ok=True, parents=True)

    # 添加示例文档（如果目录为空）
    if not any(doc_dir.iterdir()):
        print("文档目录为空，创建示例文件...")
        (doc_dir / "example.txt").write_text("这是知识库的示例文档。包含关于人工智能基础大作业的信息。")

    # 构建索引
    print("构建知识库索引...")
    kb.build_index(str(doc_dir))

    # 执行语义搜索
    print("执行搜索测试...")
    results = kb.search("爬虫的用途和原理？", top_k=3)

    # 打印搜索结果
    print(f"找到 {len(results)} 个相关结果:")
    for i, (content, meta, score) in enumerate(results):
        print(f"\n结果 #{i + 1} (相似度: {score:.2f})")
        print(f"来源: {meta['source']} - 页码: {meta['page'] + 1}")
        print(f"内容: {content[:200]}...\n")

    # 保存索引
    index_path = root_dir / "knowledge_index.idx"
    if kb.save_index(str(index_path)):
        print(f"索引保存成功: {index_path}")

    # 测试索引加载
    print("测试索引加载...")
    new_kb = knowledge_base.KnowledgeBase(str(model_path))
    if new_kb.load_index(str(index_path)):
        print(f"索引加载成功，包含 {len(new_kb.documents)} 个文档块")
    else:
        print("索引加载失败")


if __name__ == "__main__":
    run_tests()
