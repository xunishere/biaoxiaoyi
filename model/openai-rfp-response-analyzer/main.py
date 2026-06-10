from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback
import uuid
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from openai import OpenAI
from PIL import Image
from pypdf import PdfReader


BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR.parent
ROOT_DIR = MODEL_DIR.parent
UPLOAD_DIR = BASE_DIR / "uploads"
ENV_PATH = MODEL_DIR / ".env"

sys.path.insert(0, str(MODEL_DIR))
import run_extraction_pipeline as pipeline  # noqa: E402


load_dotenv(ENV_PATH)

app = Flask(__name__)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

PIPELINE_LOCK = threading.Lock()
LAST_RUN: dict[str, Any] = {}
JOBS_LOCK = threading.Lock()
JOBS: dict[str, dict[str, Any]] = {}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".wps",
    ".rtf",
    ".txt",
    ".md",
    ".xlsx",
    ".xls",
    ".csv",
    ".json",
    *IMAGE_EXTENSIONS,
}
STRUCTURED_SCORE_EXTENSIONS = {".json"}


def now_ts() -> float:
    return round(time.time(), 3)


def update_job(job_id: str, **updates: Any) -> None:
    with JOBS_LOCK:
        job = JOBS.setdefault(job_id, {})
        job.setdefault("job_id", job_id)
        job.update(updates)
        job["updated_at"] = now_ts()


def append_job_log(job_id: str, message: str, stage: str | None = None) -> None:
    with JOBS_LOCK:
        job = JOBS.setdefault(job_id, {})
        logs = job.setdefault("logs", [])
        logs.append(
            {
                "time": time.strftime("%H:%M:%S"),
                "stage": stage or job.get("stage", ""),
                "message": message,
            }
        )
        if len(logs) > 200:
            del logs[:-200]
        if stage:
            job["stage"] = stage
        job["updated_at"] = now_ts()


def snapshot_job(job_id: str) -> dict[str, Any] | None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return None
        return json.loads(json.dumps(job, ensure_ascii=False))


def load_env_config() -> dict[str, str]:
    return {
        "api_key": os.getenv("MIMO_API_KEY", ""),
        "base_url": os.getenv("MIMO_BASE_URL", ""),
        "model": os.getenv("MIMO_MODEL", "deepseek-v4-pro"),
    }


def model_manifest() -> list[dict[str, str]]:
    mimo_model = load_env_config()["model"]
    return [
        {
            "stage": "采购评分表定位",
            "model": "Poppler(pdfinfo/pdftotext) + 规则扫描；图片直接作为评分表页",
            "input": "采购文件PDF/Word/图片等相关文档",
            "output": "评分表页码或上传图片页",
        },
        {
            "stage": "采购评分表文档提取",
            "model": "PP-StructureV3(PaddleOCR, GPU, table recognition)",
            "input": "评分表页PNG",
            "output": "带坐标的OCR文本行、表格单元格、页级Markdown/JSON",
        },
        {
            "stage": "评分单元文本规整",
            "model": mimo_model,
            "input": "PP-StructureV3输出的评分单元OCR原文",
            "output": "仅机械规整后的评分单元文本，不新增评分要求",
        },
        {
            "stage": "评分细则拆分与标注",
            "model": f"规则切分 + {mimo_model}",
            "input": "评分单元文本",
            "output": "评分细则、对象、特性、评价方法、分值、主观/客观",
        },
        {
            "stage": "投标响应片段切分",
            "model": "DOCX OOXML标题解析 / PDF文本标题规则切分 / 图片引用片段",
            "input": "投标技术文件PDF/Word/图片等相关文档",
            "output": "标题路径、正文、表格文本、图片引用、字数/段落/表格/图片统计",
        },
        {
            "stage": "采购-投标映射",
            "model": f"RAG式向量召回(cosine topK) + {mimo_model}/reranker命中判断；规则仅作boost和兜底",
            "input": "采购评分细则 + 投标响应片段",
            "output": "每条评分细则到0个或多个投标片段的映射",
        },
        {
            "stage": "响应文本特征提取",
            "model": f"规则特征 + {mimo_model}(主观项写作结构抽取)",
            "input": "映射后的投标片段",
            "output": "主观写作结构、覆盖词、执行要素、客观证据特征",
        },
        {
            "stage": "得分点/扣分点分析",
            "model": f"PaddleOCR/文本抽取 + {mimo_model}结构化 final_scores.json + 规则分析器",
            "input": "最终得分文件(JSON/PDF/Word/图片等) + 映射/特征数据",
            "output": "得分点、扣分点、改进建议结构",
        },
    ]


def safe_name(filename: str, fallback: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    stem = re.sub(r"[^A-Za-z0-9_.\-\u4e00-\u9fff]+", "_", Path(filename or fallback).stem)
    return f"{stem[:80]}{suffix or Path(fallback).suffix}"


def save_upload(field: str, fallback: str) -> Path:
    file = request.files.get(field)
    if file is None or not file.filename:
        raise ValueError(f"缺少上传文件：{field}")
    path = UPLOAD_DIR / f"{int(time.time())}_{safe_name(file.filename, fallback)}"
    file.save(path)
    return path


def save_uploads(field: str, fallback: str) -> list[Path]:
    """多文件版：从 request.files.getlist(field) 收所有上传文件，按上传顺序返回路径列表。

    至少需要 1 个文件，否则抛错。允许 0 个的请用 save_optional_uploads。
    """
    files = [f for f in request.files.getlist(field) if f and f.filename]
    if not files:
        raise ValueError(f"缺少上传文件：{field}")
    paths: list[Path] = []
    base_ts = int(time.time())
    for idx, file in enumerate(files):
        path = UPLOAD_DIR / f"{base_ts}_{idx:02d}_{safe_name(file.filename, fallback)}"
        file.save(path)
        paths.append(path)
    return paths


def save_optional_upload(field: str, fallback: str) -> Path | None:
    file = request.files.get(field)
    if file is None or not file.filename:
        return None
    path = UPLOAD_DIR / f"{int(time.time())}_{safe_name(file.filename, fallback)}"
    file.save(path)
    return path


def remove_score_outputs(include_final_scores: bool = False) -> None:
    paths = [pipeline.SCORE_POINT_ANALYSIS_JSON, pipeline.SCORE_POINT_ANALYSIS_MD]
    if include_final_scores:
        paths.append(pipeline.FINAL_SCORES_JSON)
    for path in paths:
        if path.exists():
            path.unlink()


def ensure_file_type(path: Path, allowed: set[str], label: str) -> None:
    suffix = path.suffix.lower()
    if suffix not in allowed:
        allowed_text = "、".join(sorted(allowed))
        raise ValueError(f"{label}暂只支持 {allowed_text}，当前文件为 {suffix or '无扩展名'}")


def chinese_number_to_int(text: str) -> int | None:
    text = (text or "").strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    digits = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if text == "十":
        return 10
    if "十" in text:
        left, _, right = text.partition("十")
        tens = digits.get(left, 1) if left else 1
        ones = digits.get(right, 0) if right else 0
        return tens * 10 + ones
    return digits.get(text)


def rank_from_filename(filename: str) -> int | None:
    match = re.search(r"第([0-9一二两三四五六七八九十]+)名", filename or "")
    if not match:
        return None
    return chinese_number_to_int(match.group(1))


def default_tier_features(source: str = "auto_default_not_extracted_from_final_score_file") -> dict[str, Any]:
    return {
        "is_incumbent": False,
        "same_buyer_history_count": 0,
        "similar_project_count": 0,
        "same_region": False,
        "tier_label": "T5_generic",
        "coefficient": 1.0,
        "source": source,
    }


def ocr_image_to_text(image_path: Path) -> tuple[str, list[dict[str, Any]]]:
    """用 PaddleOCR 提取最终得分图片文本，保留坐标方便后续追溯。"""
    from paddleocr import PaddleOCR

    last_error: Exception | None = None
    attempts = [
        {"device": "gpu:0"},
        {"device": "cpu", "enable_mkldnn": False},
        {"device": "cpu"},
    ]
    for kwargs in attempts:
        try:
            ocr = PaddleOCR(
                lang="ch",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                **kwargs,
            )
            result = ocr.predict(str(image_path))[0]
            texts = list(result.get("rec_texts") or [])
            boxes_raw = result.get("rec_boxes")
            boxes = list(boxes_raw) if boxes_raw is not None else []
            lines: list[dict[str, Any]] = []
            for index, text in enumerate(texts):
                clean = pipeline.normalize_text(str(text))
                if not clean:
                    continue
                box_value = boxes[index] if index < len(boxes) else None
                box = box_value.tolist() if hasattr(box_value, "tolist") else box_value
                x1 = float(box[0]) if box is not None and len(box) >= 4 else 0.0
                y1 = float(box[1]) if box is not None and len(box) >= 4 else float(index)
                lines.append({"text": clean, "box": box, "x1": x1, "y1": y1})
            lines.sort(key=lambda item: (round(item["y1"] / 12), item["x1"]))
            return "\n".join(item["text"] for item in lines), lines
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"最终得分图片OCR失败：{last_error}") from last_error


