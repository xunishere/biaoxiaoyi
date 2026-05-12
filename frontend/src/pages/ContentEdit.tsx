/**
 * 内容编辑页面 — 双目录独立生成 + 审查评分优化全流水线
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { OutlineData, OutlineItem } from '../types';
import {
  DocumentTextIcon, DocumentArrowDownIcon, CheckCircleIcon,
  ExclamationCircleIcon, ArrowUpIcon, MagnifyingGlassIcon,
  ChartBarIcon, SparklesIcon, ChevronDownIcon
} from '@heroicons/react/24/outline';
import {
  collectSseText, contentApi, ChapterContentRequest,
  reviewApi, GapAnalysisResponse, ScoringTableResponse,
  documentApi, getErrorMessage, mergeApi,
} from '../services/api';
import { saveAs } from 'file-saver';
import { draftStorage } from '../utils/draftStorage';

interface ContentEditProps {
  projectOverview: string;
  techRequirements: string;
  bidFramework: string;
  outlineData: OutlineData | null;
  frameworkOutlineData: OutlineData | null;
  onOutlineGenerated: (outline: OutlineData) => void;
  onFrameworkOutlineGenerated: (outline: OutlineData) => void;
}

interface GenProgress {
  total: number;
  completed: number;
  current: string;
  failed: string[];
  generating: Set<string>;
}

type PipelineStage = 'idle' | 'generating' | 'reviewing' | 'scoring' | 'optimizing' | 'done';

const ContentEdit: React.FC<ContentEditProps> = ({
  projectOverview,
  techRequirements,
  bidFramework,
  outlineData,
  frameworkOutlineData,
  onOutlineGenerated,
  onFrameworkOutlineGenerated,
}) => {
  const [activeTab, setActiveTab] = useState<'scoring' | 'framework' | 'merged'>('scoring');
  const [isGenerating, setIsGenerating] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // 两个独立的叶子节点 + 生成列表
  const [leafItemsScoring, setLeafItemsScoring] = useState<OutlineItem[]>([]);
  const [leafItemsFramework, setLeafItemsFramework] = useState<OutlineItem[]>([]);
  const [progress, setProgress] = useState<GenProgress>({ total: 0, completed: 0, current: '', failed: [], generating: new Set() });

  // 合并版状态
  const [mergedOutline, setMergedOutline] = useState<OutlineItem[]>([]);
  const [mergedContent, setMergedContent] = useState<Record<string, string>>({});
  const [isMerging, setIsMerging] = useState(false);
  const [mergeProgressText, setMergeProgressText] = useState('');

  // 审查/评分/优化状态
  const [stage, setStage] = useState<PipelineStage>('idle');
  const [gapResult, setGapResultState] = useState<GapAnalysisResponse | null>(null);
  const [scoreResult, setScoreResultState] = useState<ScoringTableResponse | null>(null);

  // ── 耗时统计 ──
  type TimingLabel = 'generate' | 'gap' | 'score' | 'optimize' | 'merge' | 'export';
  const [timing, setTiming] = useState<{ label: TimingLabel | null; elapsedSec: number; done: boolean }>({ label: null, elapsedSec: 0, done: false });
  const timingRef = useRef<{ start: number; interval: ReturnType<typeof setInterval> | null }>({ start: 0, interval: null });
  const formatDuration = (sec: number): string => sec < 60 ? `${sec}秒` : `${Math.floor(sec / 60)}分${sec % 60}秒`;
  const startTimer = (label: TimingLabel) => {
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

  // 持久化 gap/score 结果（按 tab 分 key）
  const saveReviewCache = (key: string, data: any) => {
    try { localStorage.setItem(`yibiao_review_${key}`, JSON.stringify(data)); } catch {}
  };
  const loadReviewCache = (key: string) => {
    try {
      const raw = localStorage.getItem(`yibiao_review_${key}`);
      return raw ? JSON.parse(raw) : null;
    } catch { return null; }
  };
  const setGapResult = (v: GapAnalysisResponse | null) => {
    setGapResultState(v);
    if (v) saveReviewCache(`gap_${activeTab}`, v);
  };
  const setScoreResult = (v: ScoringTableResponse | null) => {
    setScoreResultState(v);
    if (v) saveReviewCache(`score_${activeTab}`, v);
  };
  // 切 tab 时恢复对应缓存
  const switchTab = (tab: 'scoring' | 'framework' | 'merged') => {
    setActiveTab(tab);
    setGapResultState(loadReviewCache(`gap_${tab}`));
    setScoreResultState(loadReviewCache(`score_${tab}`));
    setProgress(prev => ({ ...prev, total: tab === 'scoring' ? leafItemsScoring.length : tab === 'framework' ? leafItemsFramework.length : 0 }));
    setStage('idle');
  };
  const [referenceDoc, setReferenceDoc] = useState<string | null>(null);
  const [refFileName, setRefFileName] = useState('');
  const [showScrollToTop, setShowScrollToTop] = useState(false);

  const activeOutline = activeTab === 'scoring' ? outlineData : activeTab === 'framework' ? frameworkOutlineData : null;
  const activeLeafItems = activeTab === 'scoring' ? leafItemsScoring : activeTab === 'framework' ? leafItemsFramework : [];
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const _setActiveLeafItems = activeTab === 'scoring' ? setLeafItemsScoring : setLeafItemsFramework;

  // ── leaf collection ──
  const collectLeafItems = useCallback((items: OutlineItem[]): OutlineItem[] => {
    let leaves: OutlineItem[] = [];
    items.forEach(item => {
      if (!item.children || item.children.length === 0) leaves.push(item);
      else leaves = leaves.concat(collectLeafItems(item.children));
    });
    return leaves;
  }, []);

  const getParentChapters = useCallback((targetId: string, items: OutlineItem[], parents: OutlineItem[] = []): OutlineItem[] => {
    for (const item of items) {
      if (item.id === targetId) return parents;
      if (item.children?.length) {
        const found = getParentChapters(targetId, item.children, [...parents, item]);
        if (found.length > 0 || item.children.some(c => c.id === targetId)) return found.length > 0 ? found : [...parents, item];
      }
    }
    return [];
  }, []);

  const getSiblingChapters = useCallback((targetId: string, items: OutlineItem[]): OutlineItem[] => {
    if (items.some(item => item.id === targetId)) return items;
    for (const item of items) {
      if (item.children?.length) {
        const s = getSiblingChapters(targetId, item.children);
        if (s.length > 0) return s;
      }
    }
    return [];
  }, []);

  // ── sync leaf items from outline ──
  useEffect(() => {
    if (outlineData) {
      const leaves = collectLeafItems(outlineData.outline);
      draftStorage.filterContentByOutlineLeaves(outlineData.outline).then(filtered => {
        const merged = leaves.map(l => {
          const cached = filtered[l.id];
          return { ...l, content: cached || l.content || '' };
        });
        setLeafItemsScoring(merged);
      });
      setProgress(prev => ({ ...prev, total: leaves.length }));
    }
  }, [outlineData, collectLeafItems]);

  useEffect(() => {
    if (frameworkOutlineData) {
      const allLeaves = collectLeafItems(frameworkOutlineData.outline);
      // 跳过资信/商务部分，只留技术部分
      const isCommercial = (item: OutlineItem): boolean => {
        const t = item.title.replace(/\s/g, '');
        if (/技术/.test(t)) return false; // 含"技术"就不是商业
        return /资信|商务|报价|资质|信誉|资格|财务|纳税/.test(t);
      };
      // 找到商业父节点，排除其下的叶子
      const commercialParentIds = new Set<string>();
      const markCommercial = (items: OutlineItem[], commercial: boolean) => {
        items.forEach(item => {
          if (commercial || isCommercial(item)) {
            commercialParentIds.add(item.id);
            if (item.children) markCommercial(item.children, true);
          } else if (item.children) {
            markCommercial(item.children, false);
          }
        });
      };
      markCommercial(frameworkOutlineData.outline, false);
      const isUnderCommercial = (item: OutlineItem): boolean => {
        const parts = item.id.split('.');
        for (let i = parts.length; i > 0; i--) {
          if (commercialParentIds.has(parts.slice(0, i).join('.'))) return true;
        }
        return false;
      };
      const leaves = allLeaves.filter(l => !isUnderCommercial(l));
      draftStorage.filterContentByOutlineLeaves(frameworkOutlineData.outline).then(filtered => {
        const merged = leaves.map(l => {
          const cached = filtered[l.id];
          return { ...l, content: cached || l.content || '' };
        });
        setLeafItemsFramework(merged);
      });
      if (activeTab === 'framework') setProgress(prev => ({ ...prev, total: leaves.length }));
    }
  }, [frameworkOutlineData, collectLeafItems, activeTab]);

  // scroll
  useEffect(() => {
    const el = document.getElementById('app-main-scroll');
    const h = () => setShowScrollToTop((el?.scrollTop || window.pageYOffset) > 300);
    h();
    (el || window).addEventListener('scroll', h);
    return () => (el || window).removeEventListener('scroll', h);
  }, []);

  // ── build document string for review (max 15000 chars) ──
  const buildDocumentContent = (items: OutlineItem[]): string => {
    const MAX_LEN = 12000;
    const parts: string[] = [];
    let total = 0;
    for (const item of items) {
      const content = item.content || '';
      const header = `## ${item.id} ${item.title}`;
      const body = content.length > 2000 ? content.slice(0, 2000) + '…' : content;
      const chunk = `${header}\n\n${body}`;
      if (total + chunk.length > MAX_LEN) {
        parts.push(`\n…（后续 ${items.length - parts.length} 个章节已截断）`);
        break;
      }
      parts.push(chunk);
      total += chunk.length;
    }
    return parts.join('\n\n');
  };

  // 为合并版构建文档
  const buildMergedDocumentContent = (): string => {
    const MAX_LEN = 12000;
    const parts: string[] = [];
    let total = 0;
    const walk = (items: any[]) => {
      for (const item of items) {
        if (total >= MAX_LEN) return;
        const content = mergedContent[item.id] || '';
        if (content) {
          const header = `## ${item.id} ${item.title}`;
          const body = content.length > 2000 ? content.slice(0, 2000) + '…' : content;
          const chunk = `${header}\n\n${body}`;
          if (total + chunk.length > MAX_LEN) break;
          parts.push(chunk);
          total += chunk.length;
        }
        if (item.children) walk(item.children);
      }
    };
    walk(mergedOutline);
    return parts.join('\n\n');
  };

  const getCurrentDocument = (): string => {
    if (activeTab === 'merged') return buildMergedDocumentContent();
    return buildDocumentContent(activeLeafItems);
  };

  // ── generate single item ──
  const generateItemContent = async (item: OutlineItem): Promise<OutlineItem> => {
    const outline = activeOutline;
    if (!outline) throw new Error('no outline');

    setProgress(prev => ({ ...prev, current: item.title, generating: new Set(Array.from(prev.generating).concat(item.id)) }));

    try {
      const scoringCtx = activeTab === 'scoring' ? techRequirements : '';
      const frameworkCtx = activeTab === 'framework' ? (bidFramework || '').slice(0, 2000) : '';
      const parents = getParentChapters(item.id, outline.outline);
      const siblings = getSiblingChapters(item.id, outline.outline);

      const req: ChapterContentRequest = {
        chapter: item,
        parent_chapters: parents,
        sibling_chapters: siblings,
        project_overview: projectOverview,
        scoring_context: scoringCtx || undefined,
        framework_context: frameworkCtx || undefined,
      };

      const response = await contentApi.generateChapterContentStream(req);
      const updated = { ...item };
      await collectSseText(response, (fullText) => {
        updated.content = fullText;
        draftStorage.upsertChapterContent(item.id, fullText).catch(() => {});
        _setActiveLeafItems(prev => prev.map(l => l.id === item.id ? { ...updated } : l));
      }, '章节内容生成失败');
      return updated;
    } catch (e) {
      setProgress(prev => ({ ...prev, failed: [...prev.failed, item.title] }));
      throw e;
    } finally {
      setProgress(prev => {
        const ng = new Set(prev.generating); ng.delete(item.id);
        return { ...prev, generating: ng };
      });
    }
  };

  // ── batch generate ──
  const handleGenerateContent = async () => {
    if (!activeOutline) {
      setMessage({ type: 'error', text: '请先在目录编辑中生成目录' });
      return;
    }
    if (activeLeafItems.length === 0) {
      setMessage({ type: 'error', text: '当前目录无技术部分叶子节点可生成' });
      return;
    }
    setIsGenerating(true); setStage('generating'); setMessage(null); setGapResult(null); setScoreResult(null);
    setProgress({ total: activeLeafItems.length, completed: 0, current: '', failed: [], generating: new Set() });
    startTimer('generate');

    try {
      const concurrency = activeTab === 'framework' ? 3 : 5;
      const updated = [...activeLeafItems];
      for (let i = 0; i < activeLeafItems.length; i += concurrency) {
        const batch = activeLeafItems.slice(i, i + concurrency);
        await Promise.all(batch.map(item =>
          generateItemContent(item).then(r => {
            const idx = updated.findIndex(u => u.id === r.id);
            if (idx >= 0) updated[idx] = r;
            setProgress(p => ({ ...p, completed: p.completed + 1 }));
          }).catch((e) => {
            setProgress(p => ({ ...p, completed: p.completed + 1, failed: [...p.failed, item.title] }));
          })
        ));
      }
      _setActiveLeafItems(updated);

      // 把生成内容写回 outline 持久化，刷新不丢
      const bakeContent = (items: OutlineItem[]): OutlineItem[] =>
        items.map(item => {
          const leaf = updated.find(l => l.id === item.id);
          const content = leaf?.content || item.content;
          return { ...item, content, children: item.children ? bakeContent(item.children) : undefined };
        });
      if (activeOutline) {
        const baked = { ...activeOutline, outline: bakeContent(activeOutline.outline) };
        if (activeTab === 'scoring') onOutlineGenerated(baked);
        else onFrameworkOutlineGenerated(baked);
      }

      const elapsed = stopTimer();
      setStage('idle');
      if (updated.every(l => !l.content)) {
        setMessage({ type: 'error', text: `所有章节生成均失败，耗时 ${formatDuration(elapsed)}，请确认 API 配置正确并重试` });
      } else if (progress.failed.length > 0) {
        setMessage({ type: 'error', text: `${progress.failed.length} 个章节生成失败: ${progress.failed.slice(0, 5).join('、')}，耗时 ${formatDuration(elapsed)}` });
      } else {
        setMessage({ type: 'success', text: `正文生成完成，共 ${updated.length} 个章节，耗时 ${formatDuration(elapsed)}` });
      }
    } catch (e) {
      stopTimer();
      setMessage({ type: 'error', text: getErrorMessage(e, '生成失败') });
      setStage('idle');
    } finally {
      setIsGenerating(false);
    }
  };

  // ── gap analysis ──
  const handleGapAnalysis = async () => {
    if (activeTab === 'merged' && !mergedOutline.length) return;
    if (activeTab !== 'merged' && !activeLeafItems.length) return;
    setStage('reviewing'); setMessage(null);
    startTimer('gap');
    try {
      const doc = getCurrentDocument();
      const res = await reviewApi.gapAnalysis({
        document_content: doc,
        scoring_criteria: techRequirements,
      });
      setGapResult(res.data);
      const elapsed = stopTimer();
      setStage('idle');
      setMessage({ type: 'success', text: `缺口分析完成，发现 ${res.data.gaps?.length || 0} 个问题，耗时 ${formatDuration(elapsed)}` });
    } catch (e) {
      stopTimer();
      setMessage({ type: 'error', text: getErrorMessage(e, '缺口分析失败') });
      setStage('idle');
    }
  };

  // ── scoring table ──
  const handleScoring = async () => {
    if (activeTab === 'merged' && !mergedOutline.length) return;
    if (activeTab !== 'merged' && !activeLeafItems.length) return;
    setStage('scoring'); setMessage(null);
    startTimer('score');
    try {
      const doc = getCurrentDocument();
      const res = await reviewApi.scoringTable({
        document_content: doc,
        scoring_criteria: techRequirements,
      });
      setScoreResult(res.data);
      setStage('idle');
    } catch (e) {
      setMessage({ type: 'error', text: getErrorMessage(e, '评分失败') });
      setStage('idle');
    } finally { stopTimer(); }
  };

  // ── matching helper ──
  const matchCriteriaToTitle = (criteriaName: string, itemTitle: string): boolean => {
    const clean = (s: string) => s.replace(/[（(]\d+分?[）)]/g, '').replace(/[0-9.、，。：:（）()\s]+/g, '');
    const cn = clean(criteriaName);
    const tn = clean(itemTitle);
    if (tn.includes(cn) || cn.includes(tn)) return true;
    const words = cn.replace(/(.{2,3})/g, '$1 ').trim().split(/\s+/).filter(w => w.length >= 2);
    return words.length > 0 && words.some(w => tn.includes(w));
  };

  // ── core optimize logic (no stage management, safe for concurrent calls) ──
  const _runOptimizeChapter = async (item: OutlineItem): Promise<void> => {
    const gapSuggestions = gapResult
      ? gapResult.gaps.filter(g => matchCriteriaToTitle(g.criteria_name, item.title))
          .map(g => `[${g.issue_type}] ${g.description} → 建议: ${g.suggestion}`).join('\n')
      : '';
    const response = await reviewApi.optimizeChapterStream({
      chapter_id: item.id,
      chapter_title: item.title,
      current_content: item.content || '',
      scoring_criteria: techRequirements,
      gap_suggestions: gapSuggestions,
      reference_docs: referenceDoc || undefined,
    });
    const updated = { ...item };
    await collectSseText(response, (fullText) => {
      updated.content = fullText;
      draftStorage.upsertChapterContent(item.id, fullText).catch(() => {});
      _setActiveLeafItems(prev => prev.map(l => l.id === item.id ? { ...updated } : l));
    }, '章节优化失败');
  };

  // ── single chapter optimize (with stage wrapper) ──
  const handleOptimizeChapter = async (item: OutlineItem) => {
    setStage('optimizing'); setMessage(null);
    try {
      await _runOptimizeChapter(item);
      setStage('idle');
    } catch (e) {
      setMessage({ type: 'error', text: getErrorMessage(e, '优化失败') });
      setStage('idle');
    }
  };

  // optimize all weak chapters (score < 70% of max), 3 concurrent
  const handleOptimizeAll = async () => {
    let weakItems: OutlineItem[] = [];
    if (scoreResult) {
      const weakNames = scoreResult.scores.filter(s => s.max_score > 0 && s.scored / s.max_score < 0.7).map(s => s.criteria_name);
      weakItems = activeLeafItems.filter(item => item.content &&
        weakNames.some(n => matchCriteriaToTitle(n, item.title))
      );
    } else if (gapResult) {
      const gapNames = gapResult.gaps.map(g => g.criteria_name);
      weakItems = activeLeafItems.filter(item => item.content &&
        gapNames.some(n => matchCriteriaToTitle(n, item.title))
      );
    }
    if (weakItems.length === 0 && gapResult) {
      weakItems = activeLeafItems.filter(item => !!item.content);
    }
    if (weakItems.length === 0) {
      setMessage({ type: 'error', text: '没有可优化的章节（请先生成正文或运行检查遗漏）' });
      return;
    }
    setStage('optimizing');
    setMessage({ type: 'success', text: `正在优化 ${weakItems.length} 个章节（3并发）...` });
    setProgress(prev => ({ ...prev, completed: 0, total: weakItems.length }));
    startTimer('optimize');

    const concurrency = 3;
    for (let i = 0; i < weakItems.length; i += concurrency) {
      const batch = weakItems.slice(i, i + concurrency);
      await Promise.all(batch.map(async (item) => {
        try {
          await _runOptimizeChapter(item);
        } catch { /* per-item failure is silent, reflected in UI via missing content update */ }
        setProgress(prev => ({ ...prev, completed: prev.completed + 1 }));
      }));
    }

    const elapsed = stopTimer();
    setStage('idle');
    setMessage({ type: 'success', text: `已优化 ${weakItems.length} 个章节，耗时 ${formatDuration(elapsed)}` });
  };

  // ── merge ──
  const handleMerge = async () => {
    if (!frameworkOutlineData?.outline || !outlineData?.outline) {
      setMessage({ type: 'error', text: '需要两个版本的目录数据' });
      return;
    }
    const scoringMap: Record<string, string> = {};
    leafItemsScoring.forEach(l => { if (l.content) scoringMap[l.id] = l.content; });
    const frameworkMap: Record<string, string> = {};
    leafItemsFramework.forEach(l => { if (l.content) frameworkMap[l.id] = l.content; });

    setIsMerging(true);
    setMergeProgressText('Phase 1/2: 目录融合+内容匹配...');
    setMessage(null);
    startTimer('merge');

    try {
      const prepRes = await mergeApi.prepare({
        framework_outline: frameworkOutlineData.outline,
        scoring_criteria: techRequirements,
        scoring_content_map: scoringMap,
        framework_content_map: frameworkMap,
        gap_analysis_json: gapResult ? JSON.stringify(gapResult) : '',
      });

      const mergedOutline = prepRes.data.outline;
      const matches = prepRes.data.matches;
      setMergedOutline(mergedOutline);
      setMergeProgressText(`目录融合完成，${matches.length} 个匹配节点`);

      // 收集叶子节点
      const leaves: any[] = [];
      const walk = (items: any[]) => {
        for (const item of items) {
          if (item.children?.length) walk(item.children);
          else leaves.push(item);
        }
      };
      walk(mergedOutline);

      const matchMap: Record<string, any> = {};
      matches.forEach((m: any) => { matchMap[m.node_id] = m; });

      // Phase 3: 逐章合成（独立请求，不依赖长 SSE 流）
      const contentResult: Record<string, string> = {};
      for (let i = 0; i < leaves.length; i++) {
        const leaf = leaves[i];
        const match = matchMap[leaf.id] || {};
        const scoringSrcIds = (match.scoring_sources || []).map((s: any) => s.id);
        const frameworkSrcIds = (match.framework_sources || []).map((s: any) => s.id);
        const scoringContent = scoringSrcIds.map((id: string) => scoringMap[id] || '').join('\n\n');
        const frameworkContent = frameworkSrcIds.map((id: string) => frameworkMap[id] || '').join('\n\n');

        const criteriaNames: string[] = leaf.covers_criteria || [];
        let gapSuggestions = '';
        if (gapResult) {
          gapSuggestions = gapResult.gaps
            .filter((g: any) => criteriaNames.some((cn: string) => g.criteria_name.includes(cn)))
            .map((g: any) => `[${g.issue_type}] ${g.description} → ${g.suggestion}`)
            .slice(0, 5).join('\n');
        }

        setMergeProgressText(`Phase 3: 合成章节 [${i+1}/${leaves.length}] ${leaf.title}...`);
        try {
          const synRes = await mergeApi.synthesize({
            node_id: leaf.id,
            node_title: leaf.title,
            node_description: leaf.description || '',
            covers_criteria: criteriaNames.join(', '),
            scoring_content: scoringContent,
            framework_content: frameworkContent,
            gap_suggestions: gapSuggestions,
          });
          contentResult[leaf.id] = synRes.data.content;
        } catch {
          contentResult[leaf.id] = scoringContent || frameworkContent || '（内容合成失败）';
        }
      }

      setMergedContent(contentResult);
      switchTab('merged');
      const elapsed = stopTimer();
      setMessage({ type: 'success', text: `合并完成！共合成 ${leaves.length} 个章节，耗时 ${formatDuration(elapsed)}` });
    } catch (e) {
      stopTimer();
      setMessage({ type: 'error', text: getErrorMessage(e, '合并失败') });
    } finally {
      setIsMerging(false);
    }
  };

  // ── reference doc upload ──
  const handleRefUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setRefFileName(file.name);
    const reader = new FileReader();
    reader.onload = () => setReferenceDoc(reader.result as string);
    reader.readAsText(file);
  };

  // ── export ──
  const handleExportWord = async () => {
    startTimer('export');
    if (activeTab === 'merged') {
      // 合并版导出
      if (!mergedOutline.length) { stopTimer(); return; }
      try {
        const buildExport = (items: any[]): any[] => {
          return items.map((item: any) => {
            const exported: any = { ...item, content: mergedContent[item.id] || '' };
            if (item.children?.length) exported.children = buildExport(item.children);
            return exported;
          });
        };
        const payload = {
          project_name: '投标技术文件_综合合并版',
          project_overview: projectOverview,
          outline: buildExport(mergedOutline),
        };
        const resp = await documentApi.exportWord(payload);
        saveAs(await resp.blob(), `${payload.project_name}.docx`);
        const elapsed = stopTimer();
        setMessage({ type: 'success', text: `导出成功，耗时 ${formatDuration(elapsed)}` });
      } catch (e) {
        stopTimer();
        setMessage({ type: 'error', text: getErrorMessage(e, '导出失败') });
      }
      return;
    }

    const outline = activeOutline;
    if (!outline) { stopTimer(); return; }
    try {
      const buildExport = (items: OutlineItem[]): OutlineItem[] => {
        return items.map(item => {
          const leaf = activeLeafItems.find(l => l.id === item.id);
          const latestContent = leaf?.content || item.content || '';
          const exported: OutlineItem = { ...item, content: latestContent };
          if (item.children?.length) exported.children = buildExport(item.children);
          return exported;
        });
      };
      const payload = {
        project_name: outline.project_name || (activeTab === 'scoring' ? '投标技术文件_评分标准版' : '投标文件_框架结构版'),
        project_overview: outline.project_overview || projectOverview,
        outline: buildExport(outline.outline),
      };
      const resp = await documentApi.exportWord(payload);
      saveAs(await resp.blob(), `${payload.project_name}.docx`);
      const elapsed = stopTimer();
      setMessage({ type: 'success', text: `导出成功，耗时 ${formatDuration(elapsed)}` });
    } catch (e) {
      stopTimer();
      setMessage({ type: 'error', text: getErrorMessage(e, '导出失败') });
    }
  };

  // ── render outline ──
  const renderOutline = (items: OutlineItem[], level = 1): React.ReactElement[] => {
    return items.map(item => {
      const isLeaf = !item.children?.length;
      const leafItem = activeLeafItems.find(l => l.id === item.id);
      const currentContent = isLeaf ? leafItem?.content || item.content : item.content;

      return (
        <div key={item.id} className={`mb-6`}>
          <div className={`font-semibold text-gray-900 mb-2 ${level === 1 ? 'text-lg border-b pb-1' : level === 2 ? 'text-base' : 'text-sm'}`}>
            {item.id} {item.title}
          </div>
          {item.description && <p className="text-xs text-gray-500 mb-3">{item.description}</p>}

          {isLeaf && (
            <div className="border-l-4 border-blue-200 pl-4 mb-4">
              {currentContent ? (
                <div className="prose max-w-none text-sm">
                  <ReactMarkdown>{currentContent}</ReactMarkdown>
                </div>
              ) : (
                <div className="text-gray-400 italic py-2 text-sm">
                  <DocumentTextIcon className="inline w-4 h-4 mr-1" />
                  {progress.generating.has(item.id) ? '正在生成...' : '内容待生成'}
                </div>
              )}
              {currentContent && (
                <button
                  onClick={() => handleOptimizeChapter(item)}
                  disabled={stage === 'optimizing'}
                  className="mt-2 inline-flex items-center text-xs text-purple-600 hover:text-purple-700 disabled:opacity-50"
                >
                  <SparklesIcon className="w-3 h-3 mr-1" />优化本章节
                </button>
              )}
            </div>
          )}

          {item.children && item.children.length > 0 && (
            <div className="ml-4">{renderOutline(item.children, level + 1)}</div>
          )}
        </div>
      );
    });
  };

  const completedCount = activeLeafItems.filter(l => l.content).length;
  const totalChars = activeLeafItems.reduce((s, l) => s + (l.content?.length || 0), 0);

  // ── render merged outline (四级目录) ──
  const renderMergedOutline = (items: any[], level = 1): React.ReactElement[] => {
    return items.map((item: any) => {
      const isLeaf = !item.children?.length;
      const content = isLeaf ? mergedContent[item.id] || '' : '';

      return (
        <div key={item.id} className={`mb-4`}>
          <div className={`font-semibold text-gray-900 mb-1 ${level === 1 ? 'text-lg border-b pb-1' : level === 2 ? 'text-base' : level === 3 ? 'text-sm' : 'text-xs text-gray-600'}`}>
            {item.id} {item.title}
          </div>
          {item.description && <p className="text-xs text-gray-500 mb-2">{item.description}</p>}
          {item.covers_criteria?.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-2">
              {item.covers_criteria.map((c: string, i: number) => (
                <span key={i} className="text-xs bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded">{c}</span>
              ))}
            </div>
          )}

          {isLeaf && (
            <div className="border-l-4 border-green-200 pl-4 mb-3">
              {content ? (
                <div className="prose max-w-none text-sm">
                  <ReactMarkdown>{content}</ReactMarkdown>
                </div>
              ) : (
                <div className="text-gray-400 italic py-1 text-xs">内容待合成</div>
              )}
            </div>
          )}

          {item.children && item.children.length > 0 && (
            <div className="ml-4">{renderMergedOutline(item.children, level + 1)}</div>
          )}
        </div>
      );
    });
  };

  // ── render ──
  return (
    <div className="max-w-6xl mx-auto space-y-4">

      {/* ===== Tab 切换 ===== */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex border-b border-gray-200">
          <button
            onClick={() => switchTab('scoring')}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${activeTab === 'scoring' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          >
            📋 目录 A：按评分标准
            {outlineData && <span className="ml-1 text-xs text-gray-400">({outlineData.outline.length}章)</span>}
          </button>
          <button
            onClick={() => switchTab('framework')}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${activeTab === 'framework' ? 'border-purple-500 text-purple-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          >
            📑 目录 B：按框架结构（仅技术部分）
            {frameworkOutlineData && <span className="ml-1 text-xs text-gray-400">({frameworkOutlineData.outline.length}章)</span>}
          </button>
          <button
            onClick={() => switchTab('merged')}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${activeTab === 'merged' ? 'border-green-500 text-green-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          >
            🔀 目录 C：综合合并版
            {mergedOutline.length > 0 && <span className="ml-1 text-xs text-gray-400">({mergedOutline.length}章)</span>}
          </button>
        </div>
      </div>

      {/* ===== 操作栏 ===== */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex flex-wrap items-center gap-3">
          <button onClick={handleGenerateContent} disabled={isGenerating || !activeOutline || activeTab === 'merged'}
            className="inline-flex items-center px-4 py-2 text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400">
            <DocumentTextIcon className="w-4 h-4 mr-1" />
            {isGenerating ? `生成中 ${progress.completed}/${progress.total}` : '① 生成正文'}
          </button>

          <button onClick={handleGapAnalysis}
            disabled={isGenerating || stage !== 'idle' || (activeTab === 'merged' ? !mergedOutline.length : completedCount === 0) || !techRequirements}
            className="inline-flex items-center px-4 py-2 text-sm font-medium rounded-md text-white bg-amber-600 hover:bg-amber-700 disabled:bg-gray-400">
            <MagnifyingGlassIcon className="w-4 h-4 mr-1" />② 检查遗漏/缺陷
          </button>

          <button onClick={handleScoring}
            disabled={isGenerating || stage !== 'idle' || (activeTab === 'merged' ? !mergedOutline.length : completedCount === 0) || !techRequirements}
            className="inline-flex items-center px-4 py-2 text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 disabled:bg-gray-400">
            <ChartBarIcon className="w-4 h-4 mr-1" />③ 评分
          </button>

          <button onClick={handleOptimizeAll}
            disabled={isGenerating || isMerging || stage !== 'idle' || (!gapResult && !scoreResult) || activeTab === 'merged'}
            className="inline-flex items-center px-4 py-2 text-sm font-medium rounded-md text-white bg-purple-600 hover:bg-purple-700 disabled:bg-gray-400">
            <SparklesIcon className="w-4 h-4 mr-1" />④ 优化薄弱章节
          </button>

          <button onClick={handleMerge}
            disabled={isGenerating || isMerging || stage !== 'idle' || !leafItemsScoring.length || !leafItemsFramework.length}
            className="inline-flex items-center px-4 py-2 text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 disabled:bg-gray-400">
            🔀 {isMerging ? '合并中...' : '⑦ 综合合并'}
          </button>

          <button onClick={handleExportWord}
            disabled={isGenerating || stage === 'optimizing'}
            className="inline-flex items-center px-4 py-2 text-sm font-medium rounded-md border border-gray-300 text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50">
            <DocumentArrowDownIcon className="w-4 h-4 mr-1" />导出 Word
          </button>

          {/* 参考方案上传 */}
          <label className="inline-flex items-center px-3 py-2 text-sm font-medium rounded-md border border-dashed border-purple-300 text-purple-600 bg-purple-50 hover:bg-purple-100 cursor-pointer">
            📎 {refFileName || '上传参考方案(.txt)'}
            <input type="file" accept=".txt,.md" onChange={handleRefUpload} className="hidden" />
          </label>
        </div>

        {/* live timer */}
        {timing.label && !timing.done && (
          <div className="mt-2 text-xs text-gray-500 flex items-center">
            <span className="inline-block w-2 h-2 bg-red-400 rounded-full animate-pulse mr-1.5" />
            ⏱ {formatDuration(timing.elapsedSec)} 已耗时
          </div>
        )}

        {/* progress bar */}
        {isGenerating && (
          <div className="mt-3">
            <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
              <span>正在生成: {progress.current}</span>
              <span>{progress.completed}/{progress.total}</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div className="bg-blue-600 h-2 rounded-full transition-all" style={{ width: `${(progress.completed / Math.max(progress.total, 1)) * 100}%` }} />
            </div>
          </div>
        )}

        {stage === 'optimizing' && (
          <div className="mt-3 text-sm text-purple-600 flex items-center">
            <div className="animate-spin h-4 w-4 border-2 border-purple-600 border-t-transparent rounded-full mr-2" />
            正在优化章节内容...
          </div>
        )}

        {isMerging && (
          <div className="mt-3 text-sm text-green-600 flex items-center">
            <div className="animate-spin h-4 w-4 border-2 border-green-600 border-t-transparent rounded-full mr-2" />
            合并进行中... {mergeProgressText}
          </div>
        )}

        {message && (
          <div className={`mt-3 rounded-md border px-4 py-2 text-sm ${message.type === 'success' ? 'border-green-200 bg-green-50 text-green-700' : 'border-red-200 bg-red-50 text-red-700'}`}>
            {message.text}
          </div>
        )}
      </div>

      {/* ===== 缺口分析结果 ===== */}
      {gapResult && (
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="text-base font-semibold text-gray-900 mb-2">
            <MagnifyingGlassIcon className="inline w-5 h-5 mr-1 text-amber-500" />
            缺口分析
            <span className="ml-2 text-xs font-normal text-gray-400">共 {gapResult.gaps.length} 个问题</span>
          </h3>
          <p className="text-sm text-gray-600 mb-3">{gapResult.summary}</p>
          {gapResult.gaps.length > 0 && (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {gapResult.gaps.map((g, i) => (
                <div key={i} className="p-2 bg-amber-50 border border-amber-200 rounded text-xs">
                  <span className={`inline-block px-1.5 py-0.5 rounded text-xs font-medium mr-2 ${
                    g.issue_type.includes('遗漏') ? 'bg-red-200 text-red-800' :
                    g.issue_type.includes('缺陷') ? 'bg-orange-200 text-orange-800' :
                    g.issue_type.includes('量化') ? 'bg-blue-200 text-blue-800' :
                    g.issue_type.includes('佐证') ? 'bg-purple-200 text-purple-800' :
                    'bg-yellow-200 text-yellow-800'
                  }`}>{g.issue_type}</span>
                  <strong>{g.criteria_name}</strong>: {g.description}
                  {g.suggestion && <p className="mt-1 text-green-700">💡 {g.suggestion}</p>}
                </div>
              ))}
            </div>
          )}
          {gapResult.quality_issues.length > 0 && (
            <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded text-xs">
              <strong className="text-red-800">⚠️ 质量警告：</strong>
              {gapResult.quality_issues.map((q, i) => <p key={i} className="text-red-700 mt-1">{q}</p>)}
            </div>
          )}
        </div>
      )}

      {/* ===== 评分表 ===== */}
      {scoreResult && (
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="text-base font-semibold text-gray-900 mb-2">
            <ChartBarIcon className="inline w-5 h-5 mr-1 text-green-500" />
            评分表
            <span className={`ml-2 text-lg font-bold ${scoreResult.total / scoreResult.max_total >= 0.8 ? 'text-green-600' : scoreResult.total / scoreResult.max_total >= 0.6 ? 'text-yellow-600' : 'text-red-600'}`}>
              {scoreResult.total}/{scoreResult.max_total}
            </span>
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="bg-gray-50">
                  <th className="border px-2 py-1 text-left">评分项</th>
                  <th className="border px-2 py-1 text-center w-16">满分</th>
                  <th className="border px-2 py-1 text-center w-16">得分</th>
                  <th className="border px-2 py-1 text-left">理由</th>
                </tr>
              </thead>
              <tbody>
                {scoreResult.scores.map((s, i) => (
                  <tr key={i} className={s.scored / Math.max(s.max_score, 1) < 0.6 ? 'bg-red-50' : ''}>
                    <td className="border px-2 py-1">{s.criteria_name}</td>
                    <td className="border px-2 py-1 text-center">{s.max_score}</td>
                    <td className={`border px-2 py-1 text-center font-bold ${s.scored / Math.max(s.max_score, 1) >= 0.8 ? 'text-green-600' : s.scored / Math.max(s.max_score, 1) >= 0.6 ? 'text-yellow-600' : 'text-red-600'}`}>{s.scored}</td>
                    <td className="border px-2 py-1 text-gray-600">{s.reasoning}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ===== 正文文档 ===== */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-8">
          <h1 className="text-2xl font-bold text-gray-900 mb-6">
            {activeTab === 'merged' ? '投标技术文件（综合合并版）' : activeOutline?.project_name || (activeTab === 'scoring' ? '投标技术文件（按评分标准）' : '投标文件（按框架结构）')}
          </h1>
          {projectOverview && (
            <div className="bg-blue-50 border-l-4 border-blue-400 p-4 mb-6 text-sm text-blue-800">
              <strong>项目概述：</strong>{projectOverview}
            </div>
          )}
          {activeTab === 'merged' && mergedOutline.length > 0
            ? renderMergedOutline(mergedOutline)
            : activeOutline && renderOutline(activeOutline.outline)
          }
        </div>
      </div>

      {/* ===== 底部统计 ===== */}
      <div className="bg-white rounded-lg shadow p-4 flex items-center justify-between text-sm text-gray-600">
        <div className="flex items-center space-x-6">
          {activeTab !== 'merged' ? (
            <>
              <span><CheckCircleIcon className="inline w-4 h-4 text-green-500 mr-1" />已完成: {completedCount}</span>
              <span><DocumentTextIcon className="inline w-4 h-4 mr-1" />待生成: {activeLeafItems.length - completedCount}</span>
            </>
          ) : (
            <span>合并版章节: {Object.keys(mergedContent).length}</span>
          )}
        </div>
        <span>总字数: {(activeTab === 'merged' ? Object.values(mergedContent).reduce((s, c) => s + c.length, 0) : totalChars).toLocaleString()}</span>
      </div>

      {showScrollToTop && (
        <button onClick={() => document.getElementById('app-main-scroll')?.scrollTo({ top: 0, behavior: 'smooth' })}
          className="fixed bottom-24 right-6 bg-blue-600 hover:bg-blue-700 text-white rounded-full p-3 shadow-lg z-50">
          <ArrowUpIcon className="w-5 h-5" />
        </button>
      )}
    </div>
  );
};

export default ContentEdit;
