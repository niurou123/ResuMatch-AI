// SSE 流式解析器 — fetch + ReadableStream + AsyncGenerator
// EventSource 不支持 POST 请求体，故用此方案
import { API_URL } from './constants';
import type { SSEEvent } from './types';

/**
 * 流式调用 SSE 端点
 *
 * 后端协议 (src/agents/graph.py run_interview_stream):
 *   POST /api/v1/interview/stream
 *   Content-Type: text/event-stream
 *
 * 每行格式:
 *   data: {"type":"start","node":"__start__","content":"..."}\n\n
 *   data: {"type":"node_complete","node":"planner","status":"success","data":{...}}\n\n
 *   data: {"type":"done","node":"end","status":"success","data":{"final_answer":"..."}}\n\n
 */
export async function* streamSSE(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): AsyncGenerator<SSEEvent> {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`SSE 请求失败: ${res.status} ${text}`);
  }

  if (!res.body) {
    throw new Error('响应体不支持流式读取');
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('data: ')) {
          try {
            yield JSON.parse(trimmed.slice(6));
          } catch {
            // 跳过无法解析的行
          }
        }
      }
    }

    // 处理 buffer 中最后一行
    if (buffer.trim().startsWith('data: ')) {
      try {
        yield JSON.parse(buffer.trim().slice(6));
      } catch {
        // 跳过
      }
    }
  } finally {
    reader.releaseLock();
  }
}