def extract_docx_text(path: Path) -> str:
    """不依赖 python-docx，直接从 OOXML 提取段落文本。"""
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(path) as zf:
        xml_text = zf.read("word/document.xml")
    root = ElementTree.fromstring(xml_text)
    lines: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        parts: list[str] = []
        for node in paragraph.iter():
            if node.tag == f"{{{namespace['w']}}}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{{{namespace['w']}}}tab":
                parts.append("\t")
        line = pipeline.normalize_text("".join(parts))
        if line:
            lines.append(line)
    return "\n".join(lines)


def extract_pdf_score_text(path: Path) -> str:
    reader = PdfReader(str(path))
    page_texts = [page.extract_text() or "" for page in reader.pages[:3]]
    text = pipeline.normalize_text("\n".join(page_texts))
    if text:
        return text

    temp_dir = pipeline.OUT_DIR / "final_scores_pdf_pages"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    page_limit = min(len(reader.pages), 3)
    subprocess.run(
        [
            "pdftoppm",
            "-f",
            "1",
            "-l",
            str(page_limit),
            "-r",
            "180",
            "-png",
            str(path),
            str(temp_dir / "page"),
        ],
        check=True,
    )
    chunks = []
    for image_path in sorted(temp_dir.glob("page-*.png")):
        chunk, _ = ocr_image_to_text(image_path)
        chunks.append(chunk)
    return pipeline.normalize_text("\n".join(chunks))


def extract_final_score_source_text(path: Path) -> tuple[str, list[dict[str, Any]]]:
    suffix = path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return ocr_image_to_text(path)
    if suffix == ".pdf":
        return extract_pdf_score_text(path), []
    if suffix == ".docx":
        return extract_docx_text(path), []
    if suffix in {".txt", ".md", ".csv", ".json"}:
        return path.read_text(encoding="utf-8", errors="ignore"), []
    return "", []


def fallback_final_scores_from_text(text: str, filename: str, source_file: str) -> dict[str, Any] | None:
    compact = pipeline.normalize_text(text)
    if not compact:
        return None

    score_match = re.search(r"得分[：:\s]*([0-9]+(?:\.[0-9]+)?)", compact)
    if score_match is None:
        score_match = re.search(r"总分[：:\s]*([0-9]+(?:\.[0-9]+)?)", compact)
    if score_match is None:
        return None
    actual_score = float(score_match.group(1))

    company_matches = re.findall(
        r"([\u4e00-\u9fffA-Za-z0-9（）()·\-]{4,80}(?:有限公司|股份有限公司|集团有限公司|公司))",
        compact,
    )
    bidder_name = company_matches[0] if company_matches else "目标投标人"

    rank = None
    rank_match = re.search(r"排名[：:\s]*第?([0-9一二两三四五六七八九十]+)名?", compact)
    if rank_match:
        rank = chinese_number_to_int(rank_match.group(1))
    if rank is None:
        rank = rank_from_filename(filename)

    return {
        "source": {
            "source_file": source_file,
            "extraction_method": "rule_fallback_from_ocr_text_v0",
            "score_level": "total",
        },
        "bidders": [
            {
                "bidder_id": "B-001",
                "name": bidder_name,
                "is_target": True,
                "rank": rank,
                "scores": [
                    {
                        "score_name": "总分",
                        "score_level": "total",
                        "actual_score": actual_score,
                        "max_score": 100,
                    }
                ],
                "tier_features": default_tier_features(),
            }
        ],
    }


def normalize_final_scores_payload(payload: dict[str, Any], source_file: str) -> dict[str, Any]:
    bidders = payload.get("bidders")
    if not isinstance(bidders, list) or not bidders:
        raise ValueError("结构化得分结果缺少 bidders")

    normalized_bidders: list[dict[str, Any]] = []
    has_target = False
    for index, bidder in enumerate(bidders, start=1):
        if not isinstance(bidder, dict):
            continue
        scores = bidder.get("scores") or []
        normalized_scores: list[dict[str, Any]] = []
        for score in scores:
            if not isinstance(score, dict):
                continue
            actual = score.get("actual_score")
            if not isinstance(actual, (int, float)):
                continue
            max_score = score.get("max_score")
            normalized_scores.append(
                {
                    "score_name": score.get("score_name") or "总分",
                    "score_level": score.get("score_level") or "total",
                    "actual_score": round(float(actual), 2),
                    "max_score": float(max_score) if isinstance(max_score, (int, float)) else 100,
                }
            )
        if not normalized_scores:
            continue
        is_target = bool(bidder.get("is_target"))
        has_target = has_target or is_target
        normalized_bidders.append(
            {
                "bidder_id": bidder.get("bidder_id") or f"B-{index:03d}",
                "name": pipeline.normalize_text(str(bidder.get("name") or f"投标人{index}")),
                "is_target": is_target,
                "rank": bidder.get("rank") if isinstance(bidder.get("rank"), int) else None,
                "scores": normalized_scores,
                "tier_features": {
                    **default_tier_features(),
                    **(bidder.get("tier_features") if isinstance(bidder.get("tier_features"), dict) else {}),
                },
            }
        )
    if not normalized_bidders:
        raise ValueError("结构化得分结果没有可用分数")
    if not has_target:
        normalized_bidders[0]["is_target"] = True

    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    source.update(
        {
            "source_file": source.get("source_file") or source_file,
            "extraction_method": source.get("extraction_method") or "mimo_from_ocr_text_v0",
        }
    )
    return {"source": source, "bidders": normalized_bidders}


