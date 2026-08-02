// API 基础 URL — 开发时使用 Vite proxy，生产时 Nginx 反向代理
export const API_URL = import.meta.env.VITE_API_URL || '';

// 应用信息
export const APP_NAME = 'ResuMatch AI';
export const APP_VERSION = 'v3.0';
export const APP_TAGLINE = 'Multi-Agent Interview System';

// DAG 节点定义
export const DAG_NODES = [
  { id: 'planner' as const, label: 'Planner' },
  { id: 'router' as const, label: 'Router' },
  { id: 'retrieval' as const, label: '并行检索' },
  { id: 'writer' as const, label: 'Writer' },
  { id: 'review' as const, label: '并行评审' },
  { id: 'end' as const, label: '完成' },
];

// 导航项
export const NAV_ITEMS = [
  { to: '/resume', label: '简历上传' },
  { to: '/interview', label: '面试模拟' },
  { to: '/intro', label: '自我介绍' },
  { to: '/match', label: 'JD 匹配' },
];

// 支持的文件格式
export const SUPPORTED_FORMATS = '.pdf,.docx,.md,.txt';
export const SUPPORTED_FORMATS_LABEL = 'PDF, DOCX, MD, TXT';
