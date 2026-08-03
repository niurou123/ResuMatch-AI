import { useState, useCallback, useReducer, useRef } from 'react';
import { toast } from 'sonner';
import { streamSSE } from '@/lib/sse';
import { MetricCard } from '@/components/shared/MetricCard';
import { VoiceInputButton } from '@/components/shared/VoiceInputButton';
import type { DAGState, DAGNodeId, WriterEntry, ReviewEntry } from '@/lib/types';

// ===== DAG Reducer =====
const DAG_NODE_IDS: DAGNodeId[] = ['planner', 'router', 'retrieval', 'writer', 'review', 'end'];

const INITIAL_DAG: DAGState = {
  nodes: Object.fromEntries(DAG_NODE_IDS.map((id) => [id, { status: 'pending' as const }])),
  writerEntries: [],
  reviewEntries: [],
  finalAnswer: '',
  progress: 0,
  progressText: '等待工作流启动...',
  error: null,
};

type DAGAction =
  | { type: 'NODE_COMPLETE'; node: DAGNodeId; data?: Record<string, unknown> }
  | { type: 'PROGRESS'; percent: number; text: string }
  | { type: 'DONE'; finalAnswer: string; reviewTotal?: number; revisionCount?: number }
  | { type: 'ERROR'; message: string }
  | { type: 'RESET' };

function dagReducer(state: DAGState, action: DAGAction): DAGState {
  switch (action.type) {
    case 'NODE_COMPLETE': {
      const next = { ...state, nodes: { ...state.nodes, [action.node]: { status: 'success' as const, data: action.data } } };
      if (action.node === 'writer' && action.data) {
        next.writerEntries = [...next.writerEntries, {
          draft: (action.data.draft as string) || '',
          revision_count: (action.data.revision_count as number) || 0,
          citations_count: (action.data.citations_count as number) || 0,
        }];
      }
      if (action.node === 'review' && action.data) {
        next.reviewEntries = [...next.reviewEntries, action.data as unknown as ReviewEntry];
      }
      return next;
    }
    case 'PROGRESS':
      return { ...state, progress: action.percent, progressText: action.text };
    case 'DONE':
      return { ...state, finalAnswer: action.finalAnswer, progress: 100, progressText: '全部完成', reviewTotal: action.reviewTotal, revisionCount: action.revisionCount };
    case 'ERROR':
      return { ...state, error: action.message };
    case 'RESET':
      return { ...INITIAL_DAG, nodes: Object.fromEntries(DAG_NODE_IDS.map((id) => [id, { status: 'pending' as const }])) };
    default:
      return state;
  }
}

// ===== DAG 可视化 =====
const NODE_LABELS: Record<DAGNodeId, string> = {
  planner: 'Planner',
  router: 'Router',
  retrieval: '并行检索',
  writer: 'Writer',
  review: '并行评审',
  end: '完成',
};

function DAGNode({ nodeId, status }: { nodeId: DAGNodeId; status: string }) {
  const colors: Record<string, { border: string; bg: string; dot: string; text: string }> = {
    pending: { border: '#2a2a5a', bg: 'transparent', dot: '#3a3a5a', text: '#5e5e88' },
    running: { border: '#f59e0b', bg: 'rgba(245,158,11,0.08)', dot: '#f59e0b', text: '#f59e0b' },
    success: { border: '#22c55e', bg: 'rgba(34,197,94,0.08)', dot: '#22c55e', text: '#22c55e' },
    failed: { border: '#ef4444', bg: 'rgba(239,68,68,0.08)', dot: '#ef4444', text: '#ef4444' },
  };
  const c = colors[status] || colors.pending;
  return (
    <div className="dag-node" style={{ borderColor: c.border, background: c.bg }}>
      <span
        className={`inline-block w-2 h-2 rounded-full ${status === 'running' ? 'animate-pulse-dot' : ''}`}
        style={{ background: c.dot, boxShadow: status === 'success' ? `0 0 4px ${c.dot}` : undefined }}
      />
      <span style={{ color: c.text, fontSize: '11px', fontWeight: 500, whiteSpace: 'nowrap' }}>
        {NODE_LABELS[nodeId]}
      </span>
    </div>
  );
}

