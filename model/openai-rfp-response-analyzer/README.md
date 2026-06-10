# 标小易（OpenBidKit_Yibiao）数据集构建与得扣分分析

中文政府采购场景下的"采购评分细则 ↔ 投标响应片段 ↔ 评委实际得分"端到端数据集构建工具。采购 PDF 经 PaddleOCR PP-StructureV3 提取评分表 → MiMo 拆分评分细则；投标 DOCX/PDF 按标题切响应片段；MiMo 在最终评委总分约束下做归因式打分；规则系数捕捉隐形加分（同甲方/类似项目/本地化）。

> Fork 自 [`lesteroliver911/openai-rfp-response-analyzer`](https://github.com/lesteroliver911/openai-rfp-response-analyzer)，主进程入口和 UI 框架保留，业务管线、数据契约、模型链全部替换为中文招投标场景，并对接同目录 `../run_extraction_pipeline.py` 流水线。

## 1. 项目流程一览

```
┌─ 采购 PDF (可多份) ─┐                                  ┌─ 投标 DOCX/PDF (可多份) ─┐
│                    │                                  │                          │
│ pdftotext 关键词 → 评分页定位                          │ DOCX OOXML / PDF 标题切  │
│ pdftoppm 180 DPI → PNG                                │     section              │
│ PP-StructureV3 (GPU)                                  │     ↓                    │
│   OCR + 表格识别                                      │ source_bid_file 标记     │
│ 几何切列状态机                                        │     ↓                    │
│ → score_unit 草稿                                     │ 跨文件重编号             │
│ source_procurement_file 标记                          │     BID-SEC-NNNN         │
│     ↓                                                 │     ↓                    │
│ 跨文件重编号 TU-DRAFT-NNN                             │ 关键词召回 → 候选片段     │
│     ↓                                                 │     ↓                    │
│ LLM OCR 文本规整 (deepseek-v4-pro)                    │ 过滤空 section →         │
│     ↓                                                 │     bid_response_fragments│
│ 按 (3分) 正则拆 criterion                             │                          │
│ + MiMo 补 object/feature/scoring_type                 │                          │
│ → procurement_scoring_criteria                        │                          │
└──────────────┬─────────────────────────┬──────────────┘
               │                         │
               ▼                         ▼
        ┌───────────────────────────────────────┐
        │   采购-投标映射 (procurement_bid_mapping) │
        │   关键词召回 + MiMo 命中 + 结构兜底       │
        │   linked_bid_fragments (契约 5 字段)     │
        └────────────────┬──────────────────────┘
                         │
                         ▼
        ┌───────────────────────────────────────┐
        │   响应文本特征 (criterion_response_features)│
        │   规则 11 维特征 + MiMo 主观写作结构抽取    │
        │   evidence_type / coverage_terms / 等     │
        └────────────────┬──────────────────────┘
                         │
                         ▼
        ┌───────────────────────────────────────┐
        │   final_scores.json（人工/OCR 录入）      │
        │   target bidder + tier_features          │
        └────────────────┬──────────────────────┘
                         │
                         ▼
        ┌───────────────────────────────────────┐
        │   得扣分分析 (score_point_analysis)        │
        │   1. analyze_one_criterion 规则 SP/DP    │
        │   2. mimo_attribute_one_criterion 归因   │
        │      MiMo 看 features+linked 给 base_score│
        │   3. apply_tier_coefficient                │
        │      actual_score = base × tier_coef        │
        │   confidence: mimo_attributed_total_constrained│
        └───────────────────────────────────────┘
```

## 2. 八阶段模型清单

| 阶段 | 算法 / 模型 |
|------|-------------|
| 采购评分表定位 | Poppler `pdfinfo` + `pdftotext` + 关键词正则；图片直接作为评分表页 |
| 采购评分表文档提取 | **PaddleOCR PP-StructureV3**（GPU + 表格识别），含 PP-DocLayout_plus-L / PP-OCRv5_server_det/rec / SLANeXt_wired / SLANet_plus / RT-DETR-L_wired/wireless_table_cell_det 等 |
| 评分单元文本规整 | **DeepSeek V4 `deepseek-v4-pro`**（OpenAI 兼容 `/chat/completions`），仅机械整理 OCR 断行 |
| 评分细则拆分与标注 | 规则正则切 `(N 分)` + MiMo 补 `object/feature/evaluation_method/scoring_type` |
| 投标响应片段切分 | DOCX OOXML 标题解析 / PDF 文本标题规则切 / 图片引用占位 |
| 采购-投标映射 | 关键词加权召回 (top-10) → MiMo 命中判断 → 结构规则兜底 (top_direction AND) |
| 响应文本特征 | 规则 11 维（coverage_terms / project_specific_terms / execution_elements / format_elements 等）+ MiMo 主观写作结构抽取 |
| 得扣分分析 | 规则 SP/DP (5+5 类) → MiMo 在总分约束下归因打 `estimated_actual_score` → 乘 tier_coefficient |

> 工具栈：Python 3.12 + Flask 3.0 + PaddlePaddle-GPU 3.3.1 (CUDA 12.6) + PaddleOCR + python-docx (OOXML) + pypdf + openai SDK。

## 3. 数据契约（dataset_extraction_output/）

四份"契约 JSON"——所有下游分析、可视化、复核都依赖这四份：

| 文件 | 内容 | 主键 |
|------|------|------|
| `procurement_scoring_criteria.json` | 32 条评分细则，含 `object`/`feature`/`scoring_type`/`raw_text`/`source.scoring_type_source` | `criterion_id` (PC-NNN-NN) |
| `bid_response_fragments.json` | 505 条响应片段，含 `heading_path`/`top_score_direction`/`text`/`table_text`/`image_refs`/`source_bid_file` | `fragment_id` (BF-NNNN) |
| `procurement_bid_mapping.json` | criterion ↔ fragment 多对多映射，`linked_bid_fragments` 严格 5 字段 (`fragment_id`/`heading_path`/`evidence_text`/`match_reason`/`decision_source`) | `criterion_id` |
| `criterion_response_features.json` | 每条 criterion 对应的写作特征 + 客观证据特征 | `criterion_id` |

加 1 份**输入**和 1 份**输出**：

| 文件 | 类型 | 说明 |
|------|------|------|
| `final_scores.json` | 输入 | 评委最终得分（人工/OCR 录入），含 `bidders[*]` 含 `tier_features` |
| `score_point_analysis.json` | 输出 | 得扣分点 + writing_pattern + `base_score × tier_coefficient = actual_score` |

中间产物（缓存，可删）：`procurement_scoring_page_range` / `procurement_scoring_lines` / `procurement_score_units_draft` / `procurement_score_units_mimo_refined` / `bid_technical_sections` / `bid_score_unit_annotations`。

> 完整 schema 见 [`../差分标注与映射逻辑.md`](../差分标注与映射逻辑.md) §1-§9。

## 4. Web UI

> http://localhost:5001 → "标小易"

| 面板 | 内容 |
|------|------|
| **左侧上传栏** | 采购文件（可多选）+ 投标技术文件（可多选）+ 最终得分文件（可选，支持 JSON / PDF / Word / Excel / 图片，非 JSON 自动 OCR → MiMo 结构化） |
| **流程与结果** | 顶部 4 个 KPI（评分细则 / 投标片段 / 映射命中 / 得扣分分析） + 项目流程框架表 + 自评 vs 实际总分对比（含 tier 系数） + 32 张评分细则可折叠卡片 |
| **卡片**（折叠 ×3 层） | 1) 顶层：cid / scoring_type / `base × tier_coef = actual` / SP·DP·片段数 / confidence<br>2) 展开层：得分点 / 扣分点 / 建议保留/改进的写作模式 / 命中片段列表<br>3) 命中片段也可折叠：证据摘录（MiMo 摘的原文）+ 片段全文（最大 360 px 滚动） |
| **数据集问答** | 围绕当前数据集向 MiMo 提问的简易聊天 |

