/**
 * 目录编辑页面 — 双模式独立生成
 */
import React, { useState, useRef } from 'react';
import { OutlineData, OutlineItem } from '../types';
import { getErrorMessage, outlineApi, readSseStream } from '../services/api';
import { ChevronRightIcon, ChevronDownIcon, DocumentTextIcon, PencilIcon, TrashIcon, PlusIcon } from '@heroicons/react/24/outline';

interface OutlineEditProps {
  projectOverview: string;
  techRequirements: string;
  commercialRequirements: string;
  bidFramework: string;
  outlineData: OutlineData | null;
  frameworkOutlineData: OutlineData | null;
  onOutlineGenerated: (outline: OutlineData) => void;
  onFrameworkOutlineGenerated: (outline: OutlineData) => void;
  onUpdateTechRequirements: (text: string) => void;
  onUpdateCommercialRequirements: (text: string) => void;
  onUpdateBidFramework: (text: string) => void;
}

const OutlineEdit: React.FC<OutlineEditProps> = ({
  projectOverview,
  techRequirements,
  commercialRequirements,
  bidFramework,
  outlineData,
  frameworkOutlineData,
  onOutlineGenerated,
  onFrameworkOutlineGenerated,
  onUpdateTechRequirements,
  onUpdateCommercialRequirements,
  onUpdateBidFramework,
}) => {
  // 评分标准模式状态
  const [generatingAligned, setGeneratingAligned] = useState(false);
  const [progressLogsAligned, setProgressLogsAligned] = useState<string[]>([]);

  // 框架结构模式状态
  const [generatingFramework, setGeneratingFramework] = useState(false);
  const [progressLogsFramework, setProgressLogsFramework] = useState<string[]>([]);

  // 文字编辑状态
  const [editingTech, setEditingTech] = useState(false);
  const [draftTech, setDraftTech] = useState(techRequirements);
  const [editingCommercial, setEditingCommercial] = useState(false);
  const [draftCommercial, setDraftCommercial] = useState(commercialRequirements);
  const [editingFramework, setEditingFramework] = useState(false);
  const [draftFramework, setDraftFramework] = useState(bidFramework);

  // Sync drafts when props change (if not actively editing)
  React.useEffect(() => { if (!editingTech) setDraftTech(techRequirements); }, [editingTech, techRequirements]);
  React.useEffect(() => { if (!editingCommercial) setDraftCommercial(commercialRequirements); }, [editingCommercial, commercialRequirements]);
  React.useEffect(() => { if (!editingFramework) setDraftFramework(bidFramework); }, [editingFramework, bidFramework]);

  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());
  const [expandedFrameworkItems, setExpandedFrameworkItems] = useState<Set<string>>(new Set());
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // ── 耗时统计 ──
  type OutlineTimer = 'aligned' | 'framework';
  const [timing, setTiming] = useState<{ label: OutlineTimer | null; elapsedSec: number; done: boolean }>({ label: null, elapsedSec: 0, done: false });
  const timingRef = useRef<{ start: number; interval: ReturnType<typeof setInterval> | null }>({ start: 0, interval: null });
  const formatDuration = (sec: number): string => sec < 60 ? `${sec}秒` : `${Math.floor(sec / 60)}分${sec % 60}秒`;
  const startTimer = (label: OutlineTimer) => {
    if (timingRef.current.interval) clearInterval(timingRef.current.interval);
    const start = Date.now();
    timingRef.current = { start, interval: setInterval(() => {
      setTiming({ label, elapsedSec: Math.floor((Date.now() - start) / 1000), done: false });
    }, 1000) };
    setTiming({ label, elapsedSec: 0, done: false });
  };
  const stopTimer = (): number => {
    if (timingRef.current.interval) { clearInterval(timingRef.current.interval); timingRef.current.interval = null; }
    const elapsed = Math.floor((Date.now() - timingRef.current.start) / 1000);
    setTiming(prev => ({ ...prev, elapsedSec: elapsed, done: true }));
    return elapsed;
  };

  const [editingItem, setEditingItem] = useState<string | null>(null);
  const [editingMode, setEditingMode] = useState<'aligned' | 'framework'>('aligned');
  const [editTitle, setEditTitle] = useState('');
  const [editDescription, setEditDescription] = useState('');

  // ========== 评分标准模式：按技术评分项一一对应生成 ==========
  const handleGenerateAligned = async () => {
    if (!projectOverview || !techRequirements) {
      setMessage({ type: 'error', text: '请先完成文档分析' });
      return;
    }

    try {
      setGeneratingAligned(true);
      setMessage(null);
      setProgressLogsAligned([]);
      startTimer('aligned');

      const response = await outlineApi.generateOutlineStream({
        overview: projectOverview,
        requirements: techRequirements,
        mode: 'aligned',
      });

      let outlineResult: OutlineData | null = null;
      await readSseStream(
        response,
        (event) => {
          if (event.error) {
            throw new Error(event.message || '目录生成失败');
          }
          if (event.type === 'progress' && event.message) {
            setProgressLogsAligned(prev => [...prev, event.message || '']);
            return;
          }
          if (event.type === 'result' && event.outline) {
            outlineResult = event.outline;
          }
        },
        '目录生成失败'
      );

      if (!outlineResult) throw new Error('未收到目录生成结果');

      onOutlineGenerated(outlineResult as OutlineData);
      const elapsed = stopTimer();
      setMessage({ type: 'success', text: `评分标准目录生成完成，耗时 ${formatDuration(elapsed)}` });

      const allIds = new Set<string>();
      const collectIds = (items: OutlineItem[]) => {
        items.forEach(item => {
          allIds.add(item.id);
          if (item.children) collectIds(item.children);
        });
      };
      collectIds((outlineResult as OutlineData).outline);
      setExpandedItems(allIds);
    } catch (error) {
      stopTimer();
      setMessage({ type: 'error', text: getErrorMessage(error, '目录生成失败') });
    } finally {
      setGeneratingAligned(false);
    }
  };

  // ========== 框架结构模式：严格按招标文件框架生成 ==========
  const handleGenerateFramework = async () => {
    if (!projectOverview || !bidFramework) {
      setMessage({ type: 'error', text: '请先在标书解析中提取投标文件框架结构' });
      return;
    }

    try {
      setGeneratingFramework(true);
      setMessage(null);
      setProgressLogsFramework([]);
      startTimer('framework');

      const response = await outlineApi.generateOutlineStream({
        overview: projectOverview,
        requirements: techRequirements,
        framework_structure: bidFramework,
        mode: 'framework',
      });

      let outlineResult: OutlineData | null = null;
      await readSseStream(
        response,
        (event) => {
          if (event.error) {
            throw new Error(event.message || '框架目录生成失败');
          }
          if (event.type === 'progress' && event.message) {
            setProgressLogsFramework(prev => [...prev, event.message || '']);
            return;
          }
          if (event.type === 'result' && event.outline) {
            outlineResult = event.outline;
          }
        },
        '框架目录生成失败'
      );

      if (!outlineResult) throw new Error('未收到框架目录生成结果');

      onFrameworkOutlineGenerated(outlineResult as OutlineData);
      const elapsed = stopTimer();
      setMessage({ type: 'success', text: `框架结构目录生成完成，耗时 ${formatDuration(elapsed)}` });

      const allIds = new Set<string>();
      const collectIds = (items: OutlineItem[]) => {
        items.forEach(item => {
          allIds.add(item.id);
          if (item.children) collectIds(item.children);
        });
      };
      collectIds((outlineResult as OutlineData).outline);
      setExpandedFrameworkItems(allIds);
    } catch (error) {
      stopTimer();
      setMessage({ type: 'error', text: getErrorMessage(error, '框架目录生成失败') });
    } finally {
      setGeneratingFramework(false);
    }
  };

  // ========== 通用编辑操作 ==========

  const toggleExpanded = (mode: 'aligned' | 'framework', itemId: string) => {
    const setter = mode === 'aligned' ? setExpandedItems : setExpandedFrameworkItems;
    const current = mode === 'aligned' ? expandedItems : expandedFrameworkItems;
    const newSet = new Set(current);
    if (newSet.has(itemId)) {
      newSet.delete(itemId);
    } else {
      newSet.add(itemId);
    }
    setter(newSet);
  };

  const startEditing = (item: OutlineItem, mode: 'aligned' | 'framework') => {
    setEditingItem(item.id);
    setEditingMode(mode);
    setEditTitle(item.title);
    setEditDescription(item.description);
  };

  const cancelEditing = () => {
    setEditingItem(null);
    setEditTitle('');
    setEditDescription('');
  };

  const getActiveOutline = (): OutlineData | null =>
    editingMode === 'aligned' ? outlineData : frameworkOutlineData;

  const saveEdit = () => {
    const activeOutline = getActiveOutline();
    if (!activeOutline || !editingItem) return;

    const updateItem = (items: OutlineItem[]): OutlineItem[] => {
      return items.map(item => {
        if (item.id === editingItem) {
          return { ...item, title: editTitle.trim(), description: editDescription.trim() };
        }
        if (item.children) {
          return { ...item, children: updateItem(item.children) };
        }
        return item;
      });
    };

    const updatedData = { ...activeOutline, outline: updateItem(activeOutline.outline) };

    if (editingMode === 'aligned') {
      onOutlineGenerated(updatedData);
    } else {
      onFrameworkOutlineGenerated(updatedData);
    }
    cancelEditing();
    setMessage({ type: 'success', text: '目录项更新成功' });
  };

  const reorderItems = (items: OutlineItem[], parentPrefix: string = ''): OutlineItem[] => {
    return items.map((item, index) => {
      const newId = parentPrefix ? `${parentPrefix}.${index + 1}` : `${index + 1}`;
      return { ...item, id: newId, children: item.children ? reorderItems(item.children, newId) : undefined };
    });
  };

  const deleteItem = (itemId: string, mode: 'aligned' | 'framework') => {
    const activeOutline = mode === 'aligned' ? outlineData : frameworkOutlineData;
    if (!activeOutline) return;

    if (window.confirm('确定要删除这个目录项吗？')) {
      const deleteFromItems = (items: OutlineItem[]): OutlineItem[] => {
        return items.flatMap(item => {
          if (item.id === itemId) return [];
          return [item.children ? { ...item, children: deleteFromItems(item.children) } : item];
        });
      };

      const filteredItems = deleteFromItems(activeOutline.outline);
      const reorderedItems = reorderItems(filteredItems);
      const updatedData = { ...activeOutline, outline: reorderedItems };

      if (mode === 'aligned') {
        onOutlineGenerated(updatedData);
      } else {
        onFrameworkOutlineGenerated(updatedData);
      }
      setMessage({ type: 'success', text: '目录项删除成功' });
    }
  };

  const addChildItem = (parentId: string, mode: 'aligned' | 'framework') => {
    const activeOutline = mode === 'aligned' ? outlineData : frameworkOutlineData;
    if (!activeOutline) return;

    const findNextId = (items: OutlineItem[], targetParentId: string): string | null => {
      for (const item of items) {
        if (item.id === targetParentId) {
          const existingChildren = item.children || [];
          let maxChildNum = 0;
          existingChildren.forEach(child => {
            const parts = child.id.split('.');
            const num = parseInt(parts[parts.length - 1]);
            if (!isNaN(num)) maxChildNum = Math.max(maxChildNum, num);
          });
          return `${parentId}.${maxChildNum + 1}`;
        }
        if (item.children) {
          const result = findNextId(item.children, targetParentId);
          if (result) return result;
        }
      }
      return null;
    };

    const newId = findNextId(activeOutline.outline, parentId) || `${parentId}.1`;
    const newItem: OutlineItem = { id: newId, title: '新目录项', description: '请编辑描述' };

    const addToItems = (items: OutlineItem[]): OutlineItem[] => {
      return items.map(item => {
        if (item.id === parentId) {
          return { ...item, children: [...(item.children || []), newItem] };
        }
        if (item.children) return { ...item, children: addToItems(item.children) };
        return item;
      });
    };

    const updatedData = { ...activeOutline, outline: addToItems(activeOutline.outline) };

    if (mode === 'aligned') {
      onOutlineGenerated(updatedData);
      setExpandedItems(prev => { const s = new Set(prev); s.add(parentId); return s; });
    } else {
      onFrameworkOutlineGenerated(updatedData);
      setExpandedFrameworkItems(prev => { const s = new Set(prev); s.add(parentId); return s; });
    }

    setTimeout(() => startEditing(newItem, mode), 100);
    setMessage({ type: 'success', text: '子目录添加成功' });
  };

  const renderOutlineItem = (item: OutlineItem, level: number = 0, mode: 'aligned' | 'framework') => {
    const hasChildren = item.children && item.children.length > 0;
    const isExpanded = (mode === 'aligned' ? expandedItems : expandedFrameworkItems).has(item.id);
    const isLeaf = !hasChildren;
    const isEditing = editingItem === item.id && editingMode === mode;

    return (
      <div key={item.id} className={`${level > 0 ? 'ml-6' : ''}`}>
        <div className="group flex items-start space-x-2 py-2 hover:bg-gray-50 rounded px-2">
          {hasChildren ? (
            <button onClick={() => toggleExpanded(mode, item.id)} className="mt-1 p-0.5 rounded hover:bg-gray-200">
              {isExpanded ? (<ChevronDownIcon className="h-4 w-4 text-gray-400" />) : (<ChevronRightIcon className="h-4 w-4 text-gray-400" />)}
            </button>
          ) : (
            <DocumentTextIcon className="mt-1 h-4 w-4 text-gray-400" />
          )}
          <div className="flex-1 min-w-0">
            {isEditing ? (
              <div className="space-y-2">
                <input type="text" value={editTitle} onChange={(e) => setEditTitle(e.target.value)}
                  className="w-full px-2 py-1 border border-gray-300 rounded text-sm" placeholder="目录标题" />
                <textarea value={editDescription} onChange={(e) => setEditDescription(e.target.value)}
                  rows={2} className="w-full px-2 py-1 border border-gray-300 rounded text-xs resize-none" placeholder="目录描述" />
                <div className="flex space-x-2">
                  <button onClick={saveEdit} className="inline-flex items-center px-2 py-1 border border-transparent text-xs font-medium rounded text-white bg-green-600 hover:bg-green-700">保存</button>
                  <button onClick={cancelEditing} className="inline-flex items-center px-2 py-1 border border-gray-300 text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50">取消</button>
                </div>
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className={`text-sm font-medium ${level === 0 ? 'text-blue-600' : level === 1 ? 'text-green-600' : level === 2 ? 'text-purple-600' : 'text-gray-700'}`}>
                      {item.id} {item.title}
                    </span>
                    {item.content && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">已生成内容</span>
                    )}
                  </div>
                  <div className="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button onClick={() => startEditing(item, mode)} className="p-1 rounded hover:bg-blue-100 text-blue-600" title="编辑"><PencilIcon className="h-3 w-3" /></button>
                    <button onClick={() => addChildItem(item.id, mode)} className="p-1 rounded hover:bg-green-100 text-green-600" title="添加子目录"><PlusIcon className="h-3 w-3" /></button>
                    <button onClick={() => deleteItem(item.id, mode)} className="p-1 rounded hover:bg-red-100 text-red-600" title="删除"><TrashIcon className="h-3 w-3" /></button>
                  </div>
                </div>
                <p className="text-xs text-gray-500 mt-1">{item.description}</p>
                {item.content && isLeaf && (
                  <div className="mt-2 p-3 bg-gray-50 rounded-md border-l-4 border-blue-200">
                    <div className="text-xs text-gray-600 whitespace-pre-wrap">{item.content}</div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
        {hasChildren && isExpanded && (
          <div>{item.children!.map(child => renderOutlineItem(child, level + 1, mode))}</div>
        )}
      </div>
    );
  };

  // ========== 页面渲染 ==========
  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* 技术评分要求 / 商务评分要求 — 可编辑 */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* 技术评分要求 */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-gray-700">技术评分要求</h3>
              {editingTech ? (
                <div className="flex gap-2">
                  <button onClick={() => { onUpdateTechRequirements(draftTech); setEditingTech(false); setMessage({ type: 'success', text: '技术评分要求已保存' }); }}
                    className="text-xs font-medium text-white bg-blue-600 px-2 py-1 rounded hover:bg-blue-700">保存</button>
                  <button onClick={() => { setDraftTech(techRequirements); setEditingTech(false); }}
                    className="text-xs font-medium text-gray-600 border px-2 py-1 rounded hover:bg-gray-100">取消</button>
                </div>
              ) : (
                <button onClick={() => { setDraftTech(techRequirements); setEditingTech(true); }}
                  className="text-xs font-medium text-blue-600 hover:text-blue-700">编辑</button>
              )}
            </div>
            {editingTech ? (
              <textarea value={draftTech} onChange={(e) => setDraftTech(e.target.value)}
                rows={8} className="w-full p-2 border border-blue-300 rounded text-xs resize-y" placeholder="尚未解析" />
            ) : (
              <div className="p-3 bg-gray-50 rounded border max-h-40 overflow-y-auto">
                <pre className="text-xs text-gray-600 whitespace-pre-wrap">{techRequirements || '尚未解析'}</pre>
              </div>
            )}
          </div>

          {/* 商务/价格评分要求 */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-gray-700">商务/价格评分要求</h3>
              {editingCommercial ? (
                <div className="flex gap-2">
                  <button onClick={() => { onUpdateCommercialRequirements(draftCommercial); setEditingCommercial(false); setMessage({ type: 'success', text: '商务评分要求已保存' }); }}
                    className="text-xs font-medium text-white bg-blue-600 px-2 py-1 rounded hover:bg-blue-700">保存</button>
                  <button onClick={() => { setDraftCommercial(commercialRequirements); setEditingCommercial(false); }}
                    className="text-xs font-medium text-gray-600 border px-2 py-1 rounded hover:bg-gray-100">取消</button>
                </div>
              ) : (
                <button onClick={() => { setDraftCommercial(commercialRequirements); setEditingCommercial(true); }}
                  className="text-xs font-medium text-blue-600 hover:text-blue-700">编辑</button>
              )}
            </div>
            {editingCommercial ? (
              <textarea value={draftCommercial} onChange={(e) => setDraftCommercial(e.target.value)}
                rows={8} className="w-full p-2 border border-yellow-300 rounded text-xs resize-y" placeholder="尚未解析" />
            ) : (
              <div className="p-3 bg-gray-50 rounded border max-h-40 overflow-y-auto">
                <pre className="text-xs text-gray-600 whitespace-pre-wrap">{commercialRequirements || '尚未解析'}</pre>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ===== 目录 A：按评分标准 ===== */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900">
            📋 目录 A：按评分标准
            <span className="ml-2 text-sm font-normal text-blue-600">（一级目录与技术评分大类一一对应）</span>
          </h2>
        </div>

        <button
          onClick={handleGenerateAligned}
          disabled={generatingAligned || generatingFramework || !projectOverview || !techRequirements}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:bg-gray-400 mb-4"
        >
          {generatingAligned ? (
            <>
              <div className="animate-spin -ml-1 mr-3 h-4 w-4 text-white">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              </div>
              正在生成目录...
            </>
          ) : (
            '生成目录（按评分标准）'
          )}
        </button>

        {/* live timer */}
        {timing.label === 'aligned' && !timing.done && (
          <div className="mb-2 text-xs text-gray-500 flex items-center">
            <span className="inline-block w-2 h-2 bg-blue-400 rounded-full animate-pulse mr-1.5" />
            ⏱ {formatDuration(timing.elapsedSec)} 已耗时
          </div>
        )}

        {progressLogsAligned.length > 0 && (
          <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-md">
            <h4 className="text-sm font-medium text-blue-800 mb-2">
              {generatingAligned ? '正在生成...' : '生成过程'}
            </h4>
            <div className="bg-white p-3 rounded border max-h-48 overflow-y-auto">
              <div className="space-y-2 text-xs text-gray-700">
                {progressLogsAligned.map((log, index) => (
                  <p key={`a-${index}`} className="whitespace-pre-wrap leading-5">{log}</p>
                ))}
              </div>
            </div>
          </div>
        )}

        {outlineData && (
          <div className="border rounded-lg p-4 max-h-96 overflow-y-auto">
            {outlineData.outline.map(item => renderOutlineItem(item, 0, 'aligned'))}
          </div>
        )}
      </div>

      {/* ===== 目录 B：按框架结构 ===== */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900">
            📑 目录 B：按框架结构
            <span className="ml-2 text-sm font-normal text-purple-600">（严格按招标文件规定的框架生成）</span>
          </h2>
        </div>

        {/* 提取的框架结构 — 可编辑 */}
        <div className="mb-4 p-4 bg-purple-50 border border-purple-200 rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-medium text-purple-900">📑 招标文件规定的投标文件框架结构</h4>
            {editingFramework ? (
              <div className="flex gap-2">
                <button onClick={() => { onUpdateBidFramework(draftFramework); setEditingFramework(false); setMessage({ type: 'success', text: '框架结构已保存' }); }}
                  className="text-xs font-medium text-white bg-purple-600 px-2 py-1 rounded hover:bg-purple-700">保存</button>
                <button onClick={() => { setDraftFramework(bidFramework); setEditingFramework(false); }}
                  className="text-xs font-medium text-gray-600 border px-2 py-1 rounded hover:bg-gray-100">取消</button>
              </div>
            ) : (
              <button onClick={() => { setDraftFramework(bidFramework); setEditingFramework(true); }}
                className="text-xs font-medium text-purple-600 hover:text-purple-700">编辑</button>
            )}
          </div>
          {editingFramework ? (
            <textarea value={draftFramework} onChange={(e) => setDraftFramework(e.target.value)}
              rows={8} className="w-full p-2 border border-purple-300 rounded text-xs resize-y" placeholder="尚未从采购文件中提取框架结构" />
          ) : (
            <div className="bg-white p-3 rounded border max-h-48 overflow-y-auto">
              <pre className="text-xs text-gray-700 whitespace-pre-wrap">{bidFramework || '尚未从采购文件中提取框架结构，请先在标书解析中运行"投标文件框架结构"分析。'}</pre>
            </div>
          )}
        </div>

        <button
          onClick={handleGenerateFramework}
          disabled={generatingAligned || generatingFramework || !projectOverview || !bidFramework}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-purple-600 hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 disabled:bg-gray-400 mb-4"
        >
          {generatingFramework ? (
            <>
              <div className="animate-spin -ml-1 mr-3 h-4 w-4 text-white">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              </div>
              正在生成框架目录...
            </>
          ) : (
            '生成目录（按框架结构）'
          )}
        </button>

        {/* live timer */}
        {timing.label === 'framework' && !timing.done && (
          <div className="mb-2 text-xs text-gray-500 flex items-center">
            <span className="inline-block w-2 h-2 bg-purple-400 rounded-full animate-pulse mr-1.5" />
            ⏱ {formatDuration(timing.elapsedSec)} 已耗时
          </div>
        )}

        {progressLogsFramework.length > 0 && (
          <div className="mb-4 p-4 bg-purple-50 border border-purple-200 rounded-md">
            <h4 className="text-sm font-medium text-purple-800 mb-2">
              {generatingFramework ? '正在生成...' : '生成过程'}
            </h4>
            <div className="bg-white p-3 rounded border max-h-48 overflow-y-auto">
              <div className="space-y-2 text-xs text-gray-700">
                {progressLogsFramework.map((log, index) => (
                  <p key={`f-${index}`} className="whitespace-pre-wrap leading-5">{log}</p>
                ))}
              </div>
            </div>
          </div>
        )}

        {frameworkOutlineData && (
          <div className="border rounded-lg p-4 max-h-96 overflow-y-auto">
            {frameworkOutlineData.outline.map(item => renderOutlineItem(item, 0, 'framework'))}
          </div>
        )}
      </div>

      {/* 消息提示 */}
      {message && (
        <div className={`p-4 rounded-md ${message.type === 'success'
          ? 'bg-green-100 text-green-700 border border-green-200'
          : 'bg-red-100 text-red-700 border border-red-200'
          }`}>
          {message.text}
        </div>
      )}
    </div>
  );
};

export default OutlineEdit;