function AgentDAG({ nodes }: { nodes: Record<string, { status: string }> }) {
  return (
    <div className="dag-flow">
      {DAG_NODE_IDS.map((nid, i) => (
        <span key={nid} className="flex items-center gap-1.5">
          <DAGNode nodeId={nid} status={nodes[nid]?.status || 'pending'} />
          {i < DAG_NODE_IDS.length - 1 && (
            <span className="dag-arrow text-text-3">&rarr;</span>
          )}
        </span>
      ))}
    </div>
  );
}

// ===== Agent 详情 =====
function AgentDetailSection({
  nodeData,
  writerEntries,
  reviewEntries,
}: {
  nodeData: Record<string, Record<string, unknown>>;
  writerEntries: WriterEntry[];
  reviewEntries: ReviewEntry[];
}) {
  const parts: { label: string; content: string }[] = [];

  const planner = nodeData['planner'];
  if (planner) {
    parts.push({
      label: `Planner — ${planner.description || ''}`,
      content: `检索: ${(planner.active_retrievers as string[])?.join(', ') || '—'} | 评审: ${(planner.active_reviewers as string[])?.join(', ') || '—'} | Top-K: ${planner.retrieval_top_k || '—'}`,
    });
  }

  const router = nodeData['router'];
  if (router) {
    parts.push({
      label: `Router — ${router.question_type || '?'} (${router.difficulty || '?'})`,
      content: `子查询: ${(router.decomposed_queries as string[])?.join('; ') || '—'}`,
    });
  }

  const retrieval = nodeData['parallel_retrieval'];
  if (retrieval) {
    const ab = (retrieval.agent_breakdown as Record<string, number>) || {};
    const at = (retrieval.agent_timing as Record<string, { elapsed_ms?: number; status?: string }>) || {};
    const items = ['keyword', 'semantic', 'graph'].map((an) => {
      const cnt = ab[an] || 0;
      const tm = at[an];
      const el = tm?.elapsed_ms || '?';
      const ok = tm?.status === 'success';
      return `${ok ? '●' : '✕'} ${an}: ${cnt}条 (${el}ms)`;
    });
    parts.push({
      label: `并行检索 — ${retrieval.total_docs || 0}条 · ${retrieval.elapsed_ms || 0}ms`,
      content: items.join('<br>'),
    });
  }

  const lastWriter = writerEntries[writerEntries.length - 1];
  if (lastWriter) {
    const rv = lastWriter.revision_count || 0;
    parts.push({
      label: `STAR Writer${rv > 0 ? ` (第${rv}轮修订)` : ''} — 引用 ${lastWriter.citations_count} 条`,
      content: (lastWriter.draft || '').slice(0, 400),
    });
  }

  const lastReview = reviewEntries[reviewEntries.length - 1];
  if (lastReview) {
    const revs = lastReview.reviewers || {};
    const items = (['correctness', 'completeness', 'advantage'] as const).map((rn) => {
      const labels: Record<string, string> = { correctness: '正确性', completeness: '完整性', advantage: '优势' };
      const rd = revs[rn];
      if (!rd) return '';
      const sc = rd.scores || {};
      const avg = Object.keys(sc).length > 0
        ? (Object.values(sc).reduce((a: number, b: number) => a + b, 0) / Object.keys(sc).length).toFixed(1)
        : '0';
      const nr = rd.needs_revision ? '△' : '●';
      const fb = (rd.feedback || '').slice(0, 80);
      return `${nr} ${labels[rn]}: ${avg}/5${fb ? ` — ${fb}` : ''}`;
    }).filter(Boolean);
    const dec = lastReview.vote_decision || 'accept';
    const rf = (lastReview.revision_feedback || '').slice(0, 200);
    parts.push({
      label: `并行评审 — ${lastReview.review_total || 0}/25 · 决策: ${dec}`,
      content: items.join('<br>') + (rf ? `<br>△ 修订反馈: ${rf}` : ''),
    });
  }

  return (
    <div>
      {parts.map((p, i) => (
        <details key={i} className="agent-detail" open={i === parts.length - 1}>
          <summary>
            <span className="inline-block w-1.5 h-1.5 rounded-full mr-1.5" style={{ background: '#22c55e' }} />
            {p.label}
          </summary>
          <div className="body" dangerouslySetInnerHTML={{ __html: p.content }} />
        </details>
      ))}
    </div>
  );
}

