import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Sidebar } from './Sidebar';
import { checkHealth } from '@/lib/api';
import { NAV_ITEMS } from '@/lib/constants';

/**
 * 应用骨架：对齐 vue-pure-admin（peidi-bi 参考项目）的后台布局
 *
 *   ┌──────────┬──────────────────────────────┐
 *   │ 侧边栏    │ 顶栏：面包屑 ······ 状态/版本  │  48px
 *   │ 210px    ├──────────────────────────────┤
 *   │          │ 内容区（卡片化）               │
 *   └──────────┴──────────────────────────────┘
 */
export function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const current = NAV_ITEMS.find((n) => location.pathname.startsWith(n.to));
  const pageTitle = current?.label ?? '工作台';

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: checkHealth,
    refetchInterval: 30000,
  });
  const connected = health?.status === 'ok';

  return (
    <div className="min-h-screen bg-bg text-text">
      <Sidebar />

      {/* 顶栏 */}
      <header className="fixed left-[224px] right-0 top-0 z-20 flex h-12 items-center justify-between border-b border-border bg-white px-5">
        {/* 面包屑 */}
        <div className="flex items-center gap-1.5 text-[13px]">
          <button
            type="button"
            onClick={() => navigate('/resume')}
            className="text-text-3 transition-colors hover:text-text"
          >
            工作台
          </button>
          <span className="text-text-4">/</span>
          <span className="font-medium text-text">{pageTitle}</span>
        </div>

        {/* 右侧：连接状态 + 版本 */}
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5 text-[12px] text-text-2">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                connected ? 'bg-success animate-pulse-dot' : 'bg-danger'
              }`}
            />
            {connected ? '服务正常' : '服务离线'}
          </span>
          <span className="mono text-[11px] text-text-3">v3.0</span>
        </div>
      </header>

      {/* 内容区 */}
      <main className="ml-[224px] min-h-screen pt-12">
        <div className="w-full px-6 py-5">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
