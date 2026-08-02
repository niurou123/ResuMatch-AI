"""
ResuMatch AI — Streamlit 前端 (v3.0 Pro Design)

⚠️ DEPRECATED — 前端已迁移至 frontend/ (React)。
本文件不再作为主入口，仅作历史保留。请改用 React 前端：
    cd frontend && npm run dev   # 默认 http://localhost:5173
"""
import streamlit as st
import requests

# ===== 页面配置 =====
st.set_page_config(
    page_title="ResuMatch AI",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_URL = "http://localhost:8004"

# ===== 全局自定义 CSS — 深色专业主题 =====
st.markdown("""
<style>
  /* === 根变量 === */
  :root {
    --bg: #0a0a1a; --surface: #13132b; --surface2: #1a1a3e;
    --border: #2a2a5a; --text: #e0e0f0; --text2: #9090b0; --text3: #5e5e88;
    --primary: #6c5ce7; --primary2: #a78bfa; --gradient: linear-gradient(135deg, #6366f1, #8b5cf6);
    --success: #22c55e; --warn: #f59e0b; --danger: #ef4444;
  }
  /* === 全局 === */
  .stApp { background: var(--bg); }
  header[data-testid="stHeader"] { background: transparent !important; }
  .main .block-container { padding-top: 1.5rem; max-width: 1200px; }

  /* === 标题 === */
  h1 { font-size: 1.6rem !important; font-weight: 700 !important; color: var(--text) !important; letter-spacing: -0.02em; }
  h2 { font-size: 1.25rem !important; font-weight: 600 !important; color: var(--text) !important; }
  h3 { font-size: 1.05rem !important; font-weight: 600 !important; color: var(--text2) !important; }
  p, li, label { color: var(--text2) !important; font-size: 0.9rem; }

  /* === 侧边栏 === */
  [data-testid="stSidebar"] { background: #08081a !important; border-right: 1px solid var(--border) !important; }
  [data-testid="stSidebar"] h2 { font-size: 1.1rem !important; }
  [data-testid="stSidebar"] .stRadio label { color: var(--text2) !important; }
  [data-testid="stSidebar"] .stRadio [data-selected="true"] label { color: var(--primary2) !important; }

  /* === 按钮 === */
  .stButton > button {
    background: var(--gradient) !important; color: #fff !important;
    border: none !important; border-radius: 10px !important;
    padding: 0.6rem 1.5rem !important; font-weight: 600 !important;
    font-size: 0.9rem !important; letter-spacing: 0.02em;
    box-shadow: 0 2px 12px rgba(99,102,241,0.25);
    transition: all 0.2s ease;
  }
  .stButton > button:hover {
    box-shadow: 0 4px 20px rgba(99,102,241,0.4);
    transform: translateY(-1px);
  }
  .stButton > button:active { transform: translateY(0); }

  /* 次要按钮 */
  .stButton.secondary > button, button[kind="secondary"] {
    background: var(--surface2) !important; color: var(--text) !important;
    border: 1px solid var(--border) !important;
    box-shadow: none !important;
  }

  /* === 卡片 === */
  .card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 14px; padding: 1.5rem; margin-bottom: 1rem;
    transition: border-color 0.2s;
  }
  .card:hover { border-color: #3a3a6a; }
  .card-header { font-size: 0.85rem; font-weight: 600; color: var(--text3); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 1rem; }

  /* === Metric === */
  [data-testid="stMetric"] { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 1rem 1.2rem !important; }
  [data-testid="stMetric"] label { color: var(--text3) !important; font-size: 0.75rem !important; font-weight: 500 !important; text-transform: uppercase; letter-spacing: 0.04em; }
  [data-testid="stMetricValue"] { color: var(--text) !important; font-size: 1.5rem !important; font-weight: 700 !important; }

  /* === 文本输入 === */
  textarea, input[type="text"], .stTextArea textarea {
    background: var(--surface) !important; color: var(--text) !important;
    border: 1px solid var(--border) !important; border-radius: 10px !important;
    font-size: 0.9rem !important; padding: 0.8rem 1rem !important;
  }
  textarea:focus, input[type="text"]:focus { border-color: var(--primary) !important; box-shadow: 0 0 0 2px rgba(99,102,241,0.15) !important; }

  /* === Radio / Select === */
  .stRadio [data-testid="stMarkdownContainer"] p { color: var(--text2) !important; }
  .stSelectbox > div > div { background: var(--surface) !important; border-color: var(--border) !important; }

  /* === Progress === */
  .stProgress > div > div { background: var(--gradient) !important; border-radius: 6px; }

  /* === Tabs === */
  .stTabs [data-baseweb="tab-list"] { gap: 0; border-bottom: 1px solid var(--border); }
  .stTabs button { color: var(--text3) !important; border-radius: 8px 8px 0 0 !important; padding: 0.6rem 1.2rem !important; font-size: 0.85rem !important; }
  .stTabs button[aria-selected="true"] { color: var(--primary2) !important; border-bottom: 2px solid var(--primary) !important; }

  /* === Expander === */
  .streamlit-expanderHeader { background: var(--surface) !important; border: 1px solid var(--border) !important; border-radius: 10px !important; color: var(--text2) !important; font-weight: 500 !important; }
  .streamlit-expanderContent { background: var(--surface) !important; border: 1px solid var(--border) !important; border-top: none !important; border-radius: 0 0 10px 10px !important; }

  /* === Info/Success/Warning/Error === */
  .stAlert { border-radius: 10px !important; border: 1px solid !important; font-size: 0.85rem !important; }
  [data-testid="stInfo"] { background: rgba(99,102,241,0.1) !important; border-color: rgba(99,102,241,0.3) !important; }
  [data-testid="stSuccess"] { background: rgba(34,197,94,0.1) !important; border-color: rgba(34,197,94,0.3) !important; }
  [data-testid="stWarning"] { background: rgba(245,158,11,0.1) !important; border-color: rgba(245,158,11,0.3) !important; }
  [data-testid="stError"] { background: rgba(239,68,68,0.1) !important; border-color: rgba(239,68,68,0.3) !important; }

  /* === Divider === */
  hr { border-color: var(--border) !important; margin: 1.5rem 0 !important; }

  /* === File Uploader === */
  [data-testid="stFileUploader"] { border: 2px dashed var(--border) !important; border-radius: 14px !important; padding: 2rem !important; }

  /* === 状态指示灯 === */
  .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
  .dot.green { background: var(--success); box-shadow: 0 0 6px rgba(34,197,94,0.5); }
  .dot.red { background: var(--danger); box-shadow: 0 0 6px rgba(239,68,68,0.5); }
  .dot.yellow { background: var(--warn); box-shadow: 0 0 6px rgba(245,158,11,0.5); }

  /* === 渐变 Header === */
  .brand-header {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a78bfa 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text; font-weight: 800; letter-spacing: -0.03em;
  }

  /* === 标签 === */
  .tag {
    display: inline-block; padding: 2px 10px; border-radius: 20px;
    font-size: 0.75rem; font-weight: 500; margin-right: 6px;
  }
  .tag.skill { background: rgba(99,102,241,0.15); color: var(--primary2); }
  .tag.match { background: rgba(34,197,94,0.12); color: var(--success); }

  /* Agent DAG 可视化 */
  .dag-flow { display:flex; align-items:center; justify-content:center; gap:6px; flex-wrap:nowrap; padding:8px 0; overflow-x:auto; }
  .dag-node { display:flex; flex-direction:column; align-items:center; gap:3px; padding:6px 12px; border-radius:8px; min-width:56px; transition:all 0.25s; }
  .dag-node.pending { background:transparent; border:1px solid #2a2a5a; }
  .dag-node.running { background:rgba(245,158,11,0.08); border:1px solid #f59e0b; }
  .dag-node.success { background:rgba(34,197,94,0.08); border:1px solid #22c55e; }
  .dag-node.failed { background:rgba(239,68,68,0.08); border:1px solid #ef4444; }
  .dag-node .dag-label { font-size:0.72rem; color:#5e5e88; font-weight:500; white-space:nowrap; }
  .dag-node.running .dag-label { color:#f59e0b; }
  .dag-node.success .dag-label { color:#22c55e; }
  .dag-arrow { color:#2a2a5a; font-size:1.1rem; flex-shrink:0; }
  @keyframes pulse-dot { 0%,100%{opacity:1;} 50%{opacity:0.4;} }
  .pulsing { animation:pulse-dot 1.2s ease-in-out infinite; }

  /* Agent 详情折叠卡片 */
  .agent-detail { margin-bottom:4px; }
  .agent-detail summary { color:#a78bfa; font-size:0.82rem; cursor:pointer; padding:4px 0; }
  .agent-detail .body { padding:2px 0 2px 18px; font-size:0.8rem; color:#9090b0; line-height:1.8; }

  /* === 禁用 Streamlit 默认加载遮罩（页面变暗问题）=== */
  /* 全方位强制 opacity = 1，覆盖 Streamlit 所有可能的 opacity 变化 */
  .stApp,
  .stApp > div,
  .stApp > div > div,
  [data-testid="stAppViewContainer"],
  [data-testid="stAppViewContainer"] > div,
  [data-testid="stAppViewContainer"] > div > div,
  [data-testid="stAppViewContainer"] > div > div > div,
  section.main,
  section.main > div,
  section.main > div > div,
  .main .block-container,
  .main .block-container > div {
    opacity: 1 !important;
    transition: none !important;
  }

  /* 隐藏 Streamlit 默认的遮罩层和加载动画 */
  [data-testid="stAppViewContainer"]::before,
  [data-testid="stAppViewContainer"]::after,
  section.main::before,
  section.main::after {
    display: none !important;
  }

  /* 自定义优雅的加载指示器 */
  .loading-indicator {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px 20px;
    margin: 12px 0;
    background: rgba(99,102,241,0.08);
    border: 1px solid rgba(99,102,241,0.2);
    border-radius: 12px;
    color: var(--primary2);
    font-size: 0.9rem;
    font-weight: 500;
  }

  .loading-indicator .pulse-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--primary);
    animation: pulse-dot 1.2s ease-in-out infinite;
  }

  /* Streamlit 原生 spinner 美化 */
  [data-testid="stSpinner"] > div {
    background: transparent !important;
    border: none !important;
  }

  [data-testid="stSpinner"] > div > div {
    border-top-color: var(--primary) !important;
    animation-duration: 0.8s !important;
  }

  /* 隐藏所有可能的遮罩层和 backdrop */
  .stApp > div[style*="opacity"],
  [data-testid="stAppViewContainer"] > div[style*="opacity"],
  [data-testid="stAppViewContainer"] > div > div[style*="opacity"] {
    opacity: 1 !important;
  }

""", unsafe_allow_html=True)


# ===== API 工具函数 =====
@st.cache_data(ttl=30)
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
        json={"question": question}, timeout=120,
    )
    return resp.json() if resp.status_code == 200 else {"error": resp.text}


