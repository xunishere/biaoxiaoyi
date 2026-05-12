"""数据模型定义"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ConfigRequest(BaseModel):
    """OpenAI配置请求"""

    model_config = {"protected_namespaces": ()}

    api_key: str = Field(..., description="OpenAI API密钥")
    base_url: Optional[str] = Field(None, description="Base URL")
    model_name: str = Field("gpt-3.5-turbo", description="模型名称")
    provider: Optional[str] = Field(None, description="预置服务商ID")
    provider_keys: Optional[dict] = Field(None, description="各服务商独立 API Key")
    provider_models: Optional[dict] = Field(None, description="API 拉取的模型列表缓存")


class ConfigResponse(BaseModel):
    """配置响应"""

    success: bool
    message: str


class ModelListResponse(BaseModel):
    """模型列表响应"""

    models: List[str]
    success: bool
    message: str = ""


class FileUploadResponse(BaseModel):
    """文件上传响应"""

    success: bool
    message: str
    file_content: Optional[str] = None
    old_outline: Optional[str] = None


class AnalysisType(str, Enum):
    """分析类型"""

    OVERVIEW = "overview"
    REQUIREMENTS = "requirements"
    COMMERCIAL = "commercial"
    FRAMEWORK = "framework"


class OutlineMode(str, Enum):
    """目录生成模式。"""

    FREE = "free"
    ALIGNED = "aligned"
    FRAMEWORK = "framework"


class AnalysisRequest(BaseModel):
    """文档分析请求"""

    file_content: str = Field(..., description="文档内容")
    analysis_type: AnalysisType = Field(..., description="分析类型")


class OutlineItem(BaseModel):
    """目录项"""

    id: str
    title: str
    description: str
    source_requirement_id: Optional[str] = None
    source_requirement_title: Optional[str] = None
    children: Optional[List["OutlineItem"]] = None
    content: Optional[str] = None


# 解决循环引用
OutlineItem.model_rebuild()


class OutlineResponse(BaseModel):
    """目录响应"""

    outline: List[OutlineItem]


class OutlineChildrenResponse(BaseModel):
    """指定一级目录下的子目录响应。"""

    children: List[OutlineItem]


class OutlineReviewResponse(BaseModel):
    """目录审核响应。"""

    passed: bool
    suggestions: List[str] = Field(default_factory=list)


class TechnicalRequirementGroup(BaseModel):
    """技术评分大类。"""

    requirement_id: str
    title: str
    description: str
    detail_points: List[str] = Field(default_factory=list)


class TechnicalRequirementGroupResponse(BaseModel):
    """技术评分大类提取响应。"""

    groups: List[TechnicalRequirementGroup]


class OutlineRequest(BaseModel):
    """目录生成请求"""

    overview: str = Field(..., description="项目概述")
    requirements: str = Field(..., description="技术评分要求")
    framework_structure: Optional[str] = Field(
        None, description="投标文件框架结构（framework模式使用）"
    )
    mode: OutlineMode = Field(OutlineMode.FREE, description="目录生成模式")
    uploaded_expand: Optional[bool] = Field(False, description="是否已上传方案扩写文件")
    old_outline: Optional[str] = Field(
        None, description="上传的方案扩写文件解析出的旧目录JSON"
    )
    old_document: Optional[str] = Field(
        None, description="上传的方案扩写文件解析出的旧文档"
    )


class ContentGenerationRequest(BaseModel):
    """内容生成请求"""

    outline: Dict[str, Any] = Field(..., description="目录结构")
    project_overview: str = Field("", description="项目概述")


class ChapterContentRequest(BaseModel):
    """单章节内容生成请求"""

    chapter: Dict[str, Any] = Field(..., description="章节信息")
    parent_chapters: Optional[List[Dict[str, Any]]] = Field(
        None, description="上级章节列表"
    )
    sibling_chapters: Optional[List[Dict[str, Any]]] = Field(
        None, description="同级章节列表"
    )
    project_overview: str = Field("", description="项目概述")
    scoring_context: Optional[str] = Field(
        None, description="评分标准上下文（技术评分要求）"
    )
    framework_context: Optional[str] = Field(
        None, description="框架结构上下文"
    )


class ErrorResponse(BaseModel):
    """错误响应"""

    error: str
    detail: Optional[str] = None


class WordExportOutlineItem(BaseModel):
    """Word 导出用目录项。"""

    id: str
    title: str
    description: Optional[str] = None
    children: Optional[List["WordExportOutlineItem"]] = None
    content: Optional[str] = None


WordExportOutlineItem.model_rebuild()


class WordExportRequest(BaseModel):
    """Word导出请求"""

    project_name: Optional[str] = Field(None, description="项目名称")
    project_overview: Optional[str] = Field(None, description="项目概述")
    outline: List[WordExportOutlineItem] = Field(..., description="目录结构，包含内容")


# ── Review 相关 ──

class GapAnalysisRequest(BaseModel):
    """遗漏/缺陷检查请求"""

    document_content: str = Field(..., description="完整投标文件正文（拼接所有章节）")
    scoring_criteria: str = Field(..., description="评分标准原文")


class GapItem(BaseModel):
    """单项缺口"""

    criteria_name: str = Field(..., description="对应评分项名称")
    issue_type: str = Field(..., description="问题类型：遗漏/缺陷/不足/缺少量化数据/无佐证")
    description: str = Field(..., description="具体问题描述")
    suggestion: str = Field("", description="改进建议")


class GapAnalysisResponse(BaseModel):
    """缺口分析响应"""

    gaps: List[GapItem] = Field(default_factory=list)
    quality_issues: List[str] = Field(default_factory=list, description="无关内容/错误信息")
    summary: str = Field("", description="总体评价")


class ScoringTableRequest(BaseModel):
    """评分表生成请求"""

    document_content: str = Field(..., description="完整投标文件正文")
    scoring_criteria: str = Field(..., description="评分标准原文")


class ScoreItem(BaseModel):
    """单项评分"""

    criteria_name: str
    max_score: float
    scored: float
    reasoning: str
    gaps: List[str] = Field(default_factory=list)


class ScoringTableResponse(BaseModel):
    """评分表响应"""

    scores: List[ScoreItem] = Field(default_factory=list)
    total: float = 0
    max_total: float = 100
    summary: str = ""


class OptimizeChapterRequest(BaseModel):
    """章节优化请求"""

    chapter_id: str = Field(..., description="章节ID")
    chapter_title: str = Field(..., description="章节标题")
    current_content: str = Field(..., description="当前内容")
    scoring_criteria: str = Field("", description="评分标准")
    gap_suggestions: str = Field("", description="缺口分析建议")
    reference_docs: Optional[str] = Field(None, description="参考技术方案文档内容")


class MergeRequest(BaseModel):
    """标书合并请求（旧 SSE 版）"""

    framework_outline: List[Dict[str, Any]] = Field(..., description="框架版目录（三级）")
    scoring_criteria: str = Field(..., description="评分标准")
    scoring_content_map: Dict[str, str] = Field(default_factory=dict, description="评分版章节ID→内容")
    framework_content_map: Dict[str, str] = Field(default_factory=dict, description="框架版章节ID→内容")
    gap_analysis_json: str = Field("", description="已有缺口分析 JSON 字符串")


class MergePrepareRequest(BaseModel):
    """合并准备请求（Phase 1+2）"""

    framework_outline: List[Dict[str, Any]] = Field(..., description="框架版目录（三级）")
    scoring_criteria: str = Field(..., description="评分标准")
    scoring_content_map: Dict[str, str] = Field(default_factory=dict, description="评分版章节ID→内容")
    framework_content_map: Dict[str, str] = Field(default_factory=dict, description="框架版章节ID→内容")
    gap_analysis_json: str = Field("", description="已有缺口分析 JSON 字符串")


class MergeSynthesizeRequest(BaseModel):
    """单章合成请求（Phase 3）"""

    node_id: str = Field(..., description="节点ID")
    node_title: str = Field(..., description="节点标题")
    node_description: str = Field("", description="节点描述")
    covers_criteria: str = Field("", description="覆盖的评分准则")
    scoring_content: str = Field("", description="评分版对应内容")
    framework_content: str = Field("", description="框架版对应内容")
    gap_suggestions: str = Field("", description="缺口分析建议")
