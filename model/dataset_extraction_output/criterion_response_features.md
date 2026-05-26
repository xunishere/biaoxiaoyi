# 评分细则响应文本特征数据集

本文件只记录已映射投标片段的文本特征和结构，不做得分预测，也不反向修改采购评分细则。

## PC-001-01 报价得分 / 报价得分 / objective

linked_fragment_ids: []

- evidence_type: price_formula
- verification_mode: 公式计算型
- required_terms: ['报价', '公式', '评标基准价', '投标报价']
- candidate_fields: ['投标报价', '评标基准价', '价格分公式']
- detected_terms: []

## PC-002-01 需求理解 / 应用环境、体系结构需求和实施要求等需求内容的理解程度 / subjective

linked_fragment_ids: BF-0002, BF-0003, BF-0004, BF-0033

- content_modules(rule): ['项目背景与目标定位', '采购需求理解', '业务场景拆解', '系统架构或分层设计', '功能模块说明', '实施步骤与计划', '测试、试运行或验收', '培训与服务保障', '风险、安全或质量控制', '人员组织与责任分工']
- writing_structure(rule): ['先给出项目定位或需求理解结论', '再按架构、模块或业务对象拆解展开', '正文使用编号条目承载多个检查点', '用步骤、流程或阶段说明可执行路径', '补充保障、风险或安全控制内容', '将通用方案绑定到本项目场景和专有名词']
- coverage_terms(rule): ['应用环境', '实施要求']
- project_terms(rule): ['闵行区', '绿化市容', '生活垃圾', '垃圾分类', '智慧收运', '一网统管', '街镇', '作业单位', '产生单位', '环卫', '政务云', '大数据中心', '区城运平台']
- execution_elements(rule): ['步骤流程', '阶段计划', '责任分工', '人员配置', '交付物', '测试验证', '培训安排', '验收闭环', '风险控制', '保障机制']
- format_elements(rule): {'uses_table': False, 'uses_image': False, 'list_marker_count': 19, 'max_heading_depth': 4}
- model_status: skipped_no_mimo

## PC-002-02 需求理解 / 系统功能需求、性能要求理解程度 / subjective

linked_fragment_ids: BF-0005, BF-0006

- content_modules(rule): ['项目背景与目标定位', '采购需求理解', '业务场景拆解', '系统架构或分层设计', '功能模块说明', '实施步骤与计划', '测试、试运行或验收', '培训与服务保障', '风险、安全或质量控制', '人员组织与责任分工']
- writing_structure(rule): ['先给出项目定位或需求理解结论', '再按架构、模块或业务对象拆解展开', '正文使用编号条目承载多个检查点', '用步骤、流程或阶段说明可执行路径', '补充保障、风险或安全控制内容', '将通用方案绑定到本项目场景和专有名词']
- coverage_terms(rule): ['系统功能需求', '性能要求']
- project_terms(rule): ['闵行区', '绿化市容', '生活垃圾', '垃圾分类', '智慧收运', '一网统管', '街镇', '产生单位', '环卫', '清运', '政务云', '大数据中心', '区城运平台']
- execution_elements(rule): ['步骤流程', '阶段计划', '责任分工', '人员配置', '交付物', '培训安排', '验收闭环', '风险控制', '保障机制']
- format_elements(rule): {'uses_table': False, 'uses_image': False, 'list_marker_count': 27, 'max_heading_depth': 3}
- model_status: skipped_no_mimo

## PC-002-03 需求理解 / 合理化建议、风险分析及控制方案 / subjective

linked_fragment_ids: BF-0033, BF-0034, BF-0035, BF-0036, BF-0022, BF-0018, BF-0019, BF-0020, BF-0021, BF-0023, BF-0024, BF-0025

