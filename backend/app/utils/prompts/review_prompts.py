"""审查、评分、优化相关提示词。"""

from typing import Dict, List


def build_gap_analysis_messages(
    document_content: str,
    scoring_criteria: str,
) -> List[Dict[str, str]]:
    """构建缺口分析消息。"""
    system_prompt = """你是一个严格的招标文件审查专家。请对照评分标准，逐条检查投标文件正文，找出所有问题。

问题分类：
1. 遗漏：评分标准要求的条目在投标文件中完全没有涉及
2. 缺陷：提到了但论述明显错误或不合理
3. 不足：涉及了但深度不够，论述过于简略
4. 缺少量化数据：涉及了但没有给出具体的指标、数据、参数
5. 无佐证：声称了能力和经验但没有提供任何证明材料引用

同时检查：
- 是否存在与项目无关的通用套话
- 是否存在明显的事实错误或逻辑矛盾
- 是否存在明显的抄袭痕迹（多处完全相同的论述）

返回 JSON 格式：
{
  "gaps": [
    {
      "criteria_name": "评分项名称",
      "issue_type": "遗漏|缺陷|不足|缺少量化数据|无佐证",
      "description": "具体问题描述",
      "suggestion": "改进建议"
    }
  ],
  "quality_issues": ["无关内容问题1", "错误信息问题2"],
  "summary": "总体评价（2-3句话）"
}

只返回 JSON，不要任何其他内容。"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"评分标准原文：\n{scoring_criteria}"},
        {"role": "user", "content": f"投标文件正文（全文）：\n{document_content}"},
        {
            "role": "user",
            "content": "请逐条对照评分标准，找出所有遗漏、缺陷、不足、缺少量化数据、无佐证的问题，同时检查无关内容和错误信息。",
        },
    ]


def build_scoring_table_messages(
    document_content: str,
    scoring_criteria: str,
) -> List[Dict[str, str]]:
    """构建评分表生成消息。"""
    system_prompt = """你是一个公正的招标评审专家。请对照评分标准，逐条对投标文件正文进行客观评分。

评分原则：
1. 严格参照评分标准中的分值分配
2. 每项给出简短的打分理由（不超过20字）
3. 缺失的项得0分
4. 返回 JSON，不要输出任何其他内容

JSON 格式：{"scores":[{"criteria_name":"","max_score":0,"scored":0,"reasoning":""}],"total":0,"max_total":100,"summary":""}"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"评分标准原文：\n{scoring_criteria}"},
        {"role": "user", "content": f"投标文件正文（全文）：\n{document_content}"},
        {
            "role": "user",
            "content": "请对照评分标准对投标文件进行逐项打分，严格按评分标准的分值分配。每个评分项的理由控制在20字以内。",
        },
    ]


def build_optimize_chapter_messages(
    chapter_id: str,
    chapter_title: str,
    current_content: str,
    scoring_criteria: str,
    gap_suggestions: str,
    reference_docs: str | None = None,
) -> List[Dict[str, str]]:
    """构建章节优化消息。"""
    system_prompt = """你是一个专业的标书优化专家。请根据评分标准和缺口分析建议，对现有标书章节内容进行优化改写。

优化原则：
1. 如果提供了参考技术方案，学习其写作风格、技术深度和论证方式，但不要直接抄
2. 针对缺口分析中提出的问题逐一改进
3. 补充量化数据、具体指标、实施方案细节
4. 引用可验证的证据来源（如有）
5. 保持专业、朴实的标书语气，避免宣传腔
6. 直接返回优化后的完整章节正文，不要输出标题、解释、总结等任何其他内容
7. 不要使用"我们"、"我公司"等第一人称，使用"投标人"或直接陈述"""

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

    if scoring_criteria.strip():
        messages.append(
            {"role": "user", "content": f"相关评分标准：\n{scoring_criteria[:5000]}"}
        )

    if gap_suggestions.strip():
        messages.append(
            {"role": "user", "content": f"缺口分析与改进建议：\n{gap_suggestions[:3000]}"}
        )

    if reference_docs and reference_docs.strip() and len(reference_docs.strip()) > 10:
        messages.append(
            {
                "role": "user",
                "content": f"参考技术方案（学习其专业性和论证深度）：\n{reference_docs[:5000]}",
            }
        )

    messages.append(
        {
            "role": "user",
            "content": f"待优化章节：{chapter_id} {chapter_title}\n\n当前内容：\n{current_content[:8000]}\n\n请按照优化原则改写本章节，直接返回完整的优化后正文。",
        }
    )

    return messages
