import { NavLink } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { checkHealth, getSystemInfo } from '@/lib/api';
import { APP_NAME, APP_VERSION, NAV_ITEMS } from '@/lib/constants';

/** 侧边栏：白底黑字，靠右侧细边框与内容区分隔 */
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
  const model = sysInfo?.model || '—';

  return (
    <aside className="fixed left-0 top-0 flex h-screen w-[224px] flex-col border-r border-border bg-white">
      {/* Logo 区 */}
      <div className="flex h-12 flex-none items-center gap-2 border-b border-border px-4">
        <span className="brand-text truncate text-[16px]">{APP_NAME}</span>
        <span className="mono text-[10px] text-text-3">{APP_VERSION}</span>
      </div>

      {/* 运行状态 */}
      <div className="mx-3 mt-3 flex-none rounded-[4px] border border-border bg-surface-2 px-3 py-2">
        <div className="flex items-center gap-2">
          <span
            className={`h-1.5 w-1.5 flex-none rounded-full ${
              connected ? 'bg-success animate-pulse-dot' : 'bg-danger'
            }`}
          />
          <span className="text-[13px] font-medium text-text">
            {connected ? 'API 已连接' : 'API 离线'}
          </span>
        </div>
        <div className="mono mt-1 truncate text-[11px] text-text-3" title={model}>
          {connected ? `${model} · ${totalDocs} 条索引` : 'python -m src.api.main'}
        </div>
      </div>

      {/* 菜单 */}
      <nav className="mt-3 flex-1 overflow-y-auto px-2">
        {NAV_ITEMS.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `relative mb-0.5 flex h-10 items-center rounded-[4px] px-3 text-[14.5px] transition-colors ${
                isActive
                  ? 'bg-primary-light font-medium text-primary'
                  : 'text-nav-text hover:bg-nav-hover hover:text-text'
              }`
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <span className="absolute left-0 top-1/2 h-4 w-[2px] -translate-y-1/2 bg-primary" />
                )}
                {label}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* 底部技术栈 */}
      <div className="flex-none border-t border-border px-4 py-3">
        <p className="mono text-[10.5px] leading-relaxed text-text-3">
          LangGraph · FastAPI
          <br />
          Milvus Lite · bge-small-zh
        </p>
      </div>
    </aside>
  );
}
