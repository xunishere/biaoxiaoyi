/**
 * 配置面板组件 — 下拉式服务商选择 + 独立 Key 存储
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { ConfigData } from '../types';
import { configApi } from '../services/api';
import { PROVIDERS, matchProvider } from '../config/providers';

interface ConfigPanelProps {
  config: ConfigData;
  onConfigChange: (config: ConfigData) => void;
}

const ConfigPanel: React.FC<ConfigPanelProps> = ({ config, onConfigChange }) => {
  const [localConfig, setLocalConfig] = useState<ConfigData>(config);
  const [models, setModels] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState('');

  const selectedId = localConfig.provider || '';
  const isCustom = selectedId === 'custom';
  const selectedProvider = PROVIDERS.find((p) => p.id === selectedId);
  const providerKey = (localConfig.provider_keys?.[selectedId]) || '';

  const loadConfig = React.useCallback(async () => {
    try {
      const response = await configApi.loadConfig();
      if (response.data) {
        const data = response.data;
        if (!data.provider && data.base_url) {
          const matched = matchProvider(data.base_url);
          data.provider = matched ? matched.id : 'custom';
        }
        const pid = data.provider || '';
        // 从缓存恢复模型列表
        const cached = data.provider_models?.[pid] || [];
        setModels(cached);
        // 从 provider_keys 恢复 Key
        if (pid && data.provider_keys?.[pid]) {
          data.api_key = data.provider_keys[pid];
        }
        setLocalConfig(data);
        onConfigChange(data);
        lastSaved.current = snap(data);
      }
    } catch { /* 静默 */ }
  }, [onConfigChange]);

  useEffect(() => { void loadConfig(); }, [loadConfig]);

  const selectProvider = (id: string) => {
    if (id === 'custom') {
      const keys = localConfig.provider_keys || {};
      const pm = localConfig.provider_models || {};
      setLocalConfig({
        ...localConfig,
        provider: 'custom',
        api_key: keys.custom || localConfig.api_key || '',
      });
      setModels(pm.custom || []);
      return;
    }
    const prov = PROVIDERS.find((p) => p.id === id);
    if (!prov) return;
    const keys = localConfig.provider_keys || {};
    const pm = localConfig.provider_models || {};
    const savedKey = keys[prov.id] || '';
    const cached = pm[prov.id] || [];
    setLocalConfig({
      ...localConfig,
      provider: prov.id,
      api_key: savedKey,
      base_url: prov.baseURL,
      model_name: cached[0] || prov.defaultModel,
    });
    setModels(cached);
  };

  const setApiKey = (key: string) => {
    const keys = { ...(localConfig.provider_keys || {}) };
    if (selectedId) keys[selectedId] = key;
    setLocalConfig({ ...localConfig, api_key: key, provider_keys: keys });
  };

  const handleGetModels = async () => {
    if (!localConfig.api_key) return;
    try {
      setLoading(true);
      setFetchError('');
      const response = await configApi.getModels(localConfig);
      if (response.data.success) {
        const fetched = response.data.models;
        if (fetched.length > 0) {
          setModels(fetched);
          const pm = { ...(localConfig.provider_models || {}) };
          if (selectedId) pm[selectedId] = fetched;
          setLocalConfig((prev) => {
            const next = { ...prev, provider_models: pm };
            if (!fetched.includes(prev.model_name)) {
              next.model_name = fetched[0];
            }
            return next;
          });
        }
      } else {
        setFetchError(response.data.message || '获取失败，请检查 Key');
      }
    } catch {
      setFetchError('网络错误，请检查 Key 和 URL');
    }
    finally { setLoading(false); }
  };

  // 自动保存：服务商/Key/模型变化时 debounce 1s 后保存
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSaved = useRef<string>('');

  const snap = (cfg: ConfigData) => JSON.stringify({
    api_key: cfg.api_key, base_url: cfg.base_url,
    model_name: cfg.model_name, provider: cfg.provider,
    provider_keys: cfg.provider_keys, provider_models: cfg.provider_models,
  });

  const autoSave = useCallback(async (cfg: ConfigData) => {
    const s = snap(cfg);
    if (s === lastSaved.current) return;
    try {
      const response = await configApi.saveConfig(cfg);
      if (response.data.success) {
        lastSaved.current = s;
        onConfigChange(cfg);
      }
    } catch { /* 静默 */ }
  }, [onConfigChange]);

  useEffect(() => {
    if (!localConfig.provider) return;
    const s = snap(localConfig);
    if (s === lastSaved.current) return;
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => autoSave(localConfig), 500);
    return () => { if (saveTimer.current) clearTimeout(saveTimer.current); };
  }, [localConfig, autoSave]);

  return (
    <div className="bg-white shadow-sm border-r border-gray-200 w-80 p-6 overflow-y-auto">
      <div className="space-y-5">
        <div>
          <img src="/brand.png" alt="荟写作" className="w-full h-auto" />
          <hr className="mt-4 border-gray-200" />
        </div>

        <div>
          <h2 className="text-base font-bold text-gray-800 text-center mb-4">
            选择模型
          </h2>

          {/* 服务商下拉选择 */}
          <div className="mb-3">
            <label className="block text-xs font-medium text-gray-700 mb-1">服务商</label>
            <select
              value={selectedId || ''}
              onChange={(e) => selectProvider(e.target.value)}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
            >
              <option value="" disabled>请选择服务商</option>
              {PROVIDERS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} — {p.description}
                </option>
              ))}
              <option value="custom">自定义</option>
            </select>
            {selectedProvider && (
              <p className="text-xs text-blue-600 mt-1">
                Base URL：{selectedProvider.baseURL}
              </p>
            )}
          </div>

          {/* API Key */}
          <div className="mb-3">
            <label htmlFor="api_key" className="block text-xs font-medium text-gray-700 mb-1">
              API Key
            </label>
            <input
              type="password"
              id="api_key"
              value={localConfig.api_key}
              onChange={(e) => setApiKey(e.target.value)}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
              placeholder={selectedProvider ? `${selectedProvider.name} API Key` : '输入 API Key'}
              autoComplete="new-password"
            />
            {selectedProvider && providerKey && (
              <p className="text-xs text-green-600 mt-1">✅ 已保存 Key</p>
            )}
          </div>

          {/* 自定义模式：Base URL 可编辑 */}
          {isCustom && (
            <div className="mb-3">
              <label htmlFor="base_url" className="block text-xs font-medium text-gray-700 mb-1">
                Base URL
              </label>
              <input
                type="text"
                id="base_url"
                value={localConfig.base_url || ''}
                onChange={(e) => setLocalConfig({ ...localConfig, base_url: e.target.value })}
                className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
                placeholder="https://api.openai.com/v1"
              />
            </div>
          )}

          {/* 模型选择 */}
          <div className="mb-3">
            <div className="flex items-center justify-between mb-1">
              <label htmlFor="model_name" className="text-xs font-medium text-gray-700">模型</label>
              <button
                onClick={handleGetModels}
                disabled={loading || !localConfig.api_key}
                className="text-xs text-blue-600 hover:text-blue-800 disabled:text-gray-400"
              >
                {loading ? '获取中...' : '拉取列表'}
              </button>
            </div>
            {fetchError && (
              <p className="text-xs text-red-600 mt-1">{fetchError}</p>
            )}
            {models.length > 0 ? (
              <select
                id="model_name"
                value={localConfig.model_name}
                onChange={(e) => setLocalConfig({ ...localConfig, model_name: e.target.value })}
                className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
              >
                {models.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            ) : selectedProvider ? (
              <p className="text-sm text-gray-400 italic py-2">请先拉取模型列表</p>
            ) : (
              <p className="text-sm text-gray-400 italic py-2">请先选择服务商</p>
            )}
          </div>


        </div>

        <div className="border-t border-gray-200 pt-4">
          <h3 className="text-sm font-medium text-gray-900 mb-2">使用说明</h3>
          <div className="text-sm text-gray-600 space-y-1">
            <p>1. 选择服务商（URL 自动填充）</p>
            <p>2. 输入 API Key（自动保存）</p>
            <p>3. 选择模型</p>
            <p>4. 开始写标书</p>
          </div>
        </div>

        <div className="border-t border-gray-200 pt-4">
          <div className="flex items-center justify-center">
            <img
              src="/huixiezuo.png"
              alt="荟写作"
              className="w-5 h-5 opacity-50 hover:opacity-75 transition-opacity"
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default ConfigPanel;