- content_modules(rule): ['项目背景与目标定位', '采购需求理解', '业务场景拆解', '系统架构或分层设计', '功能模块说明', '实施步骤与计划', '测试、试运行或验收', '培训与服务保障', '风险、安全或质量控制', '人员组织与责任分工']
- writing_structure(rule): ['先给出项目定位或需求理解结论', '再按架构、模块或业务对象拆解展开', '正文使用编号条目承载多个检查点', '用步骤、流程或阶段说明可执行路径', '补充保障、风险或安全控制内容', '将通用方案绑定到本项目场景和专有名词']
- coverage_terms(rule): ['控制方案']
- project_terms(rule): ['闵行区', '绿化市容', '生活垃圾', '垃圾分类', '一网统管', '街镇', '产生单位', '环卫', '清运', '大数据中心', '区城运平台']
- execution_elements(rule): ['步骤流程', '阶段计划', '责任分工', '人员配置', '交付物', '测试验证', '培训安排', '验收闭环', '风险控制', '保障机制']
- format_elements(rule): {'uses_table': False, 'uses_image': False, 'list_marker_count': 50, 'max_heading_depth': 4}
- model_status: skipped_no_mimo

## PC-002-04 需求理解 / 重点、难点问题的分析与措施 / subjective

linked_fragment_ids: BF-0033, BF-0029, BF-0030, BF-0031, BF-0032, BF-0034, BF-0035, BF-0036, BF-0037

- content_modules(rule): ['项目背景与目标定位', '采购需求理解', '业务场景拆解', '系统架构或分层设计', '功能模块说明', '实施步骤与计划', '测试、试运行或验收', '培训与服务保障', '风险、安全或质量控制', '人员组织与责任分工']
- writing_structure(rule): ['先给出项目定位或需求理解结论', '再按架构、模块或业务对象拆解展开', '正文使用编号条目承载多个检查点', '用步骤、流程或阶段说明可执行路径', '补充保障、风险或安全控制内容', '将通用方案绑定到本项目场景和专有名词']
- coverage_terms(rule): ['重点']
- project_terms(rule): ['闵行区', '绿化市容', '生活垃圾', '垃圾分类', '智慧收运', '一网统管', '街镇', '作业单位', '产生单位', '环卫', '清运', '大数据中心', '区城运平台']
- execution_elements(rule): ['步骤流程', '阶段计划', '责任分工', '人员配置', '交付物', '测试验证', '培训安排', '验收闭环', '风险控制', '保障机制']
- format_elements(rule): {'uses_table': False, 'uses_image': False, 'list_marker_count': 41, 'max_heading_depth': 4}
- model_status: skipped_no_mimo

## PC-003-01 投标人综合能力 / 投标人的总体履约情况、综合经营能力 / subjective

linked_fragment_ids: BF-0038, BF-0039, BF-0040, BF-0041, BF-0042, BF-0043, BF-0044, BF-0045, BF-0046, BF-0047

- content_modules(rule): []
- writing_structure(rule): ['再按架构、模块或业务对象拆解展开', '使用图片或图示承载架构、流程或关系']
- coverage_terms(rule): []
- project_terms(rule): []
- execution_elements(rule): []
- format_elements(rule): {'uses_table': False, 'uses_image': True, 'list_marker_count': 0, 'max_heading_depth': 3}
- model_status: skipped_no_mimo

## PC-003-02 投标人综合能力 / 投标人的社会信用信誉、社会评价、获奖情况等 / subjective

linked_fragment_ids: BF-0056, BF-0057, BF-0058, BF-0059, BF-0060, BF-0061, BF-0062, BF-0063, BF-0064, BF-0065

- content_modules(rule): []
- writing_structure(rule): ['使用图片或图示承载架构、流程或关系']
- coverage_terms(rule): []
- project_terms(rule): []
- execution_elements(rule): []
- format_elements(rule): {'uses_table': False, 'uses_image': True, 'list_marker_count': 0, 'max_heading_depth': 3}
- model_status: skipped_no_mimo

## PC-004-01 系统建设总体服务方案 / 根据招标文件要求编制详细的技术方案 / subjective

linked_fragment_ids: []

- content_modules(rule): []
- writing_structure(rule): ['围绕评分细则标题展开说明']
- coverage_terms(rule): []
- project_terms(rule): []
- execution_elements(rule): []
- format_elements(rule): {'uses_table': False, 'uses_image': False, 'list_marker_count': 0, 'max_heading_depth': 0}
- model_status: skipped_no_mimo

