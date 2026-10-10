# -*- coding: utf-8 -*-
"""评测集生成器 — 合成简历 × 标注面试问题

目的（毕业论文评测体系的地基）：
- 单份简历撑不起统计显著性 → 合成 12 份不同背景的匿名简历
- 每份简历配 30 道面试问题，每题标注「应命中的素材 chunk_id」（检索 ground truth）
- 全部程序化生成、可复现、零 LLM 消耗（合成遵循 CLAUDE.md LLM 边界：
  只做模板拼装，不生成"个人经历事实"以外的内容——事实来自模板参数表）

评测集落盘 data/eval/：
- resumes/resume_XX.md        12 份合成简历文本
- questions.json              [{resume_id, question, question_type,
                                expected_ids: [chunk_id...]}] 共 360 题
- profile_seed.json           每份简历的 profile.json 种子（直接喂 ProfileStore）

ground truth 标注规则（检索指标的可验证性来源）：
- 技术问题 → 对应技能 chunk（skill_N）
- 项目问题 → 对应项目 chunk（project_N）+ 其成果 chunk（achievement_N）
- 教育问题 → education_N
- 行为/通用问题 → 不设 expected（检索质量对它无意义，生成评测用）
"""
import json
import random
from pathlib import Path

# ===== 合成简历模板参数（12 份 × 3 个方向）=====
# 每份：姓名(合成)、方向、技能集、项目(2-3个)、成果、教育
RESUME_SEEDS = [
    {
        "id": "B01", "name": "陈某", "direction": "后端开发",
        "skills": ["Python", "FastAPI", "Django", "MySQL", "Redis", "Docker", "Kubernetes", "Celery", "SQLAlchemy", "pytest"],
        "projects": [
            {"name": "电商订单中台", "role": "后端负责人", "tech": ["FastAPI", "MySQL", "Redis", "Celery"],
             "desc": "处理日均10万订单的订单中台，异步削峰、幂等防重、分布式事务",
             "results": ["订单接口 P99 延迟 800ms→120ms", "大促峰值吞吐提升 5 倍", "重复下单率降为 0"]},
            {"name": "数据同步管道", "role": "核心开发", "tech": ["Python", "Kafka", "MySQL"],
             "desc": "多源异构数据库到数仓的准实时同步管道，CDC + 断点续传",
             "results": ["同步延迟分钟级→秒级", "断点恢复时间 30min→10s"]},
        ],
        "achievements": ["电商订单中台：订单接口 P99 延迟 800ms→120ms", "数据同步管道：同步延迟分钟级→秒级"],
        "education": [
            {"school": "华南理工大学", "degree": "硕士", "major": "计算机技术", "time": "2024-2027"},
            {"school": "郑州大学", "degree": "学士", "major": "软件工程", "time": "2020-2024"},
        ],
    },
    {
        "id": "B02", "name": "林某", "direction": "前端开发",
        "skills": ["TypeScript", "React", "Vue", "Vite", "TailwindCSS", "WebGL", "Three.js", "Node.js", "Webpack", "Playwright"],
        "projects": [
            {"name": "可视化大屏引擎", "role": "前端负责人", "tech": ["React", "Three.js", "WebGL"],
             "desc": "工业监控 3D 可视化大屏，WebGL 渲染管线优化 + 数据驱动场景",
             "results": ["首屏渲染 4s→1.2s", "同屏点位数 5万→20万", "GPU 内存占用降 40%"]},
            {"name": "低代码表单引擎", "role": "核心开发", "tech": ["Vue", "TypeScript", "Vite"],
             "desc": "拖拽式表单搭建引擎，Schema 驱动渲染 + 自定义组件生态",
             "results": ["表单搭建效率提升 10 倍", "覆盖公司 80% 内部系统"]},
        ],
        "achievements": ["可视化大屏引擎：首屏渲染 4s→1.2s", "低代码表单引擎：搭建效率提升 10 倍"],
        "education": [
            {"school": "厦门大学", "degree": "学士", "major": "数字媒体技术", "time": "2021-2025"},
        ],
    },
    {
        "id": "B03", "name": "高某", "direction": "AI 算法",
        "skills": ["Python", "PyTorch", "Transformers", "LangChain", "RAG", "Milvus", "LoRA", "DeepSpeed", "jieba", "Sentence-Transformers"],
        "projects": [
            {"name": "企业知识库问答系统", "role": "算法负责人", "tech": ["LangChain", "Milvus", "RAG"],
             "desc": "十万级文档企业知识库的 RAG 问答：混合检索 + 重排 + 引用溯源",
             "results": ["检索 Recall@5 达 92%", "幻觉率降 60%", "回答平均延迟 3.8s"]},
            {"name": "领域模型微调", "role": "核心开发", "tech": ["LoRA", "DeepSpeed", "PyTorch"],
             "desc": "法律领域 LLM 的 LoRA 微调：指令数据清洗 + 分布式训练",
             "results": ["领域评测准确率 61%→84%", "训练成本降 70%"]},
        ],
        "achievements": ["企业知识库问答：Recall@5 达 92%", "领域微调：准确率 61%→84%"],
        "education": [
            {"school": "中国科学技术大学", "degree": "硕士", "major": "人工智能", "time": "2024-2027"},
            {"school": "合肥工业大学", "degree": "学士", "major": "计算机科学", "time": "2020-2024"},
        ],
    },
    {
        "id": "B04", "name": "徐某", "direction": "数据工程",
        "skills": ["Python", "Spark", "Flink", "Kafka", "Hive", "Airflow", "ClickHouse", "Doris", "SQL", "Docker"],
        "projects": [
            {"name": "实时数仓平台", "role": "数据平台负责人", "tech": ["Flink", "Kafka", "Doris"],
             "desc": "实时数仓：Flink CDC + Kafka + Doris 构成的分钟级指标体系",
             "results": ["指标时效 T+1→5分钟", "日增数据处理量 2TB", "任务失败率 3%→0.2%"]},
            {"name": "数据质量监控", "role": "核心开发", "tech": ["Python", "Airflow", "Spark"],
             "desc": "全链路数据质量监控：波动检测 + 血缘追溯 + 自动告警",
             "results": ["数据事故发现时间 2h→5min", "覆盖 300+ 核心表"]},
        ],
        "achievements": ["实时数仓：指标时效 T+1→5分钟", "数据质量监控：事故发现 2h→5min"],
        "education": [
            {"school": "武汉大学", "degree": "硕士", "major": "大数据", "time": "2023-2026"},
            {"school": "华中科技大学", "degree": "学士", "major": "信息管理", "time": "2019-2023"},
        ],
    },
    {
        "id": "B05", "name": "孙某", "direction": "测试开发",
        "skills": ["Python", "Selenium", "Playwright", "pytest", "Jmeter", "Locust", "Allure", "Jenkins", "Docker", "Git"],
        "projects": [
            {"name": "自动化回归体系", "role": "测试负责人", "tech": ["Playwright", "pytest", "Jenkins"],
             "desc": "UI + API 双层自动化回归，CI 流水线集成与失败自愈",
             "results": ["回归时长 6h→40min", "线上缺陷逃逸率降 55%", "用例稳定性 97%"]},
            {"name": "全链路压测平台", "role": "核心开发", "tech": ["Locust", "Python", "InfluxDB"],
             "desc": "全链路压测平台：流量染色 + 影子库隔离 + 实时监控大屏",
             "results": ["定位 3 个容量瓶颈", "大促扩容决策依据", "压测脚本复用率 80%"]},
        ],
        "achievements": ["自动化回归：时长 6h→40min", "全链路压测：定位 3 个容量瓶颈"],
        "education": [
            {"school": "大连理工大学", "degree": "学士", "major": "软件工程", "time": "2021-2025"},
        ],
    },
    {
        "id": "B06", "name": "周某", "direction": "移动端开发",
        "skills": ["Kotlin", "Swift", "Flutter", "React Native", "Android", "iOS", "SQLite", "RxJava", "Compose", "Fastlane"],
        "projects": [
            {"name": "跨端电商 App", "role": "移动端负责人", "tech": ["Flutter", "Dart"],
             "desc": "一套代码双端发布的电商 App：首页动态化 + 购物车流畅度优化",
             "results": ["双端人力 2组→1组", "购物车操作丢帧率 8%→0.5%", "崩溃率 0.9%→0.08%"]},
            {"name": "音视频互动课堂", "role": "核心开发", "tech": ["React Native", "WebRTC"],
             "desc": "1v1 与小班课互动课堂：弱网对抗 + 互动白板同步",
             "results": ["弱网卡顿率 12%→1.5%", "白板同步延迟 <80ms"]},
        ],
        "achievements": ["跨端电商：崩溃率 0.9%→0.08%", "互动课堂：弱网卡顿率 12%→1.5%"],
        "education": [
            {"school": "东南大学", "degree": "硕士", "major": "电子信息", "time": "2023-2026"},
            {"school": "南京航空航天大学", "degree": "学士", "major": "物联网", "time": "2019-2023"},
        ],
    },
    {
        "id": "B07", "name": "吴某", "direction": "基础架构",
        "skills": ["Go", "Java", "gRPC", "Kubernetes", "Istio", "Prometheus", "etcd", "Lua", "Nginx", "Terraform"],
        "projects": [
            {"name": "服务网格落地", "role": "架构组核心", "tech": ["Istio", "Kubernetes"],
             "desc": "全公司 200+ 微服务的 Istio 服务网格灰度迁移与流量治理",
             "results": ["灰度发布全自动化", "故障注入演练覆盖 90% 服务", "P99 追加延迟 <2ms"]},
            {"name": "统一网关", "role": "负责人", "tech": ["Go", "Nginx", "Lua"],
             "desc": "自研统一 API 网关：鉴权/限流/灰度/可观测一体化",
             "results": ["网关 QPS 上限 50万", "业务接入时间 2周→2天"]},
        ],
        "achievements": ["服务网格：P99 追加延迟 <2ms", "统一网关：QPS 上限 50万"],
        "education": [
            {"school": "哈尔滨工业大学", "degree": "硕士", "major": "计算机", "time": "2022-2025"},
            {"school": "东北大学", "degree": "学士", "major": "软件工程", "time": "2018-2022"},
        ],
    },
    {
        "id": "B08", "name": "赵某", "direction": "安全工程",
        "skills": ["Python", "Burp Suite", "Metasploit", "Wireshark", "YARA", "ELK", "Wazuh", "Nmap", "Golang", "Kubernetes"],
        "projects": [
            {"name": "入侵检测系统", "role": "安全工程师", "tech": ["Wazuh", "ELK"],
             "desc": "主机 + 网络双源入侵检测：日志关联分析 + 告警降噪",
             "results": ["日均告警 2万→800", "真实攻击识别率 95%", "平均响应 10min"]},
            {"name": "SDL 流程建设", "role": "核心成员", "tech": ["Python", "YARA"],
             "desc": "研发安全左移：代码扫描/依赖审计/制品签名的流水线集成",
             "results": ["高危漏洞上线前拦截率 98%", "安全工时占比降 30%"]},
        ],
        "achievements": ["入侵检测：日均告警 2万→800", "SDL：高危漏洞拦截率 98%"],
        "education": [
            {"school": "电子科技大学", "degree": "学士", "major": "网络空间安全", "time": "2021-2025"},
        ],
    },
    {
        "id": "B09", "name": "何某", "direction": "游戏开发",
        "skills": ["C++", "Unreal Engine", "Unity", "Lua", "Blueprint", "OpenGL", "Vulkan", "Python", "Perforce", "C#"],
        "projects": [
            {"name": "开放世界地形系统", "role": "引擎组", "tech": ["Unreal Engine", "C++"],
             "desc": "流式加载的开放世界地形：LOD 调度 + 运行时烘焙 + 内存预算控制",
             "results": ["加载范围 500m→2km", "内存峰值降 35%", "穿模率降 90%"]},
            {"name": "战斗同步框架", "role": "核心开发", "tech": ["C++", "Lua"],
             "desc": "帧同步战斗框架：确定性逻辑 + 断线重连 + 回放系统",
             "results": ["不同步率 0.01%", "重连恢复 3s 内", "回放文件压缩比 20:1"]},
        ],
        "achievements": ["地形系统：内存峰值降 35%", "战斗同步：不同步率 0.01%"],
        "education": [
            {"school": "四川大学", "degree": "学士", "major": "数字娱乐", "time": "2020-2024"},
        ],
    },
    {
        "id": "B10", "name": "郑某", "direction": "嵌入式",
        "skills": ["C", "C++", "RTOS", "FreeRTOS", "STM32", "Linux 驱动", "CAN", "MQTT", "PCB", "Yocto"],
        "projects": [
            {"name": "车规域控制器", "role": "嵌入式工程师", "tech": ["FreeRTOS", "CAN", "STM32"],
             "desc": "车身域控制器固件：CAN 矩阵诊断 + 功能安全 ASIL-B + OTA 升级",
             "results": ["CAN 报文丢失率 <0.001%", "OTA 成功率 99.5%", "通过 ASIL-B 认证"]},
            {"name": "低功耗传感网", "role": "核心开发", "tech": ["MQTT", "Linux 驱动"],
             "desc": "电池供电传感网络：休眠调度 + 边缘预处理 + 断网缓存",
             "results": ["续航 6月→2年", "上报流量降 85%"]},
        ],
        "achievements": ["域控制器：OTA 成功率 99.5%", "传感网：续航 6月→2年"],
        "education": [
            {"school": "西安电子科技大学", "degree": "硕士", "major": "微电子", "time": "2023-2026"},
            {"school": "西北工业大学", "degree": "学士", "major": "自动化", "time": "2019-2023"},
        ],
    },
    {
        "id": "B11", "name": "冯某", "direction": "算法工程-推荐",
        "skills": ["Python", "TensorFlow", "PyTorch", "Faiss", "Spark MLlib", "Feature Store", "ONNX", "Ray", "SQL", "Airflow"],
        "projects": [
            {"name": "短视频推荐重构", "role": "推荐算法工程师", "tech": ["PyTorch", "Faiss"],
             "desc": "召回+排序双层推荐重构：多路召回融合 + 精排蒸馏",
             "results": ["人均时长 +18%", "召回多样性 +35%", "推理成本降 40%"]},
            {"name": "特征平台", "role": "核心开发", "tech": ["Spark", "Feature Store"],
             "desc": "实时+离线统一特征平台：点播特征口径 + 在线 serving",
             "results": ["特征上线周期 2周→1天", "训练推理一致性 100%"]},
        ],
        "achievements": ["推荐重构：人均时长 +18%", "特征平台：上线周期 2周→1天"],
        "education": [
            {"school": "中山大学", "degree": "硕士", "major": "计算机", "time": "2023-2026"},
            {"school": "暨南大学", "degree": "学士", "major": "数学", "time": "2019-2023"},
        ],
    },
    {
        "id": "B12", "name": "曹某", "direction": "全栈开发",
        "skills": ["TypeScript", "Node.js", "React", "NestJS", "PostgreSQL", "GraphQL", "Prisma", "Redis", "Docker", "AWS"],
        "projects": [
            {"name": "SaaS 多租户平台", "role": "全栈负责人", "tech": ["NestJS", "PostgreSQL", "React"],
             "desc": "B2B SaaS 多租户平台：行级隔离 + 计量计费 + 插件市场",
             "results": ["单集群租户数 5000", "插件 API 日调用千万级", "数据隔离审计零缺陷"]},
            {"name": "实时协作文档", "role": "核心开发", "tech": ["Node.js", "CRDT"],
             "desc": "富文本实时协作：CRDT 冲突消解 + 离线编辑合并",
             "results": ["百人同编延迟 <100ms", "离线合并冲突率 0.3%"]},
        ],
        "achievements": ["SaaS 平台：单集群租户 5000", "协作文档：百人同编 <100ms"],
        "education": [
            {"school": "同济大学", "degree": "学士", "major": "软件工程", "time": "2021-2025"},
        ],
    },
]

