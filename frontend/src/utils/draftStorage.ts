/**
 * 本地草稿持久化
 * - 元数据（outline/techRequirements 等）→ localStorage
 * - 章节正文 → IndexedDB（容量大，不会像 localStorage 那样爆掉）
 */

import type { AppState, OutlineItem } from '../types';
import { idbStorage } from './idbStorage';

const DRAFT_KEY = 'yibiao:draft:v1';

export type DraftState = Pick<
  AppState,
  'currentStep' | 'fileContent' | 'projectOverview' | 'techRequirements' | 'commercialRequirements' | 'bidFramework' | 'outlineData' | 'frameworkOutlineData'
>;

export type ContentById = Record<string, string>;

const safeJsonParse = <T,>(raw: string | null): T | null => {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
};

export const draftStorage = {
  loadDraft(): Partial<DraftState> | null {
    return safeJsonParse<Partial<DraftState>>(localStorage.getItem(DRAFT_KEY));
  },

  saveDraft(partial: Partial<DraftState>) {
    try {
      const prev = safeJsonParse<Partial<DraftState>>(localStorage.getItem(DRAFT_KEY)) || {};
      const next = { ...prev, ...partial };
      localStorage.setItem(DRAFT_KEY, JSON.stringify(next));
    } catch (e) {
      console.warn('保存草稿失败（可能是 localStorage 空间不足）:', e);
    }
  },

  clearAll() {
    try {
      localStorage.removeItem(DRAFT_KEY);
    } catch (e) {
      console.warn('清空 localStorage 失败:', e);
    }
    idbStorage.clearAll().catch(e => console.warn('清空 IndexedDB 失败:', e));
  },

  /** IndexedDB 读写：章节正文 */
  async loadContentById(): Promise<ContentById> {
    try {
      return await idbStorage.getAllContent();
    } catch (e) {
      console.warn('读取章节内容失败:', e);
      return {};
    }
  },

  async upsertChapterContent(chapterId: string, content: string) {
    return idbStorage.setContent(chapterId, content);
  },

  /** 按 outline 叶子节点过滤（从 IndexedDB 读取） */
  async filterContentByOutlineLeaves(outline: OutlineItem[]): Promise<ContentById> {
    const map = await draftStorage.loadContentById();
    const leafIds = new Set<string>();
    const walk = (items: OutlineItem[]) => {
      items.forEach((it) => {
        if (!it.children || it.children.length === 0) {
          leafIds.add(it.id);
          return;
        }
        walk(it.children);
      });
    };
    walk(outline);

    const filtered: ContentById = {};
    Object.keys(map).forEach((id) => {
      if (leafIds.has(id)) filtered[id] = map[id];
    });
    return filtered;
  },
};