## PC-004-02 系统建设总体服务方案 / 技术方案内容包含系统架构、系统设计、功能说明等内容 / subjective

linked_fragment_ids: []

- content_modules(rule): []
- writing_structure(rule): ['围绕评分细则标题展开说明']
- coverage_terms(rule): []
- project_terms(rule): []
- execution_elements(rule): []
- format_elements(rule): {'uses_table': False, 'uses_image': False, 'list_marker_count': 0, 'max_heading_depth': 0}
- model_status: skipped_no_mimo

## PC-004-03 系统建设总体服务方案 / 系统安全设计 / subjective

linked_fragment_ids: BF-0159, BF-0163, BF-0160, BF-0161, BF-0162, BF-0164, BF-0165, BF-0166, BF-0167, BF-0168

- content_modules(rule): ['项目背景与目标定位', '业务场景拆解', '系统架构或分层设计', '功能模块说明', '培训与服务保障', '风险、安全或质量控制']
- writing_structure(rule): ['再按架构、模块或业务对象拆解展开', '用步骤、流程或阶段说明可执行路径', '补充保障、风险或安全控制内容', '将通用方案绑定到本项目场景和专有名词']
- coverage_terms(rule): ['系统安全设计']
- project_terms(rule): ['闵行区']
- execution_elements(rule): ['步骤流程', '阶段计划', '风险控制', '保障机制']
- format_elements(rule): {'uses_table': False, 'uses_image': False, 'list_marker_count': 0, 'max_heading_depth': 4}
- model_status: skipped_no_mimo

## PC-005-01 实施方案 / 实施工作计划 / subjective

linked_fragment_ids: BF-0190, BF-0191, BF-0192, BF-0193, BF-0194, BF-0195, BF-0196, BF-0197, BF-0198, BF-0199

- content_modules(rule): ['项目背景与目标定位', '采购需求理解', '业务场景拆解', '系统架构或分层设计', '功能模块说明', '实施步骤与计划', '测试、试运行或验收', '培训与服务保障', '风险、安全或质量控制', '人员组织与责任分工']
- writing_structure(rule): ['先给出项目定位或需求理解结论', '再按架构、模块或业务对象拆解展开', '用步骤、流程或阶段说明可执行路径', '补充保障、风险或安全控制内容', '将通用方案绑定到本项目场景和专有名词', '使用表格承载清单、配置、计划或对照关系']
- coverage_terms(rule): []
- project_terms(rule): ['闵行区', '绿化市容', '生活垃圾', '智慧收运', '一网统管', '街镇', '产生单位', '环卫', '政务云', '大数据中心', '区城运平台']
- execution_elements(rule): ['步骤流程', '阶段计划', '责任分工', '人员配置', '交付物', '测试验证', '培训安排', '验收闭环', '风险控制', '保障机制']
- format_elements(rule): {'uses_table': True, 'uses_image': False, 'list_marker_count': 0, 'max_heading_depth': 4}
- model_status: skipped_no_mimo

## PC-005-02 实施方案 / 工作流程、时间安排等 / subjective

linked_fragment_ids: BF-0196, BF-0200, BF-0204, BF-0190, BF-0191, BF-0192, BF-0193, BF-0194, BF-0195, BF-0197, BF-0198, BF-0199

- content_modules(rule): ['项目背景与目标定位', '采购需求理解', '业务场景拆解', '系统架构或分层设计', '功能模块说明', '实施步骤与计划', '测试、试运行或验收', '培训与服务保障', '风险、安全或质量控制', '人员组织与责任分工']
- writing_structure(rule): ['先给出项目定位或需求理解结论', '再按架构、模块或业务对象拆解展开', '用步骤、流程或阶段说明可执行路径', '补充保障、风险或安全控制内容', '将通用方案绑定到本项目场景和专有名词', '使用表格承载清单、配置、计划或对照关系']
- coverage_terms(rule): ['工作流程', '时间安排']
- project_terms(rule): ['闵行区', '绿化市容', '生活垃圾', '智慧收运', '一网统管', '街镇', '产生单位', '环卫', '政务云', '大数据中心', '区城运平台']
- execution_elements(rule): ['步骤流程', '阶段计划', '责任分工', '人员配置', '交付物', '测试验证', '培训安排', '验收闭环', '风险控制', '保障机制']
- format_elements(rule): {'uses_table': True, 'uses_image': False, 'list_marker_count': 1, 'max_heading_depth': 4}
- model_status: skipped_no_mimo