def api_mock_start(focus_areas, difficulty="intermediate") -> dict:
    resp = requests.post(
        f"{API_URL}/api/v1/mock/start",
        json={"focus_areas": focus_areas, "difficulty": difficulty}, timeout=10,
    )
    return resp.json() if resp.status_code == 200 else {}


def api_mock_next(session_id: str, answer: str) -> dict:
    resp = requests.post(
        f"{API_URL}/api/v1/mock/next",
        json={"session_id": session_id, "answer": answer}, timeout=60,
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
        json={"jd_text": jd_text, "target_position": position}, timeout=60,
    )
    return resp.json() if resp.status_code == 200 else {}


def api_match_projects(jd_text: str, position: str = "") -> dict:
    """项目-JD 智能匹配（三维度项目匹配 + 针对性生成）"""
    resp = requests.post(
        f"{API_URL}/api/v1/match/projects",
        json={"jd_text": jd_text, "target_position": position}, timeout=120,
    )
    return resp.json() if resp.status_code == 200 else {}


def api_system_info() -> dict:
    resp = requests.get(f"{API_URL}/api/v1/system/info", timeout=10)
    return resp.json() if resp.status_code == 200 else {}




def api_interview_stream(question: str):
    """流式面试问答（SSE）- 用于 Agent 可视化"""
    import json
    with requests.post(
        f"{API_URL}/api/v1/interview/stream",
        json={"question": question},
        stream=True, timeout=120,
    ) as resp:
        for raw_line in resp.iter_lines():
            if not raw_line:
                continue
            line = raw_line.decode("utf-8")
            if line.startswith("data: "):
                yield json.loads(line[6:])


