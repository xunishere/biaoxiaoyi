"""标书审查、评分、优化服务。"""

from typing import Any, AsyncGenerator, Dict

from ..utils.openai_util import OpenAIUtil
from ..utils.prompts.review_prompts import (
    build_gap_analysis_messages,
    build_scoring_table_messages,
    build_optimize_chapter_messages,
)


class ReviewService:
    """负责缺口分析、评分表生成、内容优化。"""

    def __init__(self, ai: OpenAIUtil | None = None):
        self.ai = ai or OpenAIUtil()

    async def gap_analysis(
        self, document_content: str, scoring_criteria: str
    ) -> Dict[str, Any]:
        """分析内容缺口和缺陷。"""
        messages = build_gap_analysis_messages(
            document_content=document_content,
            scoring_criteria=scoring_criteria,
        )
        return await self.ai.collect_json_response(
            messages=messages,
            temperature=0.3,
            progress_label="缺口分析",
            failure_message="缺口分析失败",
        )

    async def scoring_table(
        self, document_content: str, scoring_criteria: str
    ) -> Dict[str, Any]:
        """生成评分表。"""
        messages = build_scoring_table_messages(
            document_content=document_content,
            scoring_criteria=scoring_criteria,
        )
        return await self.ai.collect_json_response(
            messages=messages,
            temperature=0.3,
            progress_label="评分表",
            failure_message="评分表生成失败",
        )

    async def optimize_chapter_stream(
        self,
        chapter_id: str,
        chapter_title: str,
        current_content: str,
        scoring_criteria: str = "",
        gap_suggestions: str = "",
        reference_docs: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式优化单个章节。"""
        messages = build_optimize_chapter_messages(
            chapter_id=chapter_id,
            chapter_title=chapter_title,
            current_content=current_content,
            scoring_criteria=scoring_criteria,
            gap_suggestions=gap_suggestions,
            reference_docs=reference_docs,
        )
        async for chunk in self.ai.stream_chat_completion(
            messages,
            temperature=0.5,
            max_tokens=2048,
        ):
            yield chunk
