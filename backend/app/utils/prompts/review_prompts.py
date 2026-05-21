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


def build_cross_duplicate_messages(
    chapter_previews: list[dict],
) -> List[Dict[str, str]]:
    """构建章节间交叉查重消息。"""
    preview_text = "\n".join(
        f"[{p['id']}] {p['title']}: {p['preview'][:100]}"
        for p in chapter_previews
    )

    system_prompt = """你是标书内容审查专家。请检查各章节之间是否存在明显的重复内容。

规则：
1. 比较不同章节的标题和内容预览，找出论述相同或高度相似的章节对
2. 同一评分项在不同章节中被完全相同的方式讨论 → 重复
3. 只报告明显重复（两章写的基本一样），不报告正常的内容呼应
4. 返回 JSON，不要任何其他内容

JSON 格式：
{
  "duplicates": [
    "第X章「xxx」与第Y章「yyy」关于zzz的论述重复"
  ]
}"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"各章节标题与内容摘要：\n{preview_text}"},
        {"role": "user", "content": "请检查哪些章节之间存在重复内容。"},
    ]


def build_scoring_table_messages(
    document_content: str,
    scoring_criteria: str,
    chapter_summaries: str = "",
) -> List[Dict[str, str]]:
    """构建评分表生成消息。"""
    system_prompt = """你是一个公正且严格的招标评审专家。请对照评分标准，逐条对投标文件正文进行客观评分。

关键要求——必须拆分评分项：
评分标准中列出的每一项独立需求（如"1.服务时效、2.驻场服务、3.日常巡检..."等），即使原文没有给每一项单独标注分值，你也必须将每一项拆分为独立的评分项。例如原文"服务技术方案共36分，包含14项要求"，你必须输出14个评分项，每项合理分配分值（如36÷14≈2.5分/项），不得合并为一个36分大项。

评审纪律（必须严格遵守）：
1. 下面提供了每个章节的"标题 | 开头120字"内容指纹。评分时先看内容指纹，确认该章正文真的在讨论标题所说的内容
2. 如果内容指纹显示文不对题（例如"巡检频率规划 | 开头: 投标文件需加盖公章..."），该评分项直接0分，理由写"内容与标题不符"
3. 标题覆盖 ≠ 内容覆盖，不要把"有章节"等同于"有有效内容"
4. 缺失得0分，内容错误或完全无关也得0分

评分原则：
1. 扫描评分标准中所有编号列表、要点、需求项，逐一作为独立评分项
2. 合理分配每项分值，总和等于原文总分
3. 逐项打分前先用内容指纹确认内容切题
4. 完全响应且内容正确详实→满分，提及但肤浅→半分，缺失或文不对题→0分
5. 每项给出简短理由（不超过20字）
6. 返回 JSON，不要输出任何其他内容

JSON 格式：{"scores":[{"criteria_name":"","max_score":0,"scored":0,"reasoning":""}],"total":0,"max_total":100,"summary":""}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"评分标准原文：\n{scoring_criteria}"},
    ]
    if chapter_summaries:
        messages.append({
            "role": "user",
            "content": f"各章节内容指纹（标题 | 开头120字），评分前先核对内容是否切题：\n{chapter_summaries}",
        })
    messages.extend([
        {"role": "user", "content": f"投标文件正文（全文）：\n{document_content}"},
        {
            "role": "user",
            "content": "请对照评分标准进行逐项打分。先用内容指纹确认每章内容切题，文不对题的直接0分。理由控制在20字以内。",
        },
    ])
    return messages


def build_per_chapter_eval_messages(
    chapter_id: str,
    chapter_title: str,
    chapter_content: str,
    scoring_criteria: str,
) -> List[Dict[str, str]]:
    """构建单章评分消息：只评这一章，没法偷懒。"""
    system_prompt = """你是标书评审专家。请对以下单个章节进行严格评估。

评估维度：
1. 内容切题：章节内容是否真的在讨论标题所说的话题
2. 覆盖评分：该章节响应了评分标准中的哪些需求项
3. 内容质量：论述是否详实、正确，有无明显错误

评分规则：
- 内容与标题完全无关 → relevance: false, quality: 0
- 内容切题但肤浅 → quality: 1-3
- 内容正确但缺乏量化/细节 → quality: 4-6
- 内容详实、有量化数据、可实施 → quality: 7-10

返回 JSON：
{
  "relevance": true,
  "criteria_matched": ["日常巡检"],
  "quality": 0,
  "issues": ["内容文不对题：标题是巡检频率，正文写的是公章盖章"]
}
只返回 JSON，不要任何其他内容。"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"评分标准：\n{scoring_criteria[:3000]}"},
        {"role": "user", "content": f"待评章节：[{chapter_id}] {chapter_title}\n\n正文：\n{chapter_content[:3000]}"},
        {"role": "user", "content": "请严格评估这一章，确认标题与内容一致后再打分。"},
    ]


def build_aggregate_scores_messages(
    chapter_evaluations: str,
    scoring_criteria: str,
) -> List[Dict[str, str]]:
    """构建评分汇总消息：将所有章节评估汇总为最终评分表。"""
    system_prompt = """你是标书评审组长。请根据每个章节的评估结果，对照评分标准，生成最终评分表。

