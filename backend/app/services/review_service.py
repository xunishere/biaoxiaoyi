"""标书审查、评分、优化服务。"""

import re
from typing import Any, AsyncGenerator, Dict, List

from ..utils.openai_util import OpenAIUtil
from ..utils.prompts.review_prompts import (
    build_gap_analysis_messages,
    build_scoring_table_messages,
    build_optimize_chapter_messages,
    build_cross_duplicate_messages,
)

CHUNK_SIZE = 20000  # 每块最大字符数


class ReviewService:
    """负责缺口分析、评分表生成、内容优化。"""

    def __init__(self, ai: OpenAIUtil | None = None):
        self.ai = ai or OpenAIUtil()

    @staticmethod
    def _split_document(document_content: str) -> List[str]:
        """按 ## 标题分块，每块不超过 CHUNK_SIZE 字符。"""
        # 按二级标题切分
        sections = re.split(r'\n(?=## \d)', document_content)
        chunks: list[str] = []
        current = ""
        for section in sections:
            if len(current) + len(section) > CHUNK_SIZE and current:
                chunks.append(current.strip())
                current = section
            else:
                current += "\n" + section if current else section
        if current.strip():
            chunks.append(current.strip())
        return chunks

    @staticmethod
    def _deduplicate_gaps(all_gaps: List[Dict]) -> List[Dict]:
        """按 criteria_name + issue_type 去重合并。"""
        seen: dict[tuple, Dict] = {}
        for gap in all_gaps:
            key = (gap.get("criteria_name", ""), gap.get("issue_type", ""))
            if key in seen:
                # 合并描述和建议
                existing = seen[key]
                if gap.get("description") and gap["description"] not in existing["description"]:
                    existing["description"] += "；" + gap["description"]
                if gap.get("suggestion") and gap["suggestion"] not in existing.get("suggestion", ""):
                    existing["suggestion"] = (existing.get("suggestion", "") + "；" + gap["suggestion"]).strip("；")
            else:
                seen[key] = dict(gap)
        return list(seen.values())

    @staticmethod
    def _extract_chapter_previews(document_content: str, max_chars: int = 150) -> list[dict]:
        """提取每章标题+正文前 max_chars 字作为摘要。"""
        pattern = r'## (\S+) (.+?)\n(.*?)(?=\n## |\Z)'
        previews = []
        for m in re.finditer(pattern, document_content, re.DOTALL):
            cid = m.group(1)
            title = m.group(2)
            body = m.group(3).strip()[:max_chars]
            previews.append({"id": cid, "title": title, "preview": body})
        return previews

    async def gap_analysis(
        self, document_content: str, scoring_criteria: str
    ) -> Dict[str, Any]:
        """分块全文审查 + 交叉查重 + 汇总去重。"""
        chunks = self._split_document(document_content)
        all_gaps: list[dict] = []
        all_quality: list[str] = []
        summaries: list[str] = []

        # Phase 1: 逐块审查
        for i, chunk in enumerate(chunks):
            label = f"缺口分析" if len(chunks) == 1 else f"缺口分析({i+1}/{len(chunks)})"
            messages = build_gap_analysis_messages(
                document_content=chunk,
                scoring_criteria=scoring_criteria,
            )
            result = await self.ai.collect_json_response(
                messages=messages,
                temperature=0.3,
                progress_label=label,
                failure_message=f"第{i+1}块缺口分析失败",
            )
            all_gaps.extend(result.get("gaps", []))
            all_quality.extend(result.get("quality_issues", []))
            if result.get("summary"):
                summaries.append(result["summary"])

        # Phase 2: 交叉查重
        previews = self._extract_chapter_previews(document_content)
        cross_duplicates: list[str] = []
        if len(previews) > 5:
            dup_messages = build_cross_duplicate_messages(previews)
            try:
                dup_result = await self.ai.collect_json_response(
                    messages=dup_messages,
                    temperature=0.3,
                    progress_label="交叉查重",
                    failure_message="交叉查重失败",
                )
                cross_duplicates = dup_result.get("duplicates", [])
            except Exception:
                pass  # 交叉查重失败不影响主流程

        # Phase 3: 去重合并
        gaps = self._deduplicate_gaps(all_gaps)
        quality_issues = list(dict.fromkeys(all_quality))  # 去重保序
        if cross_duplicates:
            quality_issues.insert(0, "【章节重复】" + "；".join(cross_duplicates))

        summary = "；".join(summaries) if summaries else ""
        if len(chunks) > 1:
            summary = f"（全文分{len(chunks)}块审查）{summary}"

        return {"gaps": gaps, "quality_issues": quality_issues, "summary": summary}

    async def scoring_table(
        self, document_content: str, scoring_criteria: str, gap_analysis_json: str = ""
    ) -> Dict[str, Any]:
        """逐章评估 + 汇总评分表。"""
        from ..utils.prompts.review_prompts import (
            build_per_chapter_eval_messages,
            build_aggregate_scores_messages,
        )

        # 提取每章
        chapters: list[dict] = []
        for m in re.finditer(r'## (\S+) (.+?)\n(.*?)(?=\n## |\Z)', document_content, re.DOTALL):
            chapters.append({
                "id": m.group(1), "title": m.group(2),
                "content": m.group(3).strip()[:3000],
            })

        if not chapters:
            return {"scores": [], "total": 0, "max_total": 0, "summary": "无章节"}

        # Phase 1: 逐章评估（5并发）
        evaluations: list[dict] = []
        concurrency = 5
        for i in range(0, len(chapters), concurrency):
            batch = chapters[i:i+concurrency]
            async def eval_chapter(ch: dict) -> dict:
                msgs = build_per_chapter_eval_messages(
                    chapter_id=ch["id"], chapter_title=ch["title"],
                    chapter_content=ch["content"], scoring_criteria=scoring_criteria,
                )
                try:
                    return await self.ai.collect_json_response(
                        messages=msgs, temperature=0.3,
                        progress_label=f"评估 {ch['id']}",
                        failure_message=f"章节{ch['id']}评估失败",
                    )
                except Exception:
                    return {"relevance": True, "criteria_matched": [], "quality": 5, "issues": ["评估失败"]}

            import asyncio
            results = await asyncio.gather(*[eval_chapter(c) for c in batch])
            evaluations.extend(results)

        # Phase 2: 汇总评分
        eval_lines = []
        for ch, ev in zip(chapters, evaluations):
            eval_lines.append(
                f"[{ch['id']}] {ch['title']} | "
                f"切题:{'是' if ev.get('relevance') else '否'} | "
                f"质量:{ev.get('quality',0)}/10 | "
                f"覆盖:{','.join(ev.get('criteria_matched',[])) or '无'} | "
                f"问题:{';'.join(ev.get('issues',[])) or '无'}"
            )
        eval_text = "\n".join(eval_lines)

        messages = build_aggregate_scores_messages(
            chapter_evaluations=eval_text, scoring_criteria=scoring_criteria,
        )
        return await self.ai.collect_json_response(
            messages=messages, temperature=0.3,
            progress_label="汇总评分",
            failure_message="评分汇总失败",
        )

    async def optimize_chapter_stream(
        self,
        chapter_id: str,
        chapter_title: str,
        current_content: str,
        scoring_criteria: str = "",
        gap_suggestions: str = "",
        sibling_summaries: str | None = None,
        reference_docs: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式优化单个章节。"""
        messages = build_optimize_chapter_messages(
            chapter_id=chapter_id,
            chapter_title=chapter_title,
            current_content=current_content,
            scoring_criteria=scoring_criteria,
            gap_suggestions=gap_suggestions,
            sibling_summaries=sibling_summaries,
            reference_docs=reference_docs,
        )
        async for chunk in self.ai.stream_chat_completion(
            messages,
            temperature=0.5,
            max_tokens=2048,
        ):
            yield chunk
