/**
 * 后端状态同步工具 — 将所有浏览器本地状态同步到服务端，跨电脑共享。
 */
import { draftStorage } from './draftStorage';
import { idbStorage } from './idbStorage';
import { stateApi } from '../services/api';

const SYNC_DEBOUNCE_MS = 2000;
let syncTimer: ReturnType<typeof setTimeout> | null = null;

export const syncAllState = () => {
  if (syncTimer) clearTimeout(syncTimer);
  syncTimer = setTimeout(async () => {
    try {
      const draft = draftStorage.loadDraft() || {};
      const chapterContent = await idbStorage.getAllContent().catch(() => ({}));

      // 收集 review 缓存
      const reviewData: Record<string, any> = {};
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith('yibiao_review_')) {
          try { reviewData[key] = JSON.parse(localStorage.getItem(key) || ''); } catch {}
        }
      }

      // 合并版缓存
      const mergedOutline = (() => { try { return JSON.parse(localStorage.getItem('yibiao_merged_outline') || '[]'); } catch { return []; } })();
      const mergedContent = (() => { try { return JSON.parse(localStorage.getItem('yibiao_merged_content') || '{}'); } catch { return {}; } })();

      await stateApi.save({
        draft,
        chapterContent,
        reviewData,
        mergedOutline,
        mergedContent,
      });
    } catch { /* 静默失败，不打扰用户 */ }
  }, SYNC_DEBOUNCE_MS);
};

export const restoreAllState = async (): Promise<boolean> => {
  try {
    const res = await stateApi.load();
    const data = res.data;
    if (!data || !Object.keys(data).length) return false;

    // 恢复 draft 到 localStorage
    if (data.draft && Object.keys(data.draft).length > 0) {
      draftStorage.saveDraft(data.draft);
    }

    // 恢复章节内容到 IndexedDB
    if (data.chapterContent && Object.keys(data.chapterContent).length > 0) {
      for (const [id, content] of Object.entries(data.chapterContent)) {
        await idbStorage.setContent(id, content as string).catch(() => {});
      }
    }

    // 恢复 review 缓存
    if (data.reviewData) {
      for (const [key, value] of Object.entries(data.reviewData)) {
        try { localStorage.setItem(key, JSON.stringify(value)); } catch {}
      }
    }

    // 恢复合并版
    if (data.mergedOutline?.length) {
      localStorage.setItem('yibiao_merged_outline', JSON.stringify(data.mergedOutline));
    }
    if (data.mergedContent && Object.keys(data.mergedContent).length > 0) {
      localStorage.setItem('yibiao_merged_content', JSON.stringify(data.mergedContent));
    }

    return true;
  } catch {
    return false;
  }
};
