# 评分细则响应文本特征数据集

本文件只记录已映射投标片段的文本特征和结构，不做得分预测，也不反向修改采购评分细则。

## PC-001-01 报价得分 / 报价得分 / objective

linked_fragment_ids: []

- evidence_type: price_formula
- verification_mode: 公式计算型
- required_terms: ['报价', '评标基准价']
- candidate_fields: ['投标报价', '评标基准价', '价格分公式']
- detected_terms: []

## PC-002-01 需求理解 / 需求理解 / subjective

linked_fragment_ids: BF-0427, BF-0433, BF-0434, BF-0435, BF-0436, BF-0437, BF-0438, BF-0439, BF-0440, BF-0441, BF-0442, BF-0443

- content_modules(rule): ['项目背景与目标定位', '采购需求理解', '业务场景拆解', '系统架构或分层设计', '功能模块说明', '实施步骤与计划', '测试、试运行或验收', '培训与服务保障', '风险、安全或质量控制', '人员组织与责任分工']
- writing_structure(rule): ['先给出项目定位或需求理解结论', '再按架构、模块或业务对象拆解展开', '正文使用编号条目承载多个检查点', '用步骤、流程或阶段说明可执行路径', '补充保障、风险或安全控制内容', '将通用方案绑定到本项目场景和专有名词']
- coverage_terms(rule): ['需求理解']
- project_terms(rule): ['政务云', '大数据中心']
- execution_elements(rule): ['步骤流程', '阶段计划', '责任分工', '人员配置', '交付物', '测试验证', '培训安排', '验收闭环', '风险控制', '保障机制']
- format_elements(rule): {'uses_table': False, 'uses_image': False, 'list_marker_count': 14, 'max_heading_depth': 1}
- content_modules(model): ['系统整体技术架构需求理解', '堤防泵闸设施全景管控图（升级改造）功能需求理解', '泵闸运行管理模块（国产化环境改造迁移）功能需求理解', '堤防运行管理模块（升级改造）功能需求理解', '防汛应急管理模块（应用新建）功能需求理解', '移动应用模块（升级改造）功能需求理解', '系统非功能需求理解', '系统性能需求理解']
- writing_structure(model): ['以‘需求理解’为章节标题，按系统架构和功能模块划分小节', '每个小节先阐述该部分的核心需求或目标', '再细分核心功能点，逐一描述其功能需求理解', '使用编号条目（如(1)、(2)）承载多个检查点', '将通用技术说明绑定到上海市政务云、国产化环境等具体项目场景']
- coverage_points(model): ['系统整体技术架构', '全景管控图功能（含GIS、BIM、国产化适配）', '泵闸运行管理模块功能（含环境适配、应用适配、功能升级）', '堤防运行管理模块功能（含巡查、考核、国产化适配）', '防汛应急管理模块功能（含预案、险段管理、预警）', '移动应用模块功能', '系统非功能需求（性能）']
- project_expressions(model): ['上海市政务云国产化环境', '上海市水务局数字化项目建设规范', '上海市大数据中心 GIS 服务', '上海市政务云国产化 BIM 底座', '国产化环境', '信创合规要求']
- execution_elements(model): ['步骤流程', '阶段计划', '功能需求理解']
- format_usage(model): ['编号条目（如(1)、(2)）', '层级标题（如1.5.1.、1.5.2.1.）']
- reusable_writing_pattern(model): 以‘需求理解’为核心，按照‘整体架构-分模块功能-非功能需求’的顺序，对每个模块先定性其核心需求，再通过编号列表细化功能点并绑定项目场景。

## PC-003-01 总体设计 / 总体设计 / subjective

linked_fragment_ids: BF-0825, BF-0598, BF-0663, BF-0597, BF-0601, BF-0509, BF-0624, BF-0511, BF-0537, BF-0548, BF-0546, BF-0510