# ===== 问题模板（每份 30 题：技术 8 / 项目 10 / 教育 2 / 行为 5 / 通用 5）=====
# 检索型问题的 expected 指向 chunk_id —— 与 profile_to_documents 的
# 产出编号严格对应（skill_N / project_N / achievement_N / education_N）
def _build_questions(seed):
    q = []
    rid = seed["id"]
    skills = seed["skills"]
    projects = seed["projects"]
    edu = seed["education"]

    # 技术问题 8：抽 6 个技能 + 2 个组合
    random.Random(rid).shuffle(skills)
    for i, sk in enumerate(skills[:6]):
        q.append({"resume_id": rid, "question": f"你在 {sk} 上的实践经验是什么？",
                  "qtype": "technical_depth", "expected_ids": [f"skill_{skills.index(sk)}"]})
    q.append({"resume_id": rid, "question": "你的核心技术栈里哪些用得最深？",
              "qtype": "technical_depth", "expected_ids": [f"skill_{i}" for i in range(min(5, len(skills)))]})
    q.append({"resume_id": rid, "question": "你在分布式和高并发场景做过什么？",
              "qtype": "technical_depth", "expected_ids": []})  # 泛化题：不设期望（记 non-target）

    # 项目问题 10：每项目 5 问（背景/挑战/成果/角色/深挖）
    for pi, proj in enumerate(projects):
        q.append({"resume_id": rid, "question": f"介绍一下你的{proj['name']}项目",
                  "qtype": "project_followup", "expected_ids": [f"project_{pi}"]})
        q.append({"resume_id": rid, "question": f"{proj['name']}里你遇到的最大挑战是什么？",
                  "qtype": "project_followup", "expected_ids": [f"project_{pi}", f"achievement_{pi}"]})
        q.append({"resume_id": rid, "question": f"{proj['name']}有哪些可量化的成果？",
                  "qtype": "project_followup", "expected_ids": [f"project_{pi}", f"achievement_{pi}"]})
        q.append({"resume_id": rid, "question": f"你在{proj['name']}中承担什么角色？",
                  "qtype": "project_followup", "expected_ids": [f"project_{pi}"]})
        q.append({"resume_id": rid, "question": f"{proj['name']}的技术选型是怎么考虑的？",
                  "qtype": "project_followup", "expected_ids": [f"project_{pi}"]})

    # 教育问题 2
    for ei, e in enumerate(edu):
        q.append({"resume_id": rid, "question": f"谈谈你在{e['school']}的{e['major']}学习经历",
                  "qtype": "general", "expected_ids": [f"education_{ei}"]})

    # 行为 5 / 通用 5：检索质量无 ground truth，供生成评测
    behaviors = [
        "讲一次你和队友意见冲突并解决的经历",
        "说一个你从失败中学到的教训",
        "你如何在多任务下安排优先级？",
        "描述一次你主动承担额外责任的经历",
        "你持续学习新技术的方法是什么？",
    ]
    for b in behaviors:
        q.append({"resume_id": rid, "question": b, "qtype": "behavioral", "expected_ids": []})
    generals = [
        "你最大的优势和不足分别是什么？",
        "为什么选择这个职业方向？",
        "未来三年的职业规划是什么？",
        "你期望什么样的团队氛围？",
        "你如何看待加班？",
    ]
    for g in generals:
        q.append({"resume_id": rid, "question": g, "qtype": "general", "expected_ids": []})
    return q


