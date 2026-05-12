"""标书合并服务：目录融合 → 内容匹配 → 逐节合成。"""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, List

from ..utils.openai_util import OpenAIUtil
from ..utils.prompts.merge_prompts import (
    build_level4_outline_messages,
    build_content_matching_messages,
    build_section_merge_messages,
)

logger = logging.getLogger(__name__)


def _text_summary(text: str, max_len: int = 80) -> str:
    return (text[:max_len] + "...") if len(text) > max_len else text


def _collect_leaf_ids(items: List[Dict], prefix: str = "") -> List[str]:
    """收集所有叶子节点的 id。"""
    ids: List[str] = []
    for item in items:
        full_id = f"{prefix}.{item['id']}" if prefix else item["id"]
        if item.get("children"):
            ids.extend(_collect_leaf_ids(item["children"], full_id))
        else:
            ids.append(item["id"])
    return ids


def _find_leaf_paths(items: List[Dict], path: List[str] = None) -> List[Dict]:
    """获取所有叶子节点的路径和元信息。"""
    if path is None:
        path = []
    leaves: List[Dict] = []
    for item in items:
        current_path = path + [item]
        if item.get("children"):
            leaves.extend(_find_leaf_paths(item["children"], current_path))
        else:
            leaves.append({
                "id": item["id"],
                "title": item.get("title", ""),
                "description": item.get("description", ""),
                "covers_criteria": item.get("covers_criteria", []),
                "path": [p.get("title", "") for p in current_path],
            })
    return leaves