// ===== 单次问答 =====
function SingleQA() {
  const [question, setQuestion] = useState('');
  const [dag, dispatch] = useReducer(dagReducer, INITIAL_DAG);
  const [running, setRunning] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const handleSubmit = useCallback(async () => {
    if (!question.trim()) { toast.error('请输入面试问题'); return; }
    dispatch({ type: 'RESET' });
    setRunning(true);

    const progressMap: Record<string, [number, string]> = {
      planner: [15, 'Planner 决策完成'],
      router: [30, '问题分类完成'],
      parallel_retrieval: [50, '并行检索完成'],
    };
    const controller = new AbortController();
    abortRef.current = controller;
    const nodeData: Record<string, Record<string, unknown>> = {};

    try {
      for await (const evt of streamSSE('/api/v1/interview/stream', { question }, controller.signal)) {
        if (evt.type === 'start') {
          dispatch({ type: 'PROGRESS', percent: 5, text: '工作流启动' });
        } else if (evt.type === 'node_complete' && evt.node) {
          const data = (evt.data || {}) as Record<string, unknown>;
          if (evt.node === 'writer') {
            dispatch({ type: 'PROGRESS', percent: 70, text: `回答生成完成 (修订 ${data.revision_count || 0} 轮)` });
          } else if (evt.node === 'parallel_review') {
            const dec = data.vote_decision === 'revise' ? '修订' : '通过';
            dispatch({ type: 'PROGRESS', percent: 88, text: `评审完成 · 决策: ${dec}` });
          } else if (evt.node !== 'end') {
            const [pct, lab] = progressMap[evt.node] || [dag.progress, dag.progressText];
            dispatch({ type: 'PROGRESS', percent: pct, text: lab });
          }
          dispatch({ type: 'NODE_COMPLETE', node: evt.node as DAGNodeId, data });
          if (data) nodeData[evt.node] = data;
        } else if (evt.type === 'done') {
          const d = (evt.data || {}) as Record<string, unknown>;
          dispatch({ type: 'DONE', finalAnswer: (d.final_answer as string) || '', reviewTotal: d.review_total as number, revisionCount: d.revision_count as number });
          break;
        }
      }
    } catch (err: unknown) {
      if ((err as Error).name !== 'AbortError') {
        dispatch({ type: 'ERROR', message: (err as Error).message });
        toast.error(`请求失败: ${(err as Error).message}`);
      }
    } finally {
      setRunning(false);
    }
  }, [question, dag.progress, dag.progressText]);

  const handleCancel = () => {
    abortRef.current?.abort();
    setRunning(false);
  };

  const nodeDataMap: Record<string, Record<string, unknown>> = {};
  for (const [nid, ns] of Object.entries(dag.nodes)) {
    if (ns.data) nodeDataMap[nid] = ns.data;
  }
  const lastReview = dag.reviewEntries[dag.reviewEntries.length - 1];

  return (
    <div className="space-y-4">
      <div>
        <label className="text-sm text-text-2 mb-1.5 block">输入面试问题</label>
        <div className="relative">
          <textarea
            className="w-full bg-surface border border-border rounded-btn p-3 text-text text-sm resize-none focus:outline-none focus:border-primary transition-colors"
            rows={3}
            placeholder="例如：请介绍一下你的 AI Agent 项目..."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={running}
          />
          <div className="absolute right-2 bottom-2">
            <VoiceInputButton
              onTranscript={(text) => setQuestion((q) => (q ? q + text : text))}
              disabled={running}
            />
          </div>
        </div>
      </div>

      <div className="flex gap-3">
        <button className="btn-gradient" onClick={handleSubmit} disabled={running}>
          {running ? '处理中...' : '生成回答'}
        </button>
        {running && (
          <button
            className="px-4 py-2 rounded-btn text-sm border border-border text-text-2 hover:text-text transition-colors"
            onClick={handleCancel}
          >
            取消
          </button>
        )}
      </div>

      {/* 进度条 */}
      <div className="card-custom">
        <div className="flex items-center gap-3 mb-3">
          <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: '#1a1a3e' }}>
            <div
              className="h-full transition-all duration-500 brand-gradient rounded-full"
              style={{ width: `${dag.progress}%` }}
            />
          </div>
          <span className="text-text-3 text-xs shrink-0">{dag.progress}%</span>
        </div>
        <p className="text-text-2 text-xs">{dag.progressText}</p>
      </div>

      {/* DAG */}
      <div className="card-custom !p-3">
        <AgentDAG nodes={dag.nodes} />
      </div>

      {/* Agent 详情 */}
      <AgentDetailSection
        nodeData={nodeDataMap}
        writerEntries={dag.writerEntries}
        reviewEntries={dag.reviewEntries}
      />

      {/* 最终答案 */}
      {dag.finalAnswer && (
        <div className="card-custom">
          <div className="card-header">
            回答
            {dag.reviewTotal ? ` · 总分 ${dag.reviewTotal}/25` : ''}
            {dag.revisionCount ? ` · 修订 ${dag.revisionCount} 轮` : ''}
          </div>
          <p className="text-text text-sm leading-relaxed whitespace-pre-wrap">{dag.finalAnswer}</p>
        </div>
      )}

      {/* 错误 */}
      {dag.error && (
        <div className="p-4 rounded-card" style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)' }}>
          <p className="text-danger text-sm">{dag.error}</p>
        </div>
      )}

      {/* 评审分数卡片 */}
      {lastReview?.reviewers && (
        <div className="grid grid-cols-3 gap-4 mt-4">
          {(['correctness', 'completeness', 'advantage'] as const).map((key) => {
            const labels: Record<string, string> = { correctness: '正确性', completeness: '完整性', advantage: '优势展示' };
            const rd = lastReview.reviewers[key];
            if (!rd) return null;
            const sc = rd.scores || {};
            const avg = Object.keys(sc).length > 0
              ? (Object.values(sc).reduce((a: number, b: number) => a + b, 0) / Object.keys(sc).length)
              : 0;
            return (
              <MetricCard
                key={key}
                label={`${labels[key]} ${avg.toFixed(1)}/5`}
                value={rd.needs_revision ? '需修订' : '通过'}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

// ===== 多轮模拟（AI 候选人：你当面试官提问，AI 基于简历回答） =====
function MockInterview() {
  const [focusAreas, setFocusAreas] = useState<string[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [round, setRound] = useState(0);
  const [currentQuestion, setCurrentQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [hint, setHint] = useState('');
  const [projects, setProjects] = useState<string[]>([]);
  const [targetProject, setTargetProject] = useState('');
  const [suggestMode, setSuggestMode] = useState<'followup' | 'new'>('followup');
  const [history, setHistory] = useState<{ round: number; question: string; aiAnswer: string; reviewTotal?: number; questionType?: string }[]>([]);

  // 加载简历项目列表（供生成问题时选择）
  const loadProjects = useCallback(async () => {
    try {
      const res = await fetch('/api/v1/mock/projects');
      const data = await res.json();
      if (res.ok && Array.isArray(data.projects)) {
        setProjects(data.projects);
      }
    } catch {
      // 静默失败，项目选择不阻塞功能
    }
  }, []);

  const handleSuggest = async () => {
    if (!sessionId || suggesting) return;
    setSuggesting(true);
    try {
      const res = await fetch('/api/v1/mock/suggest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          focus_areas: focusAreas,
          project: targetProject,
          mode: suggestMode,
        }),
      });
      const data = await res.json();
      if (res.ok && data.question && data.question.trim()) {
        setCurrentQuestion(data.question);
        toast.success(suggestMode === 'followup' ? '已生成一个追问，可修改后提问' : '已生成一个新问题，可修改后提问');
      } else {
        toast.error(data.detail || '生成失败，请稍后重试');
      }
    } catch (err) {
      toast.error(`生成失败: ${(err as Error).message}，请检查后端是否运行`);
    } finally {
      setSuggesting(false);
    }
  };

  const handleStart = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/v1/mock/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ focus_areas: focusAreas }),
      });
      const data = await res.json();
      if (res.ok && data.session_id) {
        setSessionId(data.session_id);
        setHint(data.message || '你作为面试官，可以开始提问了。');
        loadProjects();  // 加载简历项目列表
        toast.success('面试开始，你可以提问了');
      } else {
        toast.error(data.detail || '启动失败');
      }
    } catch (err) {
      toast.error(`连接失败: ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleAsk = async () => {
    if (!currentQuestion.trim() || !sessionId) return;
    setLoading(true);
    try {
      const res = await fetch('/api/v1/mock/next', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, question: currentQuestion }),
      });
      const data = await res.json();
      if (res.ok) {
        setHistory([...history, {
          round: data.round_number,
          question: currentQuestion,
          aiAnswer: data.ai_answer || '',
          reviewTotal: data.review_total,
          questionType: data.question_type,
        }]);
        setCurrentQuestion('');
        setRound(data.round_number);
        if (data.is_last) {
          setSessionId(null);
          toast.success('本轮模拟面试完成！');
        }
      } else {
        toast.error(data.detail || '请求失败');
      }
    } catch (err) {
      toast.error(`连接失败: ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* 开始面板 */}
      {!sessionId && (
        <div className="card-custom">
          <div className="card-header">面试对练设置</div>
          <p className="text-text-2 text-sm mb-4">
            你扮演 <span className="text-primary font-medium">面试官</span>，输入问题；AI 扮演候选人，基于你的简历素材生成 STAR 回答。
          </p>
          <div className="flex flex-wrap gap-2 mb-4">
            <label className="text-sm text-text-2 mb-1.5 block w-full">建议追问方向（可选）</label>
            {['项目经验', '技术深度', '行为面试', '系统设计', '算法'].map((a) => (
              <button
                key={a}
                onClick={() => setFocusAreas(focusAreas.includes(a) ? focusAreas.filter((f) => f !== a) : [...focusAreas, a])}
                className={`px-3 py-1.5 rounded-btn text-xs transition-colors ${
                  focusAreas.includes(a)
                    ? 'bg-primary/20 text-primary-2 border border-primary/30'
                    : 'bg-surface border border-border text-text-3 hover:text-text-2'
                }`}
              >
                {a}
              </button>
            ))}
          </div>
          <button className="btn-gradient" onClick={handleStart} disabled={loading}>
            {loading ? '启动中...' : '开始面试对练'}
          </button>
        </div>
      )}

      {/* 提问面板 */}
      {sessionId && (
        <div className="space-y-4">
          <div className="card-custom">
            <div className="card-header">第 {round + 1} 轮 · 面试官提问</div>
            {hint && <p className="text-text-3 text-xs mb-3">{hint}</p>}
            <div className="relative">
              <textarea
                className="w-full bg-surface border border-border rounded-btn p-3 text-text text-sm resize-none focus:outline-none focus:border-primary transition-colors"
                rows={3}
                placeholder="输入你的面试问题，例如：请介绍一下 ResuMatch 项目的多Agent架构..."
                value={currentQuestion}
                onChange={(e) => setCurrentQuestion(e.target.value)}
                disabled={loading}
              />
              <div className="absolute right-2 bottom-2">
                <VoiceInputButton
                  onTranscript={(text) => setCurrentQuestion((q) => (q ? q + text : text))}
                  disabled={loading}
                />
              </div>
            </div>
            {/* AI 生成问题：项目选择 + 模式切换 */}
            <div className="flex flex-wrap items-center gap-3 mt-3">
              <div className="flex items-center gap-2">
                <span className="text-text-3 text-xs">项目</span>
                <select
                  className="bg-surface border border-border rounded-btn px-2 py-1.5 text-text text-xs focus:outline-none focus:border-primary"
                  value={targetProject}
                  onChange={(e) => setTargetProject(e.target.value)}
                  disabled={suggesting || loading}
                >
                  <option value="">不限</option>
                  {projects.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </div>
              <div className="flex gap-1 rounded-btn border border-border p-0.5">
                {(['followup', 'new'] as const).map((m) => (
                  <button
                    key={m}
                    onClick={() => setSuggestMode(m)}
                    className={`px-2.5 py-1 text-xs rounded-btn transition-colors ${
                      suggestMode === m ? 'bg-primary/20 text-primary-2' : 'text-text-3 hover:text-text-2'
                    }`}
                  >
                    {m === 'followup' ? '追问' : '新问题'}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex gap-3 mt-3">
              <button className="btn-gradient" onClick={handleAsk} disabled={loading || !currentQuestion.trim()}>
                {loading ? 'AI 回答中...' : '提问，AI 回答'}
              </button>
              <button
                className="px-4 py-2 rounded-btn text-sm border border-border text-text-2 hover:text-text transition-colors"
                onClick={handleSuggest}
                disabled={suggesting || loading}
                title="AI 根据已有问答和简历生成一个问题"
              >
                {suggesting ? '生成中...' : 'AI 生成问题'}
              </button>
            </div>
          </div>

          {/* AI 候选人的回答 */}
          {history.length > 0 && (
            <div className="space-y-4">
              {history.map((h, i) => (
                <div key={i} className="card-custom">
                  <div className="card-header flex items-center gap-2">
                    <span>第 {h.round} 轮 · 面试官提问</span>
                    {h.questionType && <span className="tag-skill !m-0">{h.questionType}</span>}
                    {h.reviewTotal != null && <span className="text-text-3 text-xs">评分 {h.reviewTotal}/25</span>}
                  </div>
                  <p className="text-text-2 text-sm mb-3" style={{ borderLeft: '2px solid #6366f1', paddingLeft: '0.75rem' }}>
                    {h.question}
                  </p>
                  <div className="text-xs text-text-3 uppercase tracking-wide mb-1.5">AI 候选人回答</div>
                  <p className="text-text text-sm leading-relaxed whitespace-pre-wrap">{h.aiAnswer}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ===== 面试页面 =====
export function Interview() {
  const [mode, setMode] = useState<'single' | 'mock'>('single');

  return (
    <div>
      <h1 className="text-2xl font-bold text-text mb-1">面试模拟</h1>
      <p className="text-text-2 text-sm mb-6">
        AI 驱动的面试问答，多Agent并行检索 + 多Agent评审
      </p>

      <div className="flex gap-1 mb-6">
        {(['single', 'mock'] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`px-4 py-2 text-sm font-medium rounded-btn transition-colors ${
              mode === m
                ? 'bg-surface text-primary-2 border border-border'
                : 'text-text-3 hover:text-text-2'
            }`}
          >
            {{ single: '单次问答', mock: '多轮模拟' }[m]}
          </button>
        ))}
      </div>

      {mode === 'single' ? <SingleQA /> : <MockInterview />}
    </div>
  );
}
