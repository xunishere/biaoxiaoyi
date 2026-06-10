"""End-to-end dataset extraction pipeline.

This is the only maintained script under model/:
1. Locate the procurement scoring table in the full PDF.
2. Run PP-StructureV3 on the detected scoring pages.
3. Split scoring-table OCR lines into procurement score units.
4. Optionally normalize score-unit OCR text with MiMo.
5. Split the bid technical DOCX into indexed sections and annotate candidate
   links to procurement score units.

The pipeline extracts and labels data only. It does not estimate scores.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
import os
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None  # type: ignore[assignment]

try:
    import msvcrt
except ImportError:  # POSIX
    msvcrt = None  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "model"
DATA_DIR = MODEL_DIR / "AI测试数据-闵行区绿化市容生活垃圾分类智慧收运系统建设项目2026-4-13"
PROCUREMENT_PDF = DATA_DIR / "闵行区绿化市容生活垃圾分类智慧收运系统建设项目.pdf"
BID_DOCX = DATA_DIR / "投标标书-闵行区绿化市容生活垃圾分类智慧收运系统建设项目（260410）.docx"
ENV_PATH = MODEL_DIR / ".env"

PP_INPUT_DIR = MODEL_DIR / "pp_structurev3_input" / "procurement_scoring_pages"
PP_OUTPUT_DIR = MODEL_DIR / "pp_structurev3_output" / "procurement_scoring_pages_with_table"
OUT_DIR = MODEL_DIR / "dataset_extraction_output"

PAGE_RANGE_JSON = OUT_DIR / "procurement_scoring_page_range.json"
PROCUREMENT_LINES_JSON = OUT_DIR / "procurement_scoring_lines.json"
PROCUREMENT_UNITS_JSON = OUT_DIR / "procurement_score_units_draft.json"
PROCUREMENT_UNITS_MD = OUT_DIR / "procurement_score_units_draft.md"
PROCUREMENT_UNITS_MIMO_JSON = OUT_DIR / "procurement_score_units_mimo_refined.json"
PROCUREMENT_UNITS_MIMO_MD = OUT_DIR / "procurement_score_units_mimo_refined.md"
BID_SECTIONS_JSON = OUT_DIR / "bid_technical_sections.json"
BID_SECTIONS_MD = OUT_DIR / "bid_technical_sections.md"
BID_ANNOTATIONS_JSON = OUT_DIR / "bid_score_unit_annotations.json"
BID_ANNOTATIONS_MD = OUT_DIR / "bid_score_unit_annotations.md"
PROCUREMENT_CRITERIA_JSON = OUT_DIR / "procurement_scoring_criteria.json"
PROCUREMENT_CRITERIA_MD = OUT_DIR / "procurement_scoring_criteria.md"
BID_FRAGMENTS_JSON = OUT_DIR / "bid_response_fragments.json"
BID_FRAGMENTS_MD = OUT_DIR / "bid_response_fragments.md"
PROCUREMENT_BID_MAPPING_JSON = OUT_DIR / "procurement_bid_mapping.json"
PROCUREMENT_BID_MAPPING_MD = OUT_DIR / "procurement_bid_mapping.md"
CRITERION_RESPONSE_FEATURES_JSON = OUT_DIR / "criterion_response_features.json"
CRITERION_RESPONSE_FEATURES_MD = OUT_DIR / "criterion_response_features.md"
FINAL_SCORES_JSON = OUT_DIR / "final_scores.json"
SCORE_POINT_ANALYSIS_JSON = OUT_DIR / "score_point_analysis.json"
SCORE_POINT_ANALYSIS_MD = OUT_DIR / "score_point_analysis.md"

RENDER_DPI = 180
MAX_FRAGMENT_CHARS = 1500
FRAGMENT_OVERLAP_CHARS = 150
MAPPING_CANDIDATE_LIMIT_MIMO = 30
MAPPING_CANDIDATE_LIMIT_RULE_ONLY = 18
MAPPING_STRUCTURAL_LINK_LIMIT = 18
MAPPING_CANDIDATE_EXCERPT_LIMIT_MIMO = 900
MAPPING_CANDIDATE_EXCERPT_LIMIT_RULE = 1200
SCORE_RANGE_PAGE_RE = re.compile(r"(?<!\d)\d{1,3}(?:\.\d+)?\s*[~～\-—至]\s*\d{1,3}(?:\.\d+)?(?!\d)")
SCORE_RANGE_CELL_RE = re.compile(r"^\s*\d+(?:\.\d+)?\s*[~～\-—至]\s*\d+(?:\.\d+)?\s*$")
SCORE_RANGE_INLINE_RE = re.compile(r"(?<!\d)(\d+(?:\.\d+)?\s*[~～\-—至]\s*\d+(?:\.\d+)?)(?!\d)")
SCORE_RANGE_WITH_TYPE_RE = re.compile(
    r"0\s*[~～\-—至]\s*\d+(?:\.\d+)?\s*(?:主观分|客观分)"
)
SCORING_ROW_COMPACT_RE = re.compile(
    r"(?<!\d)\d{1,2}[\u4e00-\u9fffA-Za-z（）()、]{2,40}"
    r"0[~～\-—至]\d+(?:\.\d+)?(?:主观分|客观分)"
)
TEXT_SCORE_UNIT_ROW_RE = re.compile(
    r"(?<!\d)(?P<num>\d{1,2})\s*"
    r"(?P<name>[\u4e00-\u9fffA-Za-z（）()、]{2,30}?)\s*"
    r"(?P<range>0\s*[~～\-—至]\s*\d+(?:\.\d+)?)\s*"
    r"(?P<score_type>主观分|客观分)"
)
PAREN_SCORE_RE = re.compile(r"[（(]\s*\d+(?:\.\d+)?\s*分\s*[)）]")
NOISE_RE = re.compile(r"^[A-Za-z0-9]$")
CHAPTER_RE = re.compile(r"第[一二三四五六七八九十]+章\s+\S+")
HEADER_TEXTS = {"评分项目", "分值区间", "分值", "评分办法", "主/客观分", "主客观分", "评分要点及说明"}
OBJECTIVE_KEYWORDS = [
    "报价",
    "公式",
    "评标基准价",
    "合同",
    "扫描件",
    "每份",
    "证书",
    "人数",
    "不少于",
    "项目负责人",
    "技术负责人",
    "社保",
    "职称",
    "信息系统项目管理师",
    "系统集成项目管理师",
    "高级工程师",
    "盖章页",
    "签订日期",
    "服务期限",
]
PROJECT_SCENE_TERMS = [
    "闵行区",
    "绿化市容",
    "生活垃圾",
    "垃圾分类",
    "智慧收运",
    "一网统管",
    "街镇",
    "作业单位",
    "产生单位",
    "环卫",
    "清运",
    "政务云",
    "大数据中心",
    "区城运平台",
]

XML_NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "v": "urn:schemas-microsoft-com:vml",
}
W = f"{{{XML_NS['w']}}}"
R = f"{{{XML_NS['r']}}}"


@dataclass
class PageSignal:
    page: int
    start_score: int
    continuation_score: int
    reasons: list[str]
    preview: str


@dataclass
class ScoringPageRange:
    pdf_path: str
    page_start: int
    page_end: int
    page_count: int
    pages: list[PageSignal]

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Line:
    line_id: str
    page: int
    text: str
    box: list[float]
    source: str

    @property
    def x1(self) -> float:
        return float(self.box[0])

    @property
    def y1(self) -> float:
        return float(self.box[1])

    @property
    def x2(self) -> float:
        return float(self.box[2])

    @property
    def y2(self) -> float:
        return float(self.box[3])

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2


@dataclass
class PagePayload:
    page: int
    lines: list[Line]
    table_bbox: list[float] | None


@dataclass
class ScoreUnitDraft:
    unit_name: str
    score_range_text: str
    page_start: int
    page_end: int
    source_line_ids: list[str] = field(default_factory=list)
    raw_parts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    last_y: float = 0

    def add_line(self, line: Line) -> None:
        self.page_end = max(self.page_end, line.page)
        self.source_line_ids.append(line.line_id)
        self.raw_parts.append(line.text)
        self.last_y = max(self.last_y, line.cy)

    def to_dict(self, index: int) -> dict[str, Any]:
        return {
            "unit_id": f"TU-DRAFT-{index:03d}",
            "unit_name": normalize_text(self.unit_name),
            "score_range_text": self.score_range_text,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "raw_text": normalize_text(" ".join(self.raw_parts)),
            "source_line_ids": self.source_line_ids,
            "warnings": self.warnings,
        }


@dataclass
class DocxBlock:
    block_id: str
    block_type: str
    text: str
    style_id: str | None = None
    heading_level: int | None = None
    rows: list[list[str]] | None = None
    image_refs: list[str] = field(default_factory=list)


def relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def normalize_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", normalized)


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def preview_text(text: str, max_len: int = 160) -> str:
    return re.sub(r"\s+", " ", text).strip()[:max_len]


def run_text_command(args: list[str]) -> str:
    completed = subprocess.run(
        args,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get_page_count(pdf_path: Path) -> int:
    output = run_text_command(["pdfinfo", str(pdf_path)])
    for line in output.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())
    raise RuntimeError(f"Unable to read page count from {pdf_path}")


def extract_page_text(pdf_path: Path, page: int) -> str:
    return run_text_command(
        [
            "pdftotext",
            "-layout",
            "-f",
            str(page),
            "-l",
            str(page),
            str(pdf_path),
            "-",
        ]
    )


def score_start_page(text: str) -> tuple[int, list[str]]:
    normalized = compact_text(text)
    reasons: list[str] = []
    score = 0
    range_count = len(SCORE_RANGE_PAGE_RE.findall(text))

    if "综合评分法" in normalized:
        score += 4
        reasons.append("has_综合评分法")
    if "评分规则" in normalized:
        score += 3
        reasons.append("has_评分规则")
    if "投标评分细则" in normalized:
        score += 6
        reasons.append("has_投标评分细则")
    if "评分细则" in normalized and "具体评分细则" in normalized:
        score += 4
        reasons.append("has_具体评分细则")
    if all(term in normalized for term in ("评分项目", "分值区间", "评分办法")):
        score += 6
        reasons.append("has_table_headers")
    if "评分项目" in normalized and "分值" in normalized and (
        "主/客观分" in normalized or "主客观分" in normalized
    ) and ("评分要点" in normalized or "评分要点及说明" in normalized):
        score += 8
        reasons.append("has_score_item_value_subjective_objective_headers")
    if "客观分" in normalized and "主观分" in normalized:
        score += 2
        reasons.append("has_subjective_objective_terms")
    if range_count:
        score += min(range_count, 4)
        reasons.append(f"score_range_count={range_count}")
    if "报价得分" in normalized:
        score += 2
        reasons.append("has_报价得分")
    if "一、评审内容" in normalized and ("二、评审标准" in normalized or "二、评分标准" in normalized):
        score += 2
        reasons.append("has_review_content_and_standard")

    return score, reasons


def score_continuation_page(text: str) -> tuple[int, list[str]]:
    normalized = compact_text(text)
    reasons: list[str] = []
    score = 0
    range_count = len(SCORE_RANGE_PAGE_RE.findall(text))

    if range_count:
        score += min(range_count * 2, 6)
        reasons.append(f"score_range_count={range_count}")
    if "评分项目" in normalized and "分值" in normalized and (
        "主/客观分" in normalized or "主客观分" in normalized
    ):
        score += 4
        reasons.append("has_scoring_table_headers")
    if "主观分" in normalized or "客观分" in normalized:
        score += 1
        reasons.append("has_subjective_or_objective_score_type")
    if "一、评审内容" in normalized:
        score += 2
        reasons.append("has_review_content")
    if "二、评审标准" in normalized or "二、评分标准" in normalized:
        score += 2
        reasons.append("has_review_standard")
    if "小项" in normalized:
        score += 1
        reasons.append("has_sub_item")
    if "不得分" in normalized:
        score += 1
        reasons.append("has_zero_score_rule")
    if "得" in normalized and "分" in normalized:
        score += 1
        reasons.append("has_score_text")
    if any(term in normalized for term in ("报价得分", "需求理解", "实施方案", "培训方案", "类似项目")):
        score += 1
        reasons.append("has_known_scoring_item")

    return score, reasons


def is_new_non_scoring_chapter(text: str) -> bool:
    normalized = compact_text(text)
    return bool(CHAPTER_RE.search(text)) and "评分" not in normalized and "评标" not in normalized


def locate_scoring_pages(pdf_path: Path) -> ScoringPageRange:
    page_count = get_page_count(pdf_path)
    page_texts = {page: extract_page_text(pdf_path, page) for page in range(1, page_count + 1)}

    signals: list[PageSignal] = []
    start_page = 0
    best_score = -1

    for page, text in page_texts.items():
        start_score, start_reasons = score_start_page(text)
        cont_score, cont_reasons = score_continuation_page(text)
        reasons = [f"start:{reason}" for reason in start_reasons]
        reasons.extend(f"cont:{reason}" for reason in cont_reasons)
        signals.append(
            PageSignal(
                page=page,
                start_score=start_score,
                continuation_score=cont_score,
                reasons=reasons,
                preview=preview_text(text),
            )
        )
        if start_score > best_score:
            best_score = start_score
            start_page = page

    if not start_page or best_score < 10:
        raise RuntimeError("Unable to locate scoring table start page")

    end_page = start_page
    for page in range(start_page + 1, page_count + 1):
        text = page_texts[page]
        cont_score, _ = score_continuation_page(text)
        if cont_score >= 4:
            end_page = page
            continue
        if is_new_non_scoring_chapter(text):
            break
        break

    return ScoringPageRange(
        pdf_path=relative_path(pdf_path),
        page_start=start_page,
        page_end=end_page,
        page_count=page_count,
        pages=signals,
    )


def save_scoring_page_range(pdf_path: Path) -> ScoringPageRange:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    result = locate_scoring_pages(pdf_path)
    PAGE_RANGE_JSON.write_text(
        json.dumps(result.to_json_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def render_scoring_pages(
    pdf_path: Path,
    page_start: int,
    page_end: int,
    force: bool = False,
) -> None:
    PP_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    expected = [PP_INPUT_DIR / f"page-{page}.png" for page in range(page_start, page_end + 1)]
    if not force and all(path.exists() for path in expected):
        return

    if force:
        for path in PP_INPUT_DIR.glob("page-*.png"):
            path.unlink()

    subprocess.run(
        [
            "pdftoppm",
            "-f",
            str(page_start),
            "-l",
            str(page_end),
            "-r",
            str(RENDER_DPI),
            "-png",
            str(pdf_path),
            str(PP_INPUT_DIR / "page"),
        ],
        check=True,
    )


def run_pp_structurev3(page_start: int, page_end: int, force: bool = False) -> None:
    PP_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    expected_outputs = [
        (PP_OUTPUT_DIR / f"page-{page}_res.json", PP_OUTPUT_DIR / f"page-{page}.md")
        for page in range(page_start, page_end + 1)
    ]
    if not force and all(json_path.exists() and md_path.exists() for json_path, md_path in expected_outputs):
        print(f"skip PP-StructureV3: outputs exist for pages {page_start}-{page_end}")
        return

    from paddleocr import PPStructureV3

    pipeline = PPStructureV3(
        device="gpu:0",
        use_table_recognition=True,
        use_seal_recognition=False,
        use_formula_recognition=False,
        use_chart_recognition=False,
        use_region_detection=True,
    )

    for page in range(page_start, page_end + 1):
        image_path = PP_INPUT_DIR / f"page-{page}.png"
        json_path = PP_OUTPUT_DIR / f"page-{page}_res.json"
        md_path = PP_OUTPUT_DIR / f"page-{page}.md"
        if not force and json_path.exists() and md_path.exists():
            print(f"skip page {page}: outputs exist")
            continue

        start = time.time()
        print(f"run page {page}: {image_path}")
        for res in pipeline.predict(input=str(image_path)):
            res.save_to_json(save_path=str(PP_OUTPUT_DIR))
            res.save_to_markdown(save_path=str(PP_OUTPUT_DIR))
        print(f"done page {page}: {time.time() - start:.1f}s")


def box_from_any(value: Any) -> list[float] | None:
    if value is None:
        return None
    if isinstance(value, list) and len(value) == 4 and all(isinstance(x, (int, float)) for x in value):
        return [float(x) for x in value]
    if isinstance(value, list) and len(value) == 4 and all(isinstance(x, list) for x in value):
        xs = [float(point[0]) for point in value]
        ys = [float(point[1]) for point in value]
        return [min(xs), min(ys), max(xs), max(ys)]
    return None


def get_table_bbox(data: dict[str, Any]) -> list[float] | None:
    candidates: list[list[float]] = []
    for block in data.get("parsing_res_list") or []:
        if block.get("block_label") == "table":
            box = box_from_any(block.get("block_bbox"))
            if box:
                candidates.append(box)
    for box_item in (data.get("layout_det_res") or {}).get("boxes") or []:
        if box_item.get("label") == "table":
            box = box_from_any(box_item.get("coordinate"))
            if box:
                candidates.append(box)
    if not candidates:
        return None
    return max(candidates, key=lambda box: (box[2] - box[0]) * (box[3] - box[1]))


def load_page_payload(page: int) -> PagePayload:
    data = json.loads((PP_OUTPUT_DIR / f"page-{page}_res.json").read_text(encoding="utf-8"))
    lines: list[Line] = []
    table_bbox = get_table_bbox(data)

    table_results = data.get("table_res_list") or []
    for table_idx, table in enumerate(table_results, start=1):
        ocr = table.get("table_ocr_pred") or {}
        texts = ocr.get("rec_texts") or []
        boxes = ocr.get("rec_boxes") or ocr.get("rec_polys") or []
        for idx, text in enumerate(texts):
            clean = normalize_text(str(text))
            if not clean:
                continue
            box = box_from_any(boxes[idx] if idx < len(boxes) else None)
            if box is None:
                continue
            lines.append(Line(f"p{page}-t{table_idx}-l{idx + 1}", page, clean, box, "table_ocr_pred"))

    if lines:
        return PagePayload(page, sorted(lines, key=lambda item: (item.y1, item.x1)), table_bbox)

    ocr = data.get("overall_ocr_res") or {}
    texts = ocr.get("rec_texts") or []
    boxes = ocr.get("rec_boxes") or ocr.get("rec_polys") or []
    for idx, text in enumerate(texts):
        clean = normalize_text(str(text))
        if not clean:
            continue
        box = box_from_any(boxes[idx] if idx < len(boxes) else None)
        if box is None:
            continue
        lines.append(Line(f"p{page}-o-l{idx + 1}", page, clean, box, "overall_ocr_res"))
    return PagePayload(page, sorted(lines, key=lambda item: (item.y1, item.x1)), table_bbox)


def infer_column_boundaries(lines: list[Line], table_bbox: list[float] | None = None) -> tuple[float, float]:
    header_centers: dict[str, float] = {}
    for line in lines:
        if line.text in HEADER_TEXTS:
            header_centers[line.text] = line.cx
    score_type_header = header_centers.get("主/客观分", header_centers.get("主客观分"))
    if "评分项目" in header_centers and "分值" in header_centers and score_type_header is not None:
        left_mid = (header_centers["评分项目"] + header_centers["分值"]) / 2
        right_mid = (header_centers["分值"] + score_type_header) / 2
        return left_mid, right_mid
    if {"评分项目", "分值区间", "评分办法"}.issubset(header_centers):
        left_mid = (header_centers["评分项目"] + header_centers["分值区间"]) / 2
        right_mid = (header_centers["分值区间"] + header_centers["评分办法"]) / 2
        return left_mid, right_mid
    if table_bbox is not None:
        x1, _, x2, _ = table_bbox
        width = x2 - x1
        return x1 + width * 0.34, x1 + width * 0.66
    xs = sorted(line.cx for line in lines)
    if not xs:
        return 0, 0
    width = xs[-1] - xs[0]
    return xs[0] + width * 0.34, xs[0] + width * 0.66


def line_column(line: Line, left_mid: float, right_mid: float) -> str:
    if line.cx < left_mid:
        return "item"
    if line.cx < right_mid:
        return "range"
    return "method"


def grouped_rows(lines: list[Line]) -> list[list[Line]]:
    rows: dict[int, list[Line]] = {}
    for line in lines:
        rows.setdefault(int(round(line.cy / 18.0)), []).append(line)
    return [sorted(row, key=lambda item: item.x1) for _, row in sorted(rows.items())]


def is_probable_unit_name(text: str) -> bool:
    if text in HEADER_TEXTS:
        return False
    if SCORE_RANGE_CELL_RE.match(text):
        return False
    if NOISE_RE.match(text):
        return False
    if text.startswith(("一、", "二、", "三、", "1、", "2、", "3、", "4、", "5、")):
        return False
    if PAREN_SCORE_RE.search(text):
        return False
    return 2 <= len(text) <= 40


def clean_unit_name_text(text: str) -> str:
    return normalize_text(re.sub(r"^\s*\d+[、.．]?\s*", "", text))


def extract_score_range_text(text: str) -> str:
    clean = normalize_text(text)
    if SCORE_RANGE_CELL_RE.match(clean):
        return clean
    match = SCORE_RANGE_INLINE_RE.search(clean)
    return normalize_text(match.group(1)) if match else ""


def process_scoring_row(
    row: list[Line],
    left_mid: float,
    right_mid: float,
    units: list[ScoreUnitDraft],
    current: ScoreUnitDraft | None,
    pending_name: Line | None,
) -> tuple[ScoreUnitDraft | None, Line | None]:
    if not row:
        return current, pending_name

    by_col: dict[str, list[Line]] = {"item": [], "range": [], "method": []}
    for line in row:
        if line.text in HEADER_TEXTS:
            continue
        if NOISE_RE.match(line.text):
            if current:
                current.warnings.append(f"ignored_noise:{line.line_id}:{line.text}")
            continue
        by_col[line_column(line, left_mid, right_mid)].append(line)

    item_text = normalize_text(" ".join(line.text for line in by_col["item"]))
    unit_name_text = clean_unit_name_text(item_text)
    range_text = normalize_text(" ".join(line.text for line in by_col["range"]))
    score_range_text = extract_score_range_text(range_text)
    method_lines = by_col["method"]

    if item_text and is_probable_unit_name(unit_name_text) and score_range_text:
        current = ScoreUnitDraft(unit_name_text, score_range_text, row[0].page, row[0].page)
        for line in sorted(by_col["item"] + by_col["range"] + method_lines, key=lambda item: item.x1):
            current.add_line(line)
        units.append(current)
        return current, None

    if current and item_text == "容" and current.unit_name.endswith("内"):
        current.unit_name += item_text
        for line in sorted(by_col["item"] + method_lines, key=lambda item: item.x1):
            current.add_line(line)
        return current, None

    if item_text and len(item_text) == 1 and not range_text:
        if current:
            for line in by_col["item"]:
                current.warnings.append(f"ignored_single_char_item:{line.line_id}:{line.text}")
            for line in method_lines:
                current.add_line(line)
        return current, pending_name

    if item_text and is_probable_unit_name(unit_name_text) and not range_text and not method_lines:
        return current, by_col["item"][0]

    if pending_name and score_range_text:
        current = ScoreUnitDraft(clean_unit_name_text(pending_name.text), score_range_text, pending_name.page, row[0].page)
        current.add_line(pending_name)
        for line in sorted(by_col["range"] + method_lines, key=lambda item: item.x1):
            current.add_line(line)
        units.append(current)
        return current, None

    if current is None:
        return current, pending_name

    for line in sorted(by_col["item"] + by_col["range"] + method_lines, key=lambda item: (item.x1, item.y1)):
        current.add_line(line)
    return current, pending_name


def split_score_units_from_pp(scoring_pages: list[int]) -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pages = [load_page_payload(page) for page in scoring_pages]

    units: list[ScoreUnitDraft] = []
    current: ScoreUnitDraft | None = None
    pending_name: Line | None = None
    for payload in pages:
        if not payload.lines:
            continue
        left_mid, right_mid = infer_column_boundaries(payload.lines, payload.table_bbox)
        for row in grouped_rows(payload.lines):
            current, pending_name = process_scoring_row(
                row, left_mid, right_mid, units, current, pending_name
            )

    all_lines = [line for page in pages for line in page.lines]
    lines_json = [
        {
            "line_id": line.line_id,
            "page": line.page,
            "text": line.text,
            "box": line.box,
            "source": line.source,
        }
        for line in all_lines
    ]
    units_json = {
        "source": {
            "pp_structurev3_dir": relative_path(PP_OUTPUT_DIR),
            "pages": [scoring_pages[0], scoring_pages[-1]],
            "page_list": scoring_pages,
            "page_range_source": relative_path(PAGE_RANGE_JSON),
            "method": "geometry_text_split_v0",
        },
        "score_units": [unit.to_dict(index) for index, unit in enumerate(units, start=1)],
    }

    PROCUREMENT_LINES_JSON.write_text(json.dumps(lines_json, ensure_ascii=False, indent=2), encoding="utf-8")
    PROCUREMENT_UNITS_JSON.write_text(json.dumps(units_json, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = ["# 采购评分单元文本切分草稿", ""]
    for unit in units_json["score_units"]:
        md_lines.append(f"## {unit['unit_id']} {unit['unit_name']} {unit['score_range_text']}")
        md_lines.append("")
        md_lines.append(unit["raw_text"])
        if unit["warnings"]:
            md_lines.append("")
            md_lines.append(f"warnings: {unit['warnings']}")
        md_lines.append("")
    PROCUREMENT_UNITS_MD.write_text("\n".join(md_lines).strip() + "\n", encoding="utf-8")

    print(f"procurement score units: lines={len(all_lines)} units={len(units)}")
    return units_json


def split_score_units_from_pdf_text(pdf_path: Path, page_start: int, page_end: int) -> dict[str, Any]:
    """Fallback for text PDFs whose scoring table has reliable text but weak table geometry.

    Typical header: 评分项目 / 分值 / 主客观分 / 评分要点及说明.
    It keeps raw text only; semantic criterion splitting is still done downstream.
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    page_texts = [extract_page_text(pdf_path, page) for page in range(page_start, page_end + 1)]
    raw_text = normalize_text("\n".join(page_texts))
    matches = list(TEXT_SCORE_UNIT_ROW_RE.finditer(raw_text))
    score_units: list[dict[str, Any]] = []
    for index, match in enumerate(matches, start=1):
        next_start = matches[index].start() if index < len(matches) else len(raw_text)
        segment = normalize_text(raw_text[match.start() : next_start])
        score_units.append(
            {
                "unit_id": f"TU-DRAFT-{index:03d}",
                "unit_name": clean_unit_name_text(match.group("name")),
                "score_range_text": normalize_text(match.group("range")),
                "page_start": page_start,
                "page_end": page_end,
                "raw_text": segment,
                "source_line_ids": [],
                "warnings": ["from_pdf_text_scoring_table_fallback"],
                "score_type_hint": match.group("score_type"),
            }
        )

    result = {
        "source": {
            "pdf_path": relative_path(pdf_path),
            "page_start": page_start,
            "page_end": page_end,
            "method": "pdf_text_scoring_table_row_regex_v0",
            "task": "score_unit_text_fallback",
        },
        "score_units": score_units,
    }
    print(
        f"pdf text score units fallback: pages={page_start}-{page_end} units={len(score_units)}"
    )
    return result


