# modules/knowledge_base.py - 知识库处理
import os
import sys
from pathlib import Path
import logging
import numpy as np
from PyPDF2 import PdfReader
from docx import Document
from sentence_transformers import SentenceTransformer
import faiss
from typing import List, Tuple, Dict, Callable, Optional
import re

# 获取项目根目录
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

logger = logging.getLogger("knowledge_base")

# 配置
CHUNK_SIZE = 512
OVERLAP_SIZE = 50
EMBEDDING_MODEL = "local_models/all-MiniLM-L6-v2"
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".docx"}


class KnowledgeBase:
    def __init__(self, model_name: str = None):
        # 默认使用项目内的模型路径
        if model_name is None:
            model_name = BASE_DIR / "local_models" / "all-MiniLM-L6-v2"

        # 确保路径是绝对路径
        model_path = Path(model_name)
        if not model_path.is_absolute():
            model_path = BASE_DIR / model_path

        # 检查路径是否存在
        if not model_path.exists():
            # 创建默认模型目录
            local_model_dir = BASE_DIR / "local_models"
            local_model_dir.mkdir(exist_ok=True)
            logger.error(f"模型路径不存在: {model_path}. 请将模型下载到 {local_model_dir}")
            raise RuntimeError(f"模型路径不存在: {model_path}")

        try:
            self.model = SentenceTransformer(str(model_path))
            logger.info(f"成功加载模型: {model_path}")
        except Exception as e:
            logger.error(f"模型加载失败: {str(e)}")
            raise RuntimeError("模型加载失败") from e

        self.index: Optional[faiss.Index] = None
        self.documents: List[str] = []
        self.metadata: List[Dict] = []
        self.dimension: Optional[int] = None

        # 文件处理器注册
        self.file_handlers: Dict[str, Callable] = {
            ".pdf": self._handle_pdf,
            ".txt": self._handle_text,
            ".docx": self._handle_docx
        }

    def release(self):
        """释放资源"""
        self.index = None
        self.documents = []
        self.metadata = []
        self.dimension = None
        logger.info("知识库资源已释放")

    def load_document(self, file_path: str) -> List[Tuple[str, dict]]:
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return []

        ext = os.path.splitext(file_path)[1].lower()
        if ext not in self.file_handlers:
            logger.warning(f"不支持的文件类型: {file_path}")
            return []

        # 限制文件最大大小，避免加载超大文件
        max_file_size = 50 * 1024 * 1024
        file_size = os.path.getsize(file_path)
        if file_size > max_file_size:
            logger.warning(f"文件过大，跳过加载: {file_path}, 大小: {file_size}")
            return []

        try:
            return self.file_handlers[ext](file_path)
        except Exception as e:
            logger.error(f"处理文档失败: {file_path}, 错误: {str(e)}")
            return []

    def _handle_pdf(self, file_path: str) -> List[Tuple[str, dict]]:
        """处理PDF文件"""
        chunks = []
        with open(file_path, "rb") as f:
            reader = PdfReader(f)
            for page_num, page in enumerate(reader.pages):
                try:
                    text = page.extract_text()
                    if text:
                        chunks.extend(self._chunk_text(text, file_path, page_num))
                except Exception as e:
                    logger.warning(f"PDF页面提取失败: {file_path} 页码 {page_num}, 错误: {str(e)}")
        return chunks

    def _handle_text(self, file_path: str) -> List[Tuple[str, dict]]:
        """处理文本文件"""
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        return self._chunk_text(text, file_path, 0)

    def _handle_docx(self, file_path: str) -> List[Tuple[str, dict]]:
        """处理Word文档"""
        doc = Document(file_path)
        text = "\n".join([para.text for para in doc.paragraphs])
        return self._chunk_text(text, file_path, 0)

    # 知识库类中的分块方法优化
    def _chunk_text(self, text: str, source: str, page: int) -> List[Tuple[str, dict]]:
        if not text.strip():
            return []

        # 敏感词过滤（保持不变）
        try:
            from .preprocessing import sensitive_filter
            text = sensitive_filter.filter_text(text)
        except Exception as e:
            # 备用过滤方案
            text = re.sub(r'\b(暴力|色情|毒品|赌博|诈骗|恐怖主义)\b', '***', text, flags=re.IGNORECASE)

        chunks = []
        text_len = len(text)
        start = 0

        # 使用更高效的分块策略
        while start < text_len:
            # 确定块结束位置
            end = min(start + CHUNK_SIZE, text_len)

            # 只向后查找一次边界（提高效率）
            if end < text_len:
                # 查找最近的边界字符（句号、分号等）
                boundary_chars = {'.', '。', ';', '；', '!', '！', '?', '？', '\n'}
                for i in range(end, min(end + 50, text_len)):  # 最多向后查50字符
                    if text[i] in boundary_chars:
                        end = i + 1  # 包含边界字符
                        break

            chunk = text[start:end]

            # 跳过过短的块（提高质量）
            if len(chunk.strip()) > 20:  # 至少20个字符
                chunks.append((chunk, {
                    "source": source,
                    "page": page,
                    "start": start,
                    "end": end
                }))

            # 高效重叠处理
            start = end - OVERLAP_SIZE if (end - OVERLAP_SIZE) > start else end

        return chunks

    def build_index(self, documents_dir: str):
        """从目录构建知识库索引"""
        documents_path = Path(documents_dir)
        if not documents_path.is_dir():
            logger.error(f"目录不存在: {documents_dir}")
            return

        # 清空现有索引
        self.index = None
        self.documents = []
        self.metadata = []

        # 处理目录中的所有文件
        for file_name in os.listdir(documents_path):
            file_path = documents_path / file_name
            if file_path.is_file():
                self.add_document(str(file_path))

        logger.info(f"知识库索引构建完成，共{len(self.documents)}个文本块")

    def add_document(self, file_path: str):
        """添加单个文档到知识库索引"""
        chunks_with_meta = self.load_document(file_path)
        if not chunks_with_meta:
            return

        texts = [chunk[0] for chunk in chunks_with_meta]
        meta_list = [chunk[1] for chunk in chunks_with_meta]

        # 生成嵌入向量
        embeddings = self.model.encode(texts, show_progress_bar=False)
        embeddings = embeddings.astype(np.float32)

        n = embeddings.shape[0]

        if self.index is None:
            # 初始化新索引
            self.dimension = embeddings.shape[1]
            self.index = faiss.IndexFlatL2(self.dimension)
            self.index.add(embeddings)
            self.documents = texts
            self.metadata = meta_list
        else:
            # 添加到现有索引
            if embeddings.shape[1] != self.dimension:
                logger.error(f"嵌入维度不匹配: 现有 {self.dimension}, 新 {embeddings.shape[1]}")
                return

            self.index.add(embeddings)
            self.documents.extend(texts)
            self.metadata.extend(meta_list)

        logger.info(f"添加文档成功: {file_path}, 新增 {n} 个文本块")


    def search(self, query: str, top_k: int = 3) -> List[Tuple[str, dict, float]]:
        """检索相关文档块"""
        if ".." in query or "/" in query:
            return []
        if self.index is None or not self.documents:
            logger.warning("知识库尚未构建")
            return []

        # 生成查询嵌入
        query_embedding = self.model.encode([query])
        query_embedding = query_embedding.astype(np.float32)

        # 确保top_k不超过文档块数量
        k = min(top_k, len(self.documents))
        if k <= 0:
            return []

        # 执行搜索 - 使用新版FAISS API
        try:
            distances, indices = self.index.search(query_embedding, k)
        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
            return []

        results = []
        for i in range(k):
            idx = indices[0, i]
            distance = distances[0, i]

            if 0 <= idx < len(self.documents):
                # 计算相似度分数 (1 / (1 + distance))
                similarity = np.exp(-distance / self.dimension)
                results.append((
                    self.documents[idx],
                    self.metadata[idx],
                    similarity
                ))

        # 按相似度降序排序
        results.sort(key=lambda x: x[2], reverse=True)
        return results

    def load_index(self, index_path: str):
        index_path = Path(index_path)
        if not index_path.exists():
            logger.error(f"索引文件不存在: {index_path}")
            return False

        try:
            self.index = faiss.read_index(str(index_path))
            self.dimension = self.index.d

            # 加载文档和元数据
            doc_path = index_path.with_suffix(".docs.npy")
            meta_path = index_path.with_suffix(".meta.npy")

            if doc_path.exists() and meta_path.exists():
                self.documents = np.load(str(doc_path), allow_pickle=True).tolist()
                self.metadata = np.load(str(meta_path), allow_pickle=True).tolist()

            logger.info(f"索引加载成功: {index_path}, 包含 {len(self.documents)} 个文档块")
            return True
        except Exception as e:
            logger.error(f"加载索引失败: {str(e)}")
            self.index = None
            self.dimension = None
            return False

    def save_index(self, index_path: str):
        if self.index is None:
            logger.warning("没有可保存的索引")
            return False

        try:
            index_path = Path(index_path)
            faiss.write_index(self.index, str(index_path))

            # 保存文档和元数据
            doc_path = index_path.with_suffix(".docs.npy")
            meta_path = index_path.with_suffix(".meta.npy")

            np.save(str(doc_path), np.array(self.documents, dtype=object))
            np.save(str(meta_path), np.array(self.metadata, dtype=object))

            logger.info(f"索引保存成功: {index_path}, 包含 {len(self.documents)} 个文档块")
            return True
        except Exception as e:
            logger.error(f"保存索引失败: {str(e)}")
            return False


# 不再创建全局实例，由主程序管理
knowledge_base = None
