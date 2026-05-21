"""标书合并服务 — 单章 LLM 合成。"""

import logging

from ..utils.openai_util import OpenAIUtil
from ..utils.prompts.merge_prompts import build_section_merge_messages

logger = logging.getLogger(__name__)


class MergeService:
    """负责单章节两版内容合成。"""

    def __init__(self, ai: OpenAIUtil | None = None):
        self.ai = ai or OpenAIUtil()

    async def synthesize_leaf(
        self,
        node_id: str,
        node_title: str,
        node_description: str,
        covers_criteria: str,
        scoring_content: str,
        framework_content: str,
        gap_suggestions: str = "",
        target_words: int | None = None,
    ) -> str:
        """合并单个叶子节点的两版内容。"""
        messages = build_section_merge_messages(
            node_id=node_id,
            node_title=node_title,
            node_description=node_description,
            covers_criteria=covers_criteria,
            scoring_content=scoring_content,
            framework_content=framework_content,
            gap_suggestions=gap_suggestions,
            target_words=target_words,
        )
        return await self.ai.collect_chat_completion(
            messages=messages,
            temperature=0.5,
        )
