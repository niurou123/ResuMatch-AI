import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppLayout } from '@/components/layout/AppLayout';
import { ResumeUpload } from '@/pages/ResumeUpload';
import { Interview } from '@/pages/Interview';
import { SelfIntro } from '@/pages/SelfIntro';
import { JDMatch } from '@/pages/JDMatch';
import { Profile } from '@/pages/Profile';
import { Toaster } from 'sonner';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30000 },
    mutations: { retry: 0 },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/" element={<Navigate to="/resume" replace />} />
            <Route path="/resume" element={<ResumeUpload />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/interview" element={<Interview />} />
            <Route path="/intro" element={<SelfIntro />} />
            <Route path="/match" element={<JDMatch />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: '#13132b',
            border: '1px solid #2a2a5a',
            color: '#e0e0f0',
            fontSize: '0.875rem',
          },
        }}
      />
    </QueryClientProvider>
  );
}
