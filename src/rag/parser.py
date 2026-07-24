"""简历解析器 - 支持 PDF (PyMuPDF) / DOCX (python-docx) / MD / TXT"""
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from src.config import settings


@dataclass
class ParsedResume:
    """结构化简历数据"""
    name: str = ""
    email: str = ""
    phone: str = ""
    education: List[Dict[str, str]] = field(default_factory=list)
    skills: List[Dict[str, Any]] = field(default_factory=list)
    projects: List[Dict[str, Any]] = field(default_factory=list)
    work_experience: List[Dict[str, Any]] = field(default_factory=list)
    achievements: List[Dict[str, str]] = field(default_factory=list)
    raw_text: str = ""
    sections: Dict[str, str] = field(default_factory=dict)


@dataclass
class Document:
    """文档块"""
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunk_id: str = ""


class ResumeParser:
    """简历解析器：支持 PDF / DOCX / MD / TXT"""

    def __init__(self):
        self.supported = settings.get_supported_formats()

    def parse(self, file_path: str) -> ParsedResume:
        """解析简历文件，返回结构化数据"""
        path = Path(file_path)
        ext = path.suffix.lower().lstrip(".")
        if ext not in self.supported:
            raise ValueError(f"不支持的格式: .{ext}，支持: {self.supported}")

        if not path.exists():
            raise FileNotFoundError(f"简历文件不存在: {file_path}")

        # Step 1: 提取原始文本
        raw_text = self._extract_text(file_path, ext)

        # Step 2: 按段落分割
        paragraphs = self._split_paragraphs(raw_text)

        # Step 3: 识别简历分区
        sections = self._identify_sections(paragraphs)

        # Step 4: 构建结构化数据
        parsed = ParsedResume(raw_text=raw_text, sections=sections)

        # 提取基本信息
        parsed.name = self._extract_name(raw_text)
        parsed.email = self._extract_email(raw_text)
        parsed.phone = self._extract_phone(raw_text)

        # 提取各模块
        parsed.skills = self._extract_skills(sections)
        parsed.projects = self._extract_projects(sections)
        parsed.work_experience = self._extract_work_experience(sections)
        parsed.education = self._extract_education(sections)
        parsed.achievements = self._extract_achievements(sections, parsed.projects)

        return parsed

    def to_documents(self, parsed: ParsedResume) -> List[Document]:
        """将结构化简历转为文档块列表（用于向量化）"""
        documents = []

        # 技能块
        for i, skill in enumerate(parsed.skills):
            content = f"技能: {skill.get('name', '')}"
            if skill.get('category'):
                content += f" (类别: {skill['category']})"
            if skill.get('level'):
                content += f" (水平: {skill['level']})"
            documents.append(Document(
                content=content,
                metadata={"type": "skill", "index": i, **skill},
                chunk_id=f"skill_{i}"
            ))

        # 项目块
        for i, proj in enumerate(parsed.projects):
            parts = [f"项目: {proj.get('name', '')}"]
            if proj.get('role'):
                parts.append(f"角色: {proj['role']}")
            if proj.get('tech_stack'):
                techs = proj['tech_stack'] if isinstance(proj['tech_stack'], list) else [proj['tech_stack']]
                parts.append(f"技术栈: {', '.join(techs)}")
            if proj.get('description'):
                parts.append(f"描述: {proj['description']}")
            if proj.get('key_result'):
                parts.append(f"关键成果: {proj['key_result']}")
            documents.append(Document(
                content="\n".join(parts),
                metadata={"type": "project", "index": i, **proj},
                chunk_id=f"project_{i}"
            ))

        # 工作经历块
        for i, work in enumerate(parsed.work_experience):
            parts = [f"工作经历: {work.get('company', '')} - {work.get('position', '')}"]
            if work.get('duration'):
                parts.append(f"时间: {work['duration']}")
            if work.get('description'):
                parts.append(f"描述: {work['description']}")
            documents.append(Document(
                content="\n".join(parts),
                metadata={"type": "work", "index": i, **work},
                chunk_id=f"work_{i}"
            ))

        # 成果/成就块
        for i, ach in enumerate(parsed.achievements):
            documents.append(Document(
                content=f"成果: {ach.get('description', '')}",
                metadata={"type": "achievement", "index": i, **ach},
                chunk_id=f"achievement_{i}"
            ))

        # 教育块
        for i, edu in enumerate(parsed.education):
            parts = [f"教育: {edu.get('school', '')} - {edu.get('degree', '')}"]
            if edu.get('major'):
                parts.append(f"专业: {edu['major']}")
            if edu.get('time'):
                parts.append(f"时间: {edu['time']}")
            documents.append(Document(
                content="\n".join(parts),
                metadata={"type": "education", "index": i, **edu},
                chunk_id=f"education_{i}"
            ))

        return documents

    # ===== 私有方法 =====

    def _extract_text(self, file_path: str, ext: str) -> str:
        """根据扩展名提取文本"""
        if ext == "pdf":
            return self._extract_pdf(file_path)
        elif ext == "docx":
            return self._extract_docx(file_path)
        else:  # md, txt
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()

    def _extract_pdf(self, file_path: str) -> str:
        """使用 PyMuPDF 提取 PDF 文本"""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(file_path)
            text_parts = []
            for page in doc:
                text_parts.append(page.get_text("text"))
            doc.close()
            return "\n".join(text_parts)
        except ImportError:
            raise ImportError("需要安装 PyMuPDF: pip install PyMuPDF")

    def _extract_docx(self, file_path: str) -> str:
        """使用 python-docx 提取 Word 文本，失败时回退到 XML 直接解析"""
        try:
            from docx import Document as DocxDocument
            doc = DocxDocument(file_path)
            text_parts = []

            # 提取段落
            for para in doc.paragraphs:
                if para.text.strip():
                    text_parts.append(para.text.strip())

            # 提取表格
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(
                        cell.text.strip() for cell in row.cells if cell.text.strip()
                    )
                    if row_text:
                        text_parts.append(row_text)

            result = "\n\n".join(text_parts)

            # 如果 python-docx 提取结果太短，回退到 XML 直接解析
            if len(result) < 100:
                result = self._extract_docx_xml(file_path)

            return result
        except ImportError:
            raise ImportError("需要安装 python-docx: pip install python-docx")

    def _extract_docx_xml(self, file_path: str) -> str:
        """从 DOCX 的 XML 中直接提取文本（处理特殊格式）"""
        import zipfile
        import xml.etree.ElementTree as ET

        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

        with zipfile.ZipFile(file_path) as z:
            with z.open('word/document.xml') as f:
                tree = ET.parse(f)

        root = tree.getroot()
        paragraphs = []

        for para_elem in root.findall('.//w:p', ns):
            # 检查是否是分隔符（分页符等）
            pPr = para_elem.find('w:pPr', ns)
            texts = []
            for t in para_elem.findall('.//w:t', ns):
                if t.text:
                    texts.append(t.text)
            if texts:
                line = ''.join(texts)
                # 检测可能的分节标记
                if line.strip():
                    paragraphs.append(line.strip())

        return '\n\n'.join(paragraphs)


    def _split_paragraphs(self, text: str) -> List[str]:
        """按段落分割文本"""
        # 按双换行分割
        paras = re.split(r'\n\s*\n', text)
        return [p.strip() for p in paras if p.strip()]

    def _identify_sections(self, paragraphs: List[str]) -> Dict[str, str]:
        """识别简历分区（技能/项目/工作经历/教育）"""
        sections = {}
        current_section = "header"
        current_content: List[str] = []

        # 常见分区标题关键词
        section_keywords = {
            "skills": ["技能", "技术栈", "专业技能", "技术能力", "skills", "technologies"],
            "projects": ["项目经验", "项目经历", "项目", "projects", "project experience"],
            "work": ["工作经历", "工作经验", "实习经历", "work experience", "experience", "employment"],
            "education": ["教育背景", "教育经历", "学历", "education", "academic"],
            "achievements": ["获奖", "荣誉", "证书", "achievements", "awards", "honors"],
        }

        for para in paragraphs:
            para_clean = re.sub(r'^#+\s*', '', para.strip())
            # 只检查段落的第一行是否匹配分区标题（而非整个段落）
            first_line = para.strip().split("\n")[0].strip()
            first_line_clean = re.sub(r'^#+\s*', '', first_line).lower()
            matched = False
            for section_name, keywords in section_keywords.items():
                if any(kw in first_line_clean for kw in keywords) and len(first_line) < 50:
                    # 保存上一个分区
                    if current_content:
                        sections[current_section] = "\n".join(current_content)
                    current_section = section_name
                    current_content = []
                    # 提取标题行之后的内容
                    lines = para.strip().split("\n")
                    remaining = [l.strip() for l in lines[1:] if l.strip() and not l.strip().startswith("#")]
                    if remaining:
                        current_content.extend(remaining)
                    matched = True
                    break
            if not matched:
                current_content.append(para)

        # 保存最后一个分区
        if current_content:
            sections[current_section] = "\n".join(current_content)

        return sections

    def _extract_name(self, text: str) -> str:
        """尝试从简历中提取姓名"""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines[:10]:
            # 跳过 markdown 标题
            if line.startswith("#"):
                continue
            # 先尝试匹配"姓名"标签
            name_match = re.search(r'(?:姓名|名字)[：:]\s*(\S{2,4})', line)
            if name_match:
                return name_match.group(1)
            # 尝试按常见分隔符拆分
            parts = re.split(r'\s*[|｜\t]{2,}\s*', line)
            for part in parts:
                part = part.strip()
                if not part or len(part) > 15:
                    continue
                if any(kw in part.lower() for kw in [
                    "简历", "resume", "cv", "电话", "邮箱", "email", "手机",
                    "地址", "github", "linkedin", "博客", "blog", "姓名",
                ]):
                    continue
                if "@" in part:
                    continue
                if re.search(r'\d{8,}', part):
                    continue
                # 查找2-4个连续中文字符或2-3个英文单词
                chinese_name = re.search(r'([一-鿿]{2,4})', part)
                if chinese_name:
                    return chinese_name.group(1)
        return "未知"

    def _extract_email(self, text: str) -> str:
        """提取邮箱"""
        match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        return match.group(0) if match else ""

    def _extract_phone(self, text: str) -> str:
        """提取手机号"""
        match = re.search(r'1[3-9]\d{9}', text)
        return match.group(0) if match else ""

    def _extract_skills(self, sections: Dict[str, str]) -> List[Dict[str, Any]]:
        """提取技能列表"""
        skills = []
        skill_text = sections.get("skills", "")
        if not skill_text:
            return skills

        # 按行或逗号分割
        skill_lines = re.split(r'[,，\n]', skill_text)
        for line in skill_lines:
            line = line.strip()
            if not line or len(line) > 30:
                continue
            # 简单分类
            category = "other"
            line_lower = line.lower()
            if any(kw in line_lower for kw in ["python", "java", "go", "rust", "c++", "typescript", "javascript"]):
                category = "programming"
            elif any(kw in line_lower for kw in ["react", "vue", "fastapi", "django", "spring"]):
                category = "framework"
            elif any(kw in line_lower for kw in ["mysql", "redis", "mongodb", "chroma", "faiss", "elasticsearch"]):
                category = "database"
            elif any(kw in line_lower for kw in ["docker", "kubernetes", "git", "ci/cd", "linux"]):
                category = "devops"
            elif any(kw in line_lower for kw in ["machine learning", "nlp", "llm", "rag", "深度学习"]):
                category = "ai"
            skills.append({"name": line, "category": category})

        return skills

    def _extract_projects(self, sections: Dict[str, str]) -> List[Dict[str, Any]]:
        """提取项目经验"""
        projects = []
        project_text = sections.get("projects", "")
        if not project_text:
            return projects

        # 按项目标题分割（如 "项目名 | 角色 | 时间"）
        project_blocks = re.split(r'\n(?=[A-Za-z一-鿿][^\n]{0,50}(?:项目|系统|平台|助手|工具))', project_text)

        for block in project_blocks:
            block = block.strip()
            if not block:
                continue
            lines = block.split("\n")
            name = lines[0].strip() if lines else "未知项目"

            # 提取技术栈
            tech_stack = []
            tech_match = re.findall(r'(?:技术栈|技术|tech)[：:]\s*(.+?)(?:\n|$)', block, re.IGNORECASE)
            if tech_match:
                tech_stack = [t.strip() for t in re.split(r'[,，、]', tech_match[0])]

            # 提取角色
            role = ""
            role_match = re.search(r'(?:角色|岗位|职位)[：:]\s*(.+?)(?:\n|$)', block)
            if role_match:
                role = role_match.group(1).strip()

            projects.append({
                "name": name,
                "description": block,
                "role": role,
                "tech_stack": tech_stack,
                "key_result": self._extract_key_result(block),
            })

        return projects

    def _extract_key_result(self, text: str) -> str:
        """从文本中提取关键成果（包含数字指标的句子）"""
        # 匹配包含百分号、数字+单位、提升/降低/优化等关键词的句子
        patterns = [
            r'[^。\n]*(?:\d+%|提升\d+|降低\d+|优化\d+|减少\d+)[^。\n]*',
            r'[^。\n]*(?:从\d+到\d+|提高\d+倍|节省\d+)[^。\n]*',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                return matches[0].strip()
        return ""

    def _extract_work_experience(self, sections: Dict[str, str]) -> List[Dict[str, Any]]:
        """提取工作经历"""
        work = []
        work_text = sections.get("work", "")
        if not work_text:
            return work

        # 按公司名分割
        blocks = re.split(r'\n(?=[A-Za-z一-鿿][^\n]{0,50}(?:公司|科技|集团|有限|实验室|研究院))', work_text)
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            lines = block.split("\n")
            company = lines[0].strip() if lines else "未知公司"

            # 提取职位和时间
            position = ""
            duration = ""
            pos_match = re.search(r'(?:职位|岗位|角色)[：:]\s*(.+?)(?:\n|$)', block)
            if pos_match:
                position = pos_match.group(1).strip()
            time_match = re.search(r'(?:时间|日期|period)[：:]\s*(.+?)(?:\n|$)', block)
            if time_match:
                duration = time_match.group(1).strip()

            work.append({
                "company": company,
                "position": position,
                "duration": duration,
                "description": block,
            })

        return work

    def _extract_education(self, sections: Dict[str, str]) -> List[Dict[str, str]]:
        """提取教育背景"""
        education = []
        edu_text = sections.get("education", "")
        if not edu_text:
            return education

        lines = edu_text.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            education.append({
                "school": line,
                "degree": "",
                "major": "",
                "time": "",
            })

        return education

    def _extract_achievements(
        self, sections: Dict[str, str], projects: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """提取成就和获奖"""
        achievements = []

        # 从成就分区提取
        ach_text = sections.get("achievements", "")
        if ach_text:
            for line in ach_text.split("\n"):
                line = line.strip()
                if line and len(line) > 5:
                    achievements.append({"description": line})

        # 从项目中提取量化成果
        for proj in projects:
            if proj.get("key_result"):
                achievements.append({
                    "description": f"[{proj.get('name', '项目')}] {proj['key_result']}"
                })

        return achievements