class MergeService:
    """负责目录融合、内容匹配和合成。"""

    def __init__(self, ai: OpenAIUtil | None = None):
        self.ai = ai or OpenAIUtil()

    async def generate_level4_outline(
        self,
        framework_outline: List[Dict],
        scoring_criteria: str,
        gap_analysis_json: str = "",
    ) -> Dict[str, Any]:
        """生成四级目录。"""
        framework_json = json.dumps(framework_outline, ensure_ascii=False)
        messages = build_level4_outline_messages(
            framework_outline_json=framework_json,
            scoring_criteria=scoring_criteria,
            gap_analysis_json=gap_analysis_json,
        )
        result = await self.ai.collect_json_response(
            messages=messages,
            temperature=0.3,
            progress_label="目录融合",
            failure_message="四级目录生成失败",
        )
        return result

    async def match_content(
        self,
        merged_outline: List[Dict],
        scoring_content_map: Dict[str, str],
        framework_content_map: Dict[str, str],
    ) -> Dict[str, Any]:
        """为每个四级叶子节点匹配两版内容。"""
        merged_json = json.dumps(merged_outline, ensure_ascii=False)
        scoring_map_json = json.dumps(
            {k: _text_summary(v, 200) for k, v in scoring_content_map.items()},
            ensure_ascii=False,
        )
        framework_map_json = json.dumps(
            {k: _text_summary(v, 200) for k, v in framework_content_map.items()},
            ensure_ascii=False,
        )
        messages = build_content_matching_messages(
            merged_outline_json=merged_json,
            scoring_content_map_json=scoring_map_json,
            framework_content_map_json=framework_map_json,
        )
        result = await self.ai.collect_json_response(
            messages=messages,
            temperature=0.3,
            progress_label="内容匹配",
            failure_message="内容匹配失败",
        )
        return result

    async def synthesize_leaf(
        self,
        node_id: str,
        node_title: str,
        node_description: str,
        covers_criteria: str,
        scoring_content: str,
        framework_content: str,
        gap_suggestions: str = "",
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
        )
        return await self.ai.collect_chat_completion(
            messages=messages,
            temperature=0.5,
        )

    async def merge_full(
        self,
        framework_outline: List[Dict],
        scoring_criteria: str,
        scoring_content_map: Dict[str, str],
        framework_content_map: Dict[str, str],
        gap_analysis_json: str = "",
    ) -> AsyncGenerator[str, None]:
        """全流程合并，流式输出进度。"""
        from ..utils.sse import sse_progress, sse_chunk, sse_result, sse_done

        yield sse_progress("Phase 1/4: 目录融合中，为框架目录生成四级子目录...")

        # Phase 1: 目录融合 (LLM 调用期间发 keepalive)
        async def do_phase1():
            return await self.generate_level4_outline(
                framework_outline=framework_outline,
                scoring_criteria=scoring_criteria,
                gap_analysis_json=gap_analysis_json,
            )
        phase1_task = asyncio.create_task(do_phase1())
        while not phase1_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(phase1_task), timeout=5.0)
                break
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
        merged = await phase1_task
        merged_outline = merged.get("outline", [])
        yield sse_result({"phase": "outline", "outline": merged_outline})

        # Phase 2: 内容匹配 (LLM 调用期间发 keepalive)
        yield sse_progress("Phase 2/4: 内容匹配中，为每个章节建立两版映射...")
        async def do_phase2():
            return await self.match_content(
                merged_outline=merged_outline,
                scoring_content_map=scoring_content_map,
                framework_content_map=framework_content_map,
            )
        phase2_task = asyncio.create_task(do_phase2())
        while not phase2_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(phase2_task), timeout=5.0)
                break
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
        matches_result = await phase2_task
        matches = matches_result.get("matches", [])
        # 构建 node_id → match 的快速查找
        match_map: Dict[str, Dict] = {m["node_id"]: m for m in matches}
        yield sse_result({"phase": "matching", "matches": matches})

        # Phase 3: 逐节合成
        leaves = _find_leaf_paths(merged_outline)
        total = len(leaves)
        synthesized: Dict[str, str] = {}

        for i, leaf in enumerate(leaves):
            node_id = leaf["id"]
            yield sse_progress(f"Phase 3/4: 合成章节 [{i+1}/{total}] {leaf['title']}...")

            match = match_map.get(node_id, {})
            scoring_src_ids = [s.get("id", "") for s in match.get("scoring_sources", [])]
            framework_src_ids = [s.get("id", "") for s in match.get("framework_sources", [])]

            scoring_content = "\n\n".join(
                scoring_content_map.get(sid, "") for sid in scoring_src_ids
            )
            framework_content = "\n\n".join(
                framework_content_map.get(fid, "") for fid in framework_src_ids
            )

            # 提取该节点相关的缺口建议
            criteria_names = leaf.get("covers_criteria", [])
            gap_suggestions = ""
            if gap_analysis_json:
                try:
                    gaps = json.loads(gap_analysis_json).get("gaps", [])
                    relevant_gaps = [
                        f"[{g.get('issue_type','')}] {g.get('description','')} → {g.get('suggestion','')}"
                        for g in gaps
                        if any(cn in g.get("criteria_name", "") for cn in criteria_names)
                    ]
                    gap_suggestions = "\n".join(relevant_gaps[:5])
                except (json.JSONDecodeError, KeyError):
                    pass

            content = scoring_content or framework_content or "（内容合成失败，请手动补充）"
            try:
                # LLM 调用期间定期发 keepalive 防超时
                async def do_synthesis():
                    return await self.synthesize_leaf(
                        node_id=node_id,
                        node_title=leaf["title"],
                        node_description=leaf.get("description", ""),
                        covers_criteria=", ".join(criteria_names),
                        scoring_content=scoring_content,
                        framework_content=framework_content,
                        gap_suggestions=gap_suggestions,
                    )

                synth_task = asyncio.create_task(do_synthesis())
                while not synth_task.done():
                    try:
                        await asyncio.wait_for(asyncio.shield(synth_task), timeout=5.0)
                        break
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"

                content = await synth_task
            except Exception as exc:
                logger.warning("章节 %s 合成失败 (降级使用原始内容): %s", node_id, exc)

            synthesized[node_id] = content
            yield sse_chunk(f"[{i+1}/{total}] {leaf['title']} 完成")

        # Phase 4: 组装
        yield sse_progress("Phase 4/4: 组装最终文档...")
        yield sse_result({
            "phase": "done",
            "outline": merged_outline,
            "content": synthesized,
            "total_nodes": total,
        })

        yield sse_done()