def _render_dag(states):
    """渲染 DAG 工作流拓扑图"""
    nodes = [
        ("planner", "Planner"), ("router", "Router"), ("retrieval", "并行检索"),
        ("writer", "Writer"), ("review", "并行评审"), ("end", "完成"),
    ]
    def _dot(s):
        if s == "pending":
            return '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#3a3a5a;"></span>'
        if s == "running":
            return '<span class="pulsing" style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#f59e0b;"></span>'
        if s == "success":
            return '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#22c55e;box-shadow:0 0 4px rgba(34,197,94,0.5);"></span>'
        return '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#ef4444;box-shadow:0 0 4px rgba(239,68,68,0.5);"></span>'
    cells = []
    for nid, nlabel in nodes:
        s = states.get(nid, "pending")
        c = '<div class="dag-node %s">%s<div class="dag-label">%s</div></div>' % (s, _dot(s), nlabel)
        cells.append(c)
    arrows = ['<span class="dag-arrow">&rarr;</span>'] * (len(cells) - 1)
    result = []
    for i, cell in enumerate(cells):
        result.append(cell)
        if i < len(arrows):
            result.append(arrows[i])
    return '<div class="dag-flow">' + "".join(result) + '</div>'


def _render_detail_section(node_data, writer_entries, review_entries):
    """渲染各 Agent 详情折叠区"""
    parts = []
    if "planner" in node_data:
        d = node_data["planner"]
        line = '<details class="agent-detail"><summary><span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:#22c55e;margin-right:6px;"></span> Planner - '
        line += d.get("description", "")
        line += '</summary><div class="body">检索: ' + ", ".join(d.get("active_retrievers", [])) + '<br>评审: ' + ", ".join(d.get("active_reviewers", [])) + '<br>Top-K: ' + str(d.get("retrieval_top_k", "N/A")) + '</div></details>'
        parts.append(line)
    if "router" in node_data:
        d = node_data["router"]
        parts.append('<details class="agent-detail"><summary><span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:#22c55e;margin-right:6px;"></span> Router - ' + d.get("question_type", "") + ' (' + d.get("difficulty", "") + ')</summary><div class="body">子查询: ' + "; ".join(d.get("decomposed_queries", [])) + '</div></details>')
    if "parallel_retrieval" in node_data:
        d = node_data["parallel_retrieval"]
        ab = d.get("agent_breakdown", {})
        at = d.get("agent_timing", {})
        items = []
        for an in ["keyword", "semantic", "graph"]:
            cnt = ab.get(an, 0)
            tm = at.get(an, {})
            el = tm.get("elapsed_ms", "?")
            ok = tm.get("status", "") == "success"
            ic = "\u25cf" if ok else "\u2715"
            items.append(ic + " " + an + ": " + str(cnt) + "条 (" + str(el) + "ms)")
        parts.append('<details class="agent-detail"><summary><span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:#22c55e;margin-right:6px;"></span> 并行检索 - ' + str(d.get("total_docs", 0)) + "条 \u00b7 " + str(d.get("elapsed_ms", 0)) + "ms</summary><div class=\"body\">" + "<br>".join(items) + "</div></details>")
    if writer_entries:
        w = writer_entries[-1]
        rv = w.get("revision_count", 0)
        ct = w.get("citations_count", 0)
        dr = (w.get("draft", "") or "")[:300]
        rl = " (第" + str(rv) + "轮修订)" if rv > 0 else ""
        parts.append('<details class="agent-detail"><summary><span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:#22c55e;margin-right:6px;"></span> STAR Writer' + rl + " - 引用 " + str(ct) + " 条</summary><div class=\"body\"><p style=\"color:#e0e0f0;line-height:1.6;\">" + dr + "</p></div></details>")
    if review_entries:
        r = review_entries[-1]
        dec = r.get("vote_decision", "accept")
        total = r.get("review_total", 0)
        revs = r.get("reviewers", {})
        items = []
        for rn, rl in [("correctness", "正确性"), ("completeness", "完整性"), ("advantage", "优势")]:
            rd = revs.get(rn, {})
            sc = rd.get("scores", {})
            avg = round(sum(sc.values()) / len(sc), 1) if sc else 0
            nr = rd.get("needs_revision", False)
            ic = "\u25b3" if nr else "\u25cf"
            fb = (rd.get("feedback", "") or "")[:60]
            line = ic + " " + rl + ": " + ("%.1f" % avg) + "/5"
            if fb: line += " - " + fb
            items.append(line)
        v_icon = "\u25b3" if dec == "revise" else "\u25cf"
        rf = r.get("revision_feedback", "") or ""
        rf_s = ("<br>" + v_icon + " 修订反馈: " + rf[:200]) if rf else ""
        parts.append('<details class="agent-detail" open><summary><span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:#22c55e;margin-right:6px;"></span> 并行评审 - ' + str(total) + "/25 \u00b7 决策: " + dec + "</summary><div class=\"body\">" + "<br>".join(items) + rf_s + "</div></details>")
    return "<div>" + "".join(parts) + "</div>"