def get_mimo_config() -> dict[str, str] | None:
    file_values = load_env_file(ENV_PATH)
    config = {
        "api_key": os.environ.get("MIMO_API_KEY") or file_values.get("MIMO_API_KEY", ""),
        "base_url": os.environ.get("MIMO_BASE_URL") or file_values.get("MIMO_BASE_URL", ""),
        "model": os.environ.get("MIMO_MODEL") or file_values.get("MIMO_MODEL", "deepseek-v4-pro"),
    }
    if not config["api_key"] or not config["base_url"]:
        return None
    return config


def extract_json_object(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end >= start:
        stripped = stripped[start : end + 1]
    return json.loads(stripped)


def openai_compatible_chat(
    config: dict[str, str],
    messages: list[dict[str, str]],
    max_tokens: int = 1800,
    response_format: bool = True,
    timeout_seconds: int = 60,
) -> str:
    url = config["base_url"].rstrip("/") + "/chat/completions"
    payload: dict[str, Any] = {
        "model": config["model"],
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    if response_format:
        payload["response_format"] = {"type": "json_object"}

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if response_format and exc.code in {400, 422}:
            return openai_compatible_chat(
                config,
                messages,
                max_tokens=max_tokens,
                response_format=False,
                timeout_seconds=timeout_seconds,
            )
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"MiMo request failed: HTTP {exc.code}: {detail}") from exc

    return body["choices"][0]["message"].get("content") or ""


def build_mimo_messages(unit: dict[str, Any]) -> list[dict[str, str]]:
    source = {
        "unit_id": unit["unit_id"],
        "unit_name": unit["unit_name"],
        "score_range_text": unit["score_range_text"],
        "page_start": unit["page_start"],
        "page_end": unit["page_end"],
        "raw_text": unit["raw_text"],
        "source_line_ids": unit["source_line_ids"],
        "warnings": unit.get("warnings", []),
    }
    return [
        {
            "role": "system",
            "content": (
                "你是采购文件OCR文本规整器。你的任务只限于机械整理文本："
                "修复OCR断行、中文词中间空格、明显的跨行断词、标点统一、"
                "在“一、评审内容”“二、评分标准”等处补充段落换行。"
                "不得解释评分规则，不得新增采购文件没有的信息，不得改写含义，"
                "不得判断主观/客观，不得评分。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请基于下面JSON规整一个评分单元文本。只输出JSON对象，不要输出解释。\n"
                "输出格式：\n"
                "{\n"
                '  "unit_id": "...",\n'
                '  "unit_name": "...",\n'
                '  "score_range_text": "...",\n'
                '  "normalized_text": "规整后的原文",\n'
                '  "uncertain_points": ["无法确定或疑似OCR错误的位置"]\n'
                "}\n\n"
                "硬性要求：\n"
                "1. unit_id/unit_name/score_range_text 必须沿用输入，不得改名。\n"
                "2. normalized_text 只能来自 raw_text 的内容，不得补充新规则。\n"
                "3. 如果发现疑似噪声，如“广”“c”，可以删除，但必须写入 uncertain_points。\n"
                "4. 如果无法确定是否应该合并，只保守保留原文并写入 uncertain_points。\n\n"
                f"输入JSON：\n{json.dumps(source, ensure_ascii=False, indent=2)}"
            ),
        },
    ]


def refine_score_units_with_mimo(units_json: dict[str, Any], force: bool = False) -> dict[str, Any] | None:
    config = get_mimo_config()
    if config is None:
        print("skip MiMo refinement: missing MIMO_API_KEY or MIMO_BASE_URL")
        return None
    if PROCUREMENT_UNITS_MIMO_JSON.exists() and not force:
        print(f"skip MiMo refinement: output exists {PROCUREMENT_UNITS_MIMO_JSON}")
        return json.loads(PROCUREMENT_UNITS_MIMO_JSON.read_text(encoding="utf-8"))

    refined_units: list[dict[str, Any]] = []
    for index, unit in enumerate(units_json["score_units"], start=1):
        print(f"[{index}/{len(units_json['score_units'])}] refine {unit['unit_id']} {unit['unit_name']}")
        content = openai_compatible_chat(config, build_mimo_messages(unit))
        parsed = extract_json_object(content)
        refined_units.append(
            {
                "unit_id": unit["unit_id"],
                "unit_name": unit["unit_name"],
                "score_range_text": unit["score_range_text"],
                "score_type_hint": unit.get("score_type_hint"),
                "page_start": unit["page_start"],
                "page_end": unit["page_end"],
                "source_line_ids": unit["source_line_ids"],
                "warnings": unit.get("warnings", []),
                "raw_text": unit["raw_text"],
                "normalized_text": parsed.get("normalized_text", ""),
                "uncertain_points": parsed.get("uncertain_points", []),
            }
        )

    result = {
        "source": units_json.get("source", {}),
        "refiner": {"model": config["model"], "task": "mechanical_text_normalization_only"},
        "score_units": refined_units,
    }
    PROCUREMENT_UNITS_MIMO_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = ["# MiMo评分单元文本规整结果", ""]
    for unit in refined_units:
        md_lines.append(f"## {unit['unit_id']} {unit['unit_name']} {unit['score_range_text']}")
        md_lines.append("")
        md_lines.append(unit["normalized_text"] or unit["raw_text"])
        if unit["uncertain_points"]:
            md_lines.append("")
            md_lines.append("uncertain_points:")
            for point in unit["uncertain_points"]:
                md_lines.append(f"- {point}")
        md_lines.append("")
    PROCUREMENT_UNITS_MIMO_MD.write_text("\n".join(md_lines).strip() + "\n", encoding="utf-8")
    return result


def score_unit_text(unit: dict[str, Any]) -> str:
    return unit.get("normalized_text") or unit.get("raw_text") or ""


def score_unit_index(unit_id: str) -> int:
    match = re.search(r"(\d+)$", unit_id)
    return int(match.group(1)) if match else 0


def max_score_text(score_range_text: str) -> str:
    matches = re.findall(r"\d+(?:\.\d+)?", score_range_text)
    if not matches:
        return ""
    value = matches[-1]
    return f"{value}分"


def split_review_content(text: str) -> tuple[str, str]:
    normalized = normalize_text(text)
    content_match = re.search(
        r"一、评审内容[:：]?(.*?)(?:二、(?:评审标准|评分标准)[:：]?)",
        normalized,
    )
    standard_match = re.search(r"二、(?:评审标准|评分标准)[:：]?(.*)$", normalized)
    content = content_match.group(1).strip() if content_match else normalized
    standard = standard_match.group(1).strip() if standard_match else normalized
    return content, standard


def parse_scored_items(review_content: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    pattern = re.compile(
        r"(?P<num>\d+)[、.．]\s*(?P<body>.*?[（(]\s*(?P<score>\d+(?:\.\d+)?)\s*分\s*[)）])"
        r"\s*[；;。]?"
    )
    for match in pattern.finditer(review_content):
        body = normalize_text(match.group("body"))
        score = match.group("score")
        criterion_name = re.sub(r"[（(]\s*\d+(?:\.\d+)?\s*分\s*[)）]", "", body).strip(" ；;。")
        if not criterion_name:
            continue
        items.append(
            {
                "item_no": match.group("num"),
                "criterion_name": criterion_name,
                "score_text": f"{score}分",
                "raw_text": body,
            }
        )
    return items


def infer_object_feature(criterion_name: str) -> tuple[str, str]:
    cleaned = criterion_name.strip(" ；;。")
    if "的" in cleaned:
        obj, feature = cleaned.rsplit("的", 1)
        return obj.strip(), feature.strip() or "响应情况"
    if "情况" in cleaned:
        return cleaned.replace("情况", "").strip() or cleaned, "情况"
    if any(term in cleaned for term in ("方案", "计划", "措施", "能力", "经验")):
        return cleaned, "响应内容"
    return cleaned, "响应情况"


def keyword_objective_hit(unit: dict[str, Any], criterion_name: str, raw_text: str) -> bool:
    text = compact_text(" ".join([unit.get("unit_name", ""), criterion_name, raw_text, score_unit_text(unit)]))
    return any(term in text for term in OBJECTIVE_KEYWORDS)


def scoring_type_from_procurement_table(unit: dict[str, Any]) -> str | None:
    hint = normalize_text(str(unit.get("score_type_hint") or ""))
    if hint == "主观分":
        return "subjective"
    if hint == "客观分":
        return "objective"
    text = compact_text(" ".join([unit.get("raw_text", ""), unit.get("normalized_text", "")]))
    # The source scoring table label is authoritative; it appears immediately after the score range.
    if re.search(r"0\s*[~～\-—至]\s*\d+(?:\.\d+)?\s*主观分", text):
        return "subjective"
    if re.search(r"0\s*[~～\-—至]\s*\d+(?:\.\d+)?\s*客观分", text):
        return "objective"
    return None


def build_rule_based_criteria(score_units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    criteria: list[dict[str, Any]] = []
    for unit in score_units:
        unit_no = score_unit_index(unit["unit_id"])
        unit_text = score_unit_text(unit)
        source_scoring_type = scoring_type_from_procurement_table(unit)
        review_content, review_standard = split_review_content(unit_text)
        scored_items = parse_scored_items(review_content)
        if not scored_items:
            scored_items = [
                {
                    "item_no": "01",
                    "criterion_name": unit["unit_name"],
                    "score_text": max_score_text(unit.get("score_range_text", "")),
                    "raw_text": unit_text,
                }
            ]

        for item_index, item in enumerate(scored_items, start=1):
            criterion_name = normalize_text(item["criterion_name"])
            obj, feature = infer_object_feature(criterion_name)
            raw_text = normalize_text(item["raw_text"])
            if review_standard and review_standard != raw_text:
                raw_text = normalize_text(f"{raw_text}\n二、评分标准：{review_standard}")
            objective_hit = keyword_objective_hit(unit, criterion_name, raw_text)
            scoring_type = source_scoring_type or ("objective" if objective_hit else "subjective")
            criteria.append(
                {
                    "criterion_id": f"PC-{unit_no:03d}-{item_index:02d}",
                    "score_unit_id": unit["unit_id"],
                    "score_unit_name": unit["unit_name"],
                    "criterion_name": criterion_name,
                    "object": obj,
                    "feature": feature,
                    "evaluation_method": f"该细则最高{item['score_text']}，按采购文件评分标准判断",
                    "score_text": item["score_text"],
                    "scoring_type": scoring_type,
                    "raw_text": raw_text,
                    "source": {
                        "score_unit_page_start": unit.get("page_start"),
                        "score_unit_page_end": unit.get("page_end"),
                        "extraction_method": "rule_split_v0",
                        "scoring_type_source": (
                            "procurement_table_label"
                            if source_scoring_type
                            else "keyword_objective" if objective_hit else "needs_model_review"
                        ),
                    },
                }
            )
    return criteria


def build_criteria_refine_messages(criteria: list[dict[str, Any]]) -> list[dict[str, str]]:
    slim_criteria = [
        {
            "criterion_id": item["criterion_id"],
            "score_unit_name": item["score_unit_name"],
            "criterion_name": item["criterion_name"],
            "object": item["object"],
            "feature": item["feature"],
            "evaluation_method": item["evaluation_method"],
            "score_text": item["score_text"],
            "scoring_type": item["scoring_type"],
            "raw_text": item["raw_text"],
        }
        for item in criteria
    ]
    objective_keywords_hint = "、".join(OBJECTIVE_KEYWORDS)
    return [
        {
            "role": "system",
            "content": (
                "你是采购评分细则结构补全器。只能根据输入raw_text补全或修正字段："
                "object、feature、evaluation_method、scoring_type。"
                "不得新增采购文件没有的评分要求，不得改criterion_id，不得改criterion_name，"
                "不得改score_text。scoring_type只能是subjective或objective。\n"
                f"判定scoring_type时优先参考已知客观特征关键词：{objective_keywords_hint}。"
                "出现这些关键词或同义概念（证件资质、合同份数、人数门槛、固定公式、扫描件、社保职称等）一般为objective；"
                "涉及理解程度、合理性、方案完整度、措施有效性、契合度等评估则为subjective。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请输出JSON对象，格式为："
                "{\"criteria\":[{\"criterion_id\":\"...\",\"object\":\"...\",\"feature\":\"...\","
                "\"evaluation_method\":\"...\",\"scoring_type\":\"subjective|objective\"}]}。\n"
                "输入criteria：\n"
                f"{json.dumps(slim_criteria, ensure_ascii=False, indent=2)}"
            ),
        },
    ]


def refine_criteria_with_mimo(criteria: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    config = get_mimo_config()
    if config is None:
        return criteria, "rule_split_v0"
    updates: dict[str, dict[str, Any]] = {}
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in criteria:
        groups.setdefault(item["score_unit_id"], []).append(item)

    for index, group in enumerate(groups.values(), start=1):
        print(f"[criteria {index}/{len(groups)}] refine {group[0]['score_unit_name']} items={len(group)}")
        try:
            content = openai_compatible_chat(
                config,
                build_criteria_refine_messages(group),
                max_tokens=3000,
                timeout_seconds=45,
            )
            parsed = extract_json_object(content)
        except Exception as exc:
            print(f"criteria MiMo refinement failed for {group[0]['score_unit_name']}: {exc}")
            continue
        for item in parsed.get("criteria", []):
            if isinstance(item, dict) and item.get("criterion_id"):
                updates[item["criterion_id"]] = item

    if not updates:
        return criteria, "rule_split_v0_mimo_failed"

    refined: list[dict[str, Any]] = []
    for item in criteria:
        update = updates.get(item["criterion_id"], {})
        merged = dict(item)
        for key in ("object", "feature", "evaluation_method"):
            value = update.get(key)
            if isinstance(value, str) and value.strip():
                merged[key] = normalize_text(value)

        merged["source"] = dict(merged.get("source", {}))
        scoring_type_source = merged["source"].get("scoring_type_source", "")
        if scoring_type_source == "needs_model_review":
            value = update.get("scoring_type")
            if isinstance(value, str) and value.strip() in {"subjective", "objective"}:
                merged["scoring_type"] = normalize_text(value)
                merged["source"]["scoring_type_source"] = "model_review"

        if merged["scoring_type"] not in {"subjective", "objective"}:
            merged["scoring_type"] = item["scoring_type"]
        merged["source"]["structure_refiner"] = config["model"]
        refined.append(merged)
    return refined, "rule_split_v0_mimo_structured"


def extract_procurement_criteria(
    score_units: list[dict[str, Any]],
    use_mimo: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    if PROCUREMENT_CRITERIA_JSON.exists() and not force:
        print(f"skip procurement criteria: output exists {PROCUREMENT_CRITERIA_JSON}")
        return json.loads(PROCUREMENT_CRITERIA_JSON.read_text(encoding="utf-8"))

    criteria = build_rule_based_criteria(score_units)
    method = "rule_split_v0"
    if use_mimo:
        criteria, method = refine_criteria_with_mimo(criteria)

    result = {
        "source": {
            "procurement_score_units": relative_path(
                PROCUREMENT_UNITS_MIMO_JSON if PROCUREMENT_UNITS_MIMO_JSON.exists() else PROCUREMENT_UNITS_JSON
            ),
            "method": method,
            "task": "criteria_extraction_without_scoring",
        },
        "criteria": criteria,
    }
    PROCUREMENT_CRITERIA_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = ["# 采购评分细则数据集", ""]
    for item in criteria:
        md_lines.append(
            f"## {item['criterion_id']} {item['score_unit_name']} / {item['criterion_name']} / {item['score_text']}"
        )
        md_lines.append("")
        md_lines.append(
            f"type={item['scoring_type']} object={item['object']} feature={item['feature']}"
        )
        md_lines.append("")
        md_lines.append(item["evaluation_method"])
        md_lines.append("")
    PROCUREMENT_CRITERIA_MD.write_text("\n".join(md_lines).strip() + "\n", encoding="utf-8")
    print(f"procurement criteria: criteria={len(criteria)} method={method}")
    return result


def xml_attr(element: ET.Element, namespace: str, name: str) -> str | None:
    return element.attrib.get(f"{{{XML_NS[namespace]}}}{name}")


def load_style_levels(zip_file: zipfile.ZipFile) -> dict[str, int]:
    levels: dict[str, int] = {}
    if "word/styles.xml" not in zip_file.namelist():
        return levels
    root = ET.fromstring(zip_file.read("word/styles.xml"))
    for style in root.findall(".//w:style", XML_NS):
        style_id = xml_attr(style, "w", "styleId")
        if not style_id:
            continue
        name_node = style.find("w:name", XML_NS)
        name = xml_attr(name_node, "w", "val") if name_node is not None else ""
        outline = style.find(".//w:outlineLvl", XML_NS)
        if outline is not None:
            value = xml_attr(outline, "w", "val")
            if value is not None and value.isdigit():
                levels[style_id] = int(value) + 1
                continue
        match = re.fullmatch(r"heading\s+([1-9])", (name or "").lower())
        if match:
            levels[style_id] = int(match.group(1))
    return levels


def paragraph_text(paragraph: ET.Element) -> str:
    text_parts: list[str] = []
    for node in paragraph.iter():
        if node.tag == W + "t" and node.text:
            text_parts.append(node.text)
        elif node.tag == W + "tab":
            text_parts.append("\t")
        elif node.tag == W + "br":
            text_parts.append("\n")
    return normalize_text("".join(text_parts))


def paragraph_style_id(paragraph: ET.Element) -> str | None:
    p_style = paragraph.find("w:pPr/w:pStyle", XML_NS)
    return xml_attr(p_style, "w", "val") if p_style is not None else None


def paragraph_image_refs(paragraph: ET.Element) -> list[str]:
    refs: list[str] = []
    for blip in paragraph.findall(".//a:blip", XML_NS):
        embed = xml_attr(blip, "r", "embed")
        if embed:
            refs.append(embed)
    for image_data in paragraph.findall(".//v:imagedata", XML_NS):
        rel_id = xml_attr(image_data, "r", "id")
        if rel_id:
            refs.append(rel_id)
    return refs


def cell_text(cell: ET.Element) -> str:
    paragraphs = [paragraph_text(p) for p in cell.findall(".//w:p", XML_NS)]
    return normalize_text(" ".join(text for text in paragraphs if text))


def table_rows(table: ET.Element) -> list[list[str]]:
    rows: list[list[str]] = []
    for tr in table.findall("w:tr", XML_NS):
        row: list[str] = []
        for tc in tr.findall("w:tc", XML_NS):
            row.append(cell_text(tc))
        if any(cell for cell in row):
            rows.append(row)
    return rows


def table_to_text(rows: list[list[str]], max_rows: int = 80) -> str:
    lines: list[str] = []
    for row in rows[:max_rows]:
        lines.append(" | ".join(cell for cell in row))
    if len(rows) > max_rows:
        lines.append(f"... ({len(rows) - max_rows} rows omitted)")
    return "\n".join(lines)


def iter_docx_blocks(docx_path: Path) -> list[DocxBlock]:
    blocks: list[DocxBlock] = []
    with zipfile.ZipFile(docx_path) as zip_file:
        style_levels = load_style_levels(zip_file)
        root = ET.fromstring(zip_file.read("word/document.xml"))
        body = root.find("w:body", XML_NS)
        if body is None:
            return blocks

        paragraph_index = 0
        table_index = 0
        for child in body:
            if child.tag == W + "p":
                paragraph_index += 1
                text = paragraph_text(child)
                refs = paragraph_image_refs(child)
                style_id = paragraph_style_id(child)
                heading_level = style_levels.get(style_id or "")
                if not text and not refs:
                    continue
                blocks.append(
                    DocxBlock(
                        block_id=f"p{paragraph_index}",
                        block_type="paragraph",
                        text=text,
                        style_id=style_id,
                        heading_level=heading_level,
                        image_refs=refs,
                    )
                )
            elif child.tag == W + "tbl":
                table_index += 1
                rows = table_rows(child)
                if not rows:
                    continue
                blocks.append(
                    DocxBlock(
                        block_id=f"tbl{table_index}",
                        block_type="table",
                        text=table_to_text(rows),
                        rows=rows,
                    )
                )
    return blocks


def empty_section(section_id: int, level: int, title: str, heading_path: list[str], start_block: str) -> dict[str, Any]:
    return {
        "section_id": f"BID-SEC-{section_id:04d}",
        "level": level,
        "title": title,
        "heading_path": heading_path,
        "start_block_id": start_block,
        "end_block_id": start_block,
        "paragraphs": [],
        "tables": [],
        "image_refs": [],
        "text": "",
        "text_features": {},
        "candidate_score_units": [],
    }


def finalize_section(section: dict[str, Any] | None) -> dict[str, Any] | None:
    if section is None:
        return None
    text_parts = [p["text"] for p in section["paragraphs"] if p["text"]]
    text_parts.extend(table["text"] for table in section["tables"] if table["text"])
    section["text"] = normalize_text("\n".join(text_parts))
    section["text_features"] = {
        "char_count": len(section["text"]),
        "paragraph_count": len(section["paragraphs"]),
        "table_count": len(section["tables"]),
        "image_count": len(section["image_refs"]),
        "content_type": classify_section_content(section),
    }
    return section


def classify_section_content(section: dict[str, Any]) -> str:
    has_text = any(p["text"] for p in section["paragraphs"])
    has_table = bool(section["tables"])
    has_image = bool(section["image_refs"])
    types = []
    if has_text:
        types.append("text")
    if has_table:
        types.append("table")
    if has_image:
        types.append("image")
    return "+".join(types) if types else "empty"


def split_bid_technical_docx(docx_path: Path) -> list[dict[str, Any]]:
    blocks = iter_docx_blocks(docx_path)
    sections: list[dict[str, Any]] = []
    heading_stack: dict[int, str] = {}
    current: dict[str, Any] | None = None
    section_index = 0
    in_technical_part = False

    for block in blocks:
        if block.heading_level and block.heading_level <= 5:
            if block.text == "技术响应文件":
                in_technical_part = True
                continue
            if not in_technical_part:
                continue

            finalized = finalize_section(current)
            if finalized is not None:
                sections.append(finalized)

            level = min(block.heading_level, 5)
            for old_level in list(heading_stack):
                if old_level >= level:
                    heading_stack.pop(old_level, None)
            heading_stack[level] = block.text or ""
            heading_path = [heading_stack[idx] for idx in sorted(heading_stack)]
            section_index += 1
            current = empty_section(section_index, level, block.text or "", heading_path, block.block_id)
            continue

        if not in_technical_part or current is None:
            continue

        current["end_block_id"] = block.block_id
        if block.block_type == "paragraph":
            current["paragraphs"].append(
                {
                    "block_id": block.block_id,
                    "text": block.text,
                    "style_id": block.style_id,
                    "image_refs": block.image_refs,
                }
            )
            current["image_refs"].extend(block.image_refs)
        elif block.block_type == "table":
            rows = block.rows or []
            current["tables"].append(
                {
                    "block_id": block.block_id,
                    "row_count": len(rows),
                    "col_count": max((len(row) for row in rows), default=0),
                    "rows": rows,
                    "text": block.text,
                }
            )

    finalized = finalize_section(current)
    if finalized is not None:
        sections.append(finalized)
    return sections


def extract_score_unit_terms(unit: dict[str, Any]) -> list[str]:
    raw = unit.get("normalized_text") or unit.get("raw_text") or ""
    name = unit.get("unit_name", "")
    terms: list[str] = []

    for part in re.split(r"[、,，/及和与]", name):
        part = part.strip()
        if len(part) >= 2:
            terms.append(part)
    if name:
        terms.append(name)

    for match in re.finditer(r"([一-龥A-Za-z0-9、和及与等的\-]+)[（(]\s*\d+(?:\.\d+)?\s*分", raw):
        phrase = match.group(1).strip(" ；;，,。.")
        for part in re.split(r"[、,，；;和及与]", phrase):
            part = part.strip(" 等的")
            if 2 <= len(part) <= 24:
                terms.append(part)

    known_terms = [
        "应用环境",
        "体系结构",
        "实施要求",
        "系统功能",
        "性能要求",
        "合理化建议",
        "风险分析",
        "重点",
        "难点",
        "总体履约",
        "综合经营能力",
        "社会信用",
        "社会评价",
        "获奖情况",
        "总体服务方案",
        "系统架构",
        "详细设计",
        "实施方案",
        "实施计划",
        "测试",
        "试运行",
        "培训方案",
        "验收方案",
        "软件模块",
        "软件功能",
        "服务团队",
        "人员配备",
        "类似项目",
        "合同",
    ]
    normalized_raw = compact_text(raw + name)
    for term in known_terms:
        if term in normalized_raw:
            terms.append(term)

    deduped: list[str] = []
    seen: set[str] = set()
    for term in terms:
        term = normalize_text(term)
        if len(term) < 2 or term in seen:
            continue
        seen.add(term)
        deduped.append(term)
    return deduped[:30]


def match_section_to_unit(section: dict[str, Any], unit: dict[str, Any], terms: list[str]) -> tuple[float, list[str]]:
    title_text = compact_text(" ".join(section["heading_path"]))
    body_text = compact_text(section["text"])
    unit_name = compact_text(unit.get("unit_name", ""))
    matched: list[str] = []
    score = 0.0

    if unit_name and unit_name in title_text:
        score += 30
        matched.append(unit.get("unit_name", ""))
    elif unit_name and unit_name in body_text:
        score += 8
        matched.append(unit.get("unit_name", ""))

    for term in terms:
        compact = compact_text(term)
        if not compact or compact in matched:
            continue
        if compact in title_text:
            score += 6 + min(len(compact), 8) * 0.2
            matched.append(term)
        elif compact in body_text:
            score += 1 + min(len(compact), 8) * 0.1
            matched.append(term)

    return score, matched[:12]


def annotate_bid_sections(sections: list[dict[str, Any]], score_units: list[dict[str, Any]]) -> dict[str, Any]:
    unit_terms = {unit["unit_id"]: extract_score_unit_terms(unit) for unit in score_units}
    unit_annotations: list[dict[str, Any]] = []

    for section in sections:
        candidates: list[dict[str, Any]] = []
        for unit in score_units:
            score, matched_terms = match_section_to_unit(section, unit, unit_terms[unit["unit_id"]])
            if score >= 3:
                candidates.append(
                    {
                        "unit_id": unit["unit_id"],
                        "unit_name": unit["unit_name"],
                        "score_range_text": unit["score_range_text"],
                        "match_score": round(score, 2),
                        "matched_terms": matched_terms,
                    }
                )
        section["candidate_score_units"] = sorted(candidates, key=lambda item: item["match_score"], reverse=True)[:8]

    for unit in score_units:
        candidates = []
        for section in sections:
            for candidate in section["candidate_score_units"]:
                if candidate["unit_id"] == unit["unit_id"]:
                    candidates.append(
                        {
                            "section_id": section["section_id"],
                            "title": section["title"],
                            "heading_path": section["heading_path"],
                            "match_score": candidate["match_score"],
                            "matched_terms": candidate["matched_terms"],
                            "text_features": section["text_features"],
                        }
                    )
                    break
        unit_annotations.append(
            {
                "unit_id": unit["unit_id"],
                "unit_name": unit["unit_name"],
                "score_range_text": unit["score_range_text"],
                "terms": unit_terms[unit["unit_id"]],
                "candidate_sections": sorted(candidates, key=lambda item: item["match_score"], reverse=True)[:20],
            }
        )

    return {
        "source": {
            "bid_docx": relative_path(BID_DOCX),
            "procurement_score_units": relative_path(
                PROCUREMENT_UNITS_MIMO_JSON if PROCUREMENT_UNITS_MIMO_JSON.exists() else PROCUREMENT_UNITS_JSON
            ),
            "method": "heading_split_keyword_candidate_label_v0",
        },
        "score_unit_annotations": unit_annotations,
    }


def write_bid_outputs(sections: list[dict[str, Any]], annotations: dict[str, Any]) -> None:
    data = {
        "source": {
            "bid_docx": relative_path(BID_DOCX),
            "method": "docx_heading_split_v0",
            "technical_start_heading": "技术响应文件",
        },
        "sections": sections,
    }
    BID_SECTIONS_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    BID_ANNOTATIONS_JSON.write_text(json.dumps(annotations, ensure_ascii=False, indent=2), encoding="utf-8")

    section_lines = ["# 投标技术文件拆分结果", ""]
    for section in sections:
        path = " / ".join(section["heading_path"])
        features = section["text_features"]
        section_lines.append(f"## {section['section_id']} {path}")
        section_lines.append("")
        section_lines.append(
            f"level={section['level']} chars={features['char_count']} "
            f"paragraphs={features['paragraph_count']} tables={features['table_count']} "
            f"images={features['image_count']} type={features['content_type']}"
        )
        if section["candidate_score_units"]:
            labels = ", ".join(
                f"{item['unit_name']}({item['match_score']})" for item in section["candidate_score_units"][:5]
            )
            section_lines.append(f"candidate_score_units: {labels}")
        section_lines.append("")
        section_lines.append(section["text"][:1200])
        if len(section["text"]) > 1200:
            section_lines.append("...")
        section_lines.append("")
    BID_SECTIONS_MD.write_text("\n".join(section_lines).strip() + "\n", encoding="utf-8")

    annotation_lines = ["# 投标文件与采购评分单元候选标注", ""]
    for unit in annotations["score_unit_annotations"]:
        annotation_lines.append(f"## {unit['unit_id']} {unit['unit_name']} {unit['score_range_text']}")
        annotation_lines.append("")
        for candidate in unit["candidate_sections"][:10]:
            annotation_lines.append(
                f"- {candidate['section_id']} {' / '.join(candidate['heading_path'])} "
                f"score={candidate['match_score']} terms={candidate['matched_terms']}"
            )
        annotation_lines.append("")
    BID_ANNOTATIONS_MD.write_text("\n".join(annotation_lines).strip() + "\n", encoding="utf-8")


def split_fragment_chunks(
    text: str,
    max_chars: int = MAX_FRAGMENT_CHARS,
    overlap_chars: int = FRAGMENT_OVERLAP_CHARS,
) -> list[str]:
    text = normalize_text(text)
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    paragraphs = [part.strip() for part in re.split(r"\n+|(?<=[。；;！？])", text) if part.strip()]
    chunks: list[str] = []
    current = ""

    def push_current() -> None:
        nonlocal current
        if current.strip():
            chunks.append(normalize_text(current))
        current = ""

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            push_current()
            start = 0
            step = max_chars - overlap_chars
            while start < len(paragraph):
                chunks.append(paragraph[start : start + max_chars])
                start += step
            continue
        candidate = normalize_text(f"{current}\n{paragraph}") if current else paragraph
        if len(candidate) > max_chars:
            push_current()
            current = paragraph
        else:
            current = candidate
    push_current()

    return [chunk for chunk in chunks if chunk]


def build_bid_response_fragments(sections: list[dict[str, Any]], force: bool = False) -> dict[str, Any]:
    if BID_FRAGMENTS_JSON.exists() and not force:
        print(f"skip bid response fragments: output exists {BID_FRAGMENTS_JSON}")
        return json.loads(BID_FRAGMENTS_JSON.read_text(encoding="utf-8"))

    fragments: list[dict[str, Any]] = []

    def append_fragment(
        section: dict[str, Any],
        text: str,
        table_text: str,
        image_refs: list[str],
        content_part: str,
        chunk_index: int,
        chunk_count: int,
        source_char_count: int,
        paragraph_count: int,
        table_count: int,
    ) -> None:
        fragments.append(
            {
                "fragment_id": f"BF-{len(fragments) + 1:04d}",
                "source_section_ids": [section["section_id"]],
                "heading_path": section["heading_path"],
                "top_score_direction": section["heading_path"][0] if section["heading_path"] else "",
                "text": text,
                "table_text": table_text,
                "image_refs": image_refs,
                "char_count": len(text) + len(table_text),
                "paragraph_count": paragraph_count,
                "table_count": table_count,
                "image_count": len(image_refs),
                "content_part": content_part,
                "chunk_index": chunk_index,
                "chunk_count": chunk_count,
                "source_section_char_count": source_char_count,
                "chunking": {
                    "method": "paragraph_boundary_sliding_window_v1",
                    "max_chars": MAX_FRAGMENT_CHARS,
                    "overlap_chars": FRAGMENT_OVERLAP_CHARS,
                },
            }
        )

    for section in sections:
        paragraph_texts = [paragraph["text"] for paragraph in section["paragraphs"] if paragraph["text"]]
        table_texts = [table["text"] for table in section["tables"] if table["text"]]
        image_refs = section["image_refs"]
        text = normalize_text("\n".join(paragraph_texts))
        table_text = normalize_text("\n\n".join(table_texts))
        if not text and not table_text and not image_refs:
            continue

        source_char_count = len(text) + len(table_text)
        text_chunks = split_fragment_chunks(text)
        table_chunks = split_fragment_chunks(table_text)
        emitted = 0
        total_chunks = len(text_chunks) + len(table_chunks)

        for chunk in text_chunks:
            emitted += 1
            append_fragment(
                section,
                text=chunk,
                table_text="",
                image_refs=image_refs if emitted == 1 else [],
                content_part="text",
                chunk_index=emitted,
                chunk_count=max(total_chunks, 1),
                source_char_count=source_char_count,
                paragraph_count=max(1, chunk.count("\n") + 1),
                table_count=0,
            )

        for chunk in table_chunks:
            emitted += 1
            append_fragment(
                section,
                text="",
                table_text=chunk,
                image_refs=image_refs if emitted == 1 else [],
                content_part="table",
                chunk_index=emitted,
                chunk_count=max(total_chunks, 1),
                source_char_count=source_char_count,
                paragraph_count=0,
                table_count=len(section["tables"]),
            )

        if emitted == 0 and image_refs:
            append_fragment(
                section,
                text="",
                table_text="",
                image_refs=image_refs,
                content_part="image",
                chunk_index=1,
                chunk_count=1,
                source_char_count=0,
                paragraph_count=0,
                table_count=0,
            )

    result = {
        "source": {
            "bid_sections": relative_path(BID_SECTIONS_JSON),
            "method": "non_empty_section_to_response_fragment_chunked_v1",
            "scope": "technical_response_after_heading",
            "max_fragment_chars": MAX_FRAGMENT_CHARS,
            "fragment_overlap_chars": FRAGMENT_OVERLAP_CHARS,
        },
        "fragments": fragments,
    }
    BID_FRAGMENTS_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = ["# 投标响应片段数据集", ""]
    for fragment in fragments:
        md_lines.append(f"## {fragment['fragment_id']} {' / '.join(fragment['heading_path'])}")
        md_lines.append("")
        md_lines.append(
            f"chars={fragment['char_count']} paragraphs={fragment['paragraph_count']} "
            f"tables={fragment['table_count']} images={fragment['image_count']} "
            f"part={fragment.get('content_part')} chunk={fragment.get('chunk_index')}/{fragment.get('chunk_count')}"
        )
        md_lines.append("")
        body = fragment["text"] or fragment["table_text"] or f"image_refs={fragment['image_refs']}"
        md_lines.append(body[:1200])
        if len(body) > 1200:
            md_lines.append("...")
        md_lines.append("")
    BID_FRAGMENTS_MD.write_text("\n".join(md_lines).strip() + "\n", encoding="utf-8")
    print(f"bid response fragments: fragments={len(fragments)}")
    return result


def criterion_terms(criterion: dict[str, Any]) -> list[str]:
    raw = " ".join(
        [
            criterion.get("score_unit_name", ""),
            criterion.get("criterion_name", ""),
            criterion.get("object", ""),
            criterion.get("feature", ""),
            criterion.get("raw_text", ""),
        ]
    )
    candidates: list[str] = []
    for part in re.split(r"[、,，；;。()/（）和及与等的\s]+", raw):
        part = normalize_text(part)
        if 2 <= len(part) <= 24 and not re.fullmatch(r"\d+(?:\.\d+)?分?", part):
            candidates.append(part)
    for value in (criterion.get("score_unit_name", ""), criterion.get("criterion_name", ""), criterion.get("object", "")):
        value = normalize_text(value)
        if len(value) >= 2:
            candidates.append(value)

    deduped: list[str] = []
    seen: set[str] = set()
    for term in candidates:
        if term not in seen:
            seen.add(term)
            deduped.append(term)
    return deduped[:30]


def match_fragment_to_criterion(
    fragment: dict[str, Any],
    criterion: dict[str, Any],
    terms: list[str],
) -> tuple[float, list[str]]:
    title_text = compact_text(" ".join(fragment["heading_path"]))
    body_text = compact_text(" ".join([fragment.get("text", ""), fragment.get("table_text", "")]))
    top_direction = compact_text(fragment.get("top_score_direction", ""))
    unit_name = compact_text(criterion.get("score_unit_name", ""))
    criterion_name = compact_text(criterion.get("criterion_name", ""))
    matched: list[str] = []
    score = 0.0

    if unit_name and unit_name == top_direction:
        score += 18
        matched.append(criterion.get("score_unit_name", ""))
    elif unit_name and unit_name in title_text:
        score += 14
        matched.append(criterion.get("score_unit_name", ""))

    if criterion_name and criterion_name in title_text:
        score += 16
        matched.append(criterion.get("criterion_name", ""))
    elif criterion_name and criterion_name in body_text:
        score += 5
        matched.append(criterion.get("criterion_name", ""))

    for term in terms:
        compact = compact_text(term)
        if len(compact) < 2 or term in matched:
            continue
        if compact in title_text:
            score += 5 + min(len(compact), 8) * 0.2
            matched.append(term)
        elif compact in body_text:
            score += 1 + min(len(compact), 8) * 0.1
            matched.append(term)

    return score, matched[:12]


def retrieval_tokens(text: str) -> list[str]:
    normalized = normalize_text(text).lower()
    words = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]{2,}", normalized)
    chars = re.findall(r"[\u4e00-\u9fff]", normalized)
    char_bigrams = ["".join(chars[i : i + 2]) for i in range(len(chars) - 1)]
    return words + char_bigrams


def cosine_similarity(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    common = set(left) & set(right)
    dot = sum(left[key] * right[key] for key in common)
    left_norm = sum(value * value for value in left.values()) ** 0.5
    right_norm = sum(value * value for value in right.values()) ** 0.5
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def criterion_retrieval_text(criterion: dict[str, Any]) -> str:
    return normalize_text(
        "\n".join(
            [
                criterion.get("score_unit_name", ""),
                criterion.get("criterion_name", ""),
                criterion.get("object", ""),
                criterion.get("feature", ""),
                criterion.get("raw_text", ""),
            ]
        )
    )


def fragment_retrieval_text(fragment: dict[str, Any]) -> str:
    return normalize_text(
        "\n".join(
            [
                " / ".join(fragment.get("heading_path", [])),
                fragment.get("top_score_direction", ""),
                fragment.get("text", ""),
                fragment.get("table_text", ""),
            ]
        )
    )


def fragment_length_penalty(fragment: dict[str, Any]) -> float:
    char_count = max(int(fragment.get("char_count") or 0), 1)
    if char_count <= MAX_FRAGMENT_CHARS:
        return 1.0
    return 1.0 + math.log(char_count / MAX_FRAGMENT_CHARS)


def fragment_scoring_artifact_reason(fragment: dict[str, Any]) -> str:
    """Detect procurement scoring-table snippets that leaked into bid fragments.

    These snippets are useful as trace material, but they should not compete with
    real response text during procurement-to-bid mapping.
    """
    title_text = normalize_text(" / ".join(fragment.get("heading_path", [])))
    body_text = normalize_text("\n".join([fragment.get("text", ""), fragment.get("table_text", "")]))
    combined = normalize_text(f"{title_text}\n{body_text}")
    compact = compact_text(combined)
    if not combined:
        return ""

    if re.search(r"[.．]{5,}\s*\d{1,4}", combined):
        return "table_of_contents_line"
    if SCORE_RANGE_WITH_TYPE_RE.search(combined):
        return "score_range_with_subjective_or_objective_type"
    if SCORING_ROW_COMPACT_RE.search(compact):
        return "compact_scoring_table_row"
    if SCORE_RANGE_PAGE_RE.search(combined) and ("评审标准" in combined or "评分标准" in combined):
        return "range_scored_review_standard"
    if len(SCORE_RANGE_PAGE_RE.findall(combined)) >= 2 and ("是否" in combined or "标准评审" in combined):
        return "multiple_range_scored_review_checks"
    if PAREN_SCORE_RE.search(combined) and ("评审标准" in combined or "评分标准" in combined):
        return "scored_review_standard"
    if len(PAREN_SCORE_RE.findall(combined)) >= 2 and ("是否" in combined or "标准评审" in combined):
        return "multiple_scored_review_checks"
    if "一、评审内容" in combined and ("二、评审标准" in combined or "二、评分标准" in combined):
        return "review_content_and_scoring_standard"
    if "评审内容" in title_text and (SCORE_RANGE_PAGE_RE.search(combined) or PAREN_SCORE_RE.search(combined)):
        return "review_content_heading_with_score"
    if "评分项目" in combined and ("评分要点" in combined or "主观分" in combined or "客观分" in combined):
        return "scoring_table_header"
    return ""


def is_scoring_table_artifact_fragment(fragment: dict[str, Any]) -> bool:
    return bool(fragment_scoring_artifact_reason(fragment))


def mapping_candidate_fragments(fragments: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    usable: list[dict[str, Any]] = []
    excluded = 0
    for fragment in fragments:
        reason = fragment_scoring_artifact_reason(fragment)
        if reason:
            excluded += 1
            continue
        usable.append(fragment)
    return usable, excluded


def recall_candidate_fragments(
    criterion: dict[str, Any],
    fragments: list[dict[str, Any]],
    limit: int = 10,
) -> list[dict[str, Any]]:
    terms = criterion_terms(criterion)
    criterion_vector = Counter(retrieval_tokens(criterion_retrieval_text(criterion)))
    candidates: list[dict[str, Any]] = []
    for fragment in fragments:
        rule_score, matched_terms = match_fragment_to_criterion(fragment, criterion, terms)
        fragment_vector = Counter(retrieval_tokens(fragment_retrieval_text(fragment)))
        vector_similarity = cosine_similarity(criterion_vector, fragment_vector)
        length_penalty = fragment_length_penalty(fragment)
        normalized_rule_score = rule_score / length_penalty
        combined_score = vector_similarity * 100 + min(normalized_rule_score, 30)
        if vector_similarity >= 0.08 or normalized_rule_score >= 4:
            candidates.append(
                {
                    "fragment": fragment,
                    "match_score": round(combined_score, 2),
                    "vector_similarity": round(vector_similarity, 4),
                    "rule_boost": round(normalized_rule_score, 2),
                    "raw_rule_score": round(rule_score, 2),
                    "length_penalty": round(length_penalty, 3),
                    "matched_terms": matched_terms,
                }
            )
    candidates.sort(key=lambda item: item["match_score"], reverse=True)
    return candidates[:limit]


def fragment_excerpt(fragment: dict[str, Any], terms: list[str], max_len: int = 1600) -> str:
    source = normalize_text("\n".join([fragment.get("text", ""), fragment.get("table_text", "")]))
    if len(source) <= max_len:
        return source
    compact_source = compact_text(source)
    for term in terms:
        compact = compact_text(term)
        if not compact:
            continue
        pos = compact_source.find(compact)
        if pos >= 0:
            start = max(0, pos - max_len // 3)
            end = min(len(compact_source), start + max_len)
            return compact_source[start:end]
    return source[:max_len]


def build_mapping_messages(
    criterion: dict[str, Any],
    candidates: list[dict[str, Any]],
    excerpt_limit: int = MAPPING_CANDIDATE_EXCERPT_LIMIT_MIMO,
) -> list[dict[str, str]]:
    terms = criterion_terms(criterion)
    candidate_payload = []
    for candidate in candidates:
        fragment = candidate["fragment"]
        candidate_payload.append(
            {
                "fragment_id": fragment["fragment_id"],
                "heading_path": fragment["heading_path"],
                "match_score": candidate["match_score"],
                "matched_terms": candidate["matched_terms"],
                "excerpt": fragment_excerpt(fragment, terms, max_len=excerpt_limit),
            }
        )

    return [
        {
            "role": "system",
            "content": (
                "你是采购评分细则与投标响应片段的命中判断器。"
                "只判断候选投标片段是否响应该采购评分细则。"
                "不要评分，不要评价写得好不好，不要补充候选之外的片段。"
                "只允许从候选fragment_id中选择命中的片段。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请输出JSON对象，格式为："
                "{\"linked_bid_fragments\":[{\"fragment_id\":\"BF-0001\","
                "\"evidence_text\":\"来自候选摘录的原文证据\","
                "\"match_reason\":\"为什么命中\"}]}。\n"
                "如果没有命中，linked_bid_fragments输出空数组。\n\n"
                f"采购评分细则：\n{json.dumps(criterion, ensure_ascii=False, indent=2)}\n\n"
                f"候选投标片段：\n{json.dumps(candidate_payload, ensure_ascii=False, indent=2)}"
            ),
        },
    ]


def criterion_focus_terms(criterion: dict[str, Any]) -> list[str]:
    stop_terms = {
        "需求",
        "内容",
        "程度",
        "情况",
        "方案",
        "措施",
        "分析",
        "要求",
        "项目",
        "本项目",
        "相关",
        "提供",
        "详细",
        "全面",
        "进行",
        "综合",
        "评分",
        "评审",
        "响应",
        "响应内容",
        "说明",
    }
    values = [
        criterion.get("criterion_name", ""),
        criterion.get("object", ""),
        criterion.get("feature", ""),
    ]
    terms: list[str] = []
    for value in values:
        value = normalize_text(value)
        if 2 <= len(value) <= 30 and value not in stop_terms:
            terms.append(value)
        for part in re.split(r"[、,，；;。()/（）和及与等的\s\-]+", value):
            part = normalize_text(part)
            if 2 <= len(part) <= 18 and part not in stop_terms:
                terms.append(part)

    deduped: list[str] = []
    seen: set[str] = set()
    for term in terms:
        if term not in seen:
            seen.add(term)
            deduped.append(term)
    return deduped[:20]


def criterion_subitem_terms(criterion: dict[str, Any]) -> list[str]:
    raw_text = normalize_text(criterion.get("raw_text", ""))
    if not raw_text:
        return []
    terms: list[str] = []

    for match in re.finditer(
        r"(?:^|[；;。]\s*|\s)\d+[、.．]\s*"
        r"(?P<term>[^；;。]+?)"
        r"(?:[（(]\s*0\s*[~～\-—至]\s*\d+(?:\.\d+)?\s*分\s*[)）]|[；;。]|$)",
        raw_text,
    ):
        term = normalize_text(match.group("term"))
        term = PAREN_SCORE_RE.sub("", term)
        term = re.sub(r"[（(]\s*升级改造\s*[)）]", "", term)
        term = re.sub(r"[（(]\s*国产化环境改造迁移\s*[)）]", "", term)
        term = re.sub(r"[（(]\s*应用新建\s*[)）]", "", term)
        term = normalize_text(term.strip(" ：:；;，,、"))
        if 3 <= len(term) <= 40:
            terms.append(term)

    for part in re.split(r"[、,，；;。()/（）和及与等的或\s]+", raw_text):
        part = normalize_text(part)
        if 2 <= len(part) <= 18 and part not in {"评审内容", "评审标准", "评分标准", "主观分", "客观分"}:
            if any(key in part for key in ["模块", "设计", "履历", "证书", "合同", "验收", "证明", "类似项目", "移动应用"]):
                terms.append(part)

    deduped: list[str] = []
    seen: set[str] = set()
    for term in terms:
        compact = compact_text(term)
        if compact and compact not in seen:
            seen.add(compact)
            deduped.append(term)
    return deduped[:30]


def expanded_criterion_focus_terms(criterion: dict[str, Any]) -> list[str]:
    terms = criterion_focus_terms(criterion) + criterion_subitem_terms(criterion)
    deduped: list[str] = []
    seen: set[str] = set()
    for term in terms:
        compact = compact_text(term)
        if len(compact) < 2 or compact in seen:
            continue
        seen.add(compact)
        deduped.append(term)
    return deduped[:40]


def criterion_score_value(criterion: dict[str, Any]) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)", criterion.get("score_text", "") or "")
    return float(match.group(1)) if match else 0.0


def is_broad_mapping_criterion(criterion: dict[str, Any]) -> bool:
    raw_text = normalize_text(criterion.get("raw_text", ""))
    subitems = criterion_subitem_terms(criterion)
    return (
        criterion.get("scoring_type") == "subjective"
        and (
            criterion_score_value(criterion) >= 5
            or len(subitems) >= 2
            or "团队综合能力" in raw_text
        )
    )


TEAM_COMPREHENSIVE_EVIDENCE_TERMS = [
    "项目组成员",
    "团队人员",
    "团队成员",
    "履历",
    "岗位证书",
    "职业资格",
    "相关工作经历",
    "个人业绩",
    "团队人员业绩",
    "类似项目建设经验",
    "承担过类似项目",
    "用户证明",
    "验收报告",
]


def team_comprehensive_hits(text: str) -> list[str]:
    hits = keyword_hits(text, TEAM_COMPREHENSIVE_EVIDENCE_TERMS, limit=12)
    compact = compact_text(text)
    personnel_context = any(
        token in compact for token in ["团队", "人员", "项目组成员", "履历", "岗位证书", "职业资格", "个人业绩"]
    )
    if not personnel_context:
        return []
    if hits == ["验收报告"] or hits == ["用户证明"]:
        return []
    return hits


def is_form_or_navigation_heading(fragment: dict[str, Any]) -> bool:
    title_text = normalize_text(" / ".join(fragment.get("heading_path", [])))
    return any(
        marker in title_text
        for marker in [
            "目录",
            "开标一览表",
            "投标函",
            "授权委托书",
            "资格条件响应表",
            "实质性要求响应表",
            "中小企业声明函",
        ]
    )


def structural_rule_links(
    criterion: dict[str, Any],
    fragments: list[dict[str, Any]],
    limit: int = MAPPING_STRUCTURAL_LINK_LIMIT,
) -> list[dict[str, Any]]:
    unit_name = normalize_text(criterion.get("score_unit_name", ""))
    criterion_name = normalize_text(criterion.get("criterion_name", ""))
    focus_terms = expanded_criterion_focus_terms(criterion)
    links: list[dict[str, Any]] = []
    exact_links: list[dict[str, Any]] = []

    compact_unit_name = compact_text(unit_name)
    compact_criterion_name = compact_text(criterion_name)
    broad = is_broad_mapping_criterion(criterion)
    for fragment in fragments:
        if is_scoring_table_artifact_fragment(fragment):
            continue
        top_direction = normalize_text(fragment.get("top_score_direction", ""))
        title_text = compact_text(" ".join(fragment.get("heading_path", [])))
        body_text = compact_text(" ".join([fragment.get("text", ""), fragment.get("table_text", "")]))[:4000]
        combined_text = f"{title_text}{body_text}"
        matched_terms = [
            term for term in focus_terms if compact_text(term) and compact_text(term) in combined_text
        ]

        same_direction = False
        if unit_name:
            if top_direction == unit_name:
                same_direction = True
            elif compact_unit_name and compact_unit_name in title_text:
                same_direction = True
            elif broad and compact_unit_name and compact_unit_name in body_text[:800]:
                same_direction = True

        if not same_direction:
            if is_form_or_navigation_heading(fragment):
                continue
            if not (broad and matched_terms):
                continue

        if unit_name == "团队综合能力":
            team_hits = team_comprehensive_hits(combined_text)
            if not team_hits:
                continue
            for hit in team_hits:
                if hit not in matched_terms:
                    matched_terms.append(hit)

        exact_match = bool(compact_criterion_name and compact_criterion_name in title_text)
        if exact_match and criterion_name not in matched_terms:
            matched_terms.insert(0, criterion_name)
        if not matched_terms and criterion_name == unit_name and compact_text(unit_name) in title_text:
            matched_terms = [unit_name]
        if not matched_terms:
            continue

        source_text = fragment.get("text") or fragment.get("table_text") or ""
        if not source_text and fragment.get("image_refs"):
            source_text = f"image_refs={fragment['image_refs']}"
        link = {
            "fragment_id": fragment["fragment_id"],
            "heading_path": fragment["heading_path"],
            "evidence_text": source_text[:600],
            "match_reason": f"同一评分方向下标题路径命中核心词：{matched_terms}",
            "match_score": 120 + len(matched_terms) if exact_match else 100 + len(matched_terms),
            "matched_terms": matched_terms,
            "decision_source": "structural_rule",
        }
        if exact_match:
            exact_links.append(link)
        else:
            links.append(link)

    selected = exact_links + links
    return sorted(selected, key=lambda item: item["match_score"], reverse=True)[:limit]


def merge_links(primary: list[dict[str, Any]], secondary: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for link in primary + secondary:
        fragment_id = link.get("fragment_id")
        if not fragment_id or fragment_id in seen:
            continue
        seen.add(fragment_id)
        merged.append(link)
    return merged[:limit]


def mimo_linked_fragments(
    criterion: dict[str, Any],
    candidates: list[dict[str, Any]],
    excerpt_limit: int = MAPPING_CANDIDATE_EXCERPT_LIMIT_MIMO,
) -> list[dict[str, Any]]:
    config = get_mimo_config()
    if config is None:
        return []
    content = openai_compatible_chat(
        config,
        build_mapping_messages(criterion, candidates, excerpt_limit=excerpt_limit),
        max_tokens=3000,
        timeout_seconds=90,
    )
    parsed = extract_json_object(content)
    candidate_by_id = {candidate["fragment"]["fragment_id"]: candidate for candidate in candidates}
    links: list[dict[str, Any]] = []
    for item in parsed.get("linked_bid_fragments", []):
        if not isinstance(item, dict):
            continue
        fragment_id = item.get("fragment_id")
        if fragment_id not in candidate_by_id:
            continue
        candidate = candidate_by_id[fragment_id]
        fragment = candidate["fragment"]
        links.append(
            {
                "fragment_id": fragment_id,
                "heading_path": fragment["heading_path"],
                "evidence_text": normalize_text(str(item.get("evidence_text", "")))[:1200],
                "match_reason": normalize_text(str(item.get("match_reason", "")))[:600],
                "match_score": candidate["match_score"],
                "matched_terms": candidate["matched_terms"],
                "decision_source": config["model"],
            }
        )
    return links


LINKED_BID_FRAGMENT_KEYS: frozenset[str] = frozenset(
    {"fragment_id", "heading_path", "evidence_text", "match_reason", "decision_source"}
)


def sanitize_linked_bid_fragments(mapping_doc: dict[str, Any]) -> dict[str, Any]:
    """Strip non-contract keys from every linked_bid_fragments entry in mapping_doc."""
    for mapping in mapping_doc.get("mappings", []):
        links = mapping.get("linked_bid_fragments")
        if not isinstance(links, list):
            continue
        mapping["linked_bid_fragments"] = [
            {k: v for k, v in link.items() if k in LINKED_BID_FRAGMENT_KEYS}
            for link in links
            if isinstance(link, dict)
        ]
    return mapping_doc


def atomic_write_mapping(mapping_doc: dict[str, Any]) -> None:
    """Atomically replace PROCUREMENT_BID_MAPPING_JSON via unique temp file in same dir."""
    PROCUREMENT_BID_MAPPING_JSON.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_name = tempfile.mkstemp(
        dir=PROCUREMENT_BID_MAPPING_JSON.parent,
        prefix=PROCUREMENT_BID_MAPPING_JSON.name + ".",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(mapping_doc, f, ensure_ascii=False, indent=2)
        tmp_path.replace(PROCUREMENT_BID_MAPPING_JSON)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


@contextmanager
def mapping_file_lock():
    """Exclusive file lock around mapping JSON reads/writes.

    Uses a sidecar .lock file so the lock identity survives atomic rename of the data file.
    POSIX uses fcntl.flock; Windows uses msvcrt.locking on the first byte.
    """
    PROCUREMENT_BID_MAPPING_JSON.parent.mkdir(parents=True, exist_ok=True)
    lock_path = PROCUREMENT_BID_MAPPING_JSON.with_suffix(
        PROCUREMENT_BID_MAPPING_JSON.suffix + ".lock"
    )
    lock_fd = open(lock_path, "a+", encoding="utf-8")
    try:
        if fcntl is not None:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
        elif msvcrt is not None:
            lock_fd.seek(0)
            msvcrt.locking(lock_fd.fileno(), msvcrt.LK_LOCK, 1)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            elif msvcrt is not None:
                lock_fd.seek(0)
                msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        lock_fd.close()


def map_criteria_to_bid_fragments(
    criteria: list[dict[str, Any]],
    fragments: list[dict[str, Any]],
    use_mimo: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    if PROCUREMENT_BID_MAPPING_JSON.exists() and not force:
        with mapping_file_lock():
            # 重新检查文件是否仍存在：锁外检查可能被并发 force 写入抢先
            if PROCUREMENT_BID_MAPPING_JSON.exists():
                print(f"skip procurement-bid mapping: output exists {PROCUREMENT_BID_MAPPING_JSON}")
                cached = json.loads(PROCUREMENT_BID_MAPPING_JSON.read_text(encoding="utf-8"))
                before = json.dumps(cached, ensure_ascii=False, sort_keys=True)
                sanitize_linked_bid_fragments(cached)
                after = json.dumps(cached, ensure_ascii=False, sort_keys=True)
                if before != after:
                    atomic_write_mapping(cached)
                    print(
                        f"rewrote cached mapping with sanitized linked_bid_fragments: {PROCUREMENT_BID_MAPPING_JSON}"
                    )
                return cached
            # cache 在等锁期间被并发 force 删除/重写——回落到新建路径
            print(f"cache vanished while waiting for lock, regenerating: {PROCUREMENT_BID_MAPPING_JSON}")

    mappings: list[dict[str, Any]] = []
    usable_fragments, excluded_scoring_artifact_count = mapping_candidate_fragments(fragments)
    candidate_limit = MAPPING_CANDIDATE_LIMIT_MIMO if use_mimo else MAPPING_CANDIDATE_LIMIT_RULE_ONLY
    excerpt_limit = (
        MAPPING_CANDIDATE_EXCERPT_LIMIT_MIMO if use_mimo else MAPPING_CANDIDATE_EXCERPT_LIMIT_RULE
    )
    print(
        "mapping candidate pool: "
        f"usable={len(usable_fragments)} excluded_scoring_artifacts={excluded_scoring_artifact_count} "
        f"candidate_limit={candidate_limit}"
    )
    for index, criterion in enumerate(criteria, start=1):
        candidates = recall_candidate_fragments(criterion, usable_fragments, limit=candidate_limit)
        structural_links = structural_rule_links(criterion, usable_fragments)
        if not candidates:
            links = structural_links
        elif use_mimo:
            print(f"[{index}/{len(criteria)}] map {criterion['criterion_id']} candidates={len(candidates)}")
            try:
                links = mimo_linked_fragments(criterion, candidates, excerpt_limit=excerpt_limit)
            except Exception as exc:
                print(f"mapping MiMo failed for {criterion['criterion_id']}: {exc}")
                links = []
            links = merge_links(links, structural_links)
        else:
            links = structural_links

        sanitized_links = [
            {k: v for k, v in link.items() if k in LINKED_BID_FRAGMENT_KEYS}
            for link in links
        ]
        mappings.append(
            {
                "criterion_id": criterion["criterion_id"],
                "score_unit_id": criterion["score_unit_id"],
                "score_unit_name": criterion["score_unit_name"],
                "criterion_name": criterion["criterion_name"],
                "linked_bid_fragments": sanitized_links,
                "candidate_fragment_ids": [candidate["fragment"]["fragment_id"] for candidate in candidates],
            }
        )

    result = {
        "source": {
            "procurement_criteria": relative_path(PROCUREMENT_CRITERIA_JSON),
            "bid_response_fragments": relative_path(BID_FRAGMENTS_JSON),
            "method": (
                "criterion_to_fragment_vector_recall_mimo_rerank_structural_fallback_v2"
                if use_mimo
                else "criterion_to_fragment_vector_recall_structural_hit_v2"
            ),
            "task": "binary_hit_mapping_without_scoring",
            "candidate_limit": candidate_limit,
            "excluded_scoring_artifact_fragment_count": excluded_scoring_artifact_count,
        },
        "mappings": mappings,
    }
    with mapping_file_lock():
        # 并发保护：non-force 调用在我们 compute 期间，可能有 force/其他 writer 抢先发布了
        # 新 mapping。这种情况下不能用 stale in-memory result 覆盖 fresh disk，要 honor disk。
        if not force and PROCUREMENT_BID_MAPPING_JSON.exists():
            print(
                f"another writer published mapping during regeneration; honoring it: {PROCUREMENT_BID_MAPPING_JSON}"
            )
            result = json.loads(PROCUREMENT_BID_MAPPING_JSON.read_text(encoding="utf-8"))
            before = json.dumps(result, ensure_ascii=False, sort_keys=True)
            sanitize_linked_bid_fragments(result)
            after = json.dumps(result, ensure_ascii=False, sort_keys=True)
            if before != after:
                atomic_write_mapping(result)
        else:
            atomic_write_mapping(result)
    # disk 已敲定 result（可能是我们的也可能是其他 writer 的），用最新的 mappings 渲染 MD
    mappings = result["mappings"]

    md_lines = ["# 采购评分细则到投标响应片段映射", ""]
    for mapping in mappings:
        md_lines.append(
            f"## {mapping['criterion_id']} {mapping['score_unit_name']} / {mapping['criterion_name']}"
        )
        md_lines.append("")
        if not mapping["linked_bid_fragments"]:
            md_lines.append("linked_bid_fragments: []")
        for link in mapping["linked_bid_fragments"]:
            md_lines.append(
                f"- {link['fragment_id']} {' / '.join(link['heading_path'])} "
                f"score={link.get('match_score')} source={link.get('decision_source')}"
            )
            if link.get("match_reason"):
                md_lines.append(f"  reason: {link['match_reason']}")
        md_lines.append("")
    PROCUREMENT_BID_MAPPING_MD.write_text("\n".join(md_lines).strip() + "\n", encoding="utf-8")
    print(f"procurement-bid mapping: criteria={len(criteria)} mappings={len(mappings)}")
    return result


def normalize_str_list(value: Any, limit: int = 12) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        clean = normalize_text(item)
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
        if len(result) >= limit:
            break
    return result


def full_fragment_text(fragment: dict[str, Any]) -> str:
    return normalize_text("\n".join([fragment.get("text", ""), fragment.get("table_text", "")]))


def linked_fragment_objects(
    mapping: dict[str, Any],
    fragments_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    linked: list[dict[str, Any]] = []
    for link in mapping.get("linked_bid_fragments", []):
        fragment_id = link.get("fragment_id")
        fragment = fragments_by_id.get(fragment_id)
        if fragment:
            linked.append(fragment)
    return linked


def keyword_hits(text: str, terms: list[str], limit: int = 20) -> list[str]:
    compact = compact_text(text)
    hits: list[str] = []
    seen: set[str] = set()
    for term in terms:
        clean = normalize_text(term)
        if len(clean) < 2 or clean in seen:
            continue
        if compact_text(clean) in compact:
            seen.add(clean)
            hits.append(clean)
        if len(hits) >= limit:
            break
    return hits


def fragment_feature_stats(fragments: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "fragment_count": len(fragments),
        "char_count": sum(int(fragment.get("char_count") or 0) for fragment in fragments),
        "paragraph_count": sum(int(fragment.get("paragraph_count") or 0) for fragment in fragments),
        "table_count": sum(int(fragment.get("table_count") or 0) for fragment in fragments),
        "image_count": sum(int(fragment.get("image_count") or 0) for fragment in fragments),
        "max_heading_depth": max((len(fragment.get("heading_path", [])) for fragment in fragments), default=0),
    }


def detect_content_modules(text: str) -> list[str]:
    module_rules = [
        ("项目背景与目标定位", ["背景", "目标", "定位", "核心", "建设"]),
        ("采购需求理解", ["需求", "理解", "招标文件", "采购需求"]),
        ("业务场景拆解", ["业务", "场景", "流程", "链路", "街镇", "作业"]),
        ("系统架构或分层设计", ["架构", "体系", "分层", "支撑层", "数据资源层", "应用层"]),
        ("功能模块说明", ["功能", "模块", "子系统", "移动端", "管理端"]),
        ("实施步骤与计划", ["实施", "步骤", "计划", "阶段", "进度", "里程碑"]),
        ("测试、试运行或验收", ["测试", "试运行", "验收"]),
        ("培训与服务保障", ["培训", "服务", "运维", "保障"]),
        ("风险、安全或质量控制", ["风险", "安全", "质量", "应急", "控制"]),
        ("人员组织与责任分工", ["人员", "团队", "职责", "责任", "分工"]),
    ]
    return [name for name, terms in module_rules if keyword_hits(text, terms, limit=1)]


def detect_execution_elements(text: str) -> list[str]:
    element_rules = [
        ("步骤流程", ["步骤", "流程", "环节", "路线"]),
        ("阶段计划", ["阶段", "计划", "周期", "进度", "里程碑"]),
        ("责任分工", ["责任", "职责", "分工", "岗位"]),
        ("人员配置", ["人员", "团队", "项目经理", "负责人"]),
        ("交付物", ["交付", "成果", "文档", "清单"]),
        ("测试验证", ["测试", "联调", "验证", "试运行"]),
        ("培训安排", ["培训", "授课", "考核"]),
        ("验收闭环", ["验收", "整改", "确认"]),
        ("风险控制", ["风险", "应急", "预案", "控制"]),
        ("保障机制", ["保障", "运维", "服务", "响应"]),
    ]
    return [name for name, terms in element_rules if keyword_hits(text, terms, limit=1)]


def count_list_markers(text: str) -> int:
    return len(re.findall(r"(?:^|\s)(?:\d+[、.．]|[（(]\d+[)）]|[一二三四五六七八九十]+[、.．])", text))


def detect_writing_structure(
    criterion: dict[str, Any],
    fragments: list[dict[str, Any]],
    combined_text: str,
) -> list[str]:
    moves: list[str] = []
    title_text = " / ".join(" / ".join(fragment.get("heading_path", [])) for fragment in fragments)
    if keyword_hits(combined_text, ["本项目", "我方理解", "充分认识", "招标文件明确"], limit=1):
        moves.append("先给出项目定位或需求理解结论")
    if keyword_hits(title_text + combined_text, ["架构", "体系", "分层", "模块", "子系统"], limit=1):
        moves.append("再按架构、模块或业务对象拆解展开")
    if count_list_markers(combined_text) >= 3:
        moves.append("正文使用编号条目承载多个检查点")
    if keyword_hits(combined_text, ["步骤", "流程", "阶段", "计划", "进度"], limit=1):
        moves.append("用步骤、流程或阶段说明可执行路径")
    if keyword_hits(combined_text, ["保障", "风险", "安全", "质量", "应急"], limit=1):
        moves.append("补充保障、风险或安全控制内容")
    if keyword_hits(combined_text, PROJECT_SCENE_TERMS, limit=1):
        moves.append("将通用方案绑定到本项目场景和专有名词")
    if any(int(fragment.get("table_count") or 0) > 0 for fragment in fragments):
        moves.append("使用表格承载清单、配置、计划或对照关系")
    if any(int(fragment.get("image_count") or 0) > 0 for fragment in fragments):
        moves.append("使用图片或图示承载架构、流程或关系")
    if not moves and criterion.get("criterion_name"):
        moves.append("围绕评分细则标题展开说明")
    return moves


def heading_patterns(fragments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    patterns: list[dict[str, Any]] = []
    for fragment in fragments[:12]:
        path = fragment.get("heading_path", [])
        patterns.append(
            {
                "fragment_id": fragment["fragment_id"],
                "heading_path": path,
                "depth": len(path),
                "leaf_heading": path[-1] if path else "",
            }
        )
    return patterns


def build_rule_subjective_writing_features(
    criterion: dict[str, Any],
    fragments: list[dict[str, Any]],
) -> dict[str, Any]:
    combined_text = normalize_text("\n".join(full_fragment_text(fragment) for fragment in fragments))
    criterion_focus = criterion_focus_terms(criterion)
    stats = fragment_feature_stats(fragments)
    return {
        "feature_source": "rule_extraction",
        "text_stats": stats,
        "heading_patterns": heading_patterns(fragments),
        "coverage_terms_found": keyword_hits(combined_text, criterion_focus, limit=20),
        "project_specific_terms": keyword_hits(combined_text, PROJECT_SCENE_TERMS, limit=20),
        "content_modules": detect_content_modules(combined_text),
        "writing_structure": detect_writing_structure(criterion, fragments, combined_text),
        "execution_elements": detect_execution_elements(combined_text),
        "format_elements": {
            "uses_table": stats["table_count"] > 0,
            "uses_image": stats["image_count"] > 0,
            "list_marker_count": count_list_markers(combined_text),
            "max_heading_depth": stats["max_heading_depth"],
        },
    }


def infer_objective_evidence_type(criterion: dict[str, Any]) -> tuple[str, str, list[str]]:
    text = compact_text(
        " ".join(
            [
                criterion.get("score_unit_name", ""),
                criterion.get("criterion_name", ""),
                criterion.get("object", ""),
                criterion.get("feature", ""),
                criterion.get("raw_text", ""),
            ]
        )
    )
    if "报价" in text or "评标基准价" in text or "公式" in text:
        return "price_formula", "公式计算型", ["投标报价", "评标基准价", "价格分公式"]
    if "合同" in text or "类似项目" in text:
        return "contract_case", "证明材料计数型", ["合同名称", "签订日期", "服务期限", "盖章页", "合同扫描件"]
    if "人数" in text or "不少于" in text:
        return "personnel_count", "数量门槛型", ["人员数量", "岗位角色", "人员清单"]
    if "证书" in text or "职称" in text or "项目负责人" in text or "技术负责人" in text:
        return "personnel_certificate", "人员资质核验型", ["人员姓名", "岗位角色", "证书名称", "证书等级", "社保证明"]
    if "获奖" in text or "信用" in text or "评价" in text:
        return "reputation_evidence", "外部证明核验型", ["证明名称", "颁发单位", "有效时间", "证明材料"]
    return "objective_evidence", "证据核验型", keyword_hits(text, OBJECTIVE_KEYWORDS, limit=8)


def build_objective_evidence_features(
    criterion: dict[str, Any],
    fragments: list[dict[str, Any]],
) -> dict[str, Any]:
    evidence_type, verification_mode, field_candidates = infer_objective_evidence_type(criterion)
    criterion_text = normalize_text(
        " ".join(
            [
                criterion.get("score_unit_name", ""),
                criterion.get("criterion_name", ""),
                criterion.get("raw_text", ""),
            ]
        )
    )
    linked_text = normalize_text("\n".join(full_fragment_text(fragment) for fragment in fragments))
    required_terms = keyword_hits(criterion_text, OBJECTIVE_KEYWORDS + field_candidates, limit=20)
    detected_terms = keyword_hits(linked_text, required_terms + field_candidates, limit=20)
    return {
        "feature_source": "rule_extraction",
        "evidence_type": evidence_type,
        "verification_mode": verification_mode,
        "required_evidence_terms_from_criterion": required_terms,
        "candidate_evidence_fields": field_candidates,
        "detected_evidence_terms_in_linked_fragments": detected_terms,
        "linked_fragment_stats": fragment_feature_stats(fragments),
        "note": "本结构只描述客观项的证据核验字段，不做得分计算。",
    }


def feature_fragment_excerpt(fragment: dict[str, Any], max_len: int = 1100) -> dict[str, Any]:
    text = full_fragment_text(fragment)
    return {
        "fragment_id": fragment["fragment_id"],
        "heading_path": fragment.get("heading_path", []),
        "char_count": fragment.get("char_count", 0),
        "paragraph_count": fragment.get("paragraph_count", 0),
        "table_count": fragment.get("table_count", 0),
        "image_count": fragment.get("image_count", 0),
        "excerpt": text[:max_len],
    }


def build_subjective_feature_messages(
    criterion: dict[str, Any],
    fragments: list[dict[str, Any]],
    rule_features: dict[str, Any],
) -> list[dict[str, str]]:
    payload = {
        "criterion": {
            "criterion_id": criterion["criterion_id"],
            "score_unit_name": criterion["score_unit_name"],
            "criterion_name": criterion["criterion_name"],
            "object": criterion.get("object", ""),
            "feature": criterion.get("feature", ""),
            "score_text": criterion.get("score_text", ""),
        },
        "rule_features": rule_features,
        "linked_fragments": [feature_fragment_excerpt(fragment) for fragment in fragments[:8]],
    }
    return [
        {
            "role": "system",
            "content": (
                "你是投标响应文本结构抽取器。只从已命中的投标片段中抽取写作结构和文本特征。"
                "不得评分，不得评价写得好坏，不得生成新的投标文本，不得新增采购文件没有的要求，"
                "也不得把这些特征反写成采购文件字段。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请输出JSON对象，格式为：\n"
                "{\n"
                '  "content_modules": ["片段中实际出现的内容模块"],\n'
                '  "writing_structure": ["片段实际采用的展开顺序或组织方式"],\n'
                '  "coverage_points": ["片段围绕该评分细则覆盖的要点"],\n'
                '  "project_specific_expressions": ["片段中体现项目化的原文短语"],\n'
                '  "execution_elements": ["步骤、流程、计划、分工、交付、验收等实际出现的执行要素"],\n'
                '  "format_usage": ["表格、图示、编号条目等实际出现的表达载体"],\n'
                '  "reusable_writing_pattern": "用一句话概括该细则下投标响应的写作路径",\n'
                '  "source_fragment_ids": ["使用到的fragment_id"]\n'
                "}\n\n"
                "只允许依据输入片段原文归纳，不要写泛泛的评价词。\n\n"
                f"输入JSON：\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
            ),
        },
    ]


def refine_subjective_features_with_mimo(
    criterion: dict[str, Any],
    fragments: list[dict[str, Any]],
    rule_features: dict[str, Any],
) -> dict[str, Any] | None:
    config = get_mimo_config()
    if config is None or not fragments:
        return None
    content = openai_compatible_chat(
        config,
        build_subjective_feature_messages(criterion, fragments, rule_features),
        max_tokens=2400,
        timeout_seconds=45,
    )
    parsed = extract_json_object(content)
    return {
        "feature_source": config["model"],
        "content_modules": normalize_str_list(parsed.get("content_modules"), limit=16),
        "writing_structure": normalize_str_list(parsed.get("writing_structure"), limit=16),
        "coverage_points": normalize_str_list(parsed.get("coverage_points"), limit=20),
        "project_specific_expressions": normalize_str_list(
            parsed.get("project_specific_expressions"), limit=16
        ),
        "execution_elements": normalize_str_list(parsed.get("execution_elements"), limit=16),
        "format_usage": normalize_str_list(parsed.get("format_usage"), limit=12),
        "reusable_writing_pattern": normalize_text(str(parsed.get("reusable_writing_pattern", "")))[:500],
        "source_fragment_ids": normalize_str_list(parsed.get("source_fragment_ids"), limit=12),
    }


def extract_criterion_response_features(
    criteria: list[dict[str, Any]],
    fragments: list[dict[str, Any]],
    mappings: list[dict[str, Any]],
    use_mimo: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    if CRITERION_RESPONSE_FEATURES_JSON.exists() and not force:
        print(f"skip criterion response features: output exists {CRITERION_RESPONSE_FEATURES_JSON}")
        return json.loads(CRITERION_RESPONSE_FEATURES_JSON.read_text(encoding="utf-8"))

    criteria_by_id = {item["criterion_id"]: item for item in criteria}
    fragments_by_id = {item["fragment_id"]: item for item in fragments}
    features: list[dict[str, Any]] = []

    for index, mapping in enumerate(mappings, start=1):
        criterion = criteria_by_id.get(mapping["criterion_id"])
        if not criterion:
            continue
        linked_fragments = linked_fragment_objects(mapping, fragments_by_id)
        scoring_type = criterion.get("scoring_type", "subjective")
        subjective_features = None
        objective_features = None
        model_status = "not_applicable"

        if scoring_type == "objective":
            objective_features = build_objective_evidence_features(criterion, linked_fragments)
        else:
            rule_features = build_rule_subjective_writing_features(criterion, linked_fragments)
            subjective_features = {"rule_features": rule_features, "model_features": None}
            model_status = "skipped_no_mimo" if not use_mimo else "not_called_no_linked_fragment"
            if use_mimo and linked_fragments:
                print(
                    f"[features {index}/{len(mappings)}] extract "
                    f"{criterion['criterion_id']} fragments={len(linked_fragments)}",
                    flush=True,
                )
                try:
                    model_features = refine_subjective_features_with_mimo(
                        criterion,
                        linked_fragments,
                        rule_features,
                    )
                except Exception as exc:
                    print(f"feature MiMo extraction failed for {criterion['criterion_id']}: {exc}")
                    model_features = None
                    model_status = "mimo_failed"
                else:
                    model_status = "mimo_extracted" if model_features else "mimo_unavailable"
                subjective_features["model_features"] = model_features

        features.append(
            {
                "criterion_id": criterion["criterion_id"],
                "score_unit_id": criterion["score_unit_id"],
                "score_unit_name": criterion["score_unit_name"],
                "criterion_name": criterion["criterion_name"],
                "score_text": criterion.get("score_text", ""),
                "scoring_type": scoring_type,
                "linked_fragment_ids": [fragment["fragment_id"] for fragment in linked_fragments],
                "mapping_status": "linked" if linked_fragments else "no_linked_fragment",
                "subjective_writing_features": subjective_features,
                "objective_evidence_features": objective_features,
                "model_status": model_status,
            }
        )

    result = {
        "source": {
            "procurement_criteria": relative_path(PROCUREMENT_CRITERIA_JSON),
            "bid_response_fragments": relative_path(BID_FRAGMENTS_JSON),
            "procurement_bid_mapping": relative_path(PROCUREMENT_BID_MAPPING_JSON),
            "method": (
                "mapping_to_response_feature_extraction_mimo_with_rule_fallback_v0"
                if use_mimo
                else "mapping_to_response_feature_rule_extraction_v0"
            ),
            "task": "response_text_feature_extraction_without_scoring",
        },
        "features": features,
    }
    CRITERION_RESPONSE_FEATURES_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    write_criterion_response_features_md(features)
    print(f"criterion response features: features={len(features)}")
    return result


def write_criterion_response_features_md(features: list[dict[str, Any]]) -> None:
    lines = ["# 评分细则响应文本特征数据集", ""]
    lines.append("本文件只记录已映射投标片段的文本特征和结构，不做得分预测，也不反向修改采购评分细则。")
    lines.append("")

    for item in features:
        lines.append(
            f"## {item['criterion_id']} {item['score_unit_name']} / {item['criterion_name']} / {item['scoring_type']}"
        )
        lines.append("")
        linked = ", ".join(item["linked_fragment_ids"]) if item["linked_fragment_ids"] else "[]"
        lines.append(f"linked_fragment_ids: {linked}")
        lines.append("")

        if item["scoring_type"] == "objective":
            obj = item["objective_evidence_features"] or {}
            lines.append(f"- evidence_type: {obj.get('evidence_type', '')}")
            lines.append(f"- verification_mode: {obj.get('verification_mode', '')}")
            lines.append(f"- required_terms: {obj.get('required_evidence_terms_from_criterion', [])}")
            lines.append(f"- candidate_fields: {obj.get('candidate_evidence_fields', [])}")
            lines.append(f"- detected_terms: {obj.get('detected_evidence_terms_in_linked_fragments', [])}")
            lines.append("")
            continue

        subjective = item["subjective_writing_features"] or {}
        rule = subjective.get("rule_features") or {}
        model = subjective.get("model_features") or {}
        lines.append(f"- content_modules(rule): {rule.get('content_modules', [])}")
        lines.append(f"- writing_structure(rule): {rule.get('writing_structure', [])}")
        lines.append(f"- coverage_terms(rule): {rule.get('coverage_terms_found', [])}")
        lines.append(f"- project_terms(rule): {rule.get('project_specific_terms', [])}")
        lines.append(f"- execution_elements(rule): {rule.get('execution_elements', [])}")
        lines.append(f"- format_elements(rule): {rule.get('format_elements', {})}")
        if model:
            lines.append(f"- content_modules(model): {model.get('content_modules', [])}")
            lines.append(f"- writing_structure(model): {model.get('writing_structure', [])}")
            lines.append(f"- coverage_points(model): {model.get('coverage_points', [])}")
            lines.append(f"- project_expressions(model): {model.get('project_specific_expressions', [])}")
            lines.append(f"- execution_elements(model): {model.get('execution_elements', [])}")
            lines.append(f"- format_usage(model): {model.get('format_usage', [])}")
            if model.get("reusable_writing_pattern"):
                lines.append(f"- reusable_writing_pattern(model): {model['reusable_writing_pattern']}")
        else:
            lines.append(f"- model_status: {item.get('model_status')}")
        lines.append("")

    CRITERION_RESPONSE_FEATURES_MD.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def load_final_dataset(path: Path, key: str) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required dataset: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get(key)
    if not isinstance(items, list):
        raise ValueError(f"Dataset {path} does not contain list key: {key}")
    return items


def parse_max_score(score_text: str) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)", score_text or "")
    return float(match.group(1)) if match else 0.0


def find_target_bidder(final_scores: dict[str, Any]) -> dict[str, Any] | None:
    for bidder in final_scores.get("bidders", []):
        if bidder.get("is_target"):
            return bidder
    return None


def get_target_score_level(target_bidder: dict[str, Any]) -> str:
    scores = target_bidder.get("scores") or []
    if not scores:
        return "unknown"
    return scores[0].get("score_level", "unknown")


def analyze_one_criterion(
    criterion: dict[str, Any],
    feature: dict[str, Any],
    score_level: str,
) -> dict[str, Any]:
    """Rule-based 得扣分点抽取。

    符合 .md §9.4 (主观项 coverage/depth/project_specific/execution/format) 和
    .md §9.5 (客观项 missing_evidence/document_valid/threshold) 的口径。
    score_level=='total' 时强制 confidence='low_total_only'，actual_score 留 null。
    """
    scoring_type = criterion.get("scoring_type", "subjective")
    max_score = parse_max_score(criterion.get("score_text", ""))
    linked_ids = list(feature.get("linked_fragment_ids") or [])
    mapping_status = feature.get("mapping_status", "no_linked_fragment")

    scoring_points: list[dict[str, Any]] = []
    deduction_points: list[dict[str, Any]] = []
    writing_pattern_to_keep: list[str] = []
    writing_pattern_to_improve: list[str] = []

    sp_counter = 0
    dp_counter = 0

    def add_sp(point_name: str, evidence_ids: list[str], basis: str, point_type: str) -> None:
        nonlocal sp_counter
        sp_counter += 1
        scoring_points.append(
            {
                "point_id": f"SP-{sp_counter:03d}",
                "point_type": point_type,
                "point_name": point_name,
                "evidence_fragment_ids": evidence_ids,
                "evidence_text": "",
                "basis": basis,
            }
        )

    def add_dp(
        point_name: str,
        dtype: str,
        related_req: str,
        evidence_ids: list[str],
        reason: str,
    ) -> None:
        nonlocal dp_counter
        dp_counter += 1
        deduction_points.append(
            {
                "point_id": f"DP-{dp_counter:03d}",
                "deduction_type": dtype,
                "point_name": point_name,
                "related_requirement": related_req,
                "evidence_fragment_ids": evidence_ids,
                "evidence_text": "",
                "deduction_reason": reason,
                "deduction_score_estimate": None,
            }
        )

    if mapping_status == "no_linked_fragment":
        add_dp(
            point_name=f"未在技术响应文件中找到对应「{criterion.get('criterion_name', '')}」的响应",
            dtype="not_in_technical_scope" if scoring_type == "objective" else "coverage_gap",
            related_req=criterion.get("criterion_name", ""),
            evidence_ids=[],
            reason="映射阶段未召回任何投标片段；可能在商务/报价文件而非技术文件，或写作完全缺失",
        )
    elif scoring_type == "objective":
        ofeat = feature.get("objective_evidence_features") or {}
        required = ofeat.get("required_evidence_terms_from_criterion") or []
        detected = ofeat.get("detected_evidence_terms_in_linked_fragments") or []
        evidence_type = ofeat.get("evidence_type", "objective_evidence")
        stats = ofeat.get("linked_fragment_stats") or {}

        if detected and len(detected) >= max(1, len(required) // 2):
            add_sp(
                point_name=f"检出客观证据词：{detected[:5]}",
                evidence_ids=linked_ids,
                basis=f"verification_mode={ofeat.get('verification_mode', '')}",
                point_type="evidence_count_hit",
            )
        if required and not detected:
            add_dp(
                point_name=f"缺少必要的客观证据词（期望 {required[:5]}）",
                dtype="missing_evidence",
                related_req="、".join(required[:5]),
                evidence_ids=linked_ids,
                reason="required_evidence_terms_from_criterion 非空但 detected_evidence_terms 为空",
            )
        if stats.get("table_count", 0) == 0 and evidence_type in {
            "contract_case",
            "personnel_certificate",
            "reputation_evidence",
        }:
            add_dp(
                point_name="客观证据未以表格/清单形式承载",
                dtype="invalid_document",
                related_req=evidence_type,
                evidence_ids=linked_ids,
                reason="该 evidence_type 通常需要表格/清单，但 linked_fragment_stats.table_count=0",
            )
    else:
        rf = (feature.get("subjective_writing_features") or {}).get("rule_features") or {}
        stats = rf.get("text_stats") or {}
        cov = rf.get("coverage_terms_found") or []
        proj = rf.get("project_specific_terms") or []
        writing = rf.get("writing_structure") or []
        exec_el = rf.get("execution_elements") or []
        fmt = rf.get("format_elements") or {}

        char_count = int(stats.get("char_count", 0))
        depth = int(stats.get("max_heading_depth", 0))
        uses_table = bool(fmt.get("uses_table"))
        uses_image = bool(fmt.get("uses_image"))
        list_count = int(fmt.get("list_marker_count", 0))

        if len(cov) >= 2:
            add_sp(
                f"覆盖采购评分细则核心对象：{cov[:5]}",
                linked_ids,
                f"coverage_terms_found={len(cov)}",
                "coverage_hit",
            )
            writing_pattern_to_keep.append(
                f"按 {cov[:3]} 等核心对象逐项展开是有效的覆盖结构"
            )
        if len(proj) >= 3:
            add_sp(
                f"内容结合本项目场景：{proj[:5]}",
                linked_ids,
                f"project_specific_terms={len(proj)}",
                "project_specific_hit",
            )
            writing_pattern_to_keep.append("把通用方案绑定到本项目场景和专有名词")
        if depth >= 2 and writing:
            add_sp(
                "文本具备清晰层级和模块化结构",
                linked_ids,
                f"max_heading_depth={depth} writing_structure={len(writing)}",
                "structure_hit",
            )
        if len(exec_el) >= 4:
            add_sp(
                f"覆盖执行要素：{exec_el[:5]}",
                linked_ids,
                f"execution_elements={len(exec_el)}",
                "execution_hit",
            )
        if uses_table or uses_image or list_count >= 5:
            add_sp(
                "表达形式多样（含表格/图示/清单）",
                linked_ids,
                f"uses_table={uses_table} uses_image={uses_image} list_marker_count={list_count}",
                "format_hit",
            )

        if len(cov) == 0:
            add_dp(
                f"未明确覆盖评分细则关键对象「{criterion.get('object', '')}」",
                "coverage_gap",
                criterion.get("object", ""),
                linked_ids,
                "coverage_terms_found 为空",
            )
            writing_pattern_to_improve.append(
                f"补充明确覆盖 {criterion.get('object', '')} 的内容"
            )
        if char_count < 500 and linked_ids:
            add_dp(
                f"展开深度不足（仅 {char_count} 字）",
                "depth_gap",
                criterion.get("feature", ""),
                linked_ids,
                f"linked 片段总 char_count={char_count} 偏短",
            )
            writing_pattern_to_improve.append("增加对核心要点的展开论述与案例细节")
        if len(proj) == 0:
            add_dp(
                "未结合本项目专有名词/场景",
                "project_specific_gap",
                "本项目场景",
                linked_ids,
                "project_specific_terms 为空",
            )
            writing_pattern_to_improve.append("把通用模板与本项目业务对象/术语绑定")
        if len(exec_el) == 0:
            add_dp(
                "缺少可执行要素（步骤、计划、责任、交付、验收）",
                "execution_gap",
                criterion.get("feature", ""),
                linked_ids,
                "execution_elements 为空",
            )
            writing_pattern_to_improve.append("补充阶段、责任、交付物、验收闭环等可执行要素")
        if (not uses_table) and (not uses_image) and list_count < 3 and linked_ids:
            add_dp(
                "缺乏表格/图示/清单等结构化载体",
                "evidence_gap",
                criterion.get("feature", ""),
                linked_ids,
                "无表/图且列表项稀少（list_marker_count<3）",
            )
            writing_pattern_to_improve.append("用表格或图示承载关键信息，便于评审定位")

    if score_level == "total":
        actual_score: Any = None
        score_status = (
            "below_max_aggregate" if (scoring_points or deduction_points) else "unknown"
        )
        confidence = "low_total_only"
        analysis_source = "rule_based_total_only"
    elif score_level == "criterion":
        actual_score = None
        score_status = "criterion_score_pending_inject"
        confidence = "pending_criterion_score"
        analysis_source = "rule_based"
    else:
        actual_score = None
        score_status = "unknown"
        confidence = "unknown"
        analysis_source = "rule_based"

    return {
        "criterion_id": criterion["criterion_id"],
        "score_unit_id": criterion["score_unit_id"],
        "score_unit_name": criterion["score_unit_name"],
        "criterion_name": criterion["criterion_name"],
        "scoring_type": scoring_type,
        "max_score": max_score,
        "actual_score": actual_score,
        "lost_score": None,
        "score_status": score_status,
        "linked_fragment_ids": linked_ids,
        "scoring_points": scoring_points,
        "deduction_points": deduction_points,
        "writing_pattern_to_keep": writing_pattern_to_keep,
        "writing_pattern_to_improve": writing_pattern_to_improve,
        "confidence": confidence,
        "analysis_source": analysis_source,
    }


TIER_COEFFICIENT_TABLE: dict[str, float] = {
    "T1_incumbent":       1.35,
    "T2_same_buyer":      1.25,
    "T3_similar_project": 1.15,
    "T4_same_region":     1.08,
    "T5_generic":         1.00,
}


def classify_tier_from_features(features: dict[str, Any]) -> str:
    """从 tier_features 反推 tier_label。优先级 T1 > T2 > T3 > T4 > T5。"""
    if features.get("is_incumbent"):
        return "T1_incumbent"
    if (features.get("same_buyer_history_count") or 0) >= 1:
        return "T2_same_buyer"
    if (features.get("similar_project_count") or 0) >= 1:
        return "T3_similar_project"
    if features.get("same_region"):
        return "T4_same_region"
    return "T5_generic"


def resolve_tier_for_bidder(
    bidder: dict[str, Any],
    table: dict[str, float] | None = None,
) -> tuple[str, float]:
    """从 bidder.tier_features 拿 tier_label/coefficient；缺字段时按特征推断 + 查表。"""
    table = table or TIER_COEFFICIENT_TABLE
    tf = bidder.get("tier_features") or {}
    label = tf.get("tier_label") or classify_tier_from_features(tf)
    coefficient = tf.get("coefficient")
    if not isinstance(coefficient, (int, float)):
        coefficient = table.get(label, 1.00)
    return label, float(coefficient)


def apply_tier_coefficient_to_analyses(
    analyses: list[dict[str, Any]],
    tier_label: str,
    coefficient: float,
) -> None:
    """对每条 analysis：actual_score 改名为 base_score，actual_score = min(base × c, max_score)。

    out_of_scope（如报价分）保持原 actual_score=null 不变。
    """
    for entry in analyses:
        if any(
            dp.get("deduction_type") == "not_in_technical_scope"
            for dp in (entry.get("deduction_points") or [])
        ):
            entry["tier_label"] = tier_label
            entry["tier_coefficient"] = coefficient
            entry["base_score"] = None
            continue
        base = entry.get("actual_score")
        entry["tier_label"] = tier_label
        entry["tier_coefficient"] = coefficient
        if isinstance(base, (int, float)):
            entry["base_score"] = round(float(base), 2)
            max_score = entry.get("max_score") or 0
            boosted = float(base) * coefficient
            if max_score:
                boosted = min(boosted, float(max_score))
            entry["actual_score"] = round(boosted, 2)
            if max_score:
                entry["lost_score"] = round(float(max_score) - entry["actual_score"], 2)
        else:
            entry["base_score"] = None


SCORING_POINT_TYPES = (
    "coverage_hit",
    "project_specific_hit",
    "structure_hit",
    "execution_hit",
    "format_hit",
    "evidence_count_hit",
    "threshold_hit",
    "document_valid",
    "formula_valid",
)

DEDUCTION_POINT_TYPES = (
    "coverage_gap",
    "depth_gap",
    "project_specific_gap",
    "execution_gap",
    "evidence_gap",
    "missing_evidence",
    "count_not_enough",
    "threshold_not_met",
    "invalid_document",
    "not_in_technical_scope",
)


def build_mimo_attribution_messages(
    rule_analysis: dict[str, Any],
    criterion: dict[str, Any],
    feature: dict[str, Any],
    linked_fragments_text: dict[str, str],
    total_constraint: dict[str, Any],
) -> list[dict[str, str]]:
    fragment_excerpts: list[str] = []
    for fid, text in linked_fragments_text.items():
        excerpt = (text or "").strip()[:800]
        if excerpt:
            fragment_excerpts.append(f"片段 {fid}:\n{excerpt}")
    fragments_str = "\n\n".join(fragment_excerpts) if fragment_excerpts else "（无命中片段）"

    feature_brief: dict[str, Any] = {
        "scoring_type": feature.get("scoring_type"),
        "mapping_status": feature.get("mapping_status"),
        "linked_fragment_count": len(feature.get("linked_fragment_ids") or []),
    }
    if feature.get("subjective_writing_features"):
        rf = (feature["subjective_writing_features"] or {}).get("rule_features") or {}
        feature_brief["subjective_signals"] = {
            "text_stats": rf.get("text_stats"),
            "coverage_terms_found": rf.get("coverage_terms_found"),
            "project_specific_terms": rf.get("project_specific_terms"),
            "execution_elements": rf.get("execution_elements"),
            "format_elements": rf.get("format_elements"),
        }
    if feature.get("objective_evidence_features"):
        of = feature["objective_evidence_features"] or {}
        feature_brief["objective_signals"] = {
            "evidence_type": of.get("evidence_type"),
            "verification_mode": of.get("verification_mode"),
            "required_evidence_terms_from_criterion": of.get("required_evidence_terms_from_criterion"),
            "detected_evidence_terms_in_linked_fragments": of.get("detected_evidence_terms_in_linked_fragments"),
            "linked_fragment_stats": of.get("linked_fragment_stats"),
        }

    max_score = rule_analysis.get("max_score") or 0
    sp_types_str = "、".join(SCORING_POINT_TYPES)
    dp_types_str = "、".join(DEDUCTION_POINT_TYPES)
    criterion_payload = {
        "criterion_id": criterion["criterion_id"],
        "score_unit_name": criterion["score_unit_name"],
        "criterion_name": criterion["criterion_name"],
        "object": criterion.get("object"),
        "feature": criterion.get("feature"),
        "evaluation_method": criterion.get("evaluation_method"),
        "raw_text": (criterion.get("raw_text") or "")[:800],
    }
    rule_payload = {
        "rule_scoring_points": rule_analysis.get("scoring_points", []),
        "rule_deduction_points": rule_analysis.get("deduction_points", []),
    }

    return [
        {
            "role": "system",
            "content": (
                "你是采购评分得分点扣分点归因器，按 .md §9.6 口径工作。"
                "对单条评分细则在最终总分约束下做归因式打分。\n"
                "硬约束：\n"
                f"1. estimated_actual_score 必须是 [0, {max_score}] 内的数值。\n"
                "2. evidence_text 只能逐字从给定 fragment 原文中摘录（不超过 200 字），不得改写不得新增。\n"
                "3. 不得新增采购文件没有的评分要求。\n"
                "4. 主观项关注：覆盖度、深度、项目化、执行性、证据形式；客观项关注：材料齐全、数量门槛、有效性。\n"
                f"5. scoring_points 的 point_type 必须从词表选择：{sp_types_str}。\n"
                f"6. deduction_points 的 deduction_type 必须从词表选择：{dp_types_str}。\n"
                "7. 没有命中片段时不得猜测 evidence_text，只能列扣分点。\n"
                "8. 输出必须是合法 JSON。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"投标人最终总分约束：实际 {total_constraint.get('actual_total')} / "
                f"满分 {total_constraint.get('max_total')}，整体失 {total_constraint.get('lost_total')} 分。"
                f"本细则 max_score={max_score} 分；scoring_type={criterion.get('scoring_type')}。\n\n"
                f"采购评分细则：\n{json.dumps(criterion_payload, ensure_ascii=False, indent=2)}\n\n"
                f"特征信号：\n{json.dumps(feature_brief, ensure_ascii=False, indent=2)}\n\n"
                f"已映射投标片段原文：\n{fragments_str}\n\n"
                f"规则版分析（参考，可采纳/驳斥/补充）：\n{json.dumps(rule_payload, ensure_ascii=False)}\n\n"
                "请输出 JSON 对象：\n"
                "{\n"
                f'  "estimated_actual_score": <float in [0, {max_score}]>,\n'
                '  "scoring_points": [{"point_type": "...", "point_name": "...", "evidence_fragment_ids": ["BF-xxxx"], "evidence_text": "原文摘录", "basis": "..."}],\n'
                '  "deduction_points": [{"deduction_type": "...", "point_name": "...", "evidence_fragment_ids": [], "evidence_text": "", "deduction_reason": "..."}],\n'
                '  "writing_pattern_to_keep": ["..."],\n'
                '  "writing_pattern_to_improve": ["..."]\n'
                "}"
            ),
        },
    ]


def mimo_attribute_one_criterion(
    rule_analysis: dict[str, Any],
    criterion: dict[str, Any],
    feature: dict[str, Any],
    linked_fragments_text: dict[str, str],
    total_constraint: dict[str, Any],
    config: dict[str, str],
) -> dict[str, Any]:
    """按 .md §9.6 用 MiMo 做归因式打分，失败回退到规则版。

    out_of_scope（如报价分）保留 rule_analysis 不动。
    """
    is_out_of_scope = any(
        dp.get("deduction_type") == "not_in_technical_scope"
        for dp in (rule_analysis.get("deduction_points") or [])
    )
    if is_out_of_scope:
        return rule_analysis

    messages = build_mimo_attribution_messages(
        rule_analysis, criterion, feature, linked_fragments_text, total_constraint
    )
    try:
        content = openai_compatible_chat(config, messages, max_tokens=1800, timeout_seconds=60)
        parsed = extract_json_object(content)
    except Exception as exc:
        print(f"mimo attribution failed for {criterion['criterion_id']}: {exc}")
        return rule_analysis

    enhanced = dict(rule_analysis)
    max_score = enhanced.get("max_score") or 0
    actual = parsed.get("estimated_actual_score")
    if isinstance(actual, (int, float)) and max_score:
        clamped = max(0.0, min(float(max_score), float(actual)))
        enhanced["actual_score"] = round(clamped, 2)
        enhanced["lost_score"] = round(max_score - enhanced["actual_score"], 2)
        enhanced["score_status"] = (
            "max_score" if abs(max_score - enhanced["actual_score"]) < 1e-6
            else "zero_score" if enhanced["actual_score"] < 1e-6
            else "partial_score"
        )

    def _merge_points(
        rule_points: list[dict[str, Any]],
        parsed_points: list[dict[str, Any]] | None,
        type_key: str,
        allowed: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        if not isinstance(parsed_points, list):
            return rule_points
        merged: list[dict[str, Any]] = []
        counter = 0
        prefix = "SP" if type_key == "point_type" else "DP"
        for mp in parsed_points:
            if not isinstance(mp, dict):
                continue
            ptype = (mp.get(type_key) or "").strip()
            if ptype not in allowed:
                continue
            counter += 1
            entry: dict[str, Any] = {
                "point_id": f"{prefix}-{counter:03d}",
                type_key: ptype,
                "point_name": normalize_text(str(mp.get("point_name", "")))[:200],
                "evidence_fragment_ids": [
                    str(fid) for fid in (mp.get("evidence_fragment_ids") or []) if fid
                ],
                "evidence_text": normalize_text(str(mp.get("evidence_text", "")))[:400],
            }
            if type_key == "point_type":
                entry["basis"] = normalize_text(str(mp.get("basis", "")))[:200]
            else:
                entry["related_requirement"] = normalize_text(str(mp.get("related_requirement", "")))[:120]
                entry["deduction_reason"] = normalize_text(str(mp.get("deduction_reason", "")))[:300]
                entry["deduction_score_estimate"] = mp.get("deduction_score_estimate")
            merged.append(entry)
        return merged if merged else rule_points

    enhanced["scoring_points"] = _merge_points(
        enhanced.get("scoring_points", []), parsed.get("scoring_points"), "point_type", SCORING_POINT_TYPES
    )
    enhanced["deduction_points"] = _merge_points(
        enhanced.get("deduction_points", []), parsed.get("deduction_points"), "deduction_type", DEDUCTION_POINT_TYPES
    )

    def _string_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [normalize_text(str(item))[:300] for item in value if str(item).strip()]

    keep = _string_list(parsed.get("writing_pattern_to_keep"))
    improve = _string_list(parsed.get("writing_pattern_to_improve"))
    if keep:
        enhanced["writing_pattern_to_keep"] = keep
    if improve:
        enhanced["writing_pattern_to_improve"] = improve

    enhanced["confidence"] = "mimo_attributed_total_constrained"
    enhanced["analysis_source"] = "rule_based_then_mimo_attributed"
    return enhanced


def analyze_score_points(
    criteria: list[dict[str, Any]],
    mappings: list[dict[str, Any]],
    features: list[dict[str, Any]],
    fragments: list[dict[str, Any]],
    final_scores: dict[str, Any],
    use_mimo: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    if SCORE_POINT_ANALYSIS_JSON.exists() and not force:
        print(f"skip score point analysis: output exists {SCORE_POINT_ANALYSIS_JSON}")
        return json.loads(SCORE_POINT_ANALYSIS_JSON.read_text(encoding="utf-8"))

    target = find_target_bidder(final_scores)
    if target is None:
        raise RuntimeError("final_scores.json has no is_target=true bidder; cannot analyze")
    score_level = get_target_score_level(target)
    target_scores = target.get("scores") or []
    total_actual = target_scores[0].get("actual_score") if target_scores else None
    total_max = target_scores[0].get("max_score") if target_scores else None
    total_lost = (
        round(float(total_max) - float(total_actual), 2)
        if isinstance(total_actual, (int, float)) and isinstance(total_max, (int, float))
        else None
    )
    total_constraint = {
        "actual_total": total_actual,
        "max_total": total_max,
        "lost_total": total_lost,
    }

    features_by_cid = {f["criterion_id"]: f for f in features}
    criteria_by_cid = {c["criterion_id"]: c for c in criteria}
    fragments_by_id = {f["fragment_id"]: f for f in fragments}

    mimo_config = get_mimo_config() if use_mimo else None
    method = (
        "rule_based_then_mimo_attributed_total_constrained_v0"
        if mimo_config
        else "rule_based_score_point_analysis_total_only_v0"
    )

    analyses: list[dict[str, Any]] = []
    total_mappings = len(mappings)
    for index, mapping in enumerate(mappings, start=1):
        cid = mapping["criterion_id"]
        criterion = criteria_by_cid.get(cid)
        feature = features_by_cid.get(cid)
        if not criterion or not feature:
            continue
        rule_analysis = analyze_one_criterion(criterion, feature, score_level)
        if mimo_config:
            linked_text = {
                fid: " ".join(
                    filter(
                        None,
                        [
                            fragments_by_id.get(fid, {}).get("text", ""),
                            fragments_by_id.get(fid, {}).get("table_text", ""),
                        ],
                    )
                )
                for fid in (rule_analysis.get("linked_fragment_ids") or [])
            }
            print(
                f"[attribute {index}/{total_mappings}] {cid} "
                f"sp={len(rule_analysis.get('scoring_points', []))} "
                f"dp={len(rule_analysis.get('deduction_points', []))} "
                f"fragments={len(linked_text)}",
                flush=True,
            )
            rule_analysis = mimo_attribute_one_criterion(
                rule_analysis, criterion, feature, linked_text, total_constraint, mimo_config
            )
        analyses.append(rule_analysis)

    tier_table = (
        final_scores.get("tier_coefficient_table") or TIER_COEFFICIENT_TABLE
    )
    tier_label, tier_coefficient = resolve_tier_for_bidder(target, tier_table)
    apply_tier_coefficient_to_analyses(analyses, tier_label, tier_coefficient)
    print(
        f"applied tier_coefficient {tier_coefficient} ({tier_label}) to "
        f"{len(analyses)} analyses for target bidder"
    )

    result = {
        "source": {
            "procurement_criteria": relative_path(PROCUREMENT_CRITERIA_JSON),
            "bid_response_fragments": relative_path(BID_FRAGMENTS_JSON),
            "procurement_bid_mapping": relative_path(PROCUREMENT_BID_MAPPING_JSON),
            "criterion_response_features": relative_path(CRITERION_RESPONSE_FEATURES_JSON),
            "final_scores": relative_path(FINAL_SCORES_JSON),
            "method": method,
            "task": "score_point_and_deduction_point_analysis_under_final_score_constraint",
        },
        "target_bidder": {
            "bidder_id": target.get("bidder_id"),
            "name": target.get("name"),
            "rank": target.get("rank"),
            "score_level": score_level,
            "actual_total_score": total_actual,
            "max_total_score": total_max,
            "lost_total_score": (
                round(total_max - total_actual, 2)
                if isinstance(total_actual, (int, float))
                and isinstance(total_max, (int, float))
                else None
            ),
            "tier_label": tier_label,
            "tier_coefficient": tier_coefficient,
            "tier_features": target.get("tier_features"),
        },
        "tier_coefficient_table": dict(tier_table) if isinstance(tier_table, dict) else None,
        "analyses": analyses,
    }
    SCORE_POINT_ANALYSIS_JSON.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_score_point_analysis_md(result)
    print(f"score point analysis: analyses={len(analyses)} score_level={score_level}")
    return result


def write_score_point_analysis_md(result: dict[str, Any]) -> None:
    target = result["target_bidder"]
    lines = ["# 得分点与扣分点分析数据集", ""]
    lines.append(f"投标人：{target.get('name')}（排名 {target.get('rank')}）")
    lines.append(
        f"得分粒度：{target.get('score_level')} | 总分：{target.get('actual_total_score')} "
        f"/ {target.get('max_total_score')} | 失分：{target.get('lost_total_score')}"
    )
    lines.append("")
    lines.append(
        "score_level=total 时所有条目 confidence=low_total_only；仅用于识别项目整体倾向性的薄弱单元，"
        "不可下推到具体单元/细则当作真实得分。"
    )
    lines.append("")

    for item in result["analyses"]:
        lines.append(
            f"## {item['criterion_id']} {item['score_unit_name']} / {item['criterion_name']} / {item['scoring_type']}"
        )
        lines.append("")
        lines.append(
            f"max={item['max_score']} status={item['score_status']} "
            f"confidence={item['confidence']} linked={len(item['linked_fragment_ids'])}"
        )
        lines.append("")
        if item["scoring_points"]:
            lines.append("### 得分点")
            for sp in item["scoring_points"]:
                lines.append(f"- [{sp['point_type']}] {sp['point_name']}")
                if sp.get("basis"):
                    lines.append(f"  - basis: {sp['basis']}")
        if item["deduction_points"]:
            lines.append("### 扣分点")
            for dp in item["deduction_points"]:
                lines.append(f"- [{dp['deduction_type']}] {dp['point_name']}")
                if dp.get("deduction_reason"):
                    lines.append(f"  - reason: {dp['deduction_reason']}")
        if item["writing_pattern_to_keep"]:
            lines.append("### 建议保留的写作模式")
            for p in item["writing_pattern_to_keep"]:
                lines.append(f"- {p}")
        if item["writing_pattern_to_improve"]:
            lines.append("### 建议改进的写作模式")
            for p in item["writing_pattern_to_improve"]:
                lines.append(f"- {p}")
        lines.append("")
    SCORE_POINT_ANALYSIS_MD.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def run_analysis_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    criteria = load_final_dataset(PROCUREMENT_CRITERIA_JSON, "criteria")
    mappings = load_final_dataset(PROCUREMENT_BID_MAPPING_JSON, "mappings")
    features = load_final_dataset(CRITERION_RESPONSE_FEATURES_JSON, "features")
    fragments = load_final_dataset(BID_FRAGMENTS_JSON, "fragments")
    if not FINAL_SCORES_JSON.exists():
        raise FileNotFoundError(
            f"Missing required dataset: {FINAL_SCORES_JSON}; create final_scores.json first per .md §9.1"
        )
    final_scores = json.loads(FINAL_SCORES_JSON.read_text(encoding="utf-8"))
    return analyze_score_points(
        criteria,
        mappings,
        features,
        fragments,
        final_scores,
        use_mimo=not args.skip_mimo,
        force=args.force_analysis or args.force_features or args.force_mimo,
    )


def run_feature_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    criteria = load_final_dataset(PROCUREMENT_CRITERIA_JSON, "criteria")
    fragments = load_final_dataset(BID_FRAGMENTS_JSON, "fragments")
    mappings = load_final_dataset(PROCUREMENT_BID_MAPPING_JSON, "mappings")
    return extract_criterion_response_features(
        criteria,
        fragments,
        mappings,
        use_mimo=not args.skip_mimo,
        force=args.force_features or args.force_mimo,
    )


def load_score_units_for_bid_annotation() -> list[dict[str, Any]]:
    path = PROCUREMENT_UNITS_MIMO_JSON if PROCUREMENT_UNITS_MIMO_JSON.exists() else PROCUREMENT_UNITS_JSON
    if not path.exists():
        raise FileNotFoundError(f"Missing procurement score units: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["score_units"]


def run_procurement_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    page_range = save_scoring_page_range(PROCUREMENT_PDF)
    scoring_pages = list(range(page_range.page_start, page_range.page_end + 1))
    print(f"detected scoring pages: {page_range.page_start}-{page_range.page_end}")

    if not args.skip_pp:
        render_scoring_pages(
            PROCUREMENT_PDF,
            page_range.page_start,
            page_range.page_end,
            force=args.force_pp,
        )
        run_pp_structurev3(page_range.page_start, page_range.page_end, force=args.force_pp)

    units_json = split_score_units_from_pp(scoring_pages)
    if not args.skip_mimo:
        refine_score_units_with_mimo(units_json, force=args.force_mimo)
        score_units = load_score_units_for_bid_annotation()
    else:
        score_units = units_json["score_units"]
    extract_procurement_criteria(
        score_units,
        use_mimo=not args.skip_mimo,
        force=args.force_mimo,
    )
    return units_json


def run_bid_pipeline(args: argparse.Namespace) -> None:
    score_units = load_score_units_for_bid_annotation()
    sections = split_bid_technical_docx(BID_DOCX)
    annotations = annotate_bid_sections(sections, score_units)
    write_bid_outputs(sections, annotations)
    fragments_json = build_bid_response_fragments(sections, force=args.force_mimo)

    if PROCUREMENT_CRITERIA_JSON.exists() and not args.force_mimo:
        criteria_json = json.loads(PROCUREMENT_CRITERIA_JSON.read_text(encoding="utf-8"))
    else:
        criteria_json = extract_procurement_criteria(
            score_units,
            use_mimo=not args.skip_mimo,
            force=args.force_mimo,
        )
    mapping_json = map_criteria_to_bid_fragments(
        criteria_json["criteria"],
        fragments_json["fragments"],
        use_mimo=not args.skip_mimo,
        force=args.force_mimo,
    )
    extract_criterion_response_features(
        criteria_json["criteria"],
        fragments_json["fragments"],
        mapping_json["mappings"],
        use_mimo=not args.skip_mimo,
        force=args.force_features or args.force_mimo,
    )
    print(
        f"bid technical sections: sections={len(sections)} "
        f"fragments={len(fragments_json['fragments'])} score_units={len(score_units)}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run procurement and bid dataset extraction.")
    parser.add_argument("--procurement-only", action="store_true", help="Only run procurement scoring extraction.")
    parser.add_argument("--bid-only", action="store_true", help="Only run bid technical split and annotation.")
    parser.add_argument("--features-only", action="store_true", help="Only extract response text features from final datasets.")
    parser.add_argument("--analysis-only", action="store_true", help="Only run score point analysis (requires final_scores.json).")
    parser.add_argument("--skip-pp", action="store_true", help="Use existing PP-StructureV3 output.")
    parser.add_argument("--force-pp", action="store_true", help="Run PP-StructureV3 even if page outputs exist.")
    parser.add_argument("--skip-mimo", action="store_true", help="Skip all MiMo calls and use rule-based fallbacks.")
    parser.add_argument("--force-mimo", action="store_true", help="Re-run MiMo and derived outputs even if output exists.")
    parser.add_argument("--force-features", action="store_true", help="Rebuild criterion response feature outputs.")
    parser.add_argument("--force-analysis", action="store_true", help="Rebuild score point analysis output.")
    parser.add_argument("--skip-analysis", action="store_true", help="Skip the score point analysis stage even if final_scores.json exists.")
    return parser.parse_args()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    args = parse_args()
    if args.procurement_only and args.bid_only:
        raise SystemExit("--procurement-only and --bid-only cannot be used together")
    exclusives = sum(
        bool(flag)
        for flag in (args.procurement_only, args.bid_only, args.features_only, args.analysis_only)
    )
    if exclusives > 1:
        raise SystemExit(
            "--procurement-only / --bid-only / --features-only / --analysis-only are mutually exclusive"
        )

    if args.features_only:
        run_feature_pipeline(args)
        print(f"output: {OUT_DIR}")
        return

    if args.analysis_only:
        run_analysis_pipeline(args)
        print(f"output: {OUT_DIR}")
        return

    if not args.bid_only:
        run_procurement_pipeline(args)
    if not args.procurement_only:
        run_bid_pipeline(args)

    if not args.procurement_only and not args.skip_analysis and FINAL_SCORES_JSON.exists():
        run_analysis_pipeline(args)

    print(f"output: {OUT_DIR}")


if __name__ == "__main__":
    main()
