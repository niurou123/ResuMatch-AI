import { NavLink } from 'react-router-dom';
import { Circle } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { checkHealth, getSystemInfo } from '@/lib/api';
import { APP_NAME, APP_TAGLINE, NAV_ITEMS } from '@/lib/constants';

export function Sidebar() {
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: checkHealth,
    refetchInterval: 30000,
  });

  const { data: sysInfo } = useQuery({
    queryKey: ['systemInfo'],
    queryFn: getSystemInfo,
    enabled: !!health,
    refetchInterval: 30000,
  });

  const connected = health?.status === 'ok';
  const totalDocs = sysInfo?.collections
    ? Object.values(sysInfo.collections).reduce((a, b) => a + b, 0)
    : 0;
  const model = sysInfo?.model || 'N/A';

  return (
    <aside
      className="w-64 h-screen flex flex-col fixed left-0 top-0 border-r border-border overflow-y-auto"
      style={{ background: '#08081a' }}
    >
      {/* 品牌 */}
      <div className="px-5 pt-6 pb-4">
        <h2 className="text-xl font-bold m-0">
          <span className="brand-text font-extrabold tracking-tight">{APP_NAME}</span>
        </h2>
        <p className="text-text-3 text-[11px] mt-0.5">{APP_TAGLINE}</p>
      </div>

      {/* API 状态 */}
      <div className="px-4 mb-4">
        {connected ? (
          <div
            className="flex items-center gap-2 px-3.5 py-2.5 rounded-btn text-sm"
            style={{
              background: 'rgba(34,197,94,0.08)',
              border: '1px solid rgba(34,197,94,0.2)',
            }}
          >
            <Circle className="w-2 h-2 fill-current text-success" />
            <div>
              <div className="font-medium text-text">API 已连接</div>
              <div className="text-[11px] text-text-3">
                {model} &middot; 已索引 {totalDocs} 条
              </div>
            </div>
          </div>
        ) : (
          <div
            className="flex items-center gap-2 px-3.5 py-2.5 rounded-btn text-sm"
            style={{
              background: 'rgba(239,68,68,0.08)',
              border: '1px solid rgba(239,68,68,0.2)',
            }}
          >
            <Circle className="w-2 h-2 fill-current text-danger" />
            <div>
              <div className="font-medium text-text">API 离线</div>
              <div className="text-[11px] text-text-3">启动: python -m src.api.main</div>
            </div>
          </div>
        )}
      </div>

      {/* 导航 */}
      <nav className="flex-1 px-3">
        <p className="text-text-3 text-[11px] uppercase tracking-wider mb-1.5 px-2">
          功能导航
        </p>
        {NAV_ITEMS.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `block px-3 py-2.5 rounded-btn text-sm mb-0.5 transition-colors ${
                isActive
                  ? 'text-primary-2 bg-surface font-medium'
                  : 'text-text-2 hover:text-text hover:bg-surface/50'
              }`
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>

      {/* 底部 */}
      <div className="px-4 pb-5 pt-3">
        <div className="border-t border-border pt-3">
          <p className="text-[10px] text-center text-text-3">
            LangGraph Multi-Agent v3.0<br />
            DeepSeek + ChromaDB + bge
          </p>
        </div>
      </div>
    </aside>
  );
}
