"""简历解析器测试"""
import pytest
from pathlib import Path
from src.rag.parser import ResumeParser, ParsedResume, Document


class TestResumeParser:
    """简历解析器测试套件"""

    def test_parse_txt(self, sample_resume_text, tmp_path):
        """测试 TXT 格式解析"""
        # 写入临时文件
        file_path = tmp_path / "resume.txt"
        file_path.write_text(sample_resume_text, encoding="utf-8")

        parser = ResumeParser()
        result = parser.parse(str(file_path))

        assert isinstance(result, ParsedResume)
        assert result.name == "张三"
        assert result.email == "zhangsan@example.com"
        assert result.phone == "13800138000"

    def test_extract_name(self):
        """测试姓名提取"""
        parser = ResumeParser()
        text = "李四\n联系方式: lisi@test.com\n## 技能\nPython"
        name = parser._extract_name(text)
        assert name == "李四"

    def test_extract_email(self):
        """测试邮箱提取"""
        parser = ResumeParser()
        assert parser._extract_email("邮箱: test@example.com") == "test@example.com"
        assert parser._extract_email("no email here") == ""

    def test_extract_phone(self):
        """测试手机号提取"""
        parser = ResumeParser()
        assert parser._extract_phone("电话: 13812345678") == "13812345678"
        assert parser._extract_phone("no phone") == ""

    def test_identify_sections(self):
        """测试分区识别"""
        parser = ResumeParser()
        paragraphs = [
            "张三",
            "## 技能",
            "Python, Java, Go",
            "## 项目经验",
            "PaperPilot - AI科研助手",
            "技术栈: LangGraph, Python",
        ]
        sections = parser._identify_sections(paragraphs)

        assert "skills" in sections
        assert "projects" in sections
        assert "Python" in sections["skills"]
        assert "PaperPilot" in sections["projects"]

    def test_extract_skills(self, sample_resume_text):
        """测试技能提取"""
        parser = ResumeParser()

        # 手动构建 sections
        sections = {
            "skills": "Python, Java, FastAPI\nLangGraph, LangChain\nDocker, Kubernetes",
        }

        skills = parser._extract_skills(sections)
        assert len(skills) > 0
        skill_names = [s["name"] for s in skills]
        assert "Python" in skill_names
        assert "Docker" in skill_names
        # 验证分类
        python_skill = next(s for s in skills if s["name"] == "Python")
        assert python_skill["category"] == "programming"

    def test_extract_projects(self, sample_resume_text):
        """测试项目提取"""
        parser = ResumeParser()

        paragraphs = parser._split_paragraphs(sample_resume_text)
        sections = parser._identify_sections(paragraphs)
        projects = parser._extract_projects(sections)

        assert len(projects) > 0
        project_names = [p["name"] for p in projects]
        assert any("PaperPilot" in name for name in project_names)

    def test_to_documents(self, sample_parsed_resume):
        """测试结构化数据转文档块"""
        parser = ResumeParser()
        docs = parser.to_documents(sample_parsed_resume)

        assert len(docs) > 0
        # 应该有技能、项目、成果、教育等类型的文档
        types = set(doc.metadata.get("type") for doc in docs)
        assert "skill" in types
        assert "project" in types
        assert "achievement" in types

        # 验证内容完整性
        skill_docs = [d for d in docs if d.metadata["type"] == "skill"]
        assert any("Python" in d.content for d in skill_docs)

    def test_parse_nonexistent_file(self):
        """测试解析不存在的文件"""
        parser = ResumeParser()
        with pytest.raises(FileNotFoundError):
            parser.parse("/nonexistent/resume.pdf")

    def test_parse_unsupported_format(self):
        """测试不支持的格式"""
        parser = ResumeParser()
        with pytest.raises(ValueError, match="不支持的格式"):
            parser.parse("resume.xyz")
