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
    models: ['deepseek-chat', 'deepseek-reasoner'],  // 静态模型列表：在用户未点拉取列表时作为初始 dropdown
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
  {
    id: 'xiaomi-mimo',
    name: '小米 MiMo · 按量付费',
    color: '#FF6700',
    baseURL: 'https://api.xiaomimimo.com/v1',
    // 平台不暴露 /v1/models 端点，依赖此静态列表作为唯一来源
    models: ['mimo-v2.5-pro', 'mimo-v2-pro', 'mimo-v2.5', 'mimo-v2-omni', 'mimo-v2-flash'],
    description: '官方按量付费 · 不暴露 /v1/models',
    defaultModel: 'mimo-v2.5-pro',
  },
  {
    id: 'xiaomi-mimo-plan',
    name: '小米 MiMo · 订阅版',
    color: '#FF6700',
    baseURL: 'https://token-plan-cn.xiaomimimo.com/v1',
    // 订阅版 Token Plan 模型清单（来自订阅管理面板"套餐权益"实证）：4 个文本模型，无 mimo-v2-flash；TTS 系列在标书业务用不上故省略
    models: ['mimo-v2.5-pro', 'mimo-v2-pro', 'mimo-v2.5', 'mimo-v2-omni'],
    // 注意：订阅版 ToS 明示"仅限交互式使用，不可用于自动化脚本或应用后端"——使用风险自担
    description: '订阅 Token Plan · 仅限交互式使用',
    defaultModel: 'mimo-v2.5-pro',
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
