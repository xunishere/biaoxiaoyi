/**
 * 文档分析页面
 */
import React, { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { collectSseText, documentApi, getErrorMessage } from '../services/api';
import { CloudArrowUpIcon, DocumentIcon } from '@heroicons/react/24/outline';
import { draftStorage } from '../utils/draftStorage';

const STREAM_UPDATE_DELAY = 80;

interface DocumentAnalysisProps {
  fileContent: string;
  projectOverview: string;
  techRequirements: string;
  commercialRequirements: string;
  bidFramework: string;
  onFileUpload: (content: string) => void;
  onAnalysisComplete: (overview: string, requirements: string) => void;
  onCommercialComplete: (commercial: string) => void;
  onFrameworkComplete: (framework: string) => void;
}

const DocumentAnalysis: React.FC<DocumentAnalysisProps> = ({
  fileContent,
  projectOverview,
  techRequirements,
  commercialRequirements,
  bidFramework,
  onFileUpload,
  onAnalysisComplete,
  onCommercialComplete,
  onFrameworkComplete,
}) => {
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const streamFlushTimerRef = useRef<number | null>(null);
  const pendingStreamingRef = useRef({ overview: '', requirements: '', commercial: '', framework: '' });

  const [editingOverview, setEditingOverview] = useState(false);
  const [editingRequirements, setEditingRequirements] = useState(false);
  const [editingCommercial, setEditingCommercial] = useState(false);
  const [editingFramework, setEditingFramework] = useState(false);
  const [draftOverview, setDraftOverview] = useState(projectOverview);
  const [draftRequirements, setDraftRequirements] = useState(techRequirements);
  const [draftCommercial, setDraftCommercial] = useState(commercialRequirements);
  const [draftFramework, setDraftFramework] = useState(bidFramework);

  // ── 耗时统计 ──
  const [timing, setTiming] = useState<{ elapsedSec: number; done: boolean }>({ elapsedSec: 0, done: false });
  const timingRef = useRef<{ start: number; interval: ReturnType<typeof setInterval> | null }>({ start: 0, interval: null });
  const formatDuration = (sec: number): string => sec < 60 ? `${sec}秒` : `${Math.floor(sec / 60)}分${sec % 60}秒`;
  const startTimer = () => {
    if (timingRef.current.interval) clearInterval(timingRef.current.interval);
    const start = Date.now();
    timingRef.current = { start, interval: setInterval(() => {
      setTiming({ elapsedSec: Math.floor((Date.now() - start) / 1000), done: false });
    }, 1000) };
    setTiming({ elapsedSec: 0, done: false });
  };
  const stopTimer = (): number => {
    if (timingRef.current.interval) { clearInterval(timingRef.current.interval); timingRef.current.interval = null; }
    const elapsed = Math.floor((Date.now() - timingRef.current.start) / 1000);
    setTiming({ elapsedSec: elapsed, done: true });
    return elapsed;
  };

  useEffect(() => {
    if (!editingOverview) {
      setDraftOverview(projectOverview);
    }
  }, [editingOverview, projectOverview]);

  useEffect(() => {
    if (!editingRequirements) {
      setDraftRequirements(techRequirements);
    }
  }, [editingRequirements, techRequirements]);

  useEffect(() => {
    if (!editingCommercial) {
      setDraftCommercial(commercialRequirements);
    }
  }, [editingCommercial, commercialRequirements]);

  useEffect(() => {
    if (!editingFramework) {
      setDraftFramework(bidFramework);
    }
  }, [editingFramework, bidFramework]);

  // 处理换行符的函数 - 只做基本转换
  const normalizeLineBreaks = (text: string) => {
    if (!text) return text;
    
    return text
      .replace(/\\n/g, '\n')  // 将字符串 \n 转换为实际换行符
      .replace(/\r\n/g, '\n') // Windows换行符
      .replace(/\r/g, '\n');  // Mac换行符
  };
  
  // 流式显示状态
  const [currentAnalysisStep, setCurrentAnalysisStep] = useState<'overview' | 'requirements' | 'commercial' | 'framework' | null>(null);
  const [streamingOverview, setStreamingOverview] = useState('');
  const [streamingRequirements, setStreamingRequirements] = useState('');
  const [streamingCommercial, setStreamingCommercial] = useState('');
  const [streamingFramework, setStreamingFramework] = useState('');

  useEffect(() => {
    return () => {
      if (streamFlushTimerRef.current !== null) {
        window.clearTimeout(streamFlushTimerRef.current);
      }
    };
  }, []);

  // 公共的 ReactMarkdown 组件配置
  const markdownComponents = {
    p: ({ children }: any) => <p className="mb-3 leading-relaxed text-sm" style={{whiteSpace: 'pre-wrap', lineHeight: '1.5'}}>{children}</p>,
    ul: ({ children }: any) => <ul className="mb-4 pl-5 space-y-1.5 list-disc">{children}</ul>,
    ol: ({ children }: any) => <ol className="mb-4 pl-5 space-y-1.5 list-decimal">{children}</ol>,
    li: ({ children }: any) => <li className="text-sm leading-relaxed">{children}</li>,
    h1: ({ children }: any) => <h1 className="text-lg font-semibold mb-3 text-gray-900 border-b border-gray-200 pb-2">{children}</h1>,
    h2: ({ children }: any) => <h2 className="text-base font-semibold mb-2 text-gray-900">{children}</h2>,
    h3: ({ children }: any) => <h3 className="text-sm font-semibold mb-2 text-gray-800">{children}</h3>,
    strong: ({ children }: any) => <strong className="font-semibold text-gray-900">{children}</strong>,
    em: ({ children }: any) => <em className="italic text-gray-700">{children}</em>,
    blockquote: ({ children }: any) => <blockquote className="border-l-4 border-green-200 pl-4 my-3 italic text-gray-600">{children}</blockquote>,
    code: ({ children }: any) => <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs font-mono">{children}</code>,
    table: ({ children }: any) => <table className="w-full border-collapse border border-gray-300 my-3">{children}</table>,
    thead: ({ children }: any) => <thead className="bg-gray-50">{children}</thead>,
    th: ({ children }: any) => <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-xs">{children}</th>,
    td: ({ children }: any) => <td className="border border-gray-300 px-3 py-2 text-xs">{children}</td>,
    br: () => <br className="my-1" />,
    text: ({ children }: any) => <span style={{whiteSpace: 'pre-wrap'}}>{children}</span>,
  };

  const flushStreamingPreview = () => {
    if (streamFlushTimerRef.current !== null) {
      window.clearTimeout(streamFlushTimerRef.current);
      streamFlushTimerRef.current = null;
    }

    setStreamingOverview(normalizeLineBreaks(pendingStreamingRef.current.overview));
    setStreamingRequirements(normalizeLineBreaks(pendingStreamingRef.current.requirements));
    setStreamingCommercial(normalizeLineBreaks(pendingStreamingRef.current.commercial));
    setStreamingFramework(normalizeLineBreaks(pendingStreamingRef.current.framework));
  };

  // 流式阶段只做节流后的纯文本预览，避免长内容反复 Markdown 渲染把页面拖慢。
  const scheduleStreamingPreview = (step: 'overview' | 'requirements' | 'commercial' | 'framework', fullText: string) => {
    pendingStreamingRef.current[step] = fullText;

    if (streamFlushTimerRef.current !== null) {
      return;
    }

    streamFlushTimerRef.current = window.setTimeout(() => {
      flushStreamingPreview();
    }, STREAM_UPDATE_DELAY);
  };

  const resetStreamingPreview = () => {
    pendingStreamingRef.current = { overview: '', requirements: '', commercial: '', framework: '' };
    flushStreamingPreview();
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setUploadedFile(file);
      handleFileUpload(file);
    }
  };

  const handleFileUpload = async (file: File) => {
    try {
      setUploading(true);
      setMessage(null);

      const response = await documentApi.uploadFile(file);
      
      if (response.data.success && response.data.file_content) {
        // 上传新招标文件：清空上一轮 localStorage（按你的需求）
        // 注意：这会同时清掉之前保存的草稿/正文内容缓存等
        draftStorage.clearAll();
        onFileUpload(response.data.file_content);
        setMessage({ type: 'success', text: response.data.message });
      } else {
        setMessage({ type: 'error', text: response.data.message });
      }
    } catch (error) {
      setMessage({ type: 'error', text: getErrorMessage(error, '文件上传失败') });
    } finally {
      setUploading(false);
    }
  };

  const handleAnalysis = async () => {
    if (!fileContent) {
      setMessage({ type: 'error', text: '请先上传文档' });
      return;
    }

    try {
      setAnalyzing(true);
      setMessage(null);
      resetStreamingPreview();
      startTimer();

      let overviewResult = '';
      let requirementsResult = '';

      // 第一步：分析项目概述
      setCurrentAnalysisStep('overview');
      const overviewResponse = await documentApi.analyzeDocumentStream({
        file_content: fileContent,
        analysis_type: 'overview',
      });

      overviewResult = await collectSseText(
        overviewResponse,
        (fullText) => {
          scheduleStreamingPreview('overview', fullText);
        },
        '项目概述解析失败'
      );

      flushStreamingPreview();
      const finalOverview = normalizeLineBreaks(overviewResult);

      // 第二步：分析技术评分要求
      setCurrentAnalysisStep('requirements');
      const requirementsResponse = await documentApi.analyzeDocumentStream({
        file_content: fileContent,
        analysis_type: 'requirements',
      });

      requirementsResult = await collectSseText(
        requirementsResponse,
        (fullText) => {
          scheduleStreamingPreview('requirements', fullText);
        },
        '技术评分要求解析失败'
      );

      flushStreamingPreview();
      const finalRequirements = normalizeLineBreaks(requirementsResult);

      // 第三步：分析商务/价格评分要求
      setCurrentAnalysisStep('commercial');
      const commercialResponse = await documentApi.analyzeDocumentStream({
        file_content: fileContent,
        analysis_type: 'commercial',
      });

      const commercialResult = await collectSseText(
        commercialResponse,
        (fullText) => {
          scheduleStreamingPreview('commercial', fullText);
        },
        '商务评分要求解析失败'
      );

      flushStreamingPreview();
      const finalCommercial = normalizeLineBreaks(commercialResult);

      // 完成后更新父组件状态
      setEditingOverview(false);
      setEditingRequirements(false);
      setEditingCommercial(false);
      onAnalysisComplete(finalOverview, finalRequirements);
      onCommercialComplete(finalCommercial);

      // 第四步：提取投标文件框架结构
      setCurrentAnalysisStep('framework');
      const frameworkResponse = await documentApi.analyzeDocumentStream({
        file_content: fileContent,
        analysis_type: 'framework',
      });

      const frameworkResult = await collectSseText(
        frameworkResponse,
        (fullText) => {
          scheduleStreamingPreview('framework', fullText);
        },
        '投标文件框架结构提取失败'
      );

      flushStreamingPreview();
      const finalFramework = normalizeLineBreaks(frameworkResult);

      // 完成后更新父组件状态
      setEditingOverview(false);
      setEditingRequirements(false);
      setEditingCommercial(false);
      setEditingFramework(false);
      onAnalysisComplete(finalOverview, finalRequirements);
      onCommercialComplete(finalCommercial);
      onFrameworkComplete(finalFramework);
      const elapsed = stopTimer();
      setMessage({ type: 'success', text: `标书解析完成（4轮分析），耗时 ${formatDuration(elapsed)}` });

      // 清空流式内容
      resetStreamingPreview();
      setCurrentAnalysisStep(null);

    } catch (error) {
      stopTimer();
      setMessage({ type: 'error', text: getErrorMessage(error, '标书解析失败') });
      resetStreamingPreview();
      setCurrentAnalysisStep(null);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleSaveOverview = () => {
    onAnalysisComplete(draftOverview, techRequirements);
    setEditingOverview(false);
    setMessage({ type: 'success', text: '项目概述已保存' });
  };

  const handleCancelOverview = () => {
    setDraftOverview(projectOverview);
    setEditingOverview(false);
  };

  const handleSaveRequirements = () => {
    onAnalysisComplete(projectOverview, draftRequirements);
    setEditingRequirements(false);
    setMessage({ type: 'success', text: '技术评分要求已保存' });
  };

  const handleCancelRequirements = () => {
    setDraftRequirements(techRequirements);
    setEditingRequirements(false);
  };

  const handleSaveCommercial = () => {
    onCommercialComplete(draftCommercial);
    setEditingCommercial(false);
    setMessage({ type: 'success', text: '商务评分要求已保存' });
  };

  const handleCancelCommercial = () => {
    setDraftCommercial(commercialRequirements);
    setEditingCommercial(false);
  };

  const handleSaveFramework = () => {
    onFrameworkComplete(draftFramework);
    setEditingFramework(false);
    setMessage({ type: 'success', text: '投标文件框架结构已保存' });
  };

  const handleCancelFramework = () => {
    setDraftFramework(bidFramework);
    setEditingFramework(false);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* 文件上传区域 */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">📄 文档上传</h2>
        
        <div 
          className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center hover:border-gray-400 transition-colors cursor-pointer"
          onClick={() => fileInputRef.current?.click()}
        >
          <CloudArrowUpIcon className="mx-auto h-12 w-12 text-gray-400" />
          <div className="mt-4">
            <p className="text-lg text-gray-600">
              {uploadedFile ? uploadedFile.name : '点击选择文件或拖拽文件到这里'}
            </p>
            <p className="text-sm text-gray-500 mt-2">
              支持 PDF 和 Word 文档，最大 10MB
            </p>
          </div>
          
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.doc"
            onChange={handleFileSelect}
            className="hidden"
          />
        </div>
        
        {uploading && (
          <div className="mt-4 text-center">
            <div className="inline-flex items-center px-4 py-2 text-sm text-blue-600">
              <div className="animate-spin -ml-1 mr-3 h-5 w-5 text-blue-600">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              </div>
              正在上传和处理文件...
            </div>
          </div>
        )}
      </div>

      {/* 文档分析区域 */}
      {fileContent && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">🔍 文档分析</h2>
          
          <div className="flex justify-center mb-6">
            <button
              onClick={handleAnalysis}
              disabled={analyzing}
              className="inline-flex items-center justify-center px-6 py-3 border border-transparent text-base font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {analyzing ? (
                <>
                  <div className="animate-spin -ml-1 mr-3 h-5 w-5 text-white">
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                  </div>
                  {currentAnalysisStep === 'overview' ? '正在分析项目概述' :
                   currentAnalysisStep === 'requirements' ? '正在分析技术评分要求' :
                   currentAnalysisStep === 'commercial' ? '正在分析商务/价格评分要求' :
                   currentAnalysisStep === 'framework' ? '正在提取框架结构' :
                   '正在解析标书'} ⏱ {formatDuration(timing.elapsedSec)}
                </>
              ) : (
                <>
                  <DocumentIcon className="w-5 h-5 mr-2" />
                  解析标书
                </>
              )}
            </button>
          </div>

          {/* 流式分析内容显示 */}
          {analyzing && (((currentAnalysisStep === 'overview') && streamingOverview) || ((currentAnalysisStep === 'requirements') && streamingRequirements) || ((currentAnalysisStep === 'commercial') && streamingCommercial) || ((currentAnalysisStep === 'framework') && streamingFramework)) && (
            <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <h4 className="text-sm font-medium text-blue-800 mb-3">
                {currentAnalysisStep === 'overview' ? '正在分析项目概述...' : 
                 currentAnalysisStep === 'requirements' ? '正在分析技术评分要求...' : 
                 currentAnalysisStep === 'commercial' ? '正在分析商务/价格评分要求...' :
                 '正在提取投标文件框架结构...'}
              </h4>
              <div className="bg-white p-3 rounded-lg border border-gray-200 max-h-64 overflow-y-auto shadow-sm">
                <pre className="whitespace-pre-wrap break-words text-xs leading-relaxed text-blue-900 font-sans">
                  {currentAnalysisStep === 'overview' ? streamingOverview : 
                   currentAnalysisStep === 'requirements' ? streamingRequirements :
                   currentAnalysisStep === 'commercial' ? streamingCommercial :
                   streamingFramework}
                </pre>
              </div>
            </div>
          )}


          {/* 项目概述 — 折叠区 */}
          {projectOverview && (
            <details className="mb-6 group">
              <summary className="flex items-center justify-between p-3 bg-gray-50 border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-100 transition-colors select-none">
                <span className="text-sm font-medium text-gray-800">📋 项目概述</span>
                <div className="flex items-center gap-2">
                  {!editingOverview && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.preventDefault();
                        setDraftOverview(projectOverview);
                        setEditingOverview(true);
                      }}
                      className="text-xs font-medium text-blue-600 hover:text-blue-700"
                    >
                      编辑
                    </button>
                  )}
                  <svg className="w-4 h-4 text-gray-400 group-open:rotate-180 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </div>
              </summary>
              <div className="mt-2 p-4 border border-gray-200 rounded-lg bg-white">
                {editingOverview ? (
                  <div className="space-y-3">
                    <textarea
                      value={draftOverview}
                      onChange={(event) => setDraftOverview(event.target.value)}
                      rows={10}
                      className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-y text-sm"
                      placeholder="项目概述..."
                    />
                    <div className="flex justify-end gap-3">
                      <button type="button" onClick={handleCancelOverview} className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50">取消</button>
                      <button type="button" onClick={handleSaveOverview} className="px-3 py-1.5 text-xs font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700">保存</button>
                    </div>
                  </div>
                ) : (
                  <div className="prose prose-sm max-w-none text-gray-800">
                    <ReactMarkdown components={markdownComponents}>
                      {projectOverview}
                    </ReactMarkdown>
                  </div>
                )}
              </div>
            </details>
          )}

          {/* 投标文件框架结构 — 折叠区 */}
          {bidFramework && (
            <details className="mb-6 group">
              <summary className="flex items-center justify-between p-3 bg-purple-50 border border-purple-200 rounded-lg cursor-pointer hover:bg-purple-100 transition-colors select-none">
                <span className="text-sm font-medium text-gray-800">📑 投标文件框架结构（招标文件规定）</span>
                <div className="flex items-center gap-2">
                  {!editingFramework && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.preventDefault();
                        setDraftFramework(bidFramework);
                        setEditingFramework(true);
                      }}
                      className="text-xs font-medium text-blue-600 hover:text-blue-700"
                    >
                      编辑
                    </button>
                  )}
                  <svg className="w-4 h-4 text-gray-400 group-open:rotate-180 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </div>
              </summary>
              <div className="mt-2 p-4 border border-purple-200 rounded-lg bg-white">
                {editingFramework ? (
                  <div className="space-y-3">
                    <textarea
                      value={draftFramework}
                      onChange={(event) => setDraftFramework(event.target.value)}
                      rows={10}
                      className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500 resize-y text-sm"
                      placeholder="投标文件框架结构..."
                    />
                    <div className="flex justify-end gap-3">
                      <button type="button" onClick={handleCancelFramework} className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50">取消</button>
                      <button type="button" onClick={handleSaveFramework} className="px-3 py-1.5 text-xs font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700">保存</button>
                    </div>
                  </div>
                ) : (
                  <div className="prose prose-sm max-w-none text-gray-800">
                    <ReactMarkdown components={markdownComponents}>
                      {bidFramework}
                    </ReactMarkdown>
                  </div>
                )}
              </div>
            </details>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* 技术评分要求 */}
            <div>
              <div className="flex items-center justify-between mb-3 gap-3">
                <label className="block text-sm font-medium text-gray-700">
                  技术评分要求
                </label>
                {!editingRequirements && (
                  <button
                    type="button"
                    onClick={() => {
                      setDraftRequirements(techRequirements);
                      setEditingRequirements(true);
                    }}
                    className="text-sm font-medium text-blue-600 hover:text-blue-700"
                  >
                    编辑
                  </button>
                )}
              </div>

              {editingRequirements ? (
                <div className="space-y-3">
                  <textarea
                    value={draftRequirements}
                    onChange={(event) => setDraftRequirements(event.target.value)}
                    rows={14}
                    className="w-full p-4 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500 resize-y"
                    placeholder="技术评分要求将在这里显示..."
                  />
                  <div className="flex justify-end gap-3">
                    <button
                      type="button"
                      onClick={handleCancelRequirements}
                      className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                    >
                      取消
                    </button>
                    <button
                      type="button"
                      onClick={handleSaveRequirements}
                      className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700"
                    >
                      保存
                    </button>
                  </div>
                </div>
              ) : (
                <div className="w-full p-4 border border-gray-300 rounded-lg max-h-80 overflow-y-auto bg-white shadow-sm">
                  <div className="prose prose-sm max-w-none text-gray-800">
                    <ReactMarkdown components={markdownComponents}>
                      {techRequirements || '技术评分要求将在这里显示...'}
                    </ReactMarkdown>
                  </div>
                </div>
              )}
            </div>

            {/* 商务/价格评分要求 */}
            <div>
              <div className="flex items-center justify-between mb-3 gap-3">
                <label className="block text-sm font-medium text-gray-700">
                  💰 商务/价格评分要求
                </label>
                {!editingCommercial && (
                  <button
                    type="button"
                    onClick={() => {
                      setDraftCommercial(commercialRequirements);
                      setEditingCommercial(true);
                    }}
                    className="text-sm font-medium text-blue-600 hover:text-blue-700"
                  >
                    编辑
                  </button>
                )}
              </div>

              {editingCommercial ? (
                <div className="space-y-3">
                  <textarea
                    value={draftCommercial}
                    onChange={(event) => setDraftCommercial(event.target.value)}
                    rows={14}
                    className="w-full p-4 border border-gray-300 rounded-lg focus:ring-2 focus:ring-yellow-500 focus:border-yellow-500 resize-y"
                    placeholder="商务评分要求将在这里显示..."
                  />
                  <div className="flex justify-end gap-3">
                    <button
                      type="button"
                      onClick={handleCancelCommercial}
                      className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                    >
                      取消
                    </button>
                    <button
                      type="button"
                      onClick={handleSaveCommercial}
                      className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700"
                    >
                      保存
                    </button>
                  </div>
                </div>
              ) : (
                <div className="w-full p-4 border border-gray-300 rounded-lg max-h-80 overflow-y-auto bg-white shadow-sm">
                  <div className="prose prose-sm max-w-none text-gray-800">
                    <ReactMarkdown components={markdownComponents}>
                      {commercialRequirements || '商务评分要求将在这里显示...'}
                    </ReactMarkdown>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 消息提示 */}
      {message && (
        <div className={`p-4 rounded-md ${
          message.type === 'success' 
            ? 'bg-green-100 text-green-700 border border-green-200' 
            : 'bg-red-100 text-red-700 border border-red-200'
        }`}>
          {message.text}
        </div>
      )}
    </div>
  );
};

export default DocumentAnalysis;
