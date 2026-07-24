// ResuMatch Extension - API 桥接层
const API = 'http://localhost:8000/api/v1';

// ==================== 健康检查 ====================
export async function healthCheck() {
  try {
    const r = await fetch(`${API}/health`);
    const d = await r.json();
    return d.status === 'ok';
  } catch { return false; }
}

// ==================== 简历上传 ====================
export async function uploadResume(file) {
  const fd = new FormData();
  fd.append('file', file);
  const r = await fetch(`${API}/resume/upload`, { method: 'POST', body: fd });
  return r.json();
}

// ==================== 简历画像 ====================
export async function getProfile() {
  const r = await fetch(`${API}/resume/profile`);
  return r.json();
}

// ==================== 面试问答 ====================
export async function interviewAnswer(question) {
  const r = await fetch(`${API}/interview/answer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  });
  return r.json();
}

// ==================== JD 匹配 ====================
export async function matchJD(jdText, position = '') {
  const r = await fetch(`${API}/match/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jd_text: jdText, target_position: position }),
  });
  return r.json();
}

// ==================== 自我介绍 ====================
export async function generateIntro(position = '', company = '', length = '1min') {
  const r = await fetch(`${API}/intro/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target_position: position, target_company: company, length }),
  });
  return r.json();
}

// ==================== 模拟面试 ====================
export async function mockStart(focusAreas = [], difficulty = 'intermediate') {
  const r = await fetch(`${API}/mock/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ focus_areas: focusAreas, difficulty }),
  });
  return r.json();
}

export async function mockNext(sessionId, answer) {
  const r = await fetch(`${API}/mock/next`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, answer }),
  });
  return r.json();
}

// ==================== 智能表单填充（LLM驱动） ====================
export async function smartFormFill(fields, url = '') {
  const r = await fetch(`${API}/form/fill`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fields, url }),
  });
  return r.json();
}

// ==================== 系统信息 ====================
export async function systemInfo() {
  const r = await fetch(`${API}/system/info`);
  return r.json();
}