## PC-005-03 实施方案 / 平台测试（含试运行）等重要环节的方案措施等 / subjective

linked_fragment_ids: BF-0208, BF-0204, BF-0209, BF-0210, BF-0211, BF-0212, BF-0213, BF-0214, BF-0215, BF-0216, BF-0217, BF-0218

- content_modules(rule): ['项目背景与目标定位', '采购需求理解', '业务场景拆解', '系统架构或分层设计', '功能模块说明', '实施步骤与计划', '测试、试运行或验收', '培训与服务保障', '风险、安全或质量控制', '人员组织与责任分工']
- writing_structure(rule): ['先给出项目定位或需求理解结论', '再按架构、模块或业务对象拆解展开', '用步骤、流程或阶段说明可执行路径', '补充保障、风险或安全控制内容', '将通用方案绑定到本项目场景和专有名词', '使用表格承载清单、配置、计划或对照关系']
- coverage_terms(rule): ['平台测试', '方案措施']
- project_terms(rule): ['闵行区', '智慧收运', '一网统管', '街镇', '产生单位', '环卫', '大数据中心', '区城运平台']
- execution_elements(rule): ['步骤流程', '阶段计划', '人员配置', '交付物', '测试验证', '培训安排', '验收闭环', '风险控制', '保障机制']
- format_elements(rule): {'uses_table': True, 'uses_image': False, 'list_marker_count': 2, 'max_heading_depth': 5}
- model_status: skipped_no_mimo

## PC-006-01 软件模块开发方案及软件功能内容 / 生活垃圾分类智慧收运系统-智慧收运PC端 / subjective

linked_fragment_ids: BF-0294, BF-0295, BF-0296, BF-0297, BF-0298, BF-0299, BF-0300, BF-0301, BF-0302, BF-0303

- content_modules(rule): ['项目背景与目标定位', '采购需求理解', '业务场景拆解', '系统架构或分层设计', '功能模块说明', '实施步骤与计划', '测试、试运行或验收', '培训与服务保障', '风险、安全或质量控制', '人员组织与责任分工']
- writing_structure(rule): ['再按架构、模块或业务对象拆解展开', '用步骤、流程或阶段说明可执行路径', '补充保障、风险或安全控制内容', '将通用方案绑定到本项目场景和专有名词']
- coverage_terms(rule): ['智慧收运PC端']
- project_terms(rule): ['闵行区', '生活垃圾', '智慧收运', '街镇', '产生单位', '环卫', '大数据中心', '区城运平台']
- execution_elements(rule): ['步骤流程', '阶段计划', '人员配置', '交付物', '培训安排', '验收闭环', '风险控制', '保障机制']
- format_elements(rule): {'uses_table': False, 'uses_image': False, 'list_marker_count': 0, 'max_heading_depth': 5}
- model_status: skipped_no_mimo

## PC-006-02 软件模块开发方案及软件功能内容 / 生活垃圾分类智慧收运系统-智慧收运移动端 / subjective

linked_fragment_ids: BF-0314, BF-0315, BF-0316

- content_modules(rule): ['项目背景与目标定位', '采购需求理解', '业务场景拆解', '功能模块说明', '实施步骤与计划', '培训与服务保障', '人员组织与责任分工']
- writing_structure(rule): ['再按架构、模块或业务对象拆解展开', '用步骤、流程或阶段说明可执行路径', '将通用方案绑定到本项目场景和专有名词']
- coverage_terms(rule): ['智慧收运移动端']
- project_terms(rule): ['生活垃圾', '智慧收运', '产生单位', '清运']
- execution_elements(rule): ['步骤流程', '阶段计划', '人员配置', '验收闭环', '保障机制']
- format_elements(rule): {'uses_table': False, 'uses_image': False, 'list_marker_count': 0, 'max_heading_depth': 4}
- model_status: skipped_no_mimo

