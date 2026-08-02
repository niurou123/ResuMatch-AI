import type { SkillItem } from '@/lib/types';

interface SkillCloudProps {
  skills: SkillItem[];
}

export function SkillCloud({ skills }: SkillCloudProps) {
  if (!skills || skills.length === 0) {
    return <p className="text-text-3 text-sm">暂无技能数据</p>;
  }

  return (
    <div className="flex flex-wrap">
      {skills.map((s, i) => (
        <span key={i} className="tag-skill">
          {s.name}
          {s.category && (
            <span className="text-text-3 ml-1 text-[10px]">({s.category})</span>
          )}
        </span>
      ))}
    </div>
  );
}
