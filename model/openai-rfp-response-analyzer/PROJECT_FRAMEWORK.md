# 标小易数据集构建与映射项目框架

本应用不是通用 RFP Analyzer，而是对 `model/run_extraction_pipeline.py` 的 Web 包装。目标是把采购文件和投标技术文件拆成可对齐的数据集，并在映射之后继续形成响应文本特征、得分点和扣分点结构。

## 输入边界

| 输入 | 当前支持 | 说明 |
|------|----------|------|
| 采购文件 | PDF / 图片 / Word等相关文档 | PDF会先渲染成图片，图片可直接进入PP-StructureV3；Word等原始文档先作为源文件保存，后续补转换器 |
| 投标技术文件 | DOCX / PDF / 图片 / Word等相关文档 | DOCX 走标题层级解析；PDF 走文本标题规则切分；图片先作为图片响应片段；长文本按约1500字切成可召回片段 |
| 最终得分 | JSON / PDF / Word / 图片等相关文档 | JSON会保存为 `final_scores.json` 并参与得扣分分析；图片/PDF/Word先保存为原始得分文件，后续结构化 |

## 模型与算法

| 阶段 | 模型或算法 | 输入 | 输出 |
|------|------------|------|------|
| 采购评分表定位 | Poppler `pdfinfo/pdftotext` + 规则扫描 | 采购PDF全文 | 评分表起止页 |
| 采购评分表文档提取 | PP-StructureV3(PaddleOCR, GPU, table recognition) | 评分表页PNG | 带坐标OCR文本行、表格单元格 |
| 评分单元文本规整 | `MIMO_MODEL`，当前为 `mimo-v2.5-pro` | 评分单元OCR原文 | 机械规整后的评分文本 |
| 评分细则拆分与标注 | 规则切分 + MiMo结构补全 | 评分单元文本 | 评分细则、对象、特性、评价方法、分值、主观/客观 |
| 投标响应片段切分 | DOCX OOXML标题解析 / PDF文本标题规则切分 | 投标技术文件 | 标题路径、正文、表格文本、图片引用、统计字段 |
| 采购-投标映射 | RAG式向量召回(cosine topK) + 长度归一规则boost + MiMo/reranker命中判断；规则仅作boost和兜底 | 评分细则与响应片段 | 1对0/1/多映射 |
| 响应文本特征 | 规则特征 + MiMo主观写作结构抽取 | 映射后的片段 | 主观写作结构、覆盖词、执行要素、客观证据字段 |
| 得扣分分析 | 规则分析器 | final_scores + 映射/特征 | 得分点、扣分点、改进建议 |

## 主要输出

| 输出文件 | 含义 |
|----------|------|
| `procurement_scoring_criteria.json` | 采购评分细则数据集 |
| `bid_response_fragments.json` | 投标响应片段数据集 |
| `procurement_bid_mapping.json` | 采购细则到投标片段的映射 |
| `criterion_response_features.json` | 映射后的响应文本特征 |
| `score_point_analysis.json` | 得分点与扣分点分析 |
