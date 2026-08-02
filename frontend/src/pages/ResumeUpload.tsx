import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';
import { uploadResume } from '@/lib/api';
import { FileUpload } from '@/components/shared/FileUpload';
import { MetricCard } from '@/components/shared/MetricCard';
import { ConfidenceBar } from '@/components/shared/ConfidenceBar';
import { SkillCloud } from '@/components/shared/SkillCloud';
import type { ResumeUploadResponse, ProjectItem, AchievementItem } from '@/lib/types';

export function ResumeUpload() {
  const [result, setResult] = useState<ResumeUploadResponse | null>(null);
  const [activeTab, setActiveTab] = useState<string>('basic');

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadResume(file),
    onSuccess: (data) => {
      if (data.success) {
        setResult(data);
        toast.success(data.message);
      } else {
        toast.error(data.message || '解析失败');
      }
    },
    onError: (err: Error) => toast.error(`上传失败: ${err.message}`),
  });

  const p = result?.profile;
  const v = result?.verification;
  const tabs = ['basic', 'skills', 'projects', 'achievements'];

  return (
    <div>
      <h1 className="text-2xl font-bold text-text mb-1">简历上传</h1>
      <p className="text-text-2 text-sm mb-6">
        AI 蒸馏解析 — 纯规则提取，零 LLM 介入，每个字段可溯源
      </p>

      <FileUpload
        onUpload={(f) => uploadMutation.mutate(f)}
        uploading={uploadMutation.isPending}
      />

      {result && p && (
        <div className="mt-6 space-y-5">
          {/* 指标卡片 */}
          <div className="grid grid-cols-4 gap-4">
            <MetricCard label="技能" value={p.skills?.length ?? 0} />
            <MetricCard label="项目经验" value={p.projects?.length ?? 0} />
            <MetricCard label="成果" value={p.achievements?.length ?? 0} />
            <MetricCard label="教育背景" value={p.education?.length ?? 0} />
          </div>

          {/* 置信度 */}
          {v && (
            <ConfidenceBar
              high={v.high_confidence ?? 0}
              medium={v.medium_confidence ?? 0}
              low={v.low_confidence ?? 0}
            />
          )}

          {/* 详情 Tab */}
          <div className="card-custom">
            <div className="flex gap-1 mb-4 border-b border-border">
              {tabs.map((t) => (
                <button
                  key={t}
                  onClick={() => setActiveTab(t)}
                  className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-[1px] ${
                    activeTab === t
                      ? 'text-primary-2 border-primary'
                      : 'text-text-3 border-transparent hover:text-text-2'
                  }`}
                >
                  {{ basic: '基本信息', skills: '技能', projects: '项目经验', achievements: '成果' }[t]}
                </button>
              ))}
            </div>

            {activeTab === 'basic' && (
              <div className="space-y-2 text-sm">
                <InfoRow label="姓名" value={p.name} />
                <InfoRow label="邮箱" value={p.email} />
                <InfoRow label="手机" value={p.phone} />
                {p.summary && <InfoRow label="简介" value={p.summary} />}
              </div>
            )}

            {activeTab === 'skills' && <SkillCloud skills={p.skills} />}

            {activeTab === 'projects' && (
              <div className="space-y-3">
                {p.projects.map((proj: ProjectItem, i: number) => (
                  <details key={i} className="agent-detail">
                    <summary>{proj.name || `项目 ${i + 1}`}</summary>
                    <div className="body">
                      {proj.role && <p>角色: {proj.role}</p>}
                      {proj.tech_stack && (
                        <p>技术栈: {proj.tech_stack.join(', ')}</p>
                      )}
                      {proj.key_result && <p>成果: {proj.key_result}</p>}
                      {proj.time_period && <p>时间: {proj.time_period}</p>}
                      {proj.description && <p className="mt-1">{proj.description}</p>}
                    </div>
                  </details>
                ))}
              </div>
            )}

            {activeTab === 'achievements' && (
              <div className="space-y-2">
                {p.achievements.map((a: AchievementItem, i: number) => (
                  <div key={i} className="flex items-start gap-2 text-sm">
                    <span className="text-success mt-1">&#9679;</span>
                    <span className="text-text-2">{a.description}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value?: string }) {
  if (!value) return null;
  return (
    <div className="flex gap-3">
      <span className="text-text-3 w-16 shrink-0">{label}</span>
      <span className="text-text">{value}</span>
    </div>
  );
}
