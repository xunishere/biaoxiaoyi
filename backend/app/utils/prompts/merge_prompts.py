"""目录融合 + 内容匹配 + 合成相关提示词。"""

import json
from typing import Dict, List


def build_merge_outline_messages(
    framework_outline: List[Dict],
    scoring_outline: List[Dict],
    scoring_criteria: str,
) -> List[Dict[str, str]]:
    """LLM 目录融合：框架骨架不动，评分版细粒度子目录挂到框架叶子下。"""
    framework_json = json.dumps(framework_outline, ensure_ascii=False, indent=2)
    scoring_json = json.dumps(scoring_outline, ensure_ascii=False, indent=2)

    system_prompt = """你是标书目录融合专家。请将框架版目录和评分版目录合并为一个完整目录。

核心约束（必须严格遵守）：
1. 框架版的一级和二级节点 100% 不动 — 不增、不删、不改标题、不改编号、不改顺序
2. 只允许在框架版的叶子节点下补充三四级子目录（children）
3. 补充来源：评分版目录中与框架叶子同主题的章节下已有的子目录
4. 评分版特有的独立章节（框架完全没有的）不要作为新节点加入框架

处理步骤：
1. 遍历框架版每一个叶子节点（没有 children 的）
2. 在评分版目录中查找与它主题最接近的章节
3. 如果评分版该章节下面有子目录（children），把它们挂到框架叶子节点下
4. 子目录保持评分版原有的三四级层级结构和描述

返回 JSON：
{
  "outline": [
    {
      "id": "1",
      "title": "一级标题",
      "description": "...",
      "children": [
        {
          "id": "1.1",
          "title": "二级标题",
          "description": "...",
          "children": [
            {"id": "1.1.1", "title": "三级（框架原始或评分补充）", "description": "...",
             "children": [{"id": "1.1.1.1", "title": "四级（评分补充）", "description": "..."}]}
          ]
        }
      ]
    }
  ]
}
只返回 JSON，不要任何其他内容。"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"评分标准：\n{scoring_criteria}"},
        {"role": "user", "content": f"框架版目录：\n{framework_json}"},
        {"role": "user", "content": f"评分版目录：\n{scoring_json}"},
        {"role": "user", "content": "请合并两个目录，框架一二级节点不动，只在叶子下补充评分版的子目录。"},
    ]


def build_content_matching_messages(
    merged_outline: List[Dict],
    scoring_content_map: Dict[str, str],
    framework_content_map: Dict[str, str],
) -> List[Dict[str, str]]:
    """LLM 内容匹配：为每个叶子节点语义匹配两版中最相关的内容。"""
    import re

    # 收集叶子节点
    leaves: list[dict] = []
    def walk(items: list, path: str = ""):
        for item in items:
            cid = item.get("id", "")
            full = f"{path}.{cid}" if path else cid
            if item.get("children"):
                walk(item["children"], full)
            else:
                leaves.append({"id": full, "title": item.get("title", ""), "description": item.get("description", "")})
    walk(merged_outline)

    leaves_json = json.dumps(leaves, ensure_ascii=False, indent=2)

    # 内容摘要：{id: 标题 + 前200字}
    def content_summary(content_map: Dict[str, str]) -> Dict[str, str]:
        result = {}
        for cid, content in content_map.items():
            if not content:
                result[cid] = "(空)"
                continue
            first_line = content.strip().split("\n")[0][:80]
            summary = re.sub(r'[#*\-`]', '', first_line).strip() or content[:80]
            result[cid] = summary
        return result

    scoring_summary = json.dumps(content_summary(scoring_content_map), ensure_ascii=False, indent=2)
    framework_summary = json.dumps(content_summary(framework_content_map), ensure_ascii=False, indent=2)

    system_prompt = """你是标书内容匹配专家。为合并后目录的每个叶子节点，在评分版和框架版的内容中分别找到最匹配的章节ID。

规则：
1. 语义匹配：根据叶子标题和描述，理解其主题，在内容摘要中找最相关的
2. 每个叶子在评分版和框架版中各找一个最佳匹配（relevance: "高"）
3. 如果某版本没有相关章节，标注 relevance: "低" 并匹配最接近的
4. 返回 JSON，不要任何其他内容

JSON 格式：
{
  "matches": [
    {
      "node_id": "1.2.1",
      "scoring_sources": [{"id": "1.1", "relevance": "高"}],
      "framework_sources": [{"id": "1.2.1", "relevance": "高"}]
    }
  ]
}"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"合并目录的叶子节点：\n{leaves_json}"},
        {"role": "user", "content": f"评分版内容摘要（ID→前80字）：\n{scoring_summary}"},
        {"role": "user", "content": f"框架版内容摘要（ID→前80字）：\n{framework_summary}"},
        {"role": "user", "content": "请为每个叶子节点匹配最相关的评分版和框架版内容ID。"},
    ]


def build_section_merge_messages(
    node_id: str,
    node_title: str,
    node_description: str,
    covers_criteria: str,
    scoring_content: str,
    framework_content: str,
    gap_suggestions: str = "",
    target_words: int | None = None,
) -> List[Dict[str, str]]:
    """合并单个章节的两版内容。"""
    # 表格类章节：允许表格格式
    is_table = any(kw in node_title or kw in node_description for kw in ['表', '清单', '列表', '名册', '模板', '响应/偏离', '偏离说明', '响应说明'])
    table_rule = ""
    if is_table:
        table_rule = "\n10. 本章为表格类内容。如有采购文件规定的格式严格遵循；如无则自行设计合理列并填表。合并后必须输出Markdown表格，严禁描述表格格式或写长篇文本替代。"

    no_md = "" if is_table else "\n9. 禁止使用Markdown或LaTeX格式标记"
    system_prompt = f"""你是标书内容合成专家。请将两版标书章节内容合并为一份完整的正文。

规则：
1. 以评分标准为导向，确保覆盖所有评分要点
2. 以质量较高的一版为底，吸收另一版的独特内容
3. 去重：同一信息只保留一份，优先保留论证更详细、有数据的版本
4. 补漏：根据缺口分析和评分标准补充缺失内容
5. 过渡：段落间自然衔接，统一语气和风格
6. 统一人称：使用"投标人"或直接陈述，不用"我们"、"我公司"
7. 不要输出标题，直接返回合并后的正文
8. 不要输出解释、标记、溯源信息{no_md}{table_rule}"""

    messages = [{"role": "system", "content": system_prompt}]

    if covers_criteria.strip():
        messages.append({
            "role": "user",
            "content": f"本节点覆盖的评分准则：\n{covers_criteria}"
        })

    if gap_suggestions.strip():
        messages.append({
            "role": "user",
            "content": f"缺口分析建议：\n{gap_suggestions[:2000]}"
        })

    if scoring_content.strip():
        messages.append({
            "role": "user",
            "content": f"【评分版】{node_title}内容：\n{scoring_content[:6000]}"
        })

    if framework_content.strip():
        messages.append({
            "role": "user",
            "content": f"【框架版】{node_title}内容：\n{framework_content[:6000]}"
        })

    word_note = ""
    if target_words and target_words > 0:
        word_note = f"篇幅要求：合并后不少于{target_words}字。如果两版内容合并后不足，请保留所有有效内容，不硬凑字数。"

    messages.append({
        "role": "user",
        "content": f"节点：{node_id} {node_title}\n描述：{node_description}\n{word_note}\n请合并以上两版内容，输出完整的优化后正文。"
    })

    return messages
