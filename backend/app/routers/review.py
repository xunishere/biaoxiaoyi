"""审查、评分、优化相关 API 路由。"""

import logging

from fastapi import APIRouter, HTTPException

from ..models.schemas import (
    GapAnalysisRequest,
    GapAnalysisResponse,
    OptimizeChapterRequest,
    ScoringTableRequest,
    ScoringTableResponse,
)
from ..services.review_service import ReviewService
from ..utils.errors import AppError
from ..utils.sse import sse_chunk, sse_done, sse_error, sse_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/review", tags=["标书审查"])


@router.post("/gap-analysis", response_model=GapAnalysisResponse)
async def gap_analysis(request: GapAnalysisRequest):
    """分析投标文件针对评分标准的遗漏和缺陷。"""
    try:
        review_service = ReviewService()
        result = await review_service.gap_analysis(
            document_content=request.document_content,
            scoring_criteria=request.scoring_criteria,
        )
        return GapAnalysisResponse(**result)
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:
        logger.exception("缺口分析失败")
        raise HTTPException(status_code=500, detail=f"缺口分析失败: {exc}") from exc


@router.post("/scoring-table", response_model=ScoringTableResponse)
async def scoring_table(request: ScoringTableRequest):
    """生成评分表。"""
    try:
        review_service = ReviewService()
        result = await review_service.scoring_table(
            document_content=request.document_content,
            scoring_criteria=request.scoring_criteria,
        )
        return ScoringTableResponse(**result)
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:
        logger.exception("评分表生成失败")
        raise HTTPException(status_code=500, detail=f"评分表生成失败: {exc}") from exc


@router.post("/optimize-chapter-stream")
async def optimize_chapter_stream(request: OptimizeChapterRequest):
    """流式优化单个章节内容。"""
    try:
        review_service = ReviewService()
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    async def generate():
        try:
            async for chunk in review_service.optimize_chapter_stream(
                chapter_id=request.chapter_id,
                chapter_title=request.chapter_title,
                current_content=request.current_content,
                scoring_criteria=request.scoring_criteria,
                gap_suggestions=request.gap_suggestions,
                reference_docs=request.reference_docs,
            ):
                yield sse_chunk(chunk)
        except AppError as exc:
            yield sse_error(exc.message)
        except Exception:
            logger.exception("章节优化失败")
            yield sse_error("章节优化失败，请稍后重试")
        finally:
            yield sse_done()

    return sse_response(generate())
