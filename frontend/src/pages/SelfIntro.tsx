import { useState } from 'react';
import { toast } from 'sonner';
import { generateIntro } from '@/lib/api';

export function SelfIntro() {
  const [position, setPosition] = useState('');
  const [company, setCompany] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ intro_30s: string; intro_1min: string; intro_3min: string } | null>(null);
  const [activeTab, setActiveTab] = useState<string>('1min');

  const handleGenerate = async () => {
    if (!position.trim()) { toast.error('请输入目标职位'); return; }
    setLoading(true);
    try {
      const data = await generateIntro(position, company, '1min');
      setResult(data);
      toast.success('自我介绍已生成');
    } catch (err) {
      toast.error(`生成失败: ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  const tabs: { key: string; label: string; content: string | undefined; chars: number }[] = [
    { key: '30s', label: '30 秒版', content: result?.intro_30s, chars: result?.intro_30s?.length || 0 },
    { key: '1min', label: '1 分钟版', content: result?.intro_1min, chars: result?.intro_1min?.length || 0 },
    { key: '3min', label: '3 分钟版', content: result?.intro_3min, chars: result?.intro_3min?.length || 0 },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold text-text mb-1">自我介绍</h1>
      <p className="text-text-2 text-sm mb-6">
        基于简历素材，LLM 生成 30 秒/1 分钟/3 分钟三个版本的自我介绍
      </p>

      <div className="grid grid-cols-2 gap-4 mb-5">
        <div>
          <label className="text-sm text-text-2 mb-1.5 block">目标职位 <span className="text-danger">*</span></label>
          <input
            className="w-full bg-surface border border-border rounded-btn px-3 py-2 text-text text-sm focus:outline-none focus:border-primary transition-colors"
            placeholder="例如：后端开发工程师"
            value={position}
            onChange={(e) => setPosition(e.target.value)}
          />
        </div>
        <div>
          <label className="text-sm text-text-2 mb-1.5 block">目标公司</label>
          <input
            className="w-full bg-surface border border-border rounded-btn px-3 py-2 text-text text-sm focus:outline-none focus:border-primary transition-colors"
            placeholder="例如：字节跳动（选填）"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
          />
        </div>
      </div>

      <button className="btn-gradient" onClick={handleGenerate} disabled={loading}>
        {loading ? '生成中...' : '生成自我介绍'}
      </button>

      {result && (
        <div className="mt-6">
          <div className="flex gap-1 mb-4 border-b border-border">
            {tabs.map((t) => (
              <button
                key={t.key}
                onClick={() => setActiveTab(t.key)}
                className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-[1px] ${
                  activeTab === t.key
                    ? 'text-primary-2 border-primary'
                    : 'text-text-3 border-transparent hover:text-text-2'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
          {tabs
            .filter((t) => t.key === activeTab)
            .map((t) => (
              <div key={t.key} className="card-custom">
                <div className="card-header">
                  {t.label} &middot; {t.chars} 字
                </div>
                <p className="text-text text-sm leading-relaxed whitespace-pre-wrap">
                  {t.content || '暂无内容'}
                </p>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