# ===== 侧边栏 =====
def render_sidebar():
    with st.sidebar:
        st.markdown("""
        <div style="padding: 0.5rem 0 1rem 0;">
          <h2 style="margin:0;font-size:1.2rem;">
            <span class="brand-header">ResuMatch</span>
            <span style="color:#5e5e88;font-size:0.7rem;font-weight:400;margin-left:4px;">AI</span>
          </h2>
          <p style="color:#5e5e88;font-size:0.7rem;margin:2px 0 0 0;">Multi-Agent Interview System</p>
        </div>
        """, unsafe_allow_html=True)

        # 系统状态
        if api_health():
            info = api_system_info()
            st.markdown("""
            <div style="display:flex;align-items:center;gap:8px;padding:10px 14px;
              background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.2);
              border-radius:10px;margin-bottom:12px;">
              <div class="dot green"></div>
              <div>
                <div style="color:#e0e0f0;font-size:0.85rem;font-weight:500;">API 已连接</div>
                <div style="color:#5e5e88;font-size:0.7rem;">{model} &middot; 已索引 {docs} 条</div>
              </div>
            </div>
            """.format(
                model=info.get("model", "N/A"),
                docs=sum(info.get("collections", {}).values()),
            ), unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="display:flex;align-items:center;gap:8px;padding:10px 14px;
              background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.2);
              border-radius:10px;margin-bottom:12px;">
              <div class="dot red"></div>
              <div>
                <div style="color:#e0e0f0;font-size:0.85rem;font-weight:500;">API 离线</div>
                <div style="color:#5e5e88;font-size:0.7rem;">启动命令: python -m src.api.main</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown('<p style="color:#5e5e88;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.06em;margin:16px 0 6px 0;">功能导航</p>', unsafe_allow_html=True)

        page = st.radio(
            "导航",
            ["简历上传", "面试模拟", "自我介绍", "JD 匹配"],
            label_visibility="collapsed",
        )

        st.divider()
        st.markdown("""
        <p style="color:#3e3e66;font-size:0.65rem;text-align:center;">
          LangGraph Multi-Agent v3.0<br>
          DeepSeek + ChromaDB + bge
        </p>
        """, unsafe_allow_html=True)

        return page