## PC-006-03 软件模块开发方案及软件功能内容 / 生活垃圾分类智慧收运系统-街镇智慧收运监管场景 / subjective

linked_fragment_ids: BF-0317, BF-0318, BF-0319, BF-0320, BF-0321

- content_modules(rule): ['项目背景与目标定位', '业务场景拆解', '系统架构或分层设计', '功能模块说明', '实施步骤与计划', '培训与服务保障', '风险、安全或质量控制', '人员组织与责任分工']
- writing_structure(rule): ['再按架构、模块或业务对象拆解展开', '用步骤、流程或阶段说明可执行路径', '补充保障、风险或安全控制内容', '将通用方案绑定到本项目场景和专有名词']
- coverage_terms(rule): []
- project_terms(rule): ['生活垃圾', '垃圾分类', '智慧收运', '一网统管', '街镇', '产生单位', '清运']
- execution_elements(rule): ['步骤流程', '阶段计划', '责任分工', '人员配置', '验收闭环', '保障机制']
- format_elements(rule): {'uses_table': False, 'uses_image': False, 'list_marker_count': 0, 'max_heading_depth': 4}
- model_status: skipped_no_mimo

## PC-006-04 软件模块开发方案及软件功能内容 / 环境卫生监管系统 / subjective

linked_fragment_ids: BF-0322, BF-0323, BF-0324, BF-0325

- content_modules(rule): ['项目背景与目标定位', '业务场景拆解', '系统架构或分层设计', '功能模块说明', '实施步骤与计划', '风险、安全或质量控制', '人员组织与责任分工']
- writing_structure(rule): ['再按架构、模块或业务对象拆解展开', '用步骤、流程或阶段说明可执行路径', '补充保障、风险或安全控制内容', '将通用方案绑定到本项目场景和专有名词']
- coverage_terms(rule): []
- project_terms(rule): ['生活垃圾', '垃圾分类', '智慧收运', '街镇', '环卫', '清运']
- execution_elements(rule): ['步骤流程', '阶段计划', '责任分工', '人员配置', '交付物', '培训安排', '验收闭环', '风险控制']
- format_elements(rule): {'uses_table': False, 'uses_image': False, 'list_marker_count': 0, 'max_heading_depth': 4}
- model_status: skipped_no_mimo

## PC-006-05 软件模块开发方案及软件功能内容 / 综合考核评价系统 / subjective

linked_fragment_ids: BF-0326, BF-0327, BF-0328, BF-0329

- content_modules(rule): ['项目背景与目标定位', '采购需求理解', '业务场景拆解', '系统架构或分层设计', '功能模块说明', '实施步骤与计划', '人员组织与责任分工']
- writing_structure(rule): ['再按架构、模块或业务对象拆解展开', '用步骤、流程或阶段说明可执行路径', '将通用方案绑定到本项目场景和专有名词']
- coverage_terms(rule): []
- project_terms(rule): ['闵行区', '生活垃圾', '垃圾分类', '智慧收运', '街镇', '环卫']
- execution_elements(rule): ['步骤流程', '阶段计划', '责任分工', '人员配置', '交付物', '培训安排', '验收闭环']
- format_elements(rule): {'uses_table': False, 'uses_image': False, 'list_marker_count': 0, 'max_heading_depth': 4}
- model_status: skipped_no_mimo

## PC-006-06 软件模块开发方案及软件功能内容 / 综合资料库管理系统 / subjective

linked_fragment_ids: []

- content_modules(rule): []
- writing_structure(rule): ['围绕评分细则标题展开说明']
- coverage_terms(rule): []
- project_terms(rule): []
- execution_elements(rule): []
- format_elements(rule): {'uses_table': False, 'uses_image': False, 'list_marker_count': 0, 'max_heading_depth': 0}
- model_status: skipped_no_mimo

## PC-006-07 软件模块开发方案及软件功能内容 / 可视化指挥软件 / subjective

