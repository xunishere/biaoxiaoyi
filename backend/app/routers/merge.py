"""标书合并相关 API 路由。"""

import json
import logging

from fastapi import APIRouter, HTTPException

from ..models.schemas import MergePrepareRequest, MergeSynthesizeRequest
from ..services.merge_service import MergeService
from ..utils.errors import AppError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/merge", tags=["标书合并"])


@router.post("/prepare")
async def merge_prepare(request: MergePrepareRequest):
    """Phase 1+2：目录准备 + 内容匹配（规则匹配，无 LLM 调用）。"""
    try:
        # 直接用框架版目录作为合并目录，不做 LLM 四级拆分
        merged_outline = request.framework_outline

        # 收集所有叶子节点
        leaves = _collect_leaves(merged_outline)

        # 规则匹配：每个叶子节点匹配两版内容
        scoring_ids = list(request.scoring_content_map.keys())
        framework_ids = list(request.framework_content_map.keys())

        matches = []
        for leaf in leaves:
            title = leaf.get("title", "")
            # 简单关键词匹配
            scoring_sources = _keyword_match(title, scoring_ids, request.scoring_content_map)
            framework_sources = _keyword_match(title, framework_ids, request.framework_content_map)
            matches.append({
                "node_id": leaf["id"],
                "node_title": title,
                "scoring_sources": scoring_sources,
                "framework_sources": framework_sources,
            })

        return {"outline": merged_outline, "matches": matches}
    except Exception:
        logger.exception("合并准备失败")
        raise HTTPException(status_code=500, detail="合并准备失败") from None


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
        )
        return {"content": content}
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception:
        logger.exception("章节 %s 合成失败", request.node_id)
        raise HTTPException(status_code=500, detail="章节合成失败") from None


def _collect_leaves(items: list) -> list:
    """收集所有叶子节点。"""
    leaves = []
    for item in items:
        if item.get("children"):
            leaves.extend(_collect_leaves(item["children"]))
        else:
            leaves.append(item)
    return leaves


def _keyword_match(title: str, ids: list, content_map: dict) -> list:
    """简单关键词匹配。返回 id 列表。"""
    if not ids:
        return []
    # 按标题关键词匹配
    keywords = set(title.replace("（", "(").replace("）", ")").split())
    scored = []
    for cid in ids:
        content = content_map.get(cid, "")
        content_title = cid  # 用 ID 做后备
        score = sum(1 for kw in keywords if len(kw) >= 2 and kw in content)
        if score > 0:
            scored.append({"id": cid, "relevance": "高" if score >= 3 else "中"})
    if not scored:
        # 无匹配：用第一个评分版 ID
        scored.append({"id": ids[0], "relevance": "低"})
    return scored[:3]