# ===== 页面：简历上传 =====
def page_resume_upload():
    st.markdown('<h1 style="margin-bottom:4px;">简历上传</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color:#5e5e88;margin-bottom:24px;">上传简历，系统使用纯规则解析提取结构化数据，不依赖大模型概括。</p>', unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "拖拽或点击上传简历文件",
        type=["pdf", "docx", "md", "txt"],
        help="支持 PDF、DOCX、Markdown、纯文本格式",
    )

    if uploaded:
        with st.spinner("正在解析简历..."):
            result = api_upload_resume(uploaded)

        if result.get("success"):
            st.success(result.get("message", "解析完成"))

            profile = result.get("profile", {})
            collections = result.get("collections", {})
            verification = result.get("verification", {})

            # 指标卡片
            c1, c2, c3, c4 = st.columns(4)
            with c1: st.metric("技能", collections.get("skills", 0))
            with c2: st.metric("项目", collections.get("projects", 0))
            with c3: st.metric("成果", collections.get("achievements", 0))
            with c4: st.metric("教育", collections.get("education", 0))

            # 置信度摘要
            if verification:
                hi = verification.get("high_confidence", 0)
                med = verification.get("medium_confidence", 0)
                lo = verification.get("low_confidence", 0)
                st.markdown(f"""
                <div style="display:flex;gap:16px;margin:8px 0 16px 0;font-size:0.8rem;color:#5e5e88;">
                  <span><span class="dot green"></span> 高置信度: {hi}</span>
                  <span><span class="dot yellow"></span> 中: {med}</span>
                  <span><span class="dot red"></span> 低: {lo}</span>
                </div>
                """, unsafe_allow_html=True)

            # 详细信息
            if profile:
                tabs = st.tabs(["基本信息", "技能", "项目经验", "成果"])

                with tabs[0]:
                    st.write(f"**姓名**: {profile.get('name', '未知')}")
                    st.write(f"**邮箱**: {profile.get('email', '')}")
                    st.write(f"**手机**: {profile.get('phone', '')}")

                with tabs[1]:
                    skills = profile.get("skills", [])
                    if skills:
                        tags_html = " ".join([
                            f'<span class="tag skill">{s.get("name", "")}</span>'
                            for s in skills
                        ])
                        st.markdown(f'<div style="line-height:2.2;">{tags_html}</div>', unsafe_allow_html=True)

                with tabs[2]:
                    projects = profile.get("projects", [])
                    for proj in projects:
                        with st.expander(f"{proj.get('name', 'Project')}  ·  {proj.get('role', '')}"):
                            tech = proj.get("tech_stack", [])
                            if tech:
                                tags = " ".join([f'<span class="tag skill">{t}</span>' for t in tech])
                                st.markdown(f'<div style="margin-bottom:8px;">{tags}</div>', unsafe_allow_html=True)
                            result_text = proj.get("key_result", "")
                            if result_text:
                                st.markdown(f'<p style="color:#9090b0;">{result_text}</p>', unsafe_allow_html=True)

                with tabs[3]:
                    achievements = profile.get("achievements", [])
                    for ach in achievements:
                        st.markdown(f'- {ach.get("description", "")}')
        else:
            st.error(f"解析失败: {result.get('message', '未知错误')}")


# ===== 页面：面试模拟 =====
def page_interview():
    st.markdown('<h1 style="margin-bottom:4px;">面试模拟</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color:#5e5e88;margin-bottom:24px;">AI 驱动的面试问答，多Agent并行检索 + 多Agent评审。</p>', unsafe_allow_html=True)

    mode = st.radio("模式", ["单次问答", "多轮模拟"], horizontal=True, label_visibility="collapsed")

    if mode == "单次问答":
        _single_qa_mode()
    else:
        _mock_interview_mode()