linked_fragment_ids: BF-0330, BF-0331, BF-0332, BF-0333

- content_modules(rule): ['项目背景与目标定位', '采购需求理解', '业务场景拆解', '系统架构或分层设计', '功能模块说明', '实施步骤与计划', '培训与服务保障', '风险、安全或质量控制', '人员组织与责任分工']
- writing_structure(rule): ['再按架构、模块或业务对象拆解展开', '用步骤、流程或阶段说明可执行路径', '补充保障、风险或安全控制内容', '将通用方案绑定到本项目场景和专有名词']
- coverage_terms(rule): []
- project_terms(rule): ['闵行区', '生活垃圾', '垃圾分类', '智慧收运', '街镇', '环卫', '清运']
- execution_elements(rule): ['阶段计划', '人员配置', '验收闭环', '风险控制', '保障机制']
- format_elements(rule): {'uses_table': False, 'uses_image': False, 'list_marker_count': 0, 'max_heading_depth': 4}
- model_status: skipped_no_mimo

## PC-006-08 软件模块开发方案及软件功能内容 / 数据接口开发 / subjective

linked_fragment_ids: BF-0334, BF-0335, BF-0336, BF-0337, BF-0338

- content_modules(rule): ['项目背景与目标定位', '采购需求理解', '业务场景拆解', '系统架构或分层设计', '功能模块说明', '实施步骤与计划', '培训与服务保障', '风险、安全或质量控制', '人员组织与责任分工']
- writing_structure(rule): ['再按架构、模块或业务对象拆解展开', '正文使用编号条目承载多个检查点', '用步骤、流程或阶段说明可执行路径', '补充保障、风险或安全控制内容', '将通用方案绑定到本项目场景和专有名词']
- coverage_terms(rule): []
- project_terms(rule): ['闵行区', '绿化市容', '智慧收运', '一网统管', '街镇', '产生单位', '环卫', '大数据中心', '区城运平台']
- execution_elements(rule): ['阶段计划', '人员配置', '培训安排', '风险控制', '保障机制']
- format_elements(rule): {'uses_table': False, 'uses_image': False, 'list_marker_count': 8, 'max_heading_depth': 4}
- model_status: skipped_no_mimo

## PC-006-09 软件模块开发方案及软件功能内容 / 密码应用建设 / subjective

linked_fragment_ids: BF-0339, BF-0340, BF-0341, BF-0342

- content_modules(rule): ['项目背景与目标定位', '业务场景拆解', '系统架构或分层设计', '功能模块说明', '实施步骤与计划', '测试、试运行或验收', '培训与服务保障', '风险、安全或质量控制', '人员组织与责任分工']
- writing_structure(rule): ['再按架构、模块或业务对象拆解展开', '用步骤、流程或阶段说明可执行路径', '补充保障、风险或安全控制内容', '将通用方案绑定到本项目场景和专有名词']
- coverage_terms(rule): []
- project_terms(rule): ['街镇', '产生单位']
- execution_elements(rule): ['步骤流程', '阶段计划', '人员配置', '测试验证', '培训安排', '验收闭环', '风险控制', '保障机制']
- format_elements(rule): {'uses_table': False, 'uses_image': False, 'list_marker_count': 0, 'max_heading_depth': 4}
- model_status: skipped_no_mimo

## PC-007-01 服务综合支撑能力 / 本地化服务团队配置及服务能力 / subjective

linked_fragment_ids: BF-0343, BF-0344, BF-0345, BF-0346

- content_modules(rule): []
- writing_structure(rule): ['再按架构、模块或业务对象拆解展开', '使用图片或图示承载架构、流程或关系']
- coverage_terms(rule): []
- project_terms(rule): []
- execution_elements(rule): []
- format_elements(rule): {'uses_table': False, 'uses_image': True, 'list_marker_count': 0, 'max_heading_depth': 3}
- model_status: skipped_no_mimo

## PC-007-02 服务综合支撑能力 / 可提供与本项目相关的资源情况 / subjective

linked_fragment_ids: BF-0347

