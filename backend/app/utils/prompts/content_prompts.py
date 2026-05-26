"""正文生成相关提示词。"""

import re
from typing import Any, Dict, List


def build_chapter_content_messages(
    chapter: Dict[str, Any],
    parent_chapters: List[Dict[str, Any]] | None = None,
    sibling_chapters: List[Dict[str, Any]] | None = None,
    project_overview: str = "",
    scoring_context: str = "",
    framework_context: str = "",
    target_words: int | None = None,
) -> List[Dict[str, str]]:
    """构建章节正文生成消息。"""
    chapter_id = chapter.get("id", "unknown")
    chapter_title = chapter.get("title", "未命名章节")
    chapter_description = chapter.get("description", "")

    system_prompt = f"""你是一个专业的标书编写专家，负责为投标文件的技术标部分生成具体内容。

核心规则（违反将导致废标）：
1. 严禁出现任何第三方公司名称、产品品牌、具体型号。设备一律使用通用名称。甲方名称从项目概述中提取，我方统一使用"上海荟宸信息科技有限公司"。
2. 严禁使用任何表格格式（|...|）。所有内容用段落文字表达，需要列举时用"一、二、三"或"第一、第二"。
3. 不要使用任何Markdown格式标记（**、*、#、|等），直接返回纯文本段落。

写作要求：
4. 内容要专业、准确，与章节标题和描述保持一致。
5. 语言要正式、规范，标书语气，朴实无华。
6. 内容要详细具体，避免空泛的描述。
7. 注意避免与同级章节内容重复。"""

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

    if project_overview.strip():
        # 提取甲方名称
        client_match = re.search(r'采购[单单位位人][：:]\s*([^\n]+)', project_overview)
        client_name = client_match.group(1).strip() if client_match else '采购人'
        messages.append(
            {"role": "user", "content": f"项目概述信息（甲方：{client_name}）：\n{project_overview}"}
        )

    if scoring_context and scoring_context.strip():
        messages.append(
            {"role": "user", "content": f"评分标准（你的内容必须针对以下评分标准展开）：\n{scoring_context}"}
        )

    if framework_context and framework_context.strip():
        messages.append(
            {"role": "user", "content": f"本章节在招标文件框架中的位置：\n{framework_context}"}
        )

    if parent_chapters:
        parent_lines = ["上级章节信息："]
        for parent in parent_chapters:
            parent_lines.append(
                f"- {parent.get('id', 'unknown')} {parent.get('title', '未命名章节')}\n  {parent.get('description', '')}"
            )
        messages.append({"role": "user", "content": "\n".join(parent_lines)})

    if sibling_chapters:
        sibling_lines = ["同级章节信息（请避免内容重复）："]
        for sibling in sibling_chapters:
            if sibling.get("id") == chapter_id:
                continue
            sibling_lines.append(
                f"- {sibling.get('id', 'unknown')} {sibling.get('title', '未命名章节')}\n  {sibling.get('description', '')}"
            )
        if len(sibling_lines) > 1:
            messages.append({"role": "user", "content": "\n".join(sibling_lines)})

    word_count_note = ""
    if target_words and target_words > 0:
        word_count_note = f"篇幅要求：本章不少于{target_words}字。请据此展开论述，确保内容详实充实。\n"

    messages.append(
        {
            "role": "user",
            "content": f"""请为以下标书章节生成具体内容：

当前章节信息：
章节ID: {chapter_id}
章节标题: {chapter_title}
章节描述: {chapter_description}

{word_count_note}
请根据项目概述信息和上述章节层级关系，生成详细的专业内容。确保与上级章节的内容逻辑相承，同时避免与同级章节内容重复，突出本章节的独特性和技术方案优势。
直接返回编写的正文内容，不要输出标题、解释、总结等任何其他内容""",
        }
    )

    return messages