def structure_final_scores_from_text(text: str, source_file: str, filename: str) -> dict[str, Any] | None:
    fallback = fallback_final_scores_from_text(text, filename, source_file)
    config = load_env_config()
    if not config["api_key"] or not config["base_url"]:
        return fallback

    prompt = (
        "你是最终评标得分文件结构化抽取器。只抽取原文或文件名明确给出的事实，"
        "不得编造细则分、不得编造其他投标人得分。\n"
        "如果文本中出现“你方得分/未能中标/排名”，该对象就是本次目标投标人 is_target=true。"
        "如果只有总分，score_level 必须为 total，max_score 默认 100。"
        "如果排名在文件名中如“第二名”，可以转成 rank=2。\n"
        "输出 JSON：{\"source\": {\"extraction_method\": \"mimo_from_ocr_text_v0\"}, "
        "\"bidders\": [{\"bidder_id\":\"B-001\",\"name\":\"...\",\"is_target\":true,"
        "\"rank\":2,\"scores\":[{\"score_name\":\"总分\",\"score_level\":\"total\","
        "\"actual_score\":73.63,\"max_score\":100}],\"tier_features\":{...}}]}"
    )
    client = OpenAI(api_key=config["api_key"], base_url=config["base_url"])
    try:
        response = client.chat.completions.create(
            model=config["model"],
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": (
                        f"文件名：{filename}\n"
                        f"源文件：{source_file}\n"
                        f"OCR/文本内容：\n{text[:8000]}"
                    ),
                },
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        parsed = pipeline.extract_json_object(response.choices[0].message.content or "")
        normalized = normalize_final_scores_payload(parsed, source_file)
        file_rank = rank_from_filename(filename)
        if file_rank is not None:
            for bidder in normalized["bidders"]:
                if bidder.get("is_target") and bidder.get("rank") is None:
                    bidder["rank"] = file_rank
        return normalized
    except Exception as exc:
        print(f"final score MiMo structuring failed, fallback to rules: {exc}")
        return fallback


