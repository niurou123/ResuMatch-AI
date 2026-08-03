import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { getProfileDetail, updateProfileProject, deleteProfileProject, updateProfileSkills, uploadProjectDoc, listProjectDocs } from '@/lib/api';

interface ProjectItem {
  name: string;
  role?: string;
  tech_stack?: string[];
  time_period?: string;
  key_result?: string;
  description?: string;
  details?: string[];
  difficulties?: string[];
  challenges?: string;
  responsibilities?: string;
}

const EMPTY_PROJECT: ProjectItem = {
  name: '',
  role: '',
  tech_stack: [],
  time_period: '',
  key_result: '',
  description: '',
  details: [''],
  difficulties: [''],
  challenges: '',
  responsibilities: '',
};

export function Profile() {
  const [profile, setProfile] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getProfileDetail();
      setProfile(data.profile || {});
    } catch (err) {
      toast.error(`加载档案失败: ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const projects: ProjectItem[] = (profile.projects || []) as ProjectItem[];
  const skills: any[] = (profile.skills || []) as any[];
  const skillNames = skills.map((s) => (typeof s === 'string' ? s : s?.name || '')).filter(Boolean);

  // ===== 技能编辑 =====
  const [skillInput, setSkillInput] = useState('');
  const [skillList, setSkillList] = useState<string[]>([]);

  // 同步 skillList 到 profile.skills
  useEffect(() => { setSkillList(skillNames); }, [profile]);

  const handleSaveSkills = async () => {
    try {
      const res = await updateProfileSkills(skillList.filter((s) => s.trim()));
      toast.success(res.message || '技能已保存');
      await load();
    } catch (err) {
      toast.error(`保存技能失败: ${(err as Error).message}`);
    }
  };

  const addSkill = () => {
    const s = skillInput.trim();
    if (!s) return;
    if (!skillList.includes(s)) setSkillList([...skillList, s]);
    setSkillInput('');
  };

  // ===== 项目编辑 =====
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [form, setForm] = useState<ProjectItem>({ ...EMPTY_PROJECT });

  const startEdit = (index: number) => {
    setEditingIndex(index);
    const p = projects[index];
    setForm({
      ...EMPTY_PROJECT,
      ...p,
      details: (p.details && p.details.length ? p.details : ['']),
      difficulties: (p.difficulties && p.difficulties.length ? p.difficulties : ['']),
    });
  };

  const startAdd = () => {
    setEditingIndex(-1);
    setForm({ ...EMPTY_PROJECT });
  };

  const handleSaveProject = async () => {
    if (!form.name.trim()) { toast.error('项目名称不能为空'); return; }
    try {
      const res = await updateProfileProject({
        project_index: editingIndex ?? -1,
        name: form.name,
        role: form.role || '',
        tech_stack: (form.tech_stack || []).map((t) => t.trim()).filter(Boolean),
        time_period: form.time_period || '',
        key_result: form.key_result || '',
        description: form.description || '',
        details: (form.details || []).map((d) => d.trim()).filter(Boolean),
        difficulties: (form.difficulties || []).map((d) => d.trim()).filter(Boolean),
        challenges: form.challenges || '',
        responsibilities: form.responsibilities || '',
      });
      toast.success(res.message || '项目已保存');
      setEditingIndex(null);
      await load();
    } catch (err) {
      toast.error(`保存项目失败: ${(err as Error).message}`);
    }
  };

  const handleDeleteProject = async (index: number) => {
    try {
      const res = await deleteProfileProject(index);
      toast.success(res.message || '项目已删除');
      await load();
    } catch (err) {
      toast.error(`删除项目失败: ${(err as Error).message}`);
    }
  };

  const setTechStack = (text: string) => {
    setForm({ ...form, tech_stack: text.split(/[,，、]/).map((t) => t.trim()).filter(Boolean) });
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-text mb-1">档案</h1>
      <p className="text-text-2 text-sm mb-6">
        上传简历自动解析入库；此处可手动完善技能与项目细节，供面试模拟使用
      </p>

      {loading ? (
        <p className="text-text-2 text-sm">加载中...</p>
      ) : (
        <div className="space-y-5">
          {/* 基本信息 */}
          {profile.name && (
            <div className="card-custom">
              <div className="card-header">基本信息</div>
              <div className="flex gap-6 text-sm flex-wrap">
                <span className="text-text-2">{profile.name}</span>
                {profile.email && <span className="text-text-3">{profile.email}</span>}
                {profile.phone && <span className="text-text-3">{profile.phone}</span>}
              </div>
            </div>
          )}

          {/* 技能编辑 */}
          <div className="card-custom">
            <div className="card-header">技能（{skillList.length}）</div>
            <div className="flex flex-wrap gap-2 mb-3">
              {skillList.map((s, i) => (
                <span key={i} className="tag-skill">
                  {s}
                  <button
                    className="ml-1 text-danger hover:opacity-70"
                    onClick={() => setSkillList(skillList.filter((_, j) => j !== i))}
                    title="移除"
                  >×</button>
                </span>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                className="flex-1 bg-surface border border-border rounded-btn px-3 py-2 text-text text-sm focus:outline-none focus:border-primary"
                placeholder="输入技能名后回车添加"
                value={skillInput}
                onChange={(e) => setSkillInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addSkill(); } }}
              />
              <button className="px-3 py-2 rounded-btn text-sm border border-border text-text-2 hover:text-text" onClick={addSkill}>添加</button>
              <button className="btn-gradient" onClick={handleSaveSkills}>保存技能</button>
            </div>
          </div>

          {/* 项目列表 */}
          <div className="card-custom">
            <div className="flex items-center justify-between mb-3">
              <div className="card-header !mb-0">项目经验（{projects.length}）</div>
              <button className="px-3 py-1.5 rounded-btn text-sm btn-gradient" onClick={startAdd}>＋ 新增项目</button>
            </div>

            <div className="space-y-4">
              {projects.map((p, i) => (
                <div key={i} className="p-4 rounded-card" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid #2a2a5a' }}>
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <span className="text-text font-semibold">{p.name || '未命名项目'}</span>
                      {p.role && <span className="text-text-3 text-xs ml-2">{p.role}</span>}
                      {p.time_period && <span className="text-text-3 text-xs ml-2">{p.time_period}</span>}
                    </div>
                    <div className="flex gap-2">
                      <button className="px-2.5 py-1 rounded-btn text-xs border border-border text-text-2 hover:text-text" onClick={() => startEdit(i)}>编辑</button>
                      <button className="px-2.5 py-1 rounded-btn text-xs border border-border text-danger" onClick={() => handleDeleteProject(i)}>删除</button>
                    </div>
                  </div>
                  {p.tech_stack && p.tech_stack.length > 0 && (
                    <div className="flex flex-wrap mb-2">
                      {p.tech_stack.slice(0, 12).map((t, j) => <span key={j} className="tag-match !m-0 mr-1 mb-1">{t}</span>)}
                    </div>
                  )}
                  {p.key_result && <p className="text-text-2 text-xs mb-1">成果: {p.key_result}</p>}
                  {p.description && <p className="text-text-3 text-xs mb-1">描述: {p.description}</p>}
                  {(p.details || []).filter(Boolean).length > 0 && (
                    <div className="mb-1">
                      <span className="text-text-3 text-xs">项目细节:</span>
                      {(p.details || []).filter(Boolean).map((d, j) => (
                        <p key={j} className="text-text-3 text-xs ml-3">• {d}</p>
                      ))}
                    </div>
                  )}
                  {(p.difficulties || []).filter(Boolean).length > 0 && (
                    <div className="mb-1">
                      <span className="text-text-3 text-xs">项目难点问题:</span>
                      {(p.difficulties || []).filter(Boolean).map((d, j) => (
                        <p key={j} className="text-text-3 text-xs ml-3">• {d}</p>
                      ))}
                    </div>
                  )}
                  {p.challenges && <p className="text-text-3 text-xs mb-1">挑战: {p.challenges}</p>}
                  {p.responsibilities && <p className="text-text-3 text-xs">职责: {p.responsibilities}</p>}
                  {/* 项目资料库（RAG 文档上传） */}
                  <ProjectDocs projectName={p.name || ''} />
                </div>
              ))}
              {projects.length === 0 && <p className="text-text-3 text-sm">暂无项目，可点击「新增项目」手动添加</p>}
            </div>
          </div>

          {/* 编辑/新增表单 */}
          {editingIndex !== null && (
            <div className="card-custom" style={{ border: '1px solid #6366f1' }}>
              <div className="card-header">{editingIndex === -1 ? '新增项目' : `编辑: ${projects[editingIndex]?.name || ''}`}</div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="项目名称 *" value={form.name} onChange={(v) => setForm({ ...form, name: v })} />
                <Field label="角色" value={form.role || ''} onChange={(v) => setForm({ ...form, role: v })} />
                <Field label="时间段" value={form.time_period || ''} onChange={(v) => setForm({ ...form, time_period: v })} />
                <Field label="技术栈（逗号分隔）" value={(form.tech_stack || []).join(', ')} onChange={setTechStack} />
              </div>
              <TextArea label="关键成果" value={form.key_result || ''} onChange={(v) => setForm({ ...form, key_result: v })} />
              <TextArea label="项目描述" value={form.description || ''} onChange={(v) => setForm({ ...form, description: v })} />
              <ListEditor
                label="项目细节（分点填写，可添加）"
                items={form.details || ['']}
                onChange={(items) => setForm({ ...form, details: items })}
              />
              <ListEditor
                label="项目难点问题（分点填写，可添加）"
                items={form.difficulties || ['']}
                onChange={(items) => setForm({ ...form, difficulties: items })}
              />
              <TextArea label="职责明细" value={form.responsibilities || ''} onChange={(v) => setForm({ ...form, responsibilities: v })} />
              <TextArea label="挑战与解决（面试追问重点）" value={form.challenges || ''} onChange={(v) => setForm({ ...form, challenges: v })} />
              <div className="flex gap-3 mt-3">
                <button className="btn-gradient" onClick={handleSaveProject}>保存</button>
                <button className="px-4 py-2 rounded-btn text-sm border border-border text-text-2 hover:text-text" onClick={() => setEditingIndex(null)}>取消</button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="text-sm text-text-2 mb-1 block">{label}</label>
      <input
        className="w-full bg-surface border border-border rounded-btn px-3 py-2 text-text text-sm focus:outline-none focus:border-primary"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

function TextArea({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div className="mt-3">
      <label className="text-sm text-text-2 mb-1 block">{label}</label>
      <textarea
        className="w-full bg-surface border border-border rounded-btn p-3 text-text text-sm resize-none focus:outline-none focus:border-primary"
        rows={2}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

// 项目资料库：上传项目文档（技术栈/模型/细节）存入 RAG，面试回答会检索
function ProjectDocs({ projectName }: { projectName: string }) {
  const [docs, setDocs] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const loadDocs = useCallback(async () => {
    if (!projectName) return;
    try {
      const data = await listProjectDocs(projectName);
      setDocs(data.documents || []);
    } catch {
      setDocs([]);
    }
  }, [projectName]);

  useEffect(() => { loadDocs(); }, [loadDocs]);

  const handleUpload = async (file: File | undefined) => {
    if (!file || !projectName) return;
    setUploading(true);
    try {
      const res = await uploadProjectDoc(projectName, file);
      toast.success(res.message || '文档已上传并索引');
      await loadDocs();
    } catch (err) {
      toast.error(`上传失败: ${(err as Error).message}`);
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  };

  return (
    <div className="mt-3 pt-3" style={{ borderTop: '1px dashed #2a2a5a' }}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-text-3 text-xs">📄 项目资料库（面试回答会检索）</span>
        <button
          className="px-2.5 py-1 rounded-btn text-xs border border-border text-text-2 hover:text-text"
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
        >
          {uploading ? '上传中...' : '上传资料'}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.md,.txt"
          className="hidden"
          onChange={(e) => handleUpload(e.target.files?.[0])}
        />
      </div>
      {docs.length > 0 ? (
        <ul className="space-y-0.5">
          {docs.map((d, i) => (
            <li key={i} className="text-text-3 text-xs">{d}</li>
          ))}
        </ul>
      ) : (
        <p className="text-text-3 text-xs">尚未上传资料，可上传技术栈/模型/项目细节文档</p>
      )}
    </div>
  );
}

// 动态分点编辑器：初始 1 项，可添加（自动编号 1. 2. 3. ...）
function ListEditor({ label, items, onChange }: { label: string; items: string[]; onChange: (v: string[]) => void }) {
  const update = (idx: number, val: string) => {
    const next = items.map((it, i) => (i === idx ? val : it));
    onChange(next);
  };
  const remove = (idx: number) => {
    const next = items.filter((_, i) => i !== idx);
    onChange(next.length ? next : ['']);
  };
  const add = () => onChange([...items, '']);

  return (
    <div className="mt-3">
      <label className="text-sm text-text-2 mb-1 block">{label}</label>
      <div className="space-y-2">
        {items.map((it, i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="text-text-3 text-xs shrink-0 w-5">{i + 1}.</span>
            <input
              className="flex-1 bg-surface border border-border rounded-btn px-3 py-1.5 text-text text-sm focus:outline-none focus:border-primary"
              value={it}
              placeholder={`第 ${i + 1} 点`}
              onChange={(e) => update(i, e.target.value)}
            />
            <button
              className="px-2 py-1 rounded-btn text-xs border border-border text-danger"
              onClick={() => remove(i)}
              title="删除此项"
            >×</button>
          </div>
        ))}
      </div>
      <button
        className="mt-2 px-3 py-1 rounded-btn text-xs border border-border text-text-2 hover:text-text"
        onClick={add}
      >
        ＋ 添加一项
      </button>
    </div>
  );
}
