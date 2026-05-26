/**
 * AI 服务商注册表 — 预配置常见大模型接口
 */

export interface ProviderInfo {
  id: string;
  name: string;
  color: string;      // 品牌色
  baseURL: string;
  models: string[];
  description: string;
  defaultModel: string;
}

export const PROVIDERS: ProviderInfo[] = [
  {
    id: 'deepseek',
    name: 'DeepSeek',
    color: '#4F6BF7',
    baseURL: 'https://api.deepseek.com',
    models: ['deepseek-chat', 'deepseek-reasoner'],  // 仅作 fallback，实际从 API 拉取
    description: '性价比最高 · 中文能力强',
    defaultModel: 'deepseek-chat',
  },
  {
    id: 'qwen',
    name: '通义千问',
    color: '#6B3FF5',
    baseURL: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    models: ['qwen-turbo', 'qwen-plus', 'qwen-max'],
    description: '阿里云 · 通义系列',
    defaultModel: 'qwen-plus',
  },
  {
    id: 'zhipu',
    name: '智谱AI',
    color: '#3D7CFA',
    baseURL: 'https://open.bigmodel.cn/api/paas/v4',
    models: ['glm-4-plus', 'glm-4-flash', 'glm-4-air'],
    description: '清华系 · GLM 系列',
    defaultModel: 'glm-4-flash',
  },
  {
    id: 'moonshot',
    name: '月之暗面',
    color: '#FF7A45',
    baseURL: 'https://api.moonshot.cn/v1',
    models: ['moonshot-v1-8k', 'moonshot-v1-32k', 'moonshot-v1-128k'],
    description: 'Kimi · 长文本处理',
    defaultModel: 'moonshot-v1-32k',
  },
  {
    id: 'siliconflow',
    name: 'SiliconFlow',
    color: '#7C3AED',
    baseURL: 'https://api.siliconflow.cn/v1',
    models: ['deepseek-ai/DeepSeek-V3', 'Qwen/Qwen2.5-72B-Instruct'],
    description: '模型聚合平台 · 多模型',
    defaultModel: 'deepseek-ai/DeepSeek-V3',
  },
  {
    id: 'openai',
    name: 'OpenAI',
    color: '#10A37F',
    baseURL: 'https://api.openai.com/v1',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo'],
    description: 'GPT 系列',
    defaultModel: 'gpt-4o-mini',
  },
];

export function findProvider(id: string): ProviderInfo | undefined {
  return PROVIDERS.find((p) => p.id === id);
}

export function matchProvider(baseURL: string): ProviderInfo | undefined {
  if (!baseURL) return undefined;
  const normalized = baseURL.replace(/\/+$/, '').toLowerCase();
  return PROVIDERS.find(
    (p) => p.baseURL.replace(/\/+$/, '').toLowerCase() === normalized,
  );
}