def _resume_text(seed):
    """合成简历 Markdown 文本（走真实上传链路：parser → chunker → milvus）"""
    lines = [f"# {seed['name']}的简历", "", f"求职方向: {seed['direction']}", "",
             "## 技能"]
    for i in range(0, len(seed["skills"]), 5):
        lines.append(", ".join(seed["skills"][i:i + 5]))
    lines += ["", "## 项目经验"]
    for p in seed["projects"]:
        lines += [f"### {p['name']}", f"角色: {p['role']}", f"技术栈: {', '.join(p['tech'])}",
                  f"描述: {p['desc']}", "关键成果:"]
        lines += [f"- {r}" for r in p["results"]]
        lines.append("")
    lines += ["## 关键成就"]
    lines += [f"- {a}" for a in seed["achievements"]]
    lines += ["", "## 教育背景"]
    for e in seed["education"]:
        lines.append(f"{e['school']} {e['major']} {e['degree']} {e['time']}")
    return "\n".join(lines)


def _profile_seed(seed):
    """profile.json 种子（与 parser 产出结构一致，直接喂档案编辑链路）"""
    return {
        "name": seed["name"],
        "email": "", "phone": "",
        "skills": [{"name": s, "category": "eval"} for s in seed["skills"]],
        "projects": [
            {"name": p["name"], "role": p["role"], "tech_stack": p["tech"],
             "time_period": "", "key_result": p["results"][0] if p["results"] else "",
             "description": p["desc"], "details": [], "difficulties": [],
             "challenges": "", "responsibilities": ""}
            for p in seed["projects"]
        ],
        "achievements": [{"description": a} for a in seed["achievements"]],
        "education": [
            {"school": e["school"], "degree": e["degree"], "major": e["major"], "time": e["time"]}
            for e in seed["education"]
        ],
    }


def generate(out_dir="data/eval"):
    """生成完整评测集（幂等：重复执行覆盖重写）"""
    out = Path(out_dir)
    (out / "resumes").mkdir(parents=True, exist_ok=True)

    questions = []
    profiles = {}
    for seed in RESUME_SEEDS:
        (out / "resumes" / f"resume_{seed['id']}.md").write_text(_resume_text(seed), encoding="utf-8")
        questions.extend(_build_questions(seed))
        profiles[seed["id"]] = _profile_seed(seed)

    (out / "questions.json").write_text(
        json.dumps(questions, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "profile_seed.json").write_text(
        json.dumps(profiles, ensure_ascii=False, indent=1), encoding="utf-8")

    # 检索型问题统计（有 expected 的）
    n_target = sum(1 for q in questions if q["expected_ids"])
    print(f"评测集生成完成: {len(RESUME_SEEDS)} 份简历, {len(questions)} 题中 {n_target} 题带检索 ground truth")
    return out


if __name__ == "__main__":
    generate()
