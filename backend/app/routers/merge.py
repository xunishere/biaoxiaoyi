"""标书合并相关 API 路由。"""

import json
import logging
import os

from fastapi import APIRouter, HTTPException

from ..models.schemas import MergePrepareRequest, MergeSynthesizeRequest
from ..services.merge_service import MergeService
from ..utils.errors import AppError
from ..utils.prompts.merge_prompts import build_content_matching_messages

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/merge", tags=["标书合并"])

_MERGE_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")
_MERGE_FILE = os.path.join(_MERGE_DATA_DIR, "merged_result.json")


@router.post("/save")
async def merge_save(data: dict):
    """持久化合并版数据到服务端文件。"""
    try:
        os.makedirs(_MERGE_DATA_DIR, exist_ok=True)
        with open(_MERGE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return {"success": True}
    except Exception as exc:
        logger.exception("合并版数据保存失败")
        raise HTTPException(status_code=500, detail=f"保存失败: {exc}") from exc


@router.get("/load")
async def merge_load():
    """从服务端文件加载合并版数据。"""
    try:
        if not os.path.exists(_MERGE_FILE):
            return {"outline": [], "content": {}}
        with open(_MERGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.exception("合并版数据加载失败")
        raise HTTPException(status_code=500, detail=f"加载失败: {exc}") from exc


@router.post("/prepare")
async def merge_prepare(request: MergePrepareRequest):
    """Phase 1+2：LLM 目录融合 + 关键词内容匹配。"""
    try:
        merge_service = MergeService()
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    try:
        # Phase 1: 以框架结构目录为合并基准（框架结构好移植，现在108叶子已够细）
        merged_outline = request.framework_outline if request.framework_outline else request.scoring_outline

        # Phase 2: 关键词内容匹配（稳健，不会被大 prompt 搞挂）
        matches = _keyword_match_all(
            merged_outline=merged_outline,
            scoring_ids=list(request.scoring_content_map.keys()),
            framework_ids=list(request.framework_content_map.keys()),
        )

        return {"outline": merged_outline, "matches": matches}

    except AppError:
        raise
    except Exception:
        logger.exception("合并准备失败")
        raise HTTPException(status_code=500, detail="合并准备失败") from None


def _collect_leaves(items: list) -> list:
    """收集所有叶子节点。"""
    leaves = []
    for item in items:
        if item.get("children"):
            leaves.extend(_collect_leaves(item["children"]))
        else:
            leaves.append(item)
    return leaves


def _keyword_match(title: str, ids: list) -> list:
    """简单关键词匹配。返回 id 列表。"""
    if not ids:
        return []
    keywords = set(title.replace("（", "(").replace("）", ")").split())
    scored = []
    for cid in ids:
        score = sum(1 for kw in keywords if len(kw) >= 2 and kw in cid)
        if score > 0:
            scored.append({"id": cid, "relevance": "高" if score >= 3 else "中"})
    if not scored:
        scored.append({"id": ids[0], "relevance": "低"})
    return scored[:3]


def _keyword_match_all(
    merged_outline: list,
    scoring_ids: list,
    framework_ids: list,
) -> list:
    """为所有叶子节点做关键词匹配。"""
    leaves = _collect_leaves(merged_outline)
    matches = []
    for leaf in leaves:
        title = leaf.get("title", "")
        matches.append({
            "node_id": leaf["id"],
            "node_title": title,
            "scoring_sources": _keyword_match(title, scoring_ids),
            "framework_sources": _keyword_match(title, framework_ids),
        })
    return matches


@router.post("/synthesize")
async def merge_synthesize(request: MergeSynthesizeRequest):
    """Phase 3：LLM 合成单个章节。"""
    try:
        merge_service = MergeService()
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    try:
        content = await merge_service.synthesize_leaf(
            node_id=request.node_id,
            node_title=request.node_title,
            node_description=request.node_description,
            covers_criteria=request.covers_criteria,
            scoring_content=request.scoring_content,
            framework_content=request.framework_content,
            gap_suggestions=request.gap_suggestions,
            target_words=request.target_words,
        )
        return {"content": content}
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception:
        logger.exception("章节 %s 合成失败", request.node_id)
        raise HTTPException(status_code=500, detail="章节合成失败") from None