def save_final_scores(uploaded_path: Path | None) -> str:
    if uploaded_path is None:
        if pipeline.FINAL_SCORES_JSON.exists():
            return "existing"
        return "missing"

    ensure_file_type(uploaded_path, DOCUMENT_EXTENSIONS, "最终得分文件")
    if uploaded_path.suffix.lower() not in STRUCTURED_SCORE_EXTENSIONS:
        pipeline.OUT_DIR.mkdir(parents=True, exist_ok=True)
        remove_score_outputs(include_final_scores=True)
        target = pipeline.OUT_DIR / f"final_scores_source{uploaded_path.suffix.lower()}"
        shutil.copyfile(uploaded_path, target)
        rel_target = str(target.relative_to(ROOT_DIR))
        extracted_text, ocr_lines = extract_final_score_source_text(target)
        structured = structure_final_scores_from_text(extracted_text, rel_target, uploaded_path.name)
        metadata = {
            "source_file": rel_target,
            "status": "uploaded_structured_from_source" if structured else "uploaded_unstructured",
            "text_char_count": len(extracted_text),
            "ocr_line_count": len(ocr_lines),
            "note": (
                "最终得分原始文件已保存，并已自动结构化为 final_scores.json。"
                if structured
                else "最终得分原始文件已保存；自动结构化失败，需要人工整理为 final_scores.json。"
            ),
        }
        if extracted_text:
            metadata["extracted_text_preview"] = extracted_text[:1000]
        if ocr_lines:
            metadata["ocr_lines"] = ocr_lines[:80]
        (pipeline.OUT_DIR / "final_scores_source.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if structured:
            pipeline.FINAL_SCORES_JSON.write_text(
                json.dumps(structured, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return "uploaded_structured_from_source"
        return "uploaded_unstructured"

    try:
        parsed = json.loads(uploaded_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"最终得分文件不是合法JSON：{exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("最终得分文件必须是JSON对象")
    if "bidders" not in parsed:
        raise ValueError("最终得分文件缺少 bidders 字段")

    pipeline.OUT_DIR.mkdir(parents=True, exist_ok=True)
    remove_score_outputs(include_final_scores=False)
    pipeline.FINAL_SCORES_JSON.write_text(
        json.dumps(parsed, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return "uploaded"


def is_image_file(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTENSIONS


def prepare_procurement_image_page(image_path: Path) -> pipeline.ScoringPageRange:
    pipeline.OUT_DIR.mkdir(parents=True, exist_ok=True)
    pipeline.PP_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    target = pipeline.PP_INPUT_DIR / "page-1.png"
    with Image.open(image_path) as image:
        image.convert("RGB").save(target)

    page_range = pipeline.ScoringPageRange(
        pdf_path=str(image_path.relative_to(ROOT_DIR)),
        page_start=1,
        page_end=1,
        page_count=1,
        pages=[
            pipeline.PageSignal(
                page=1,
                start_score=0,
                continuation_score=0,
                reasons=["uploaded_image_as_scoring_page"],
                preview=f"uploaded image: {image_path.name}",
            )
        ],
    )
    pipeline.PAGE_RANGE_JSON.write_text(
        json.dumps(page_range.to_json_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return page_range


def pdf_page_count(path: Path) -> int:
    try:
        return len(PdfReader(str(path)).pages)
    except Exception:
        return 0


def is_pdf_heading(line: str) -> bool:
    if len(line) < 3 or len(line) > 80:
        return False
    patterns = [
        r"^第[一二三四五六七八九十百\d]+[章节部分篇]\s*.+",
        r"^[一二三四五六七八九十]+[、.．]\s*.+",
        r"^\d+(?:\.\d+){0,4}[、.．]?\s+.+",
        r"^\d+[、.．]\s*.+",
    ]
    return any(re.match(pattern, line) for pattern in patterns)


def make_pdf_section(section_index: int, title: str, page: int, paragraphs: list[str]) -> dict[str, Any]:
    text = pipeline.normalize_text("\n".join(paragraphs))
    heading_path = [title or f"PDF第{page}页"]
    return {
        "section_id": f"BID-SEC-{section_index:04d}",
        "level": 1,
        "title": heading_path[-1],
        "heading_path": heading_path,
        "start_block_id": f"pdf-p{page}",
        "end_block_id": f"pdf-p{page}",
        "paragraphs": [
            {
                "block_id": f"pdf-p{page}-{idx + 1}",
                "text": paragraph,
                "style_id": None,
                "image_refs": [],
            }
            for idx, paragraph in enumerate(paragraphs)
            if paragraph
        ],
        "tables": [],
        "image_refs": [],
        "text": text,
        "text_features": {
            "char_count": len(text),
            "paragraph_count": len([p for p in paragraphs if p]),
            "table_count": 0,
            "image_count": 0,
            "content_type": "text" if text else "empty",
        },
        "candidate_score_units": [],
    }


def split_bid_pdf_to_sections(path: Path) -> list[dict[str, Any]]:
    reader = PdfReader(str(path))
    sections: list[dict[str, Any]] = []
    current_title = ""
    current_page = 1
    current_paragraphs: list[str] = []

    def flush() -> None:
        nonlocal current_title, current_page, current_paragraphs
        if not any(current_paragraphs):
            current_title = ""
            current_paragraphs = []
            return
        sections.append(
            make_pdf_section(
                len(sections) + 1,
                current_title or f"PDF第{current_page}页",
                current_page,
                current_paragraphs,
            )
        )
        current_title = ""
        current_paragraphs = []

    for page_index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        lines = [pipeline.normalize_text(line) for line in text.splitlines()]
        lines = [line for line in lines if line]
        if not lines:
            continue

        for line in lines:
            if is_pdf_heading(line):
                flush()
                current_title = line
                current_page = page_index
                continue
            if not current_title:
                current_title = f"PDF第{page_index}页"
                current_page = page_index
            current_paragraphs.append(line)
    flush()
    return sections


def split_bid_image_to_sections(path: Path) -> list[dict[str, Any]]:
    rel = str(path.relative_to(ROOT_DIR))
    return [
        {
            "section_id": "BID-SEC-0001",
            "level": 1,
            "title": f"图片响应材料：{path.name}",
            "heading_path": [f"图片响应材料：{path.name}"],
            "start_block_id": "image-1",
            "end_block_id": "image-1",
            "paragraphs": [],
            "tables": [],
            "image_refs": [rel],
            "text": "",
            "text_features": {
                "char_count": 0,
                "paragraph_count": 0,
                "table_count": 0,
                "image_count": 1,
                "content_type": "image",
            },
            "candidate_score_units": [],
        }
    ]


def output_meta(path: Path, key: str | None = None) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path.relative_to(ROOT_DIR)), "exists": False, "count": 0}
    count = 0
    if key:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            value = data.get(key, [])
            count = len(value) if isinstance(value, list) else 0
        except Exception:
            count = 0
    return {"path": str(path.relative_to(ROOT_DIR)), "exists": True, "count": count}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _process_one_procurement_file(
    proc_file: Path,
    skip_pp: bool,
    emit: Any,
) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    """跑单个采购文件，返回 (score_units, procurement_mode, page_range_meta)。"""
    if proc_file.suffix.lower() == ".pdf":
        page_range = pipeline.save_scoring_page_range(proc_file)
        procurement_mode = "pdf_rendered_to_images"
        emit("采购评分表定位", f"{proc_file.name}：检测到评分表页 {page_range.page_start}-{page_range.page_end}")
        if not skip_pp:
            emit("采购评分页渲染", f"{proc_file.name}：渲染评分表 PDF 页为 PNG")
            pipeline.render_scoring_pages(
                proc_file,
                page_range.page_start,
                page_range.page_end,
                force=True,
            )
    elif is_image_file(proc_file):
        page_range = prepare_procurement_image_page(proc_file)
        procurement_mode = "uploaded_image_direct_to_pp_structurev3"
        emit("采购评分表定位", f"{proc_file.name}：图片直接作为评分表页")
    else:
        raise ValueError(
            f"{proc_file.name}：采购评分表提取当前可直接处理 PDF 或评分表图片；"
            "Word/Excel等原始文件需要先转换成 PDF 或图片。"
        )
    scoring_pages = list(range(page_range.page_start, page_range.page_end + 1))

    if not skip_pp:
        emit("PP-StructureV3", f"{proc_file.name}：识别页 {page_range.page_start}-{page_range.page_end}")
        pipeline.run_pp_structurev3(page_range.page_start, page_range.page_end, force=True)
    else:
        emit("PP-StructureV3", f"{proc_file.name}：跳过PP，使用现有 OCR 输出")

    emit("评分单元切分", f"{proc_file.name}：按坐标聚行、切列、拼接跨页评分单元")
    units_json = pipeline.split_score_units_from_pp(scoring_pages)
    score_units = units_json.get("score_units", [])
    if proc_file.suffix.lower() == ".pdf" and len(score_units) < 6:
        emit(
            "评分单元切分",
            f"{proc_file.name}：PP几何切分仅得到 {len(score_units)} 条，尝试 PDF 文本评分表兜底切分",
        )
        fallback_units_json = pipeline.split_score_units_from_pdf_text(
            proc_file,
            page_range.page_start,
            page_range.page_end,
        )
        fallback_units = fallback_units_json.get("score_units", [])
        if len(fallback_units) > len(score_units):
            units_json = fallback_units_json
            score_units = fallback_units
            emit("评分单元切分", f"{proc_file.name}：PDF文本兜底切出 {len(score_units)} 条评分单元")
    emit("评分单元切分", f"{proc_file.name}：评分单元 {len(score_units)} 条")
    return score_units, procurement_mode, {
        "file": str(proc_file.relative_to(ROOT_DIR)),
        "page_start": page_range.page_start,
        "page_end": page_range.page_end,
        "procurement_mode": procurement_mode,
    }


def _process_one_bid_file(bid_file: Path, emit: Any) -> tuple[list[dict[str, Any]], str]:
    """跑单个投标文件，返回 (sections, bid_split_method)。"""
    if bid_file.suffix.lower() == ".docx":
        sections = pipeline.split_bid_technical_docx(bid_file)
        method = "docx_ooxml_heading_split_v0"
    elif bid_file.suffix.lower() == ".pdf":
        sections = split_bid_pdf_to_sections(bid_file)
        method = "pdf_text_heading_split_v0"
    elif is_image_file(bid_file):
        sections = split_bid_image_to_sections(bid_file)
        method = "image_reference_fragment_v0"
    else:
        raise ValueError(
            f"{bid_file.name}：投标响应片段切分当前可直接处理 DOCX、PDF 或图片；"
            "其他 Word/Excel 等格式需要先转换。"
        )
    emit("投标响应片段切分", f"{bid_file.name}：章节 {len(sections)} 条（split_method={method}）")
    return sections, method


def run_openbidkit_pipeline(
    procurement_files: list[Path] | Path,
    bid_files: list[Path] | Path,
    skip_pp: bool,
    skip_mimo: bool,
    final_scores_status: str,
    progress: Any | None = None,
) -> dict[str, Any]:
    if isinstance(procurement_files, Path):
        procurement_files = [procurement_files]
    if isinstance(bid_files, Path):
        bid_files = [bid_files]
    if not procurement_files:
        raise ValueError("至少需要 1 份采购文件")
    if not bid_files:
        raise ValueError("至少需要 1 份投标文件")

    def emit(stage: str, message: str) -> None:
        print(f"[{stage}] {message}", flush=True)
        if progress:
            progress(stage, message)

    emit("排队", "等待流水线锁，避免多个PP/MiMo任务同时抢GPU和输出文件。")
    with PIPELINE_LOCK:
        started = time.time()
        emit("采购评分表定位", f"开始处理 {len(procurement_files)} 份采购文件")

        merged_score_units: list[dict[str, Any]] = []
        procurement_modes: list[str] = []
        procurement_metas: list[dict[str, Any]] = []
        skipped_procurement_metas: list[dict[str, Any]] = []
        for proc_file in procurement_files:
            try:
                file_units, mode, meta = _process_one_procurement_file(proc_file, skip_pp, emit)
            except Exception as exc:
                reason = str(exc)
                skipped_procurement_metas.append(
                    {
                        "file": str(proc_file.relative_to(ROOT_DIR)),
                        "status": "skipped_no_scoring_table",
                        "reason": reason,
                    }
                )
                emit("采购评分表定位", f"{proc_file.name}：未作为评分表来源，原因：{reason}")
                continue

            if not file_units:
                skipped_procurement_metas.append(
                    {
                        "file": str(proc_file.relative_to(ROOT_DIR)),
                        "status": "skipped_empty_score_units",
                        "reason": "评分表页已定位但未切出评分单元",
                    }
                )
                emit("评分单元切分", f"{proc_file.name}：未切出评分单元，跳过该采购文件")
                continue

            for unit in file_units:
                unit["source_procurement_file"] = meta["file"]
                merged_score_units.append(unit)
            procurement_modes.append(mode)
            procurement_metas.append(meta)

        if not merged_score_units:
            details = "; ".join(
                f"{Path(item['file']).name}: {item['reason']}"
                for item in skipped_procurement_metas
            ) or "没有可用采购文件"
            raise RuntimeError(
                "所有采购文件都未能定位到评分表。请确认至少上传一份包含“综合评分法/评分项目/分值区间/评分办法”"
                f"的采购文件或评分表图片。详情：{details}"
            )

        # 跨文件重编号 unit_id，并落盘合并后的 score_units 草稿，给下游 MiMo/criteria 用。
        for idx, unit in enumerate(merged_score_units, start=1):
            unit["unit_id"] = f"TU-DRAFT-{idx:03d}"
        merged_units_json = {
            "source": {
                "uploaded_procurement_files": [str(path.relative_to(ROOT_DIR)) for path in procurement_files],
                "procurement_files": [meta["file"] for meta in procurement_metas],
                "skipped_procurement_files": skipped_procurement_metas,
                "method": "geometry_text_split_v0_multi_file_merged",
                "task": "multi_procurement_file_merge",
            },
            "score_units": merged_score_units,
        }
        pipeline.PROCUREMENT_UNITS_JSON.write_text(
            json.dumps(merged_units_json, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        emit("评分单元切分", f"合并后评分单元总数：{len(merged_score_units)}（{len(procurement_files)} 份文件）")

        if skip_mimo:
            score_units = merged_units_json["score_units"]
            emit("MiMo文本规整", "已跳过MiMo，评分单元使用规则切分原文。")
        else:
            emit("MiMo文本规整", f"用 MiMo 规整 {len(merged_score_units)} 条评分单元 OCR 文本")
            pipeline.refine_score_units_with_mimo(merged_units_json, force=True)
            score_units = pipeline.load_score_units_for_bid_annotation()

        emit("评分细则拆分与标注", "拆分评分细则并补全 object/feature/scoring_type")
        criteria_json = pipeline.extract_procurement_criteria(
            score_units,
            use_mimo=not skip_mimo,
            force=True,
        )
        emit("评分细则拆分与标注", f"评分细则数量：{len(criteria_json.get('criteria', []))}")

        emit("投标响应片段切分", f"开始处理 {len(bid_files)} 份投标文件")
        merged_sections: list[dict[str, Any]] = []
        bid_split_methods: list[str] = []
        for bid_file in bid_files:
            file_sections, method = _process_one_bid_file(bid_file, emit)
            for s in file_sections:
                s["source_bid_file"] = str(bid_file.relative_to(ROOT_DIR))
                merged_sections.append(s)
            bid_split_methods.append(method)

        # 跨文件重编号 section_id，避免 BID-SEC-0001 在多文件下冲突。
        for idx, s in enumerate(merged_sections, start=1):
            s["section_id"] = f"BID-SEC-{idx:04d}"
        sections = merged_sections
        bid_split_method = "+".join(sorted(set(bid_split_methods))) or "unknown"
        emit("投标响应片段切分", f"合并后投标章节总数：{len(sections)}")
        annotations = pipeline.annotate_bid_sections(sections, score_units)
        pipeline.write_bid_outputs(sections, annotations)
        fragments_json = pipeline.build_bid_response_fragments(sections, force=True)
        emit("投标响应片段切分", f"投标响应片段数量：{len(fragments_json.get('fragments', []))}")

        emit("采购-投标映射", "正在进行RAG式向量召回、规则boost和MiMo/reranker命中判断。")
        mapping_json = pipeline.map_criteria_to_bid_fragments(
            criteria_json["criteria"],
            fragments_json["fragments"],
            use_mimo=not skip_mimo,
            force=True,
        )
        linked_count = sum(1 for item in mapping_json["mappings"] if item.get("linked_bid_fragments"))
        emit("采购-投标映射", f"映射完成：{linked_count}/{len(mapping_json.get('mappings', []))} 条细则有命中片段。")

        emit("响应文本特征", "正在提取主观写作结构、客观证据字段和响应覆盖特征。")
        features_json = pipeline.extract_criterion_response_features(
            criteria_json["criteria"],
            fragments_json["fragments"],
            mapping_json["mappings"],
            use_mimo=not skip_mimo,
            force=True,
        )
        emit("响应文本特征", f"响应特征数量：{len(features_json.get('features', []))}")

        analysis_json = None
        if final_scores_status in {"uploaded", "existing", "uploaded_structured_from_source"} and pipeline.FINAL_SCORES_JSON.exists():
            emit("得扣分分析", "检测到结构化final_scores.json，正在生成得分点/扣分点。")
            final_scores = load_json(pipeline.FINAL_SCORES_JSON)
            analysis_json = pipeline.analyze_score_points(
                criteria_json["criteria"],
                mapping_json["mappings"],
                features_json["features"],
                fragments_json["fragments"],
                final_scores,
                use_mimo=not skip_mimo,
                force=True,
            )
            emit("得扣分分析", f"得扣分分析数量：{len((analysis_json or {}).get('analyses', []))}")
        else:
            remove_score_outputs(include_final_scores=False)
            emit("得扣分分析", "未检测到结构化final_scores.json，跳过得扣分分析。")

        result = {
            "message": "数据集切分、标注与映射完成",
            "elapsed_seconds": round(time.time() - started, 1),
            "inputs": {
                "uploaded_procurement_files": [str(path.relative_to(ROOT_DIR)) for path in procurement_files],
                "procurement_files": [meta["file"] for meta in procurement_metas],
                "skipped_procurement_files": skipped_procurement_metas,
                "procurement_modes": procurement_modes,
                "procurement_per_file": procurement_metas,
                "bid_files": [str(p.relative_to(ROOT_DIR)) for p in bid_files],
                "bid_split_method": bid_split_method,
            },
            "models": model_manifest(),
            "metrics": {
                "procurement_file_count": len(procurement_files),
                "procurement_scoring_file_count": len(procurement_metas),
                "procurement_skipped_count": len(skipped_procurement_metas),
                "bid_file_count": len(bid_files),
                "score_units": len(score_units),
                "criteria": len(criteria_json["criteria"]),
                "bid_sections": len(sections),
                "bid_fragments": len(fragments_json["fragments"]),
                "mappings": len(mapping_json["mappings"]),
                "criteria_with_links": linked_count,
                "features": len(features_json["features"]),
                "score_point_analysis": len((analysis_json or {}).get("analyses", [])),
                "final_scores_present": pipeline.FINAL_SCORES_JSON.exists(),
            },
            "outputs": {
                "procurement_criteria": output_meta(pipeline.PROCUREMENT_CRITERIA_JSON, "criteria"),
                "bid_fragments": output_meta(pipeline.BID_FRAGMENTS_JSON, "fragments"),
                "mapping": output_meta(pipeline.PROCUREMENT_BID_MAPPING_JSON, "mappings"),
                "features": output_meta(pipeline.CRITERION_RESPONSE_FEATURES_JSON, "features"),
                "final_scores": output_meta(pipeline.FINAL_SCORES_JSON, "bidders"),
                "score_point_analysis": output_meta(pipeline.SCORE_POINT_ANALYSIS_JSON, "analyses"),
            },
        }
        LAST_RUN.clear()
        LAST_RUN.update(result)
        emit("完成", "全部流程完成，结果已写入 model/dataset_extraction_output。")
        return result


def run_pipeline_job(
    job_id: str,
    procurement_files: list[Path] | Path,
    bid_files: list[Path] | Path,
    skip_pp: bool,
    skip_mimo: bool,
    final_scores_status: str,
) -> None:
    update_job(job_id, status="running", stage="启动", started_at=now_ts())

    def progress(stage: str, message: str) -> None:
        append_job_log(job_id, message, stage=stage)

    try:
        progress("启动", "后台任务已启动。")
        result = run_openbidkit_pipeline(
            procurement_files,
            bid_files,
            skip_pp=skip_pp,
            skip_mimo=skip_mimo,
            final_scores_status=final_scores_status,
            progress=progress,
        )
        result["inputs"]["final_scores"] = final_scores_status
        update_job(
            job_id,
            status="completed",
            stage="完成",
            result=result,
            metrics=result.get("metrics", {}),
            completed_at=now_ts(),
        )
    except Exception as exc:
        traceback.print_exc()
        append_job_log(job_id, str(exc), stage="失败")
        update_job(
            job_id,
            status="failed",
            stage="失败",
            error=str(exc),
            traceback=traceback.format_exc(),
            completed_at=now_ts(),
        )


def estimate_self_score(criterion: dict[str, Any], analysis: dict[str, Any]) -> tuple[float | None, float, str]:
    """打分来源优先级：MiMo 归因的 actual_score → 待归因/无数据。

    scope:
      - "in_scope"     : 参与汇总
      - "out_of_scope" : 报价分等不在技术响应（not_in_technical_scope）
      - "score_pending": 有映射/分析，但没有可汇总的 actual_score
      - "no_data"      : 还没分析结果
    """
    max_score = pipeline.parse_max_score(criterion.get("score_text", ""))
    if not analysis:
        return None, max_score, "no_data"

    sps = analysis.get("scoring_points") or []
    dps = analysis.get("deduction_points") or []
    linked = analysis.get("linked_fragment_ids") or []

    is_not_in_scope = any(dp.get("deduction_type") == "not_in_technical_scope" for dp in dps)
    if is_not_in_scope:
        return None, max_score, "out_of_scope"

    mimo_score = analysis.get("actual_score")
    if isinstance(mimo_score, (int, float)):
        return round(float(mimo_score), 2), max_score, "in_scope"

    if linked or sps or dps:
        return None, max_score, "score_pending"

    if not linked:
        return None, max_score, "no_data"

    return None, max_score, "no_data"


def aggregate_self_score(
    criteria: list[dict[str, Any]],
    analysis_by_cid: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """聚合所有有 actual_score 的 in_scope 细则归因估计分。"""
    in_scope_actual = 0.0
    in_scope_max = 0.0
    out_of_scope_max = 0.0
    in_scope_count = 0
    out_of_scope_count = 0
    pending_score_count = 0
    no_data_count = 0
    for crit in criteria:
        a = analysis_by_cid.get(crit["criterion_id"], {})
        score, mx, scope = estimate_self_score(crit, a)
        if scope == "in_scope":
            in_scope_actual += score or 0.0
            in_scope_max += mx
            in_scope_count += 1
        elif scope == "out_of_scope":
            out_of_scope_max += mx
            out_of_scope_count += 1
        elif scope == "score_pending":
            in_scope_max += mx
            pending_score_count += 1
        else:
            no_data_count += 1

    final_scores = load_json(pipeline.FINAL_SCORES_JSON)
    target = None
    for bidder in final_scores.get("bidders", []):
        if bidder.get("is_target"):
            target = bidder
            break

    actual_total = None
    actual_max = None
    bidder_name = None
    rank = None
    tier_label = None
    tier_coefficient = None
    if target:
        bidder_name = target.get("name")
        rank = target.get("rank")
        scores = target.get("scores") or []
        if scores:
            actual_total = scores[0].get("actual_score")
            actual_max = scores[0].get("max_score")
        tf = target.get("tier_features") or {}
        tier_label = tf.get("tier_label")
        tier_coefficient = tf.get("coefficient")

    return {
        "self_total": round(in_scope_actual, 2),
        "self_max_in_scope": round(in_scope_max, 2),
        "out_of_scope_max": round(out_of_scope_max, 2),
        "in_scope_count": in_scope_count,
        "out_of_scope_count": out_of_scope_count,
        "pending_score_count": pending_score_count,
        "no_data_count": no_data_count,
        "actual_total": actual_total,
        "actual_max": actual_max,
        "delta": (
            round(in_scope_actual - actual_total, 2)
            if isinstance(actual_total, (int, float))
            else None
        ),
        "bidder_name": bidder_name,
        "rank": rank,
        "tier_label": tier_label,
        "tier_coefficient": tier_coefficient,
    }


def build_criteria_cards_html() -> str:
    """每条评分细则一张可折叠卡片：默认只显示 ID + 得分；点击展开看详情。"""
    criteria = load_json(pipeline.PROCUREMENT_CRITERIA_JSON).get("criteria", [])
    if not criteria:
        return '<p style="color:#647084;">还没有评分细则。运行一次切分/标注/映射后会出现。</p>'

    mappings_by_cid = {m["criterion_id"]: m for m in load_json(pipeline.PROCUREMENT_BID_MAPPING_JSON).get("mappings", [])}
    features_by_cid = {f["criterion_id"]: f for f in load_json(pipeline.CRITERION_RESPONSE_FEATURES_JSON).get("features", [])}
    analysis_by_cid = {a["criterion_id"]: a for a in load_json(pipeline.SCORE_POINT_ANALYSIS_JSON).get("analyses", [])}
    fragments_by_id = {f["fragment_id"]: f for f in load_json(pipeline.BID_FRAGMENTS_JSON).get("fragments", [])}

    cards: list[str] = []
    for criterion in criteria:
        cid = criterion["criterion_id"]
        max_score = criterion.get("score_text") or "—"
        scoring_type = criterion.get("scoring_type", "—")
        unit_name = criterion.get("score_unit_name", "")
        crit_name = criterion.get("criterion_name", "")

        analysis = analysis_by_cid.get(cid) or {}
        sps = analysis.get("scoring_points") or []
        dps = analysis.get("deduction_points") or []
        keeps = analysis.get("writing_pattern_to_keep") or []
        improves = analysis.get("writing_pattern_to_improve") or []
        self_score, self_max, scope = estimate_self_score(criterion, analysis)
        if scope == "out_of_scope":
            score_label = f"超技术范围 / {max_score}"
        elif scope == "score_pending":
            score_label = f"待归因 / {max_score}"
        elif self_score is None:
            score_label = f"? / {max_score}"
        else:
            base_score = analysis.get("base_score")
            tier_coef = analysis.get("tier_coefficient")
            if (
                isinstance(base_score, (int, float))
                and isinstance(tier_coef, (int, float))
                and abs(tier_coef - 1.0) > 1e-6
            ):
                score_label = f"{base_score} × {tier_coef:.2f} = {self_score} / {max_score}"
            else:
                score_label = f"{self_score} / {max_score}"
        confidence = analysis.get("confidence") or "—"

        mapping = mappings_by_cid.get(cid) or {}
        linked = mapping.get("linked_bid_fragments") or []
        feature = features_by_cid.get(cid) or {}

        def _ul(items: list[str]) -> str:
            if not items:
                return '<p style="color:#647084;font-size:13px;margin:6px 0;">（空）</p>'
            return "<ul>" + "".join(f"<li>{html_escape(str(s))}</li>" for s in items) + "</ul>"

        def _points_block(points: list[dict[str, Any]], key_type: str) -> str:
            if not points:
                return '<p style="color:#647084;font-size:13px;margin:6px 0;">（空）</p>'
            blocks = []
            for p in points:
                ptype = p.get(key_type, "")
                name = p.get("point_name", "")
                basis = p.get("basis") or p.get("deduction_reason") or ""
                blocks.append(
                    f'<div class="point"><div class="point-head"><span class="ptype">{html_escape(str(ptype))}</span>'
                    f'<span class="pname">{html_escape(str(name))}</span></div>'
                    f'<div class="pbasis">{html_escape(str(basis))}</div></div>'
                )
            return "".join(blocks)

        if linked:
            frag_items: list[str] = []
            for link in linked:
                fid = link.get("fragment_id", "")
                hp = link.get("heading_path") or []
                evidence = link.get("evidence_text") or ""
                fragment = fragments_by_id.get(fid) or {}
                full_text = fragment.get("text") or ""
                table_text = fragment.get("table_text") or ""
                char_count = fragment.get("char_count", len(full_text) + len(table_text))
                full_html_parts: list[str] = []
                if full_text:
                    full_html_parts.append(
                        f'<div class="frag-fulltext">{html_escape(full_text)}</div>'
                    )
                if table_text:
                    full_html_parts.append(
                        f'<div class="frag-tabletext"><b>表格文本：</b><pre>{html_escape(table_text)}</pre></div>'
                    )
                if not full_html_parts:
                    full_html_parts.append(
                        '<div class="frag-empty" style="color:#647084;">（fragment 文本为空）</div>'
                    )
                full_body = "".join(full_html_parts)
                evidence_html = (
                    f'<div class="frag-evidence">证据摘录：「{html_escape(evidence)}」</div>'
                    if evidence
                    else ""
                )
                frag_items.append(
                    f"""
                    <div class="frag-card">
                      <div class="frag-head" onclick="toggleFrag(this)">
                        <span class="frag-id">{html_escape(fid)}</span>
                        <span class="frag-path">{html_escape(" / ".join(hp))}</span>
                        <span class="frag-meta">{char_count} 字</span>
                        <span class="frag-chev">▸</span>
                      </div>
                      <div class="frag-body" style="display:none;">
                        {evidence_html}
                        {full_body}
                      </div>
                    </div>
                    """
                )
            linked_block = "".join(frag_items)
        else:
            linked_block = '<p style="color:#647084;font-size:13px;margin:6px 0;">（无命中片段）</p>'

        cards.append(
            f"""
            <div class="crit-card">
              <div class="crit-head" onclick="toggleCrit(this)">
                <span class="cid">{html_escape(cid)}</span>
                <span class="cname">{html_escape(unit_name)} / {html_escape(crit_name)}</span>
                <span class="cmeta">
                  <span class="badge {scoring_type}">{html_escape(scoring_type)}</span>
                  <span class="score">{html_escape(score_label)}</span>
                  <span class="counts">SP {len(sps)} · DP {len(dps)} · 片段 {len(linked)}</span>
                  <span class="conf">{html_escape(confidence)}</span>
                </span>
                <span class="chev">▸</span>
              </div>
              <div class="crit-body" style="display:none;">
                <div class="crit-row">
                  <h4>得分点</h4>
                  {_points_block(sps, "point_type")}
                </div>
                <div class="crit-row">
                  <h4>扣分点</h4>
                  {_points_block(dps, "deduction_type")}
                </div>
                <div class="crit-row">
                  <h4>建议保留的写作模式</h4>
                  {_ul(keeps)}
                </div>
                <div class="crit-row">
                  <h4>建议改进的写作模式</h4>
                  {_ul(improves)}
                </div>
                <div class="crit-row">
                  <h4>命中的投标响应片段</h4>
                  {linked_block}
                </div>
              </div>
            </div>
            """
        )
    return "".join(cards)


def html_escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_report_html() -> str:
    criteria = load_json(pipeline.PROCUREMENT_CRITERIA_JSON).get("criteria", [])
    fragments = load_json(pipeline.BID_FRAGMENTS_JSON).get("fragments", [])
    mappings = load_json(pipeline.PROCUREMENT_BID_MAPPING_JSON).get("mappings", [])
    features = load_json(pipeline.CRITERION_RESPONSE_FEATURES_JSON).get("features", [])
    analysis = load_json(pipeline.SCORE_POINT_ANALYSIS_JSON).get("analyses", [])

    linked = sum(1 for item in mappings if item.get("linked_bid_fragments"))
    objective = sum(1 for item in criteria if item.get("scoring_type") == "objective")
    subjective = sum(1 for item in criteria if item.get("scoring_type") == "subjective")

    rows = [
        ("采购评分细则", len(criteria), f"主观 {subjective} / 客观 {objective}"),
        ("投标响应片段", len(fragments), "来自技术响应文件标题层级或PDF文本切分"),
        ("采购-投标映射", len(mappings), f"已命中 {linked} / 未命中 {len(mappings) - linked}"),
        ("响应文本特征", len(features), "主观写作结构 + 客观证据字段"),
        ("最终得分文件", output_meta(pipeline.FINAL_SCORES_JSON, "bidders")["count"], "外部评标结果/人工录入，不由模型自动生成"),
        ("得分点/扣分点分析", len(analysis), "需要 final_scores.json 约束"),
    ]

    table = "\n".join(
        f"<tr><td>{name}</td><td>{count}</td><td>{note}</td></tr>" for name, count, note in rows
    )

    analysis_by_cid = {item["criterion_id"]: item for item in analysis}
    agg = aggregate_self_score(criteria, analysis_by_cid)
    if agg["actual_total"] is None:
        compare_panel = (
            '<p style="color:#647084;">还没有 final_scores.json 中的实际总分；自评结果是 '
            f'<b>{agg["self_total"]} / {agg["self_max_in_scope"]}</b>（in_scope {agg["in_scope_count"]} 条，'
            f'待归因 {agg["pending_score_count"]} 条，out_of_scope {agg["out_of_scope_count"]} 条，'
            f'no_data {agg["no_data_count"]} 条）。</p>'
        )
    else:
        delta = agg["delta"]
        if delta is None:
            delta_label = "—"
            delta_class = ""
        elif delta > 1:
            delta_label = f"+{delta}（归因估计偏高）"
            delta_class = "delta-high"
        elif delta < -1:
            delta_label = f"{delta}（归因估计偏低）"
            delta_class = "delta-low"
        else:
            delta_label = f"{delta:+.2f}（归因估计与实际接近）"
            delta_class = "delta-ok"
        tier_info = (
            f"{html_escape(agg.get('tier_label') or '—')} × {agg.get('tier_coefficient'):.2f}"
            if isinstance(agg.get("tier_coefficient"), (int, float))
            else "—"
        )
        compare_panel = f"""
          <div class="score-compare">
            <div class="sc-tile">
              <div class="sc-label">投标人</div>
              <div class="sc-value-small">{html_escape(agg["bidder_name"] or "—")}（排名 {agg["rank"] or "—"}）</div>
              <div class="sc-note">隐形加分 tier: {tier_info}</div>
            </div>
            <div class="sc-tile">
              <div class="sc-label">模型归因估计分（已乘 tier 系数）</div>
              <div class="sc-value">{agg["self_total"]} <span class="sc-of">/ {agg["self_max_in_scope"]}</span></div>
              <div class="sc-note">已归因 {agg["in_scope_count"]} 条 · 待归因 {agg["pending_score_count"]} 条 · out_of_scope {agg["out_of_scope_count"]} 条（{agg["out_of_scope_max"]} 分超技术范围）</div>
            </div>
            <div class="sc-tile">
              <div class="sc-label">评委实际总分</div>
              <div class="sc-value">{agg["actual_total"]} <span class="sc-of">/ {agg["actual_max"]}</span></div>
              <div class="sc-note">来自 final_scores.json</div>
            </div>
            <div class="sc-tile {delta_class}">
              <div class="sc-label">归因估计 - 实际</div>
              <div class="sc-value">{delta_label}</div>
              <div class="sc-note">MiMo 归因 base × tier 系数；total-only 时不可当作真实细则分</div>
            </div>
          </div>
        """

    return f"""
    <section class="panel">
      <h2>自评 vs 实际总分对比</h2>
      {compare_panel}
    </section>
    <section class="panel">
      <h2>当前数据集结果</h2>
      <table><thead><tr><th>数据层</th><th>数量</th><th>说明</th></tr></thead><tbody>{table}</tbody></table>
    </section>
    <section class="panel">
      <h2>评分细则得分摘要（点击展开看得分点 / 扣分点 / 写作建议 / 命中片段）</h2>
      <div class="crit-list">{build_criteria_cards_html()}</div>
    </section>
    """


def chat_with_dataset(query: str) -> str:
    config = load_env_config()
    if not config["api_key"] or not config["base_url"]:
        return "当前没有配置 MiMo API，无法进行模型问答。"

    criteria = load_json(pipeline.PROCUREMENT_CRITERIA_JSON).get("criteria", [])[:12]
    mappings = load_json(pipeline.PROCUREMENT_BID_MAPPING_JSON).get("mappings", [])[:12]
    features = load_json(pipeline.CRITERION_RESPONSE_FEATURES_JSON).get("features", [])[:12]
    context = {
        "pipeline": "采购评分细则-投标响应片段-映射-响应特征-得扣分结构",
        "models": model_manifest(),
        "sample_criteria": criteria,
        "sample_mappings": mappings,
        "sample_features": features,
    }
    client = OpenAI(api_key=config["api_key"], base_url=config["base_url"])
    response = client.chat.completions.create(
        model=config["model"],
        messages=[
            {
                "role": "system",
                "content": (
                    "你是标小易项目的数据集构建助手。回答必须基于给定JSON上下文，"
                    "重点解释采购评分细则、投标响应片段、映射、主客观特征和得扣分结构。"
                    "不要把本项目说成通用RFP Analyzer。"
                ),
            },
            {
                "role": "user",
                "content": f"上下文：\n{json.dumps(context, ensure_ascii=False)[:12000]}\n\n问题：{query}",
            },
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content or ""


@app.route("/")
def index():
    return render_template("index.html", models=model_manifest(), last_run=LAST_RUN)


@app.route("/process", methods=["POST"])
def process_documents():
    try:
        procurement_files = save_uploads("procurement", "procurement.pdf")
        bid_files = save_uploads("bid", "bid.docx")
        final_scores_file = save_optional_upload("final_scores", "final_scores.json")
        for p in procurement_files:
            ensure_file_type(p, DOCUMENT_EXTENSIONS, "采购文件")
        for p in bid_files:
            ensure_file_type(p, DOCUMENT_EXTENSIONS, "投标文件")
        final_scores_status = save_final_scores(final_scores_file)

        job_id = uuid.uuid4().hex
        update_job(
            job_id,
            status="queued",
            stage="排队",
            created_at=now_ts(),
            updated_at=now_ts(),
            logs=[],
            inputs={
                "procurement_files": [str(p.relative_to(ROOT_DIR)) for p in procurement_files],
                "bid_files": [str(p.relative_to(ROOT_DIR)) for p in bid_files],
                "final_scores": final_scores_status,
            },
        )
        append_job_log(
            job_id,
            f"任务已创建：采购 {len(procurement_files)} 份、投标 {len(bid_files)} 份，等待后台执行。",
            stage="排队",
        )

        thread = threading.Thread(
            target=run_pipeline_job,
            args=(
                job_id,
                procurement_files,
                bid_files,
                request.form.get("skip_pp") == "on",
                request.form.get("skip_mimo") == "on",
                final_scores_status,
            ),
            daemon=True,
        )
        thread.start()

        return jsonify({"job_id": job_id, "status": "queued"}), 202
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


@app.route("/jobs/<job_id>")
def get_job(job_id: str):
    job = snapshot_job(job_id)
    if job is None:
        return jsonify({"error": "job not found"}), 404
    return jsonify(job)


@app.route("/process_sync", methods=["POST"])
def process_documents_sync():
    """Debug endpoint: keep the old synchronous behavior for local troubleshooting."""
    try:
        procurement_files = save_uploads("procurement", "procurement.pdf")
        bid_files = save_uploads("bid", "bid.docx")
        final_scores_file = save_optional_upload("final_scores", "final_scores.json")
        for p in procurement_files:
            ensure_file_type(p, DOCUMENT_EXTENSIONS, "采购文件")
        for p in bid_files:
            ensure_file_type(p, DOCUMENT_EXTENSIONS, "投标文件")
        final_scores_status = save_final_scores(final_scores_file)

        result = run_openbidkit_pipeline(
            procurement_files,
            bid_files,
            skip_pp=request.form.get("skip_pp") == "on",
            skip_mimo=request.form.get("skip_mimo") == "on",
            final_scores_status=final_scores_status,
        )
        result["inputs"]["final_scores"] = final_scores_status
        return jsonify(result)
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


@app.route("/generate_report", methods=["POST"])
def generate_report():
    return jsonify({"structured_report": build_report_html()})


@app.route("/chat", methods=["POST"])
def chat():
    try:
        query = (request.json or {}).get("query", "").strip()
        if not query:
            return jsonify({"error": "问题不能为空"}), 400
        return jsonify({"response": chat_with_dataset(query)})
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


@app.route("/manifest")
def manifest():
    return jsonify({"models": model_manifest(), "mimo": {k: v for k, v in load_env_config().items() if k != "api_key"}})


def local_ipv4_addresses() -> list[str]:
    addresses: list[str] = []
    seen: set[str] = set()

    def add(address: str) -> None:
        if not address or address.startswith("127.") or address in seen:
            return
        seen.add(address)
        addresses.append(address)

    try:
        host_name = socket.gethostname()
        for item in socket.getaddrinfo(host_name, None, family=socket.AF_INET):
            add(item[4][0])
    except OSError:
        pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            add(sock.getsockname()[0])
    except OSError:
        pass

    return addresses


def print_access_urls(host: str, port: int) -> None:
    print(f"Local access: http://127.0.0.1:{port}", flush=True)
    if host in {"0.0.0.0", "::"}:
        addresses = local_ipv4_addresses()
        for address in addresses:
            print(f"LAN access:   http://{address}:{port}", flush=True)
        if not addresses:
            print("LAN access:   use this machine's IPv4 address and ensure firewall allows the port.", flush=True)


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5001))
    print_access_urls(host, port)
    app.run(host=host, port=port, debug=False, threaded=True, use_reloader=False)