- content_modules(rule): ['项目背景与目标定位', '采购需求理解', '业务场景拆解', '系统架构或分层设计', '功能模块说明', '培训与服务保障', '风险、安全或质量控制', '人员组织与责任分工']
- writing_structure(rule): ['先给出项目定位或需求理解结论', '再按架构、模块或业务对象拆解展开', '用步骤、流程或阶段说明可执行路径', '补充保障、风险或安全控制内容', '将通用方案绑定到本项目场景和专有名词']
- coverage_terms(rule): ['总体设计']
- project_terms(rule): ['政务云', '大数据中心']
- execution_elements(rule): ['步骤流程', '阶段计划', '人员配置', '交付物', '培训安排', '风险控制', '保障机制']
- format_elements(rule): {'uses_table': False, 'uses_image': False, 'list_marker_count': 0, 'max_heading_depth': 1}
- content_modules(model): ['项目背景与目标定位', '系统架构或分层设计', '功能模块说明', '风险、安全或质量控制', '培训与服务保障']
- writing_structure(model): ['先给出项目定位或需求理解结论', '再按架构、模块或业务对象拆解展开', '用步骤、流程或阶段说明可执行路径', '补充保障、风险或安全控制内容', '将通用方案绑定到本项目场景和专有名词']
- coverage_points(model): ['总体设计', '设计目标', '设计原则', '总体架构设计思路', '总体架构图设计', '业务逻辑图设计', '核心业务流程设计', '总体性能设计', '系统体系框架设计', '总体技术路线', '标准规范体系']
- project_expressions(model): ['政务云', '大数据中心', '堤防泵闸管理', '防汛应急', '国产化自主可控', '国产化适配', '上海市水务管理的市-区-镇三级联动', '上海市政务云国产化建设', '水利水务行业标准规范']
- execution_elements(model): ['步骤流程', '风险控制', '保障机制']
- format_usage(model): []
- reusable_writing_pattern(model): 以设计目标和原则为总领，依次展开总体架构、业务流程、性能设计等具体方案，并贯穿国产化、安全合规等项目化要求。

## PC-004-01 功能设计 / 功能设计 / subjective

linked_fragment_ids: BF-0700, BF-0703, BF-0704, BF-0705, BF-0731, BF-0732, BF-0733, BF-0767, BF-0426, BF-0751, BF-0753, BF-0823

- content_modules(rule): ['项目背景与目标定位', '采购需求理解', '业务场景拆解', '系统架构或分层设计', '功能模块说明', '实施步骤与计划', '测试、试运行或验收', '培训与服务保障', '风险、安全或质量控制', '人员组织与责任分工']
- writing_structure(rule): ['先给出项目定位或需求理解结论', '再按架构、模块或业务对象拆解展开', '用步骤、流程或阶段说明可执行路径', '补充保障、风险或安全控制内容', '将通用方案绑定到本项目场景和专有名词']
- coverage_terms(rule): ['功能设计']
- project_terms(rule): ['政务云', '大数据中心']
- execution_elements(rule): ['步骤流程', '阶段计划', '责任分工', '人员配置', '交付物', '测试验证', '培训安排', '验收闭环', '风险控制', '保障机制']
- format_elements(rule): {'uses_table': False, 'uses_image': False, 'list_marker_count': 0, 'max_heading_depth': 1}
- content_modules(model): ['总体功能设计概述', '堤防业务服务图功能设计', 'BIM综合管控图功能设计', '国产化环境适配改造功能设计', '防汛数字化预案功能设计', '薄弱险段上报功能设计', '防汛预警发布功能设计', '核心应用安全功能设计']
- writing_structure(model): ['先以目标或原则概述总体设计', '再针对具体业务或技术模块（如GIS、BIM、国产化、预案、险段、预警、安全）逐个展开', '在每个模块内，按问题痛点、功能子项、技术方案、预期效果的顺序组织']
- coverage_points(model): ['功能设计的全面性', '功能点的详细说明', '功能如何解决具体业务痛点', '功能实现的技术路径', '功能带来的业务价值']
- project_expressions(model): ['上海市堤防泵闸设施管理数字化转型', '上海市政务云国产化环境', '全市堤防泵闸设施的三维数字孪生体', '防汛数字化预案', '薄弱险段上报', '防汛预警发布']
- execution_elements(model): ['功能模块设计', '技术方案适配', '流程管理（如审批、上报、发布）', '风险评估', '监控预警', '数据闭环']
- format_usage(model): ['编号条目（如五大核心模块、七大标准化专题视图）']
- reusable_writing_pattern(model): 先阐述总体设计目标与原则，再按业务模块或技术模块逐一展开，每个模块内先点明要解决的核心痛点，然后分点列出具体功能设计、技术实现及预期效果。

