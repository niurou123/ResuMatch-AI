import { useState } from 'react';
import { toast } from 'sonner';
import { analyzeMatch, analyzeMatchProjects } from '@/lib/api';
import type { JDMatchResponse, ProjectMatchResponse } from '@/lib/types';

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className="px-5 py-2 rounded-lg text-sm font-medium transition-colors"
      style={{
        background: active ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : 'transparent',
        color: active ? '#fff' : '#8a8ab0',
        border: active ? 'none' : '1px solid #2a2a5a',
      }}
    >
      {children}
    </button>
  );
}

export function JDMatch() {
  const [tab, setTab] = useState<'skill' | 'project'>('skill');

  return (
    <div>
      <h1 className="text-2xl font-bold text-text mb-1">JD 匹配</h1>
      <p className="text-text-2 text-sm mb-6">
        分析简历与职位描述的匹配程度，覆盖技能与项目两个维度
      </p>

      <div className="flex gap-2 mb-6">
        <TabButton active={tab === 'skill'} onClick={() => setTab('skill')}>技能匹配</TabButton>
        <TabButton active={tab === 'project'} onClick={() => setTab('project')}>项目匹配</TabButton>
      </div>

      {tab === 'skill' ? <SkillMatch /> : <ProjectMatch />}
    </div>
  );
}

