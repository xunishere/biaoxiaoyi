/**
 * API 服务与流式响应工具
 */
import axios from 'axios';
import { ConfigData, OutlineData, OutlineItem, OutlineMode } from '../types';

const API_BASE_URL = process.env.REACT_APP_API_URL || '';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
});

api.interceptors.response.use(
  (response) => response,
  (error) => Promise.reject(error)
);

export interface FileUploadResponse {
  success: boolean;
  message: string;
  file_content?: string;
  old_outline?: string;
}

export interface AnalysisRequest {
  file_content: string;
  analysis_type: 'overview' | 'requirements' | 'commercial' | 'framework';
}

export interface OutlineRequest {
  overview: string;
  requirements: string;
  framework_structure?: string;
  commercial?: string;
  mode?: OutlineMode;
  uploaded_expand?: boolean;
  old_outline?: string;
  old_document?: string;
}

export interface ChapterContentRequest {
  chapter: OutlineItem;
  parent_chapters?: OutlineItem[];
  sibling_chapters?: OutlineItem[];
  project_overview: string;
  scoring_context?: string;
  framework_context?: string;
}

export interface GapAnalysisRequest {
  document_content: string;
  scoring_criteria: string;
}

export interface GapItem {
  criteria_name: string;
  issue_type: string;
  description: string;
  suggestion: string;
}

export interface GapAnalysisResponse {
  gaps: GapItem[];
  quality_issues: string[];
  summary: string;
}

export interface ScoringTableRequest {
  document_content: string;
  scoring_criteria: string;
}

export interface ScoreItem {
  criteria_name: string;
  max_score: number;
  scored: number;
  reasoning: string;
  gaps: string[];
}

export interface ScoringTableResponse {
  scores: ScoreItem[];
  total: number;
  max_total: number;
  summary: string;
}

export interface OptimizeChapterRequest {
  chapter_id: string;
  chapter_title: string;
  current_content: string;
  scoring_criteria?: string;
  gap_suggestions?: string;
  reference_docs?: string;
}

export interface WordExportRequest {
  project_name?: string;
  project_overview?: string;
  outline: OutlineItem[];
}

export interface StreamEvent {
  type?: 'progress' | 'result';
  chunk?: string;
  outline?: OutlineData;
  error?: boolean;
  message?: string;
}

const formatErrorDetail = (detail: unknown): string | null => {
  if (!detail) {
    return null;
  }

  if (typeof detail === 'string') {
    return detail;
  }

  if (Array.isArray(detail)) {
    const lines = detail
      .map((item) => {
        if (typeof item === 'string') {
          return item;
        }

        if (item && typeof item === 'object') {
          const maybeItem = item as { loc?: Array<string | number>; msg?: string };
          const path = maybeItem.loc?.join(' -> ');
          return path ? `${path}: ${maybeItem.msg || '参数校验失败'}` : (maybeItem.msg || '参数校验失败');
        }

        return null;
      })
      .filter((line): line is string => Boolean(line));

    return lines.length > 0 ? lines.join('；') : null;
  }

  if (detail && typeof detail === 'object') {
    const maybeDetail = detail as { detail?: unknown; message?: string };
    return formatErrorDetail(maybeDetail.detail) || maybeDetail.message || JSON.stringify(detail);
  }

  return String(detail);
};

export const getErrorMessage = (error: unknown, fallback = '请求失败'): string => {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    const message = error.response?.data?.message;
    return formatErrorDetail(detail) || message || error.message || fallback;
  }

  if (error instanceof Error) {
    return error.message || fallback;
  }

  return fallback;
};

const ensureResponseOk = async (response: Response, fallback: string): Promise<Response> => {
  if (response.ok) {
    return response;
  }

  try {
    const data = await response.json();
    throw new Error(formatErrorDetail(data.detail) || data.message || fallback);
  } catch (error) {
    if (error instanceof Error && error.message !== 'Unexpected end of JSON input') {
      throw error;
    }
  }

  const text = await response.text();
  throw new Error(text || fallback);
};