- content_modules(rule): ['项目背景与目标定位', '业务场景拆解', '功能模块说明', '测试、试运行或验收', '培训与服务保障', '风险、安全或质量控制']
- writing_structure(rule): ['先给出项目定位或需求理解结论', '再按架构、模块或业务对象拆解展开', '补充保障、风险或安全控制内容', '将通用方案绑定到本项目场景和专有名词', '使用表格承载清单、配置、计划或对照关系']
- coverage_terms(rule): []
- project_terms(rule): ['环卫', '清运']
- execution_elements(rule): ['测试验证', '风险控制', '保障机制']
- format_elements(rule): {'uses_table': True, 'uses_image': False, 'list_marker_count': 2, 'max_heading_depth': 2}
- model_status: skipped_no_mimo

## PC-007-03 服务综合支撑能力 / 服务响应时间、修复时间、应急预案等 / subjective

linked_fragment_ids: BF-0348, BF-0349, BF-0351, BF-0350, BF-0352, BF-0353, BF-0354, BF-0355, BF-0356

- content_modules(rule): ['项目背景与目标定位', '采购需求理解', '业务场景拆解', '系统架构或分层设计', '功能模块说明', '实施步骤与计划', '测试、试运行或验收', '培训与服务保障', '风险、安全或质量控制', '人员组织与责任分工']
- writing_structure(rule): ['再按架构、模块或业务对象拆解展开', '正文使用编号条目承载多个检查点', '用步骤、流程或阶段说明可执行路径', '补充保障、风险或安全控制内容', '将通用方案绑定到本项目场景和专有名词', '使用图片或图示承载架构、流程或关系']
- coverage_terms(rule): ['修复时间', '应急预案']
- project_terms(rule): ['闵行区', '绿化市容', '生活垃圾', '垃圾分类', '智慧收运', '一网统管', '街镇', '环卫', '大数据中心']
- execution_elements(rule): ['步骤流程', '阶段计划', '责任分工', '人员配置', '测试验证', '培训安排', '验收闭环', '风险控制', '保障机制']
- format_elements(rule): {'uses_table': False, 'uses_image': True, 'list_marker_count': 10, 'max_heading_depth': 5}
- model_status: skipped_no_mimo

## PC-007-04 服务综合支撑能力 / 售后服务人员配备及管理措施 / subjective

linked_fragment_ids: BF-0357, BF-0358, BF-0359, BF-0360, BF-0361

- content_modules(rule): ['项目背景与目标定位', '采购需求理解', '业务场景拆解', '培训与服务保障', '风险、安全或质量控制', '人员组织与责任分工']
- writing_structure(rule): ['先给出项目定位或需求理解结论', '用步骤、流程或阶段说明可执行路径', '补充保障、风险或安全控制内容', '将通用方案绑定到本项目场景和专有名词', '使用表格承载清单、配置、计划或对照关系']
- coverage_terms(rule): []
- project_terms(rule): ['闵行区', '环卫', '大数据中心']
- execution_elements(rule): ['步骤流程', '责任分工', '人员配置', '培训安排', '验收闭环', '风险控制', '保障机制']
- format_elements(rule): {'uses_table': True, 'uses_image': False, 'list_marker_count': 2, 'max_heading_depth': 5}
- model_status: skipped_no_mimo

## PC-008-01 项目服务团队配备情况 / 项目负责人、技术负责人 / objective

linked_fragment_ids: BF-0188, BF-0475, BF-0374, BF-0023, BF-0033, BF-0362

- evidence_type: personnel_count
- verification_mode: 数量门槛型
- required_terms: ['证书', '人数', '不少于', '项目负责人', '技术负责人', '职称', '信息系统项目管理师', '系统集成项目管理师', '高级工程师']
- candidate_fields: ['人员数量', '岗位角色', '人员清单']
- detected_terms: ['证书', '人数', '不少于', '项目负责人', '技术负责人', '职称', '信息系统项目管理师', '高级工程师']

## PC-008-02 项目服务团队配备情况 / 团队配备人数 / objective

linked_fragment_ids: []

