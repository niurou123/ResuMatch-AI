"""ResuMatch AI - Streamlit 前端应用"""
import streamlit as st
import requests

# ===== 页面配置 =====
st.set_page_config(
    page_title="ResuMatch AI - Agent 面试助手",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_URL = "http://localhost:8000"


# ===== API 工具函数 =====
def api_health() -> bool:
    try:
        resp = requests.get(f"{API_URL}/api/v1/health", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def api_upload_resume(file) -> dict:
    files = {"file": (file.name, file.getvalue(), file.type)}
    resp = requests.post(f"{API_URL}/api/v1/resume/upload", files=files, timeout=120)
    return resp.json() if resp.status_code == 200 else {"success": False, "message": resp.text}


def api_get_profile() -> dict:
    resp = requests.get(f"{API_URL}/api/v1/resume/profile", timeout=10)
    return resp.json() if resp.status_code == 200 else {}


def api_interview_answer(question: str) -> dict:
    resp = requests.post(
        f"{API_URL}/api/v1/interview/answer",
        json={"question": question},
        timeout=120,
    )
    return resp.json() if resp.status_code == 200 else {"error": resp.text}



def api_mock_start(focus_areas, difficulty="intermediate") -> dict:
    resp = requests.post(
        f"{API_URL}/api/v1/mock/start",
        json={"focus_areas": focus_areas, "difficulty": difficulty},
        timeout=10,
    )
    return resp.json() if resp.status_code == 200 else {}


def api_mock_next(session_id: str, answer: str) -> dict:
    resp = requests.post(
        f"{API_URL}/api/v1/mock/next",
        json={"session_id": session_id, "answer": answer},
        timeout=60,
    )
    return resp.json() if resp.status_code == 200 else {}


def api_generate_intro(position: str = "", company: str = "", length: str = "1min") -> dict:
    resp = requests.post(
        f"{API_URL}/api/v1/intro/generate",
        json={"target_position": position, "target_company": company, "length": length},
        timeout=60,
    )
    return resp.json() if resp.status_code == 200 else {}


def api_match_jd(jd_text: str, position: str = "") -> dict:
    resp = requests.post(
        f"{API_URL}/api/v1/match/analyze",
        json={"jd_text": jd_text, "target_position": position},
        timeout=60,
    )
    return resp.json() if resp.status_code == 200 else {}


def api_system_info() -> dict:
    resp = requests.get(f"{API_URL}/api/v1/system/info", timeout=10)
    return resp.json() if resp.status_code == 200 else {}


# ===== 侧边栏 =====
def render_sidebar():
    with st.sidebar:
        st.title("🤖 ResuMatch AI")
        st.caption("Agent 面试助手 v2.0")

        # 系统状态
        if api_health():
            st.success("✅ API 已连接")
            info = api_system_info()
            if info:
                st.metric("模型", info.get("model", "N/A"))
                cols = info.get("collections", {})
                if sum(cols.values()) > 0:
                    st.metric("已索引资料", sum(cols.values()))
        else:
            st.error("❌ API 未连接")
            st.info("启动命令: `python -m src.api.main`")

        st.divider()

        # 导航
        page = st.radio(
            "📋 功能导航",
            ["📤 简历上传", "🎤 面试模拟", "📝 自我介绍", "📊 JD 匹配"],
            label_visibility="collapsed",
        )

        st.divider()
        st.caption("基于 LangGraph 多Agent协作")
        st.caption("DeepSeek + ChromaDB + bge-small-zh")

        return page


# ===== 页面：简历上传 =====
def page_resume_upload():
    st.header("📤 上传简历")
    st.markdown("支持 PDF / DOCX / MD / TXT 格式。上传后AI将自动解析并向量化您的简历。")

    uploaded = st.file_uploader(
        "拖拽或点击上传简历文件",
        type=["pdf", "docx", "md", "txt"],
        help="上传后系统会自动解析并构建个人画像",
    )

    if uploaded:
        with st.spinner("🔍 正在解析简历..."):
            result = api_upload_resume(uploaded)

        if result.get("success"):
            st.success(f"✅ {result.get('message', '解析成功')}")

            # 显示结构化结果
            profile = result.get("profile", {})
            collections = result.get("collections", {})

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("技能数", collections.get("skills", 0))
            with col2:
                st.metric("项目数", collections.get("projects", 0))
            with col3:
                st.metric("成果数", collections.get("achievements", 0))
            with col4:
                st.metric("教育", collections.get("education", 0))

            # 详细信息
            if profile:
                tabs = st.tabs(["基本信息", "技能", "项目经验", "成果"])

                with tabs[0]:
                    st.write(f"**姓名**: {profile.get('name', '未知')}")
                    st.write(f"**邮箱**: {profile.get('email', '')}")
                    st.json({k: v for k, v in profile.items()
                             if k not in ["skills", "projects", "achievements", "education"]},
                            expanded=False)

                with tabs[1]:
                    skills = profile.get("skills", [])
                    if skills:
                        for s in skills:
                            st.markdown(f"- `{s.get('name', '')}` *({s.get('category', '')})*")

                with tabs[2]:
                    projects = profile.get("projects", [])
                    for proj in projects:
                        with st.expander(f"📁 {proj.get('name', '项目')}"):
                            st.write(f"**角色**: {proj.get('role', '')}")
                            tech = proj.get("tech_stack", [])
                            if tech:
                                st.write(f"**技术栈**: {', '.join(tech)}")
                            result_text = proj.get("key_result", "")
                            if result_text:
                                st.write(f"**关键成果**: {result_text}")

                with tabs[3]:
                    achievements = profile.get("achievements", [])
                    for ach in achievements:
                        st.write(f"🏆 {ach.get('description', '')}")
        else:
            st.error(f"❌ 解析失败: {result.get('message', '未知错误')}")


# ===== 页面：面试模拟 =====
def page_interview():
    st.header("🎤 面试模拟")

    mode = st.radio("模式", ["单次问答", "多轮模拟"], horizontal=True)

    if mode == "单次问答":
        _single_qa_mode()
    else:
        _mock_interview_mode()


def _single_qa_mode():
    question = st.text_area(
        "输入面试问题",
        placeholder="例如：请介绍你在 PaperPilot 项目中的贡献...",
        height=120,
        key="qa_question",
    )

    if st.button("🚀 生成回答", type="primary", use_container_width=True):
        if not question.strip():
            st.error("请输入面试问题")
            return

        with st.spinner("🤔 正在检索你的经历并生成回答..."):
            result = api_interview_answer(question)
            if result.get("error"):
                st.error(result["error"])
            else:
                st.markdown(result.get("answer", ""))
                scores = result.get("review_scores", {})
                if scores:
                    cols = st.columns(5)
                    for i, (k, v) in enumerate(scores.items()):
                        with cols[i]:
                            st.metric(k, f"{v}/5")
                    st.info(f"📊 综合评分: {result.get('review_total', 0)}/25 | 修订{result.get('revision_count', 0)}轮")

                citations = result.get("citations", [])
                if citations:
                    with st.expander("📎 引用来源"):
                        for c in citations:
                            st.write(f"- [{c.get('collection', '')}] {c.get('text', '')}")


def _mock_interview_mode():
    if "mock_session" not in st.session_state:
        st.session_state.mock_session = None
        st.session_state.mock_round = 0
        st.session_state.mock_history = []

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("模拟面试")
    with col2:
        focus = st.multiselect(
            "关注领域",
            ["算法", "系统设计", "项目经验", "行为面试", "Agent开发"],
            default=["项目经验"],
        )
        difficulty = st.selectbox("难度", ["basic", "intermediate", "advanced"])

    if st.button("🎬 开始模拟面试", type="primary"):
        result = api_mock_start(focus, difficulty)
        st.session_state.mock_session = result.get("session_id")
        st.session_state.mock_round = 1
        st.session_state.mock_history = []
        st.session_state.current_question = result.get("first_question", "")
        st.rerun()

    if st.session_state.mock_session:
        st.info(f"📋 第 {st.session_state.mock_round} 轮")

        # 显示问题
        st.markdown(f"### 🎯 面试官提问")
        st.markdown(f"> {st.session_state.get('current_question', '')}")

        # 回答输入
        answer = st.text_area("你的回答", height=200, key=f"answer_{st.session_state.mock_round}")

        if st.button("📤 提交回答"):
            if not answer.strip():
                st.error("请输入你的回答")
            else:
                result = api_mock_next(st.session_state.mock_session, answer)
                st.session_state.mock_round = result.get("round_number", 0)
                st.session_state.current_question = result.get("question", "")

                if result.get("is_last"):
                    st.success("🎉 模拟面试完成！")
                    if result.get("session_summary"):
                        st.info(result["session_summary"])
                    st.session_state.mock_session = None
                st.rerun()


# ===== 页面：自我介绍 =====
def page_self_intro():
    st.header("📝 自我介绍生成器")
    st.markdown("根据简历自动生成不同长度的自我介绍（30秒 / 1分钟 / 3分钟）")

    col1, col2, col3 = st.columns(3)
    with col1:
        position = st.text_input("目标职位", placeholder="如：后端开发工程师")
    with col2:
        company = st.text_input("目标公司（可选）", placeholder="如：字节跳动")
    with col3:
        length = st.selectbox("默认长度", ["30s", "1min", "3min"])

    if st.button("✨ 生成自我介绍", type="primary", use_container_width=True):
        with st.spinner("生成中..."):
            result = api_generate_intro(position, company, length)

        if result:
            tabs = st.tabs(["⏱️ 30秒版", "⏱️ 1分钟版", "⏱️ 3分钟版"])

            with tabs[0]:
                intro = result.get("intro_30s", "")
                st.text_area("30秒自我介绍", intro, height=150, key="i30")
                st.caption(f"约 {len(intro)} 字")
                if intro:
                    st.button("📋 复制", key="copy30", on_click=lambda: st.write(intro))

            with tabs[1]:
                intro = result.get("intro_1min", "")
                st.text_area("1分钟自我介绍", intro, height=250, key="i60")
                st.caption(f"约 {len(intro)} 字")

            with tabs[2]:
                intro = result.get("intro_3min", "")
                st.text_area("3分钟自我介绍", intro, height=400, key="i180")
                st.caption(f"约 {len(intro)} 字")
        else:
            st.warning("请先上传简历")


# ===== 页面：JD 匹配 =====
def page_jd_match():
    st.header("📊 JD-简历匹配度分析")
    st.markdown("粘贴职位描述（JD），分析你的简历与职位的匹配程度")

    col1, col2 = st.columns([2, 1])
    with col1:
        jd_text = st.text_area(
            "粘贴 JD 内容",
            placeholder="粘贴职位描述全文...",
            height=300,
        )
    with col2:
        target_position = st.text_input("目标职位", placeholder="如：AI工程师")
        st.caption("系统将对比JD需求与你的技能、项目经验")

    if st.button("🔍 分析匹配度", type="primary", use_container_width=True):
        if not jd_text.strip():
            st.error("请粘贴 JD 内容")
            return

        with st.spinner("📊 分析中..."):
            result = api_match_jd(jd_text, target_position)

        if result:
            match_score = result.get("match_score", 0)
            st.metric("综合匹配度", f"{match_score}%")

            # 进度条
            st.progress(match_score / 100)

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("✅ 匹配的技能")
                matched = result.get("matched_skills", [])
                for s in matched[:10]:
                    st.markdown(f"- `{s}`")

            with col2:
                st.subheader("⚠️ 缺失的技能")
                missing = result.get("missing_skills", [])
                for s in missing[:10]:
                    st.markdown(f"- `{s}`")

            # 分析文本
            strength = result.get("strength_analysis", "")
            gap = result.get("gap_analysis", "")
            if strength:
                st.success(f"💪 {strength}")
            if gap:
                st.warning(f"📝 {gap}")

            missing_cats = result.get("missing_categories", [])
            if missing_cats:
                st.info(f"📚 建议补强的领域: {', '.join(missing_cats)}")
        else:
            st.warning("请先上传简历")


# ===== 主函数 =====
def main():
    page = render_sidebar()

    if page == "📤 简历上传":
        page_resume_upload()
    elif page == "🎤 面试模拟":
        page_interview()
    elif page == "📝 自我介绍":
        page_self_intro()
    elif page == "📊 JD 匹配":
        page_jd_match()


if __name__ == "__main__":
    main()