## PC-005-01 安全方案 / 安全方案 / subjective

linked_fragment_ids: BF-0760, BF-0676, BF-0797, BF-0444, BF-0864, BF-0979, BF-0814, BF-0820, BF-0432, BF-0498, BF-0509, BF-0544

- content_modules(rule): ['项目背景与目标定位', '采购需求理解', '业务场景拆解', '系统架构或分层设计', '功能模块说明', '实施步骤与计划', '测试、试运行或验收', '培训与服务保障', '风险、安全或质量控制', '人员组织与责任分工']
- writing_structure(rule): ['先给出项目定位或需求理解结论', '再按架构、模块或业务对象拆解展开', '用步骤、流程或阶段说明可执行路径', '补充保障、风险或安全控制内容', '将通用方案绑定到本项目场景和专有名词']
- coverage_terms(rule): ['安全方案']
- project_terms(rule): ['政务云']
- execution_elements(rule): ['步骤流程', '阶段计划', '人员配置', '交付物', '测试验证', '培训安排', '验收闭环', '风险控制', '保障机制']
- format_elements(rule): {'uses_table': False, 'uses_image': False, 'list_marker_count': 0, 'max_heading_depth': 1}
- content_modules(model): ['安全设计方案', '密码应用方案', '系统安全需求理解', '安全实施阶段规划', '安全验收标准']
- writing_structure(model): ['先阐述安全体系设计（涵盖维度与合规依据）', '再细化密码应用与需求理解', '接着规划分阶段的实施步骤与计划', '最后明确验收标准与交付物']
- coverage_points(model): ['安全体系维度（物理、网络、主机、应用、数据等）', '合规要求（等保二级、数据安全法、密码法等）', '密码应用体系', '安全需求细化（身份鉴别、访问控制、审计、加密等）', '分阶段安全实施计划（与项目进度绑定）', '安全验收标准（功能、测评、适配、文档等）']
- project_expressions(model): ['政务云', '国产化环境适配安全', '国密算法应用', 'SM2、SM3、SM4', '全栈国产化环境']
- execution_elements(model): ['阶段计划（需求与设计阶段、开发与集成阶段、中期验收、安全测试与整改、试运行、终验）', '交付物（安全方案、密码应用方案、测试报告、测评报告、管理制度、手册）', '测试验证（漏洞扫描、代码审计、渗透测试、等保预测试、商密预测试）', '验收闭环（等保二级测评、商密应用安全性测评）']
- format_usage(model): ['编号条目（如十大维度、核心安全需求列表）', '分阶段规划（用文字描述阶段、时间、任务）']
- reusable_writing_pattern(model): 从构建符合法规标准的多维度安全体系开始，细化到密码应用和具体需求，再绑定项目进度制定分阶段实施计划，最后以明确的验收标准和交付物收尾。

## PC-006-01 实施方案 / 实施方案 / subjective

linked_fragment_ids: BF-0844, BF-0845, BF-0846, BF-0847, BF-0848, BF-0849, BF-0363