// ===== 技能匹配（原有逻辑 + 简历增强） =====
function SkillMatch() {
  const [jdText, setJdText] = useState('');
  const [position, setPosition] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<JDMatchResponse | null>(null);
  const [enhanced, setEnhanced] = useState<ProjectMatchResponse | null>(null);

  const handleAnalyze = async () => {
    if (!jdText.trim()) { toast.error('请输入 JD 文本'); return; }
    setLoading(true);
    try {
      // 并行调用：技能级分析 + 项目匹配（含简历内容增强）
      const [data, enh] = await Promise.all([
        analyzeMatch(jdText, position),
        analyzeMatchProjects(jdText, position).catch(() => null),
      ]);
      setResult(data);
      setEnhanced(enh);
      toast.success(`匹配度: ${data.match_score}%`);
    } catch (err) {
      toast.error(`分析失败: ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="grid grid-cols-[1fr_200px] gap-4 mb-5">
        <div>
          <label className="text-sm text-text-2 mb-1.5 block">JD 文本 <span className="text-danger">*</span></label>
          <textarea
            className="w-full bg-surface border border-border rounded-btn p-3 text-text text-sm resize-none focus:outline-none focus:border-primary transition-colors"
            rows={8}
            placeholder="粘贴职位描述 (JD) 文本..."
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
          />
        </div>
        <div>
          <label className="text-sm text-text-2 mb-1.5 block">目标职位</label>
          <input
            className="w-full bg-surface border border-border rounded-btn px-3 py-2 text-text text-sm focus:outline-none focus:border-primary transition-colors"
            placeholder="例如：AI 工程师"
            value={position}
            onChange={(e) => setPosition(e.target.value)}
          />
          <button className="btn-gradient w-full mt-3" onClick={handleAnalyze} disabled={loading}>
            {loading ? '分析中...' : '分析匹配度'}
          </button>
        </div>
      </div>

      {result && (
        <div className="space-y-5">
          <div className="card-custom text-center">
            <div
              className="text-6xl font-extrabold mb-2"
              style={{ background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a78bfa 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}
            >
              {result.match_score}%
            </div>
            <p className="text-text-3 text-sm">综合匹配度</p>
            <div className="mt-4 h-2 rounded-full overflow-hidden max-w-md mx-auto" style={{ background: '#1a1a3e' }}>
              <div className="h-full brand-gradient rounded-full transition-all duration-700" style={{ width: `${result.match_score}%` }} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="card-custom">
              <div className="card-header">匹配技能 ({result.matched_skills.length})</div>
              <div className="flex flex-wrap">
                {result.matched_skills.map((s, i) => <span key={i} className="tag-match">{s}</span>)}
              </div>
            </div>
            <div className="card-custom">
              <div className="card-header">技能差距 ({result.missing_skills.length})</div>
              <div className="flex flex-wrap">
                {result.missing_skills.map((s, i) => <span key={i} className="tag-missing">{s}</span>)}
              </div>
            </div>
          </div>

          {result.strength_analysis && (
            <div className="p-4 rounded-card" style={{ background: 'rgba(34,197,94,0.06)', border: '1px solid rgba(34,197,94,0.15)' }}>
              <p className="text-xs text-success font-medium uppercase tracking-wide mb-1.5">优势分析</p>
              <p className="text-text-2 text-sm leading-relaxed">{result.strength_analysis}</p>
            </div>
          )}

          {result.gap_analysis && (
            <div className="p-4 rounded-card" style={{ background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.15)' }}>
              <p className="text-xs text-warn font-medium uppercase tracking-wide mb-1.5">差距分析</p>
              <p className="text-text-2 text-sm leading-relaxed">{result.gap_analysis}</p>
            </div>
          )}

          {result.recommended_skills && result.recommended_skills.length > 0 && (
            <div className="p-4 rounded-card" style={{ background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.15)' }}>
              <p className="text-xs text-primary font-medium uppercase tracking-wide mb-1.5">建议补强</p>
              <div className="flex flex-wrap gap-2">
                {result.recommended_skills.map((s, i) => <span key={i} className="tag-skill">{s}</span>)}
              </div>
            </div>
          )}

          {/* 技术栈增强：保留原有 + 建议补充 */}
          {enhanced?.added_skills && enhanced.added_skills.length > 0 && (
            <div className="card-custom">
              <div className="card-header">🧩 技术栈增强（保留原有 + 建议补充）</div>
              <p className="text-text-3 text-xs mb-3">在原有技术栈基础上，为更匹配该岗位建议补充以下技能：</p>
              <div className="flex flex-wrap">
                {enhanced.added_skills.map((s, i) => <span key={i} className="tag-missing">{s} ＋</span>)}
              </div>
            </div>
          )}

          {/* 针对性简历内容（技术栈增强 + 项目描述增强） */}
          {enhanced?.resume_content && (
            <div className="card-custom">
              <div className="card-header">📄 针对性简历内容（面向该岗位优化）</div>
              <p className="text-text-3 text-xs mb-3">已保留原有技能，新增岗位要求的技能，并优化了 Top 匹配项目描述。</p>
              <pre className="text-text-2 text-sm leading-relaxed whitespace-pre-wrap font-sans">{enhanced.resume_content}</pre>
            </div>
          )}
        </div>
      )}
    </>
  );
}

// ===== 项目匹配（三维度项目-JD 匹配） =====
function ProjectMatch() {
  const [jdText, setJdText] = useState('');
  const [position, setPosition] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ProjectMatchResponse | null>(null);

  const handleAnalyze = async () => {
    if (!jdText.trim()) { toast.error('请输入 JD 文本'); return; }
    setLoading(true);
    try {
      const data = await analyzeMatchProjects(jdText, position);
      if (data.message) { toast.info(data.message); }
      setResult(data);
      if (data.top_project) {
        toast.success(`最佳匹配项目: ${data.top_project.name} (${data.top_project.match_score}分)`);
      }
    } catch (err) {
      toast.error(`分析失败: ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="grid grid-cols-[1fr_200px] gap-4 mb-5">
        <div>
          <label className="text-sm text-text-2 mb-1.5 block">JD 文本 <span className="text-danger">*</span></label>
          <textarea
            className="w-full bg-surface border border-border rounded-btn p-3 text-text text-sm resize-none focus:outline-none focus:border-primary transition-colors"
            rows={8}
            placeholder="粘贴职位描述 (JD) 文本..."
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
          />
          <p className="text-text-3 text-xs mt-2">自动提取 JD 需求，对项目库每个项目按 技术交集 / 年限 / 复杂度 三维度打分</p>
        </div>
        <div>
          <label className="text-sm text-text-2 mb-1.5 block">目标职位</label>
          <input
            className="w-full bg-surface border border-border rounded-btn px-3 py-2 text-text text-sm focus:outline-none focus:border-primary transition-colors"
            placeholder="例如：AI 工程师"
            value={position}
            onChange={(e) => setPosition(e.target.value)}
          />
          <button className="btn-gradient w-full mt-3" onClick={handleAnalyze} disabled={loading}>
            {loading ? '匹配中...' : '匹配项目'}
          </button>
        </div>
      </div>

      {result && (
        <div className="space-y-6">
          {result.message ? (
            <div className="p-4 rounded-card" style={{ background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.15)' }}>
              <p className="text-text-2 text-sm">{result.message}</p>
            </div>
          ) : (
            <>
              {/* JD 需求提取 */}
              <div className="card-custom">
                <div className="card-header">JD 需求提取</div>
                {result.jd_requirements?.tech_stack && result.jd_requirements.tech_stack.length > 0 && (
                  <div className="mb-3">
                    <p className="text-text-3 text-xs mb-2">技术栈要求</p>
                    <div className="flex flex-wrap">
                      {result.jd_requirements.tech_stack.map((s, i) => <span key={i} className="tag-match">{s}</span>)}
                    </div>
                  </div>
                )}
                {result.jd_requirements?.soft_skills && result.jd_requirements.soft_skills.length > 0 && (
                  <div className="mb-3">
                    <p className="text-text-3 text-xs mb-2">软技能要求</p>
                    <div className="flex flex-wrap">
                      {result.jd_requirements.soft_skills.map((s, i) => <span key={i} className="tag-skill">{s}</span>)}
                    </div>
                  </div>
                )}
                {result.jd_requirements?.experience_years != null && (
                  <p className="text-text-2 text-sm">经验年限：<span className="text-primary font-medium">{result.jd_requirements.experience_years} 年</span></p>
                )}
              </div>

              {/* 项目匹配排行 */}
              {result.projects.length > 0 && (
                <div className="card-custom">
                  <div className="card-header">项目匹配排行</div>
                  <div className="space-y-4">
                    {result.projects.map((p, i) => (
                      <div key={i} className="p-4 rounded-card" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid #2a2a5a' }}>
                        <div className="flex justify-between items-center mb-2">
                          <div>
                            <span className="text-text font-semibold">{p.name}</span>
                            {(p.role || p.time_period) && (
                              <span className="text-text-3 text-xs ml-2">{p.role} {p.time_period}</span>
                            )}
                          </div>
                          <span className="text-2xl font-extrabold" style={{ background: 'linear-gradient(135deg,#6366f1,#8b5cf6)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                            {Math.round(p.match_score)}
                          </span>
                        </div>
                        {p.matched_tech.length > 0 && (
                          <div className="flex flex-wrap mb-3">
                            {p.matched_tech.slice(0, 8).map((t, j) => <span key={j} className="tag-match">{t}</span>)}
                          </div>
                        )}
                        <div className="grid grid-cols-4 gap-3">
                          <Metric label="技术交集" value={`${Math.round(p.tech_overlap * 100)}%`} />
                          <Metric label="年限匹配" value={`${Math.round(p.years_match * 100)}%`} />
                          <Metric label="复杂度" value={`${Math.round(p.complexity_score * 100)}%`} />
                          <Metric label="综合" value={`${Math.round(p.match_score)}`} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 技术栈增强：保留原有 + 建议补充 */}
              {result.added_skills && result.added_skills.length > 0 && (
                <div className="card-custom">
                  <div className="card-header">🧩 技术栈增强（保留原有 + 建议补充）</div>
                  <p className="text-text-3 text-xs mb-3">
                    在原有技术栈基础上，为更匹配该岗位建议补充以下技能：
                  </p>
                  <div className="flex flex-wrap">
                    {result.added_skills.map((s, i) => <span key={i} className="tag-missing">{s} ＋</span>)}
                  </div>
                </div>
              )}

              {/* 针对性生成 */}
              {(result.targeted_answer || result.targeted_resume_desc) && result.top_project && (
                <div className="space-y-4">
                  <div className="card-custom">
                    <div className="card-header">🎯 针对性 STAR 回答（基于「{result.top_project.name}」）</div>
                    <p className="text-text-2 text-sm leading-relaxed whitespace-pre-wrap">{result.targeted_answer || '（LLM 不可用或生成失败，跳过）'}</p>
                  </div>
                  {result.targeted_resume_desc && (
                    <div className="card-custom">
                      <div className="card-header">📝 针对性简历项目描述</div>
                      <pre className="text-text-2 text-sm leading-relaxed whitespace-pre-wrap font-sans">{result.targeted_resume_desc}</pre>
                    </div>
                  )}
                </div>
              )}

              {/* 针对性完整简历内容（技术栈增强 + 项目描述增强） */}
              {result.resume_content && (
                <div className="card-custom">
                  <div className="card-header">📄 针对性简历内容（面向该岗位优化）</div>
                  <p className="text-text-3 text-xs mb-3">
                    已保留原有技能，新增岗位要求的技能，并优化了 Top 匹配项目描述。
                  </p>
                  <pre className="text-text-2 text-sm leading-relaxed whitespace-pre-wrap font-sans">{result.resume_content}</pre>
                </div>
              )}

              {/* 未覆盖技术 */}
              {result.missing_skills && result.missing_skills.length > 0 && (
                <div className="card-custom">
                  <div className="card-header">项目库未覆盖的 JD 技术</div>
                  <div className="flex flex-wrap">
                    {result.missing_skills.map((s, i) => <span key={i} className="tag-missing">{s}</span>)}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-card text-center">
      <div className="text-lg font-bold text-text">{value}</div>
      <div className="text-text-3 text-xs mt-0.5">{label}</div>
    </div>
  );
}