def _single_qa_mode():
    question = st.text_area(
        "输入面试问题",
        placeholder="例如：请介绍你在 PaperPilot 项目中的贡献...",
        height=100,
        key="qa_question",
    )

    if st.button("生成回答", type="primary", use_container_width=True):
        if not question.strip():
            st.error("请输入面试问题")
            return

        # Agent 可视化布局
        progress = st.progress(0, text="等待工作流启动...")
        dag_area = st.empty()
        detail_area = st.empty()
        answer_area = st.empty()

        nm = {"planner":"pending","router":"pending","retrieval":"pending",
              "writer":"pending","review":"pending","end":"pending"}
        dag_area.markdown(_render_dag(nm), unsafe_allow_html=True)

        # SSE 流式处理
        nd = {}; we = []; re = []; fa = ""; err = None
        try:
            for evt in api_interview_stream(question):
                t = evt.get("type","")
                if t == "start":
                    progress.progress(5, text="工作流启动")
                elif t == "node_complete":
                    node = evt.get("node","")
                    nm[node] = "success"
                    dag_area.markdown(_render_dag(nm), unsafe_allow_html=True)
                    d = evt.get("data",{})
                    if node == "writer":
                        we.append(d); nd["writer"] = d
                        progress.progress(70, text="回答生成完成 (修订 %d 轮)" % d.get("revision_count",0))
                    elif node == "parallel_review":
                        re.append(d); nd["parallel_review"] = d
                        dec = d.get("vote_decision","accept")
                        lbl = "修订" if dec == "revise" else "通过"
                        progress.progress(88, text="评审完成 \u00b7 决策: %s" % lbl)
                    elif node == "end":
                        progress.progress(100, text="全部完成")
                    else:
                        nd[node] = d
                        pm = {"planner":(15,"Planner 决策完成"),"router":(30,"问题分类完成"),"parallel_retrieval":(50,"并行检索完成")}
                        if node in pm:
                            pct, lab = pm[node]; progress.progress(pct, text=lab)
                    detail_area.markdown(_render_detail_section(nd, we, re), unsafe_allow_html=True)
                elif t == "done":
                    fa = evt.get("data",{}).get("final_answer",""); break
        except Exception as ex:
            err = str(ex)

        # 最终结果展示
        if err:
            st.error("请求失败: %s" % err); return
        if fa:
            rd = nd.get("parallel_review",{})
            total = rd.get("review_total",0)
            rev_cnt = rd.get("revision_count",0)
            info = "总分 %d/25 \u00b7 修订 %d 轮" % (total, rev_cnt) if total else ""
            answer_area.markdown(
                '<div class="card"><div class="card-header">回答 %s</div><p style="color:#e0e0f0;line-height:1.7;font-size:0.9rem;">%s</p></div>'
                % (info, fa), unsafe_allow_html=True)
            reviewers = rd.get("reviewers",{})
            if reviewers:
                cols = st.columns(3)
                for i,(lab,key) in enumerate([("正确性","correctness"),("完整性","completeness"),("优势展示","advantage")]):
                    with cols[i]:
                        r = reviewers.get(key,{})
                        sc = r.get("scores",{})
                        avg = round(sum(sc.values())/len(sc),1) if sc else 0
                        fb = (r.get("feedback","") or "")[:60]
                        needs = r.get("needs_revision",False)
                        st.metric(lab, "%.1f/5" % avg, delta="修订" if needs else "通过", delta_color="off" if needs else "normal")
                        if fb: st.caption(fb)

def _mock_interview_mode():
    if "mock_session" not in st.session_state:
        st.session_state.mock_session = None
        st.session_state.mock_round = 0
        st.session_state.mock_history = []

    col1, col2 = st.columns([3, 1])

    with col2:
        focus = st.multiselect(
            "关注领域",
            ["算法", "系统设计", "项目经验", "行为面试", "Agent开发"],
            default=["项目经验"],
        )
        difficulty = st.selectbox("难度", ["basic", "intermediate", "advanced"], index=1)

    with col1:
        if st.button("开始模拟面试", type="primary"):
            result = api_mock_start(focus, difficulty)
            st.session_state.mock_session = result.get("session_id")
            st.session_state.mock_round = 1
            st.session_state.mock_history = []
            st.session_state.current_question = result.get("first_question", "")
            st.rerun()

        if st.session_state.mock_session:
            st.info(f"第 {st.session_state.mock_round} 轮")

            st.markdown(f"""
            <div class="card" style="border-left:3px solid #6c5ce7;">
              <div class="card-header">面试官提问</div>
              <p style="color:#e0e0f0;font-size:0.95rem;line-height:1.6;">{st.session_state.get('current_question', '')}</p>
            </div>
            """, unsafe_allow_html=True)

            answer = st.text_area("你的回答", height=180, key=f"answer_{st.session_state.mock_round}")

            if st.button("提交回答", type="primary"):
                if not answer.strip():
                    st.error("请输入你的回答")
                else:
                    result = api_mock_next(st.session_state.mock_session, answer)
                    st.session_state.mock_round = result.get("round_number", 0)
                    st.session_state.current_question = result.get("question", "")

                    if result.get("is_last"):
                        st.success("面试完成！")
                        if result.get("session_summary"):
                            st.info(result["session_summary"])
                        st.session_state.mock_session = None
                    st.rerun()