- content_modules(rule): ['项目背景与目标定位', '采购需求理解', '业务场景拆解', '系统架构或分层设计', '功能模块说明', '实施步骤与计划', '测试、试运行或验收', '培训与服务保障', '风险、安全或质量控制', '人员组织与责任分工']
- writing_structure(rule): ['先给出项目定位或需求理解结论', '再按架构、模块或业务对象拆解展开', '用步骤、流程或阶段说明可执行路径', '补充保障、风险或安全控制内容', '将通用方案绑定到本项目场景和专有名词']
- coverage_terms(rule): ['实施方案']
- project_terms(rule): ['一网统管', '政务云', '大数据中心']
- execution_elements(rule): ['步骤流程', '阶段计划', '人员配置', '交付物', '测试验证', '培训安排', '验收闭环', '风险控制', '保障机制']
- format_elements(rule): {'uses_table': False, 'uses_image': False, 'list_marker_count': 0, 'max_heading_depth': 1}
- content_modules(model): ['项目背景与目标定位', '采购需求理解', '业务场景拆解', '系统架构或分层设计', '功能模块说明', '实施步骤与计划', '测试、试运行或验收', '培训与服务保障', '风险、安全或质量控制', '人员组织与责任分工']
- writing_structure(model): ['先给出项目定位或需求理解结论', '再按架构、模块或业务对象拆解展开', '用步骤、流程或阶段说明可执行路径', '补充保障、风险或安全控制内容', '将通用方案绑定到本项目场景和专有名词']
- coverage_points(model): ['实施方案', '升级改造', '新建', '国产化适配', '全景管控图', '模块国产化环境改造迁移', '运行管理模块', '防汛应急管理', '移动应用']
- project_expressions(model): ['一网统管', '政务云', '大数据中心', '上海市水务海洋数字化转型', '平台+应用+数据', '市-区-镇三级', '一体化智能管理平台', '业务流程标准化', '数据资源一体化', '管理管控精细化']
- execution_elements(model): ['步骤流程', '阶段计划', '人员配置', '交付物', '测试验证', '培训安排', '验收闭环', '风险控制', '保障机制']
- format_usage(model): []
- reusable_writing_pattern(model): 以项目背景和需求理解为起点，按业务模块或系统模块分块展开实施方案，每个模块包含核心目标、核心任务、开发内容、实施要点和国产化适配改造内容，形成目标-任务-内容-要点的层层递进结构。

## PC-007-01 项目经理 / 项目经理 / objective

linked_fragment_ids: BF-0010, BF-0195, BF-0009, BF-0446, BF-1201, BF-1039, BF-1034, BF-0949, BF-1035, BF-0015, BF-0907, BF-0910

- evidence_type: personnel_certificate
- verification_mode: 人员资质核验型
- required_terms: ['证书', '社保', '信息系统项目管理师']
- candidate_fields: ['人员姓名', '岗位角色', '证书名称', '证书等级', '社保证明']
- detected_terms: ['证书', '社保', '信息系统项目管理师']

## PC-008-01 团队人员配置 / 团队人员配置 / objective

linked_fragment_ids: BF-0196

- evidence_type: personnel_count
- verification_mode: 数量门槛型
- required_terms: ['不少于']
- candidate_fields: ['人员数量', '岗位角色', '人员清单']
- detected_terms: []

## PC-009-01 团队综合能力 / 团队综合能力 / subjective

linked_fragment_ids: BF-0196, BF-0906, BF-0485, BF-0826, BF-1034, BF-0446, BF-1040, BF-1041, BF-0010, BF-1130, BF-1048, BF-1054

- content_modules(rule): ['项目背景与目标定位', '采购需求理解', '业务场景拆解', '功能模块说明', '实施步骤与计划', '测试、试运行或验收', '培训与服务保障', '风险、安全或质量控制', '人员组织与责任分工']
- writing_structure(rule): ['先给出项目定位或需求理解结论', '再按架构、模块或业务对象拆解展开', '正文使用编号条目承载多个检查点', '用步骤、流程或阶段说明可执行路径', '补充保障、风险或安全控制内容', '将通用方案绑定到本项目场景和专有名词']
- coverage_terms(rule): []
- project_terms(rule): ['一网统管']
- execution_elements(rule): ['步骤流程', '阶段计划', '责任分工', '人员配置', '交付物', '测试验证', '验收闭环', '风险控制', '保障机制']
- format_elements(rule): {'uses_table': False, 'uses_image': False, 'list_marker_count': 6, 'max_heading_depth': 1}
- content_modules(model): ['人员配置', '团队保障', '岗位职责', '组织架构', '项目经理履历', '服务与质保需求']
- writing_structure(model): ['以响应招标文件要求为起点', '分点阐述团队配置与保障措施', '通过人员履历证明经验与能力', '明确服务与质保需求的具体响应']
- coverage_points(model): ['团队人数与配置符合性', '人员资质与驻场要求', '核心岗位经验', '项目经理能力与业绩', '服务响应与质保承诺']
- project_expressions(model): ['一网统管', '徐汇智慧水务数据支撑系统', '松江区长三角 G60 科创云平台', '国产化适配']
- execution_elements(model): ['人员配置', '岗位职责', '驻场要求', '服务响应时间', '质保期', '故障修复时间']
- format_usage(model): ['编号条目']
- reusable_writing_pattern(model): 先直接响应团队配置要求，再分点说明保障措施与岗位职责，接着通过核心人员履历证明项目经验，最后明确服务与质保的具体承诺。