汇总规则：
1. 从评分标准中提取所有评分项，按标准原文的总分分配每项分值
2. 查看每个评分项相关的章节评估结果
3. 如果某个评分项下有章节被标记为 relevance=false 或 quality=0，该评分项必须大幅扣分
4. 如果某个评分项下所有章节都 quality>=7，给满分
5. max_total 必须等于评分标准原文中声明的技术部分总分

返回 JSON：
{"scores":[{"criteria_name":"","max_score":0,"scored":0,"reasoning":""}],"total":0,"max_total":0,"summary":""}
只返回 JSON。"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"评分标准：\n{scoring_criteria}"},
        {"role": "user", "content": f"各章节评估结果：\n{chapter_evaluations}"},
        {"role": "user", "content": "请汇总所有章节评估，生成最终评分表。被标记为不切题的章节对应的评分项必须扣分。"},
    ]


def build_scoring_table_with_gaps_messages(
    document_content: str,
    scoring_criteria: str,
    gap_analysis_json: str,
    chapter_summaries: str = "",
) -> List[Dict[str, str]]:
    """构建评分表生成消息（附带缺口分析结果，强制交叉验证）。"""
    system_prompt = """你是一个公正且严格的招标评审专家。请对照评分标准和已有的缺口分析结果，逐条对投标文件正文进行客观评分。

关键要求——必须拆分评分项：
评分标准中列出的每一项独立需求，你必须将每一项拆分为独立的评分项，合理分配分值，不得合并为一个大项。

交叉验证规则（必须严格遵守）：
1. 下面提供了缺口分析的结果，其中标注了具体的缺陷、遗漏、不足等问题
2. 对于缺口分析中标记为"缺陷"的项——内容文不对题或完全错误——该评分项最多得半分
3. 对于缺口分析中标记为"遗漏"的项——完全没有涉及——该评分项得0分
4. 对于缺口分析中标记为"不足"的项——深度不够——该评分项酌情扣分（不超过满分的60%）
5. 不要忽视缺口分析的结果。如果缺口分析和你的判断有冲突，以缺口分析为准

评分原则：
1. 扫描评分标准中所有编号列表、要点、需求项，逐一作为独立评分项
2. 合理分配每项分值，总和等于原文总分
3. 对照缺口分析结果确定每项的得分上限，再结合正文内容评分
4. 每项给出简短理由，如果扣分了要提到对应的缺口分析发现
5. 返回 JSON，不要输出任何其他内容

JSON 格式：{"scores":[{"criteria_name":"","max_score":0,"scored":0,"reasoning":""}],"total":0,"max_total":100,"summary":""}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"评分标准原文：\n{scoring_criteria}"},
        {"role": "user", "content": f"缺口分析结果（评分时必须参考，缺陷项扣分，遗漏项0分）：\n{gap_analysis_json}"},
    ]
    if chapter_summaries:
        messages.append({
            "role": "user",
            "content": f"各章节内容指纹（标题 | 开头120字）：\n{chapter_summaries}",
        })
    messages.extend([
        {"role": "user", "content": f"投标文件正文（全文）：\n{document_content}"},
        {
            "role": "user",
            "content": "请对照评分标准和缺口分析进行逐项打分。缺口分析发现的缺陷必须体现在评分上。理由控制在20字以内。",
        },
    ])
    return messages


def build_optimize_chapter_messages(
    chapter_id: str,
    chapter_title: str,
    current_content: str,
    scoring_criteria: str,
    gap_suggestions: str,
    sibling_summaries: str | None = None,
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
7. 不要使用"我们"、"我公司"等第一人称，使用"投标人"或直接陈述
8. 如果提供了同级章节摘要，确保优化后的内容不与它们重复，突出本章独特性"""

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

    if scoring_criteria.strip():
        messages.append(
            {"role": "user", "content": f"相关评分标准：\n{scoring_criteria[:5000]}"}
        )

    if gap_suggestions.strip():
        messages.append(
            {"role": "user", "content": f"缺口分析与改进建议：\n{gap_suggestions[:3000]}"}
        )

    if sibling_summaries and sibling_summaries.strip():
        messages.append(
            {
                "role": "user",
                "content": f"同级章节摘要（请避免内容重复，每个章节都应有独特侧重点）：\n{sibling_summaries[:4000]}",
            }
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
