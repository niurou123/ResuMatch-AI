"""父子分块器 - Parent-Child Chunking 策略"""
import re
from typing import List, Tuple, Dict
from src.rag.parser import Document
from src.config import settings


class ParentChildChunker:
    """
    父子分块策略：
    - 子块（child）：2-3 句小粒度，用于向量检索（提高精度）
    - 父块（parent）：完整段落/项目，用于 LLM 上下文（保证完整）

    检索命中 child → 通过 parent_map 找到 parent → 将完整 parent 送入 LLM
    """

    def __init__(self, child_sentence_size: int = None):
        self.child_size = child_sentence_size or settings.CHUNK_SIZE
        self.parent_min_length = settings.PARENT_CHUNK_MIN_LENGTH

    def chunk_documents(
        self, documents: List[Document]
    ) -> Tuple[List[Document], List[Document], Dict[str, int]]:
        """
        对文档列表进行父子分块

        返回:
        - child_chunks: 子块列表（存入 ChromaDB 用于检索）
        - parent_chunks: 父块列表（检索时返回完整上下文）
        - parent_map: child_id → parent_id 映射
        """
        all_children = []
        all_parents = []
        parent_map = {}

        for doc in documents:
            children, parents, mapping = self.chunk_single(doc)
            # 调整 ID 以避免冲突
            offset_pid = len(all_parents)
            offset_cid = len(all_children)

            for child in children:
                child.chunk_id = f"{doc.chunk_id}_child_{offset_cid}"
                all_children.append(child)
                offset_cid += 1

            for parent in parents:
                parent.chunk_id = f"{doc.chunk_id}_parent_{offset_pid}"
                all_parents.append(parent)

            for child_local_id, parent_local_id in mapping.items():
                global_child_id = child_local_id  # 已在上面更新
                parent_map[global_child_id] = parent_local_id + offset_pid

        return all_children, all_parents, parent_map

    def chunk_single(
        self, document: Document
    ) -> Tuple[List[Document], List[Document], Dict[str, int]]:
        """
        对单个文档进行父子分块

        返回 (children, parents, parent_map)
        """
        text = document.content
        metadata = document.metadata

        # 父块 = 整个文档
        parent = Document(
            content=text,
            metadata={**metadata, "chunk_type": "parent"},
            chunk_id="parent_0",
        )

        # 如果文档太短，子块 = 父块
        if len(text) < self.parent_min_length:
            child = Document(
                content=text,
                metadata={**metadata, "chunk_type": "child", "parent_id": 0},
                chunk_id="child_0",
            )
            return [child], [parent], {"child_0": 0}

        # 按句子分割
        sentences = self._split_sentences(text)

        # 将句子分组为子块
        children = []
        for i in range(0, len(sentences), self.child_size):
            group = sentences[i:i + self.child_size]
            child_text = "。".join(group) + "。" if group[-1].endswith("。") else ""
            child = Document(
                content=child_text.strip(),
                metadata={**metadata, "chunk_type": "child", "parent_id": 0},
                chunk_id=f"child_{len(children)}",
            )
            children.append(child)

        parent_map = {child.chunk_id: 0 for child in children}
        return children, [parent], parent_map

    def chunk_text(
        self, text: str, metadata: Dict = None
    ) -> Tuple[List[Document], List[Document], Dict[str, int]]:
        """对纯文本进行父子分块（用于简历原始文本）"""
        doc = Document(content=text, metadata=metadata or {})
        return self.chunk_single(doc)

    def chunk_by_sections(
        self, text: str, section_pattern: str = r'\n(?=##?\s|[A-Z一-鿿][^\n]{0,30}(?:项目|技能|经历|教育|背景))'
    ) -> Tuple[List[Document], List[Document], Dict[str, int]]:
        """
        按章节分块（适用于 Markdown 格式简历）
        每个章节作为一个 parent
        """
        # 按章节标题分割
        sections = re.split(section_pattern, text)
        sections = [s.strip() for s in sections if s.strip()]

        all_children = []
        all_parents = []
        parent_map = {}

        for pid, section in enumerate(sections):
            # Parent = 完整章节
            parent = Document(
                content=section,
                metadata={"chunk_type": "parent", "section_id": pid},
                chunk_id=f"parent_{pid}",
            )
            all_parents.append(parent)

            # Child = 章节内的句子组
            sentences = self._split_sentences(section)
            for i in range(0, len(sentences), self.child_size):
                group = sentences[i:i + self.child_size]
                child_text = ""
                for s in group:
                    if s.endswith(("。", "！", "？", ".", "!", "?")):
                        child_text += s
                    else:
                        child_text += s + "。"

                child = Document(
                    content=child_text.strip(),
                    metadata={"chunk_type": "child", "parent_id": pid, "section_id": pid},
                    chunk_id=f"child_{pid}_{len(all_children)}",
                )
                all_children.append(child)
                parent_map[child.chunk_id] = pid

        return all_children, all_parents, parent_map

    def _split_sentences(self, text: str) -> List[str]:
        """中文友好的句子分割"""
        # 在句号、问号、感叹号、分号、换行处分割
        raw_sentences = re.split(r'(?<=[。！？.!?；;])\s*', text)
        # 对过长的句子进一步按逗号分割
        result = []
        for sent in raw_sentences:
            sent = sent.strip()
            if not sent:
                continue
            if len(sent) > 100:
                sub_parts = re.split(r'(?<=[，,、])\s*', sent)
                result.extend([s.strip() for s in sub_parts if s.strip()])
            else:
                result.append(sent)
        return result

    def get_parent_context(
        self, child_chunk_id: str, children: List[Document],
        parents: List[Document], parent_map: Dict[str, int]
    ) -> str:
        """根据命中的 child chunk ID 获取对应的 parent 完整上下文"""
        if child_chunk_id not in parent_map:
            return ""
        parent_id = parent_map[child_chunk_id]
        if parent_id < len(parents):
            return parents[parent_id].content
        return ""