## PC-010-01 团队人员承诺 / 团队人员承诺 / objective

linked_fragment_ids: BF-0197, BF-0015, BF-1087

- evidence_type: personnel_certificate
- verification_mode: 人员资质核验型
- required_terms: ['技术负责人']
- candidate_fields: ['人员姓名', '岗位角色', '证书名称', '证书等级', '社保证明']
- detected_terms: ['技术负责人']

## PC-011-01 企业综合能力 / 企业综合能力 / objective

linked_fragment_ids: BF-0198, BF-1091

- evidence_type: objective_evidence
- verification_mode: 证据核验型
- required_terms: ['扫描件']
- candidate_fields: ['扫描件']
- detected_terms: []

## PC-012-01 类似业绩 / 类似业绩 / subjective

linked_fragment_ids: BF-0186, BF-0191, BF-0194, BF-0949, BF-1027, BF-1130, BF-1134, BF-1139, BF-1166, BF-1241

- content_modules(rule): ['项目背景与目标定位', '采购需求理解', '业务场景拆解', '系统架构或分层设计', '功能模块说明', '实施步骤与计划', '测试、试运行或验收', '培训与服务保障', '风险、安全或质量控制', '人员组织与责任分工']
- writing_structure(rule): ['先给出项目定位或需求理解结论', '再按架构、模块或业务对象拆解展开', '正文使用编号条目承载多个检查点', '用步骤、流程或阶段说明可执行路径', '补充保障、风险或安全控制内容']
- coverage_terms(rule): ['响应情况']
- project_terms(rule): []
- execution_elements(rule): ['步骤流程', '阶段计划', '责任分工', '人员配置', '交付物', '测试验证', '培训安排', '验收闭环', '风险控制', '保障机制']
- format_elements(rule): {'uses_table': False, 'uses_image': False, 'list_marker_count': 3, 'max_heading_depth': 1}
- content_modules(model): ['客观分评审因素响应情况表', '投标人近三年以来类似项目一览表']
- writing_structure(model): ['以表格形式结构化呈现响应信息', '按年份、项目名称、项目内容、服务时间、合同金额、用户情况等字段组织业绩信息']
- coverage_points(model): ['响应情况', '类似项目业绩']
- project_expressions(model): ['上海市嘉定区菊园章老师 021-39 523087 城市精细化、智慧化 469', '上海雨甜机电设备有限公司孙老师 / 水务防治 470']
- execution_elements(model): ['服务时间', '合同金额']
- format_usage(model): ['表格（结构化的行列呈现）', '编号条目（序号）']
- reusable_writing_pattern(model): 通过制作结构化的表格，逐一列出类似项目的年份、名称、内容、服务时间、金额和用户信息，以响应“类似业绩”评分要求。

## PC-013-01 售后服务方案 / 售后服务方案 / subjective

linked_fragment_ids: BF-1250

- content_modules(rule): ['采购需求理解', '培训与服务保障', '风险、安全或质量控制']
- writing_structure(rule): ['先给出项目定位或需求理解结论', '补充保障、风险或安全控制内容']
- coverage_terms(rule): ['售后服务方案']
- project_terms(rule): []
- execution_elements(rule): ['交付物', '风险控制', '保障机制']
- format_elements(rule): {'uses_table': False, 'uses_image': False, 'list_marker_count': 0, 'max_heading_depth': 1}
- content_modules(model): ['编制依据']
- writing_structure(model): ['列出法律、法规、标准、预案等依据文件']
- coverage_points(model): ['售后服务方案的编制依据']
- project_expressions(model): []
- execution_elements(model): []
- format_usage(model): ['编号条目']
- reusable_writing_pattern(model): 通过列举相关法律、法规、标准、应急预案及项目文件作为编制依据。