- evidence_type: personnel_count
- verification_mode: 数量门槛型
- required_terms: ['证书', '人数', '不少于', '项目负责人', '技术负责人', '职称', '信息系统项目管理师', '系统集成项目管理师', '高级工程师']
- candidate_fields: ['人员数量', '岗位角色', '人员清单']
- detected_terms: []

## PC-008-03 项目服务团队配备情况 / 主要技术人员配备 / objective

linked_fragment_ids: BF-0188, BF-0475, BF-0374, BF-0395

- evidence_type: personnel_count
- verification_mode: 数量门槛型
- required_terms: ['证书', '人数', '不少于', '项目负责人', '技术负责人', '职称', '信息系统项目管理师', '系统集成项目管理师', '高级工程师']
- candidate_fields: ['人员数量', '岗位角色', '人员清单']
- detected_terms: ['证书', '人数', '不少于', '项目负责人', '技术负责人', '职称', '信息系统项目管理师', '高级工程师']

## PC-009-01 系统调试及验收方案 / 系统调试及验收方案 / subjective

linked_fragment_ids: BF-0364, BF-0365, BF-0366, BF-0367, BF-0368, BF-0369, BF-0370, BF-0371, BF-0372, BF-0373

- content_modules(rule): ['项目背景与目标定位', '采购需求理解', '业务场景拆解', '系统架构或分层设计', '功能模块说明', '实施步骤与计划', '测试、试运行或验收', '培训与服务保障', '风险、安全或质量控制', '人员组织与责任分工']
- writing_structure(rule): ['先给出项目定位或需求理解结论', '再按架构、模块或业务对象拆解展开', '用步骤、流程或阶段说明可执行路径', '补充保障、风险或安全控制内容', '将通用方案绑定到本项目场景和专有名词']
- coverage_terms(rule): ['系统调试']
- project_terms(rule): ['闵行区', '绿化市容', '生活垃圾', '垃圾分类', '智慧收运', '一网统管', '街镇', '环卫', '清运', '大数据中心', '区城运平台']
- execution_elements(rule): ['步骤流程', '阶段计划', '责任分工', '人员配置', '交付物', '测试验证', '培训安排', '验收闭环', '风险控制', '保障机制']
- format_elements(rule): {'uses_table': False, 'uses_image': False, 'list_marker_count': 1, 'max_heading_depth': 4}
- model_status: skipped_no_mimo

## PC-010-01 培训方案 / 培训方案 / subjective

linked_fragment_ids: BF-0456, BF-0465, BF-0471, BF-0459, BF-0245, BF-0246, BF-0247, BF-0248, BF-0249, BF-0250, BF-0251, BF-0252

- content_modules(rule): ['项目背景与目标定位', '采购需求理解', '业务场景拆解', '系统架构或分层设计', '功能模块说明', '实施步骤与计划', '测试、试运行或验收', '培训与服务保障', '风险、安全或质量控制', '人员组织与责任分工']
- writing_structure(rule): ['再按架构、模块或业务对象拆解展开', '用步骤、流程或阶段说明可执行路径', '补充保障、风险或安全控制内容', '将通用方案绑定到本项目场景和专有名词']
- coverage_terms(rule): ['培训方案']
- project_terms(rule): ['闵行区', '生活垃圾', '智慧收运', '街镇', '产生单位', '环卫', '清运']
- execution_elements(rule): ['步骤流程', '阶段计划', '责任分工', '人员配置', '交付物', '测试验证', '培训安排', '验收闭环', '保障机制']
- format_elements(rule): {'uses_table': False, 'uses_image': False, 'list_marker_count': 0, 'max_heading_depth': 4}
- model_status: skipped_no_mimo

## PC-011-01 类似项目的经验 / 类似项目的经验 / objective

linked_fragment_ids: BF-0505

- evidence_type: contract_case
- verification_mode: 证明材料计数型
- required_terms: ['合同', '扫描件', '每份', '盖章页', '签订日期', '服务期限', '合同扫描件']
- candidate_fields: ['合同名称', '签订日期', '服务期限', '盖章页', '合同扫描件']
- detected_terms: ['合同', '扫描件', '签订日期']