# ===== 页面：自我介绍 =====
def page_self_intro():
    st.markdown('<h1 style="margin-bottom:4px;">自我介绍</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color:#5e5e88;margin-bottom:24px;">根据简历自动生成三种长度的自我介绍。</p>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1: position = st.text_input("目标职位", placeholder="如：后端开发工程师")
    with c2: company = st.text_input("目标公司", placeholder="可选")
    with c3: length = st.selectbox("默认长度", ["30s", "1min", "3min"])

    if st.button("生成自我介绍", type="primary", use_container_width=True):
        with st.spinner("正在生成..."):
            result = api_generate_intro(position, company, length)

        if result:
            tabs = st.tabs(["30 秒版", "1 分钟版", "3 分钟版"])

            with tabs[0]:
                intro = result.get("intro_30s", "")
                st.text_area("30s intro", intro, height=150, key="i30", label_visibility="collapsed")
                st.caption(f"~{len(intro)} characters")

            with tabs[1]:
                intro = result.get("intro_1min", "")
                st.text_area("1min intro", intro, height=250, key="i60", label_visibility="collapsed")
                st.caption(f"~{len(intro)} characters")

            with tabs[2]:
                intro = result.get("intro_3min", "")
                st.text_area("3min intro", intro, height=400, key="i180", label_visibility="collapsed")
                st.caption(f"~{len(intro)} characters")
        else:
            st.warning("请先上传简历")


# ===== 页面：JD 匹配 =====
def page_jd_match():
    st.markdown('<h1 style="margin-bottom:4px;">JD 匹配</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color:#5e5e88;margin-bottom:24px;">分析简历与职位描述的匹配程度，包括技能与项目两个维度。</p>', unsafe_allow_html=True)

    tab_skill, tab_project = st.tabs(["技能匹配", "项目匹配"])

    # ---- 技能匹配（原有逻辑） ----
    with tab_skill:
        c1, c2 = st.columns([3, 1])
        with c1:
            jd_text = st.text_area("粘贴 JD 内容", placeholder="在此粘贴完整的职位描述...", height=280)
        with c2:
            target_position = st.text_input("目标职位", placeholder="如：AI 工程师")
            st.caption("对比 JD 需求与你的技能、项目经验")

        if st.button("分析匹配度", type="primary", use_container_width=True):
            if not jd_text.strip():
                st.error("请粘贴 JD 内容")
                return

            with st.spinner("分析中..."):
                result = api_match_jd(jd_text, target_position)

            if result:
                match_score = result.get("match_score", 0)
                st.markdown(f"""
                <div style="text-align:center;padding:1.5rem;">
                  <div style="font-size:3rem;font-weight:800;background:linear-gradient(135deg,#6366f1,#8b5cf6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">{match_score}%</div>
                  <div style="color:#5e5e88;font-size:0.8rem;">综合匹配度</div>
                </div>
                """, unsafe_allow_html=True)
                st.progress(match_score / 100)

                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("匹配的技能")
                    matched = result.get("matched_skills", [])
                    if matched:
                        tags = " ".join([f'<span class="tag match">{s}</span>' for s in matched[:15]])
                        st.markdown(f'<div style="line-height:2.2;">{tags}</div>', unsafe_allow_html=True)

                with c2:
                    st.subheader("技能差距")
                    missing = result.get("missing_skills", [])
                    if missing:
                        tags = " ".join([f'<span class="tag gap">{s}</span>' for s in missing[:15]])
                        st.markdown(f'<div style="line-height:2.2;">{tags}</div>', unsafe_allow_html=True)

                strength = result.get("strength_analysis", "")
                gap = result.get("gap_analysis", "")
                if strength: st.success(strength)
                if gap: st.warning(gap)

                missing_cats = result.get("missing_categories", [])
                if missing_cats:
                    st.info(f"建议补强领域: {', '.join(missing_cats)}")
            else:
                st.warning("请先上传简历")

    # ---- 项目匹配（新增：三维度项目-JD 匹配） ----
    with tab_project:
        st.markdown("#### 项目匹配")
        st.caption("自动提取 JD 需求，对项目经验库中每个项目按 技术交集 / 经验年限 / 复杂度 三维度打分排序")

        c1, c2 = st.columns([3, 1])
        with c1:
            jd_text_p = st.text_area("粘贴 JD 内容", placeholder="在此粘贴完整的职位描述...", height=220, key="jd_p")
        with c2:
            position_p = st.text_input("目标职位", placeholder="如：AI 工程师", key="pos_p")

        if st.button("匹配项目", type="primary", use_container_width=True, key="btn_project"):
            if not jd_text_p.strip():
                st.error("请粘贴 JD 内容")
                return

            with st.spinner("分析项目匹配中..."):
                result = api_match_projects(jd_text_p, position_p)

            if not result:
                st.warning("请先上传简历")
                return

            message = result.get("message", "")
            if message:
                st.info(message)
                return

            # JD 需求提取
            jd_req = result.get("jd_requirements", {})
            with st.expander("📋 JD 需求提取", expanded=True):
                tech = jd_req.get("tech_stack", [])
                soft = jd_req.get("soft_skills", [])
                years = jd_req.get("experience_years")
                if tech:
                    tags = " ".join([f'<span class="tag match">{t}</span>' for t in tech[:20]])
                    st.markdown(f"**技术栈要求**：<div style='line-height:2.2;'>{tags}</div>", unsafe_allow_html=True)
                if soft:
                    tags = " ".join([f'<span class="tag">{s}</span>' for s in soft[:10]])
                    st.markdown(f"**软技能要求**：<div style='line-height:2.2;'>{tags}</div>", unsafe_allow_html=True)
                if years:
                    st.markdown(f"**经验年限**：{years} 年")
                if not tech and not soft:
                    st.markdown("未识别到明确的技术/软技能要求。")

            # 项目匹配排行
            projects = result.get("projects", [])
            if not projects:
                st.info("项目库中暂无匹配项目，请先上传简历。")
                return

            st.markdown("#### 项目匹配排行")
            for p in projects:
                name = p.get("name", "未命名项目")
                score = p.get("match_score", 0)
                role = p.get("role", "")
                period = p.get("time_period", "")
                st.markdown(f"""
                <div class="card" style="padding:1rem;margin-bottom:0.75rem;border:1px solid #2a2a4a;border-radius:10px;background:rgba(255,255,255,0.02);">
                  <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span style="font-weight:600;font-size:1.05rem;">{name} <span style="color:#5e5e88;font-weight:400;font-size:0.8rem;">{role} {period}</span></span>
                    <span style="font-size:1.4rem;font-weight:800;background:linear-gradient(135deg,#6366f1,#8b5cf6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">{int(score)}</span>
                  </div>
                  {"" if not p.get("matched_tech") else '<div style="line-height:2.0;margin-top:4px;">' + " ".join(f'<span class="tag match">{t}</span>' for t in p["matched_tech"][:8]) + "</div>"}
                </div>
                """, unsafe_allow_html=True)

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("技术交集", f'{p.get("tech_overlap", 0)*100:.0f}%')
                m2.metric("年限匹配", f'{p.get("years_match", 0)*100:.0f}%')
                m3.metric("复杂度", f'{p.get("complexity_score", 0)*100:.0f}%')
                m4.metric("综合", f'{score:.0f}')

            # 针对性生成
            top = result.get("top_project", {})
            answer = result.get("targeted_answer", "")
            resume_desc = result.get("targeted_resume_desc", "")
            if top and (answer or resume_desc):
                st.markdown("#### 针对性内容生成")
                with st.expander(f"🎯 基于最高匹配项目「{top.get('name','')}」的针对性 STAR 回答", expanded=False):
                    if answer:
                        st.markdown(answer)
                    else:
                        st.info("（LLM 不可用或生成失败，跳过）")
                with st.expander("📝 针对性简历项目描述", expanded=False):
                    if resume_desc:
                        st.code(resume_desc, language=None)
                    else:
                        st.info("（LLM 不可用或生成失败，跳过）")

            missing = result.get("missing_skills", [])
            if missing:
                tags = " ".join([f'<span class="tag gap">{s}</span>' for s in missing[:10]])
                st.markdown(f"**项目库未覆盖的 JD 技术**：<div style='line-height:2.2;'>{tags}</div>", unsafe_allow_html=True)


# ===== 主函数 =====
def main():
    page = render_sidebar()

    page_map = {
        "简历上传": page_resume_upload,
        "面试模拟": page_interview,
        "自我介绍": page_self_intro,
        "JD 匹配": page_jd_match,
    }

    if page in page_map:
        page_map[page]()
    else:
        page_resume_upload()


if __name__ == "__main__":
    main()
