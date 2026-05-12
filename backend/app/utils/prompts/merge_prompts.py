"""目录融合 + 内容匹配 + 合成相关提示词。"""

from typing import Dict, List


def build_level4_outline_messages(
    framework_outline_json: str,
    scoring_criteria: str,
    gap_analysis_json: str = "",
) -> List[Dict[str, str]]:
    """为框架目录的三级节点生成四级子目录。"""
    system_prompt = """你是一个专业的标书目录结构师。请基于框架目录的三级结构，为每个三级节点生成四级子目录。四级子目录的拆分依据是对应的评分标准——每个四级节点对应一项或多项评分准则。

规则：
1. 保持三级节点的编号体系不变（如"1.1"、"1.2"等）
2. 对每个三级节点，分析它覆盖了哪些评分标准的准则
3. 将覆盖的准则映射为四级子目录节点，编号如"1.1.1"、"1.1.2"等
4. 如果一个三级节点只覆盖一项准则，不需要拆分四级
5. 如果评分标准中有准则没有被任何三级节点覆盖，在相关位置（通常是末尾）补充新节点，标记为"评分标准补充"
6. 四级节点描述要体现对应的评分要求
7. 返回 JSON，不要任何其他内容

返回格式：
{
  "outline": [
    {
      "id": "1",
      "title": "一级标题",
      "children": [
        {
          "id": "1.1",
          "title": "二级标题",
          "children": [
            {
              "id": "1.1.1",
              "title": "三级标题",
              "children": [
                {"id": "1.1.1.1", "title": "四级标题", "description": "描述", "covers_criteria": ["准则名"]}
              ]
            }
          ]
        }
      ]
    }
  ]
}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"评分标准：\n{scoring_criteria[:8000]}"},
    ]

    if gap_analysis_json.strip():
        messages.append({
            "role": "user",
            "content": f"现有缺口分析结果（参考其指出的覆盖不足项）：\n{gap_analysis_json[:3000]}"
        })

    messages.append({
        "role": "user",
        "content": f"框架目录（三级结构）：\n{framework_outline_json}\n\n请为每个三级节点生成四级子目录。"
    })

    return messages


def build_content_matching_messages(
    merged_outline_json: str,
    scoring_content_map_json: str,
    framework_content_map_json: str,
) -> List[Dict[str, str]]:
    """为合并后的每个四级叶子节点匹配两版内容。"""
    system_prompt = """你是标书内容匹配专家。给定合并后的四级目录、评分版正文和框架版正文，为每个四级叶子节点找到对应的段落来源。

规则：
1. 遍历每个四级叶子节点（有 children 的非叶子节点不需要匹配）
2. 根据节点标题和描述，在两版正文中找到最匹配的章节/段落
3. 返回每个节点的匹配结果
4. 两版中有多重匹配时，都列出来
5. 返回 JSON，不要任何其他内容

返回格式：
{
  "matches": [
    {
      "node_id": "1.2.3.1",
      "node_title": "四级节点标题",
      "scoring_sources": [{"id": "章节ID", "title": "章节标题", "relevance": "高/中/低"}],
      "framework_sources": [{"id": "章节ID", "title": "章节标题", "relevance": "高/中/低"}]
    }
  ]
}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"合并后的四级目录：\n{merged_outline_json[:6000]}"},
        {"role": "user", "content": f"评分版正文（章节ID→内容映射）：\n{scoring_content_map_json[:5000]}"},
        {"role": "user", "content": f"框架版正文（章节ID→内容映射）：\n{framework_content_map_json[:5000]}"},
        {"role": "user", "content": "请为每个四级叶子节点匹配两版正文来源。"},
    ]

    return messages


def build_section_merge_messages(
    node_id: str,
    node_title: str,
    node_description: str,
    covers_criteria: str,
    scoring_content: str,
    framework_content: str,
    gap_suggestions: str = "",
) -> List[Dict[str, str]]:
    """合并单个章节的两版内容。"""
    system_prompt = """你是标书内容合成专家。请将两版标书章节内容合并为一份完整的正文。

规则：
1. 以评分标准为导向，确保覆盖所有评分要点
2. 以质量较高的一版为底，吸收另一版的独特内容
3. 去重：同一信息只保留一份，优先保留论证更详细、有数据的版本
4. 补漏：根据缺口分析和评分标准补充缺失内容
5. 过渡：段落间自然衔接，统一语气和风格
6. 统一人称：使用"投标人"或直接陈述，不用"我们"、"我公司"
7. 不要输出标题，直接返回合并后的正文
8. 不要输出解释、标记、溯源信息
9. 禁止使用 Markdown 或 LaTeX 格式标记"""

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

    messages.append({
        "role": "user",
        "content": f"节点：{node_id} {node_title}\n描述：{node_description}\n\n请合并以上两版内容，输出完整的优化后正文。"
    })

    return messages
