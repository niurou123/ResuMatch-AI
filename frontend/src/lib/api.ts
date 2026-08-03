// API 客户端 — 对应后端 src/api/routes.py 的 10 个端点
import { API_URL } from './constants';
import type {
  HealthResponse, ResumeUploadResponse, ProfileResponse,
  InterviewRequest, InterviewResponse,
  MockStartRequest, MockStartResponse,
  MockNextRequest, MockNextResponse,
  SelfIntroRequest, SelfIntroResponse,
  JDMatchRequest, JDMatchResponse,
  ProjectMatchRequest, ProjectMatchResponse,
  SystemInfoResponse,
} from './types';

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new ApiError(res.status, text || res.statusText);
  }
  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PUT', body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) =>
    request<T>(path, { method: 'DELETE' }),
  upload: <T>(path: string, formData: FormData) =>
    request<T>(path, { method: 'POST', body: formData, headers: {} }),
};

// ===== 健康检查 =====
export const checkHealth = () =>
  api.get<HealthResponse>('/api/v1/health');

// ===== 简历 =====
export const uploadResume = (file: File) => {
  const fd = new FormData();
  fd.append('file', file);
  return api.upload<ResumeUploadResponse>('/api/v1/resume/upload', fd);
};

export const getProfile = () =>
  api.get<ProfileResponse>('/api/v1/resume/profile');

// ===== 档案管理 =====
export const getProfileDetail = () =>
  api.get<{ profile: Record<string, unknown> }>('/api/v1/profile');

export const updateProfileProject = (payload: {
  project_index?: number;
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
}) =>
  api.put<{ success: boolean; message: string }>('/api/v1/profile/projects', payload);

export const deleteProfileProject = (projectIndex: number) =>
  api.delete<{ success: boolean; message: string }>(`/api/v1/profile/projects?project_index=${projectIndex}`);

export const updateProfileSkills = (skills: string[]) =>
  api.put<{ success: boolean; message: string }>('/api/v1/profile/skills', { skills });

// ===== 面试 =====
export const interviewAnswer = (question: string) =>
  api.post<InterviewResponse>('/api/v1/interview/answer', {
    question,
    mode: 'interview',
  } as InterviewRequest);

// ===== 模拟面试 =====
export const mockStart = (focusAreas: string[], difficulty: string) =>
  api.post<MockStartResponse>('/api/v1/mock/start', {
    focus_areas: focusAreas,
    difficulty,
  } as MockStartRequest);

export const mockNext = (sessionId: string, answer: string) =>
  api.post<MockNextResponse>('/api/v1/mock/next', {
    session_id: sessionId,
    answer,
  } as MockNextRequest);

// ===== 自我介绍 =====
export const generateIntro = (position: string, company: string, length: string) =>
  api.post<SelfIntroResponse>('/api/v1/intro/generate', {
    target_position: position,
    target_company: company,
    length,
  } as SelfIntroRequest);

// ===== JD 匹配 =====
export const analyzeMatch = (jdText: string, position: string) =>
  api.post<JDMatchResponse>('/api/v1/match/analyze', {
    jd_text: jdText,
    target_position: position,
  } as JDMatchRequest);

// ===== 项目-JD 匹配 =====
export const analyzeMatchProjects = (jdText: string, position: string) =>
  api.post<ProjectMatchResponse>('/api/v1/match/projects', {
    jd_text: jdText,
    target_position: position,
  } as ProjectMatchRequest);

// ===== 系统 =====
export const getSystemInfo = () =>
  api.get<SystemInfoResponse>('/api/v1/system/info');