## 5. 安装

需要：Python 3.12、CUDA 12.6 + RTX 系列（或换成 CPU 推理）、PaddleOCR 模型缓存约 1.5 GB。

```bash
# 在仓库根创建虚拟环境
cd model
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r openai-rfp-response-analyzer/requirements.txt
pip install paddleocr paddlepaddle-gpu==3.3.1 -i https://www.paddlepaddle.org.cn/packages/stable/cu126/
```

`.env` 放 `model/.env`：

```ini
MIMO_API_KEY=sk-xxx
MIMO_BASE_URL=https://api.deepseek.com/v1   # 或其他 OpenAI 兼容 endpoint
MIMO_MODEL=deepseek-v4-pro
```

首次 PP-StructureV3 启动会从 HuggingFace / Paddle BOS 拉模型，约 1.5 GB；建议先用 [`hf-mirror.com`](https://hf-mirror.com) 加速：`export HF_ENDPOINT=https://hf-mirror.com`。

## 6. 启动

```bash
cd model/openai-rfp-response-analyzer
../.venv/bin/python main.py
```

监听 `0.0.0.0:5001`，同一内网其他机器可以访问：

```text
http://本机IPv4:5001
```

注意必须用 venv 的 python（否则 paddleocr / openai / flask 等都找不到）。Windows 推荐直接运行：

```powershell
.\start_windows_lan.bat
```

它会尝试放行 Windows 防火墙 TCP `5001`，并打印可访问的内网地址。

## 7. 命令行流水线（不走 UI）

整条流水线也可以独立运行，UI 只是它的薄包装：

```bash
cd model
.venv/bin/python run_extraction_pipeline.py            # 全套
.venv/bin/python run_extraction_pipeline.py --skip-pp  # PP 输出已存在时跳过
.venv/bin/python run_extraction_pipeline.py --skip-mimo  # 全规则、不调 MiMo
.venv/bin/python run_extraction_pipeline.py --force-mimo  # 强制重跑 MiMo
.venv/bin/python run_extraction_pipeline.py --analysis-only --force-analysis  # 只跑得扣分分析
.venv/bin/python run_extraction_pipeline.py --features-only  # 只跑响应文本特征
```

阶段开关：`--procurement-only` / `--bid-only` / `--analysis-only` / `--features-only` / `--skip-pp` / `--force-pp` / `--skip-mimo` / `--force-mimo` / `--force-features` / `--force-analysis` / `--skip-analysis`。

## 8. 关键设计与约束

| 约束 | 来源 | 实现 |
|------|------|------|
| `linked_bid_fragments` 严格 5 字段 | .md §4 | `LINKED_BID_FRAGMENT_KEYS = frozenset({...})` 在 `map_criteria_to_bid_fragments` 写入前 sanitize；缓存命中也走 `sanitize_linked_bid_fragments`；写盘用 `tempfile.mkstemp` + `Path.replace` 原子；`mapping_file_lock` (`fcntl.LOCK_EX`) 防并发 stale overwrite |
| `scoring_type ∈ {subjective, objective}` 二选一 | .md §2 | `OBJECTIVE_KEYWORDS` 模块常量；硬词命中 → `objective` + `source.scoring_type_source = keyword_objective`；未命中 → MiMo 二判后改 `model_review`；硬词命中的 objective 不允许被模型覆盖 |
| 结构兜底方向匹配 AND（非 OR）+ 空 `top_direction` 受控 fallback | .md §5.3 | `structural_rule_links` 三态门：`top_direction == unit_name` 通过；空 `top_direction` 且 `unit_name in title_text` 通过（受控 fallback for 空标题片段）；其它 skip |
| 空标题进 heading_path 占位 | .md §6.2 | `split_bid_technical_docx` 去掉 `and block.text` 条件，空标题 `heading_stack[level] = ""`，下游 fragment 过滤空内容时仍能保留路径上下文 |
| score_level=total 时 confidence 强制 `low_total_only` | .md §9.1/§9.2 | `analyze_one_criterion` 中 `score_level == "total"` 时 `actual_score=None`、`confidence=low_total_only`；MiMo 归因升级到 `mimo_attributed_total_constrained` |
| MiMo `evidence_text` 必须摘录原文不得改写 | .md §9.6 | `build_mimo_attribution_messages` prompt 硬约束 + 受 fragments_text 范围限制；解析失败自动回退规则版 |

## 9. 输出示例

```json
// procurement_bid_mapping.json
{
  "mappings": [
    {
      "criterion_id": "PC-002-01",
      "score_unit_id": "TU-DRAFT-002",
      "score_unit_name": "需求理解",
      "criterion_name": "应用环境、体系结构需求和实施要求等需求内容的理解程度",
      "linked_bid_fragments": [
        {
          "fragment_id": "BF-0002",
          "heading_path": ["需求理解", "应用环境、体系结构需求与实施要求的理解", "应用环境需求的深度理解"],
          "evidence_text": "本项目立足闵行区绿化市容局生活垃圾分类智慧收运系统的实际应用场景...",
          "match_reason": "标题路径明确响应应用环境理解",
          "decision_source": "deepseek-v4-pro"
        }
      ],
      "candidate_fragment_ids": ["BF-0002", "BF-0003", "..."]
    }
  ]
}
```

```json
// score_point_analysis.json (片段)
{
  "target_bidder": {
    "name": "上海荟宸信息科技有限公司",
    "rank": 2,
    "score_level": "total",
    "actual_total_score": 73.63,
    "max_total_score": 100,
    "lost_total_score": 26.37,
    "tier_label": "T4_same_region",
    "tier_coefficient": 1.08
  },
  "analyses": [
    {
      "criterion_id": "PC-002-01",
      "scoring_type": "subjective",
      "max_score": 3.0,
      "base_score": 2.8,
      "tier_coefficient": 1.08,
      "actual_score": 3.0,
      "lost_score": 0.0,
      "confidence": "mimo_attributed_total_constrained",
      "analysis_source": "rule_based_then_mimo_attributed",
      "scoring_points": [
        {
          "point_id": "SP-001",
          "point_type": "coverage_hit",
          "point_name": "覆盖采购评分细则核心对象：应用环境、实施要求",
          "evidence_fragment_ids": ["BF-0002", "BF-0003"],
          "evidence_text": "本项目立足闵行区..."
        }
      ],
      "deduction_points": [],
      "writing_pattern_to_keep": ["按 ['应用环境', '实施要求'] 等核心对象逐项展开"]
    }
  ]
}
```

## 10. 隐形加分（tier coefficient）

按"亲疏远近"给评委的潜在偏好建模：

```
T1_incumbent        × 1.35   上一期承做方
T2_same_buyer       × 1.25   同甲方历史
T3_similar_project  × 1.15   同业务类似项目
T4_same_region      × 1.08   本地公司
T5_generic          × 1.00   兜底
```

每个 bidder 在 `final_scores.json.bidders[*].tier_features` 中标 `is_incumbent / same_buyer_history_count / similar_project_count / same_region`，函数 `classify_tier_from_features` 推导 `tier_label`，查表得 `coefficient`。最终 `actual_score = base_score × coefficient`（capped at `max_score`）。

当前是查表版（方案 A）。攒到 20+ 项目可升级为线性 + 单调约束（B），50+ 项目可上 XGBoost monotone GBDT（C）。详细 fitting 路线见仓库 chat 历史。

## 11. Codex 监督回路

`run_extraction_pipeline.py` 经过 6 轮 `/codex:adversarial-review`，最终 `verdict: approve`。主要发现与修复都已在第 8 节"关键设计与约束"中体现：

| Round | Finding | 修复 |
|-------|---------|------|
| 1 | cache 命中跳过 linked_bid_fragments sanitize / 结构兜底方向匹配过松 | sanitize 函数 + AND 收紧 + 受控 fallback |
| 2 | 只清内存没清磁盘 | sort_keys 比对 + 原子 atomic_write_mapping 回写 |
| 3 | 共享 `.json.tmp` 文件名并发碰撞 | `tempfile.mkstemp` 唯一名 |
| 4 | stale writer 覆盖 fresh writer | `fcntl.flock` 互斥锁 + sidecar `.lock` 文件 |
| 5 | cache-vanished fall-through 仍可能覆盖 | 锁内 final exists 二次检查 + honor 别人结果 |
| 6 | — | approve |

## 12. 测试数据

`model/AI测试数据-闵行区绿化市容生活垃圾分类智慧收运系统建设项目2026-4-13/` 自带：

- 采购 PDF（含评分表 27-32 页）
- 投标 DOCX（上海荟宸，落选 2 号）
- 开标 PNG（5 家投标人 + 报价 + 工期）
- 中标结果 PNG（第 1 名 89.48 / 第 2 名 73.63）
- 评分细则标注 PDF（评委手工色块标注）

## License

MIT（继承自上游）。

---

> 项目原仓库：[`lesteroliver911/openai-rfp-response-analyzer`](https://github.com/lesteroliver911/openai-rfp-response-analyzer)
> 本 fork：中文政府采购 + 评委归因 + 隐形加分。