export const readSseStream = async (
  response: Response,
  onEvent: (event: StreamEvent) => void,
  fallbackMessage: string,
): Promise<void> => {
  await ensureResponseOk(response, fallbackMessage);

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('无法读取响应流');
  }

  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }

      // 跳过 SSE 注释行 (keepalive)
      const text = decoder.decode(value, { stream: true });
      buffer += text;
      const events = buffer.split('\n\n');
      buffer = events.pop() || '';

      for (const eventBlock of events) {
        // 跳过纯注释块 (keepalive)
        if (eventBlock.trim().split('\n').every(l => l.startsWith(':') || l.trim() === '')) {
          continue;
        }
        const dataLine = eventBlock
          .split('\n')
          .find((line) => line.startsWith('data: '));

        if (!dataLine) {
          continue;
        }

        const data = dataLine.slice(6);
        if (data === '[DONE]') {
          return;
        }

        let event: StreamEvent | null = null;
        try {
          event = JSON.parse(data) as StreamEvent;
        } catch {
          continue;
        }

        onEvent(event);
      }
    }
  } catch (err: any) {
    // 流被中断（如前端 AbortController 超时、浏览器关闭连接）
    if (err?.name === 'AbortError' || String(err).includes('abort')) {
      throw new Error(fallbackMessage + '（连接已中断）');
    }
    throw err;
  } finally {
    try { reader.releaseLock(); } catch {}
  }
};

export const collectSseText = async (
  response: Response,
  onText?: (fullText: string, chunk: string) => void,
  fallbackMessage = '流式请求失败'
): Promise<string> => {
  let fullText = '';

  await readSseStream(
    response,
    (event) => {
      if (event.error) {
        throw new Error(event.message || fallbackMessage);
      }

      if (!event.chunk) {
        return;
      }

      fullText += event.chunk;
      onText?.(fullText, event.chunk);
    },
    fallbackMessage
  );

  return fullText;
};

const postJson = (path: string, data: unknown, timeoutMs?: number) => {
  const controller = new AbortController();
  if (timeoutMs) {
    setTimeout(() => controller.abort(), timeoutMs);
  }
  return fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
    signal: timeoutMs ? controller.signal : undefined,
  });
};

export const configApi = {
  saveConfig: (config: ConfigData) => api.post('/api/config/save', config),
  loadConfig: () => api.get<ConfigData>('/api/config/load'),
  getModels: (config: ConfigData) => api.post<{ models: string[]; success: boolean; message: string }>('/api/config/models', config),
};

export const documentApi = {
  uploadFile: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<FileUploadResponse>('/api/document/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },
  analyzeDocumentStream: (data: AnalysisRequest) => postJson('/api/document/analyze-stream', data),
  exportWord: async (data: WordExportRequest) => ensureResponseOk(await postJson('/api/document/export-word', data), '导出失败'),
};

export const outlineApi = {
  generateOutline: (data: OutlineRequest) => api.post<OutlineData>('/api/outline/generate', data),
  generateOutlineStream: (data: OutlineRequest) => postJson('/api/outline/generate-stream', data),
};

export const contentApi = {
  generateChapterContent: (data: ChapterContentRequest) => api.post<{ success: boolean; content: string }>('/api/content/generate-chapter', data),
  generateChapterContentStream: (data: ChapterContentRequest) => postJson('/api/content/generate-chapter-stream', data),
};

export const expandApi = {
  uploadExpandFile: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<FileUploadResponse>('/api/expand/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 300000,
    });
  },
};

export const reviewApi = {
  gapAnalysis: (data: GapAnalysisRequest) =>
    api.post<GapAnalysisResponse>('/api/review/gap-analysis', data, { timeout: 180000 }),
  scoringTable: (data: ScoringTableRequest) =>
    api.post<ScoringTableResponse>('/api/review/scoring-table', data, { timeout: 180000 }),
  optimizeChapterStream: (data: OptimizeChapterRequest) =>
    postJson('/api/review/optimize-chapter-stream', data, 300000), // 5分钟超时
};

export interface MergeRequest {
  framework_outline: any[];
  scoring_criteria: string;
  scoring_content_map: Record<string, string>;
  framework_content_map: Record<string, string>;
  gap_analysis_json: string;
}

export interface MergePrepareResponse {
  outline: any[];
  matches: any[];
}

export interface MergeSynthesizeRequest {
  node_id: string;
  node_title: string;
  node_description: string;
  covers_criteria: string;
  scoring_content: string;
  framework_content: string;
  gap_suggestions: string;
}

export const mergeApi = {
  prepare: (data: MergeRequest) =>
    api.post<MergePrepareResponse>('/api/merge/prepare', data, { timeout: 600000 }),
  synthesize: (data: MergeSynthesizeRequest) =>
    api.post<{ content: string }>('/api/merge/synthesize', data, { timeout: 180000 }),
};

export default api;
