// ResuMatch Extension - API 桥接层
// IIFE 模式，挂载到 window.ResuMatchAPI
(function() {
'use strict';
const API_BASE = 'http://localhost:8721/api/v1';

const api = {
  // 健康检查
  async healthCheck() {
    try {
      const r = await fetch(`${API_BASE}/health`);
      const d = await r.json();
      return d.status === 'ok';
    } catch { return false; }
  },

  // 简历上传
  async uploadResume(file) {
    const fd = new FormData();
    fd.append('file', file);
    const r = await fetch(`${API_BASE}/resume/upload`, { method: 'POST', body: fd });
    return r.json();
  },

  // 简历画像
  async getProfile() {
    const r = await fetch(`${API_BASE}/resume/profile`);
    return r.json();
  },

  // 档案导出（扩展格式）——档案页编辑与网申助手联通的数据源
  async getProfileExport() {
    const r = await fetch(`${API_BASE}/profile/export`);
    return r.json();
  },

  // 拉取最新档案并写入 chrome.storage（供 popup 匹配使用）
  async syncProfileFromBackend() {
    try {
      const d = await this.getProfileExport();
      if (d && d.profile) {
        await chrome.storage.local.set({ profile: d.profile, profileTime: Date.now() });
        return true;
      }
    } catch { /* 后端不可用 → 保留本地缓存（离线兜底） */ }
    return false;
  },

  // 面试问答
  async interviewAnswer(question) {
    const r = await fetch(`${API_BASE}/interview/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });
    return r.json();
  },

  // JD 匹配
  async matchJD(jdText, position) {
    const r = await fetch(`${API_BASE}/match/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jd_text: jdText, target_position: position || '' }),
    });
    return r.json();
  },

  // 自我介绍
  async generateIntro(position, company, length) {
    const r = await fetch(`${API_BASE}/intro/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_position: position || '', target_company: company || '', length: length || '1min' }),
    });
    return r.json();
  },

  // 模拟面试
  async mockStart(focusAreas, difficulty) {
    const r = await fetch(`${API_BASE}/mock/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ focus_areas: focusAreas || [], difficulty: difficulty || 'intermediate' }),
    });
    return r.json();
  },

  async mockNext(sessionId, answer) {
    const r = await fetch(`${API_BASE}/mock/next`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, answer }),
    });
    return r.json();
  },

  // 智能表单填充
  async smartFormFill(fields, url) {
    const r = await fetch(`${API_BASE}/form/fill`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fields, url: url || '' }),
    });
    return r.json();
  },

  // 系统信息
  async systemInfo() {
    const r = await fetch(`${API_BASE}/system/info`);
    return r.json();
  },
};

window.ResuMatchAPI = api;
})();
