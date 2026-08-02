import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';

export function AppLayout() {
  return (
    <div className="flex min-h-screen bg-bg">
      <Sidebar />
      <main className="ml-64 flex-1 p-8 max-w-[1200px]">
        <Outlet />
      </main>
    </div>
  );
}
