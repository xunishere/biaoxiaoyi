# 荟写作修改记录

> 基于 [yibiao-simple](https://github.com/yibiaoai/yibiao-simple) 开源项目  
> 维护者：标小智 (BidBrain)

---

## 2026-05-12 — 品牌改名「荟写作」+ 模型配置全面重构

### 品牌改名
| 文件 | 改动 |
|------|------|
| `frontend/public/index.html` | `<title>` 易标AI → 荟写作 |
| `frontend/public/manifest.json` | `short_name`/`name` → 荟写作 |
| `frontend/public/` | 新增 `brand.png`（荟写作 3D 品牌图）、`huixiezuo.png`（HC 图标）；`favicon.ico`/`logo192.png`/`logo512.png` 用 HC 图标重新生成 |
| `README.md` | 全局替换 易标 → 荟写作 |
| `MODIFICATIONS.md` | 标题 易标 → 荟写作 |

### 模型配置全面重构

**目标**：替换「手填 API Key + Base URL + 模型名」原始方式，改为预置服务商下拉选择 + API 实时拉取模型列表。

**新增文件**
| 文件 | 功能 |
|------|------|
| `frontend/src/config/providers.ts` | 6 个预置服务商注册表（URL + 品牌色），仅提供基础连接信息，无内置模型列表 |

**前端修改**
| 文件 | 改动 |
|------|------|
| `ConfigPanel.tsx` | **完全重写**：服务商下拉 select → 自动填 URL → 输 Key → 点「拉取列表」API 实时获取模型 → 下拉选择。去掉保存按钮，改为自动保存（500ms debounce）。Key 输入 `type="password"` + `autoComplete="new-password"` 永久遮罩。底部 GitHub 图标改为 HC logo |
| `types/index.ts` | `ConfigData` 加 `provider?`、`provider_keys?`、`provider_models?` |

**后端修改**
| 文件 | 改动 |
|------|------|
| `backend/app/models/schemas.py` | `ConfigRequest` 加 `provider`、`provider_keys`、`provider_models` |
| `backend/app/utils/config_manager.py` | `save_config()` 支持存储三个新字段 |
| `backend/app/routers/config.py` | 透传新参数 |

**核心设计**
- 6 个预置服务商（DeepSeek / 通义千问 / 智谱AI / 月之暗面 / SiliconFlow / OpenAI）+ 自定义
- 每个服务商独立存储 Key（`provider_keys`），互不覆盖
- 模型列表从 API 实时拉取并缓存（`provider_models`），切走再切回不丢
- 下拉菜单干净无 emoji
- 切换/改Key/换模型自动静默保存，刷新不丢

**用户流程**：选择服务商 → 输入 API Key → 拉取模型列表 → 选择模型（4 步，全程自动保存）

---

## 2026-05-09 — Step 3 正文编辑升级为完整流水线

**目标：** ContentEdit 改为双 Tab + 生成→审查→评分→优化→导出全流水线。

### 新增文件
| 文件 | 功能 |
|------|------|
| `backend/app/routers/review.py` | `/api/review/gap-analysis`, `/scoring-table`, `/optimize-chapter-stream` |
| `backend/app/services/review_service.py` | ReviewService：缺口分析 + 评分表 + 章节优化 |
| `backend/app/utils/prompts/review_prompts.py` | 审查/评分/优化 prompts |

### 修改文件
| 文件 | 改动 |
|------|------|
| `schemas.py` | `ChapterContentRequest` 加 `scoring_context`/`framework_context`；新增 `GapAnalysis*`, `ScoringTable*`, `OptimizeChapter*` 模型 |
| `content_prompts.py` | `build_chapter_content_messages()` 加评分标准/框架上下文参数 |
| `content_service.py` | 透传新参数 |
| `content.py` (router) | 透传新参数 |
| `main.py` | 注册 `review` router |
| `ContentEdit.tsx` | **重写**：双 Tab（目录A/B）+ 生成→审查→评分→优化→导出 |
| `api.ts` | 新增 `reviewApi`、`GapAnalysis*`、`ScoringTable*`、`OptimizeChapter*` 类型 |
| `App.tsx` | 透传 `techRequirements`/`bidFramework`/`frameworkOutlineData` 给 ContentEdit |

### 完整流水线
```
① 生成正文（5并发，评分标准/框架上下文注入）
  ↓
② 检查遗漏/缺陷（缺口分析：遗漏/缺陷/不足/缺量化/无佐证）
  ↓
③ 评分（按评分标准逐项打分 → 评分表）
  ↓
④ 优化薄弱章节（得分<70%max → 参考缺口建议+可选参考方案 → 重写）
  ↓
⑤ 再评分 → 导出 Word
```

---

## 2026-05-09 — Step 2 目录生成改为双模式独立输出

**目标：** 去掉"AI自行理解"模式，改为两个独立生成通道：
- 目录 A：按评分标准（技术评分大类一一对应）
- 目录 B：按框架结构（严格按招标文件规定的投标文件框架生成）
两个目录互不覆盖，独立存储。

### 后端改动

| # | 文件 | 改动 |
|---|------|------|
| 1 | `schemas.py` | `OutlineMode` 加 `FRAMEWORK = "framework"`；`OutlineRequest` 加 `framework_structure` 字段 |
| 2 | `outline_prompts.py` | 新增 3 个 framework 模式专用 prompt 函数：`extract_framework_groups_messages`、`generate_framework_children_outline_prompt`、`review_framework_outline_messages` |
| 3 | `outline_service.py` | `generate_outline()` 加 `framework_structure` 参数；新增 `_generate_framework_outline_workflow` 及相关方法（提取框架分组 → 生成子目录 → 审核回路） |
| 4 | `outline.py` (router) | 路由透传 `framework_structure` |

### 前端改动

| # | 文件 | 改动 |
|---|------|------|
| 5 | `types/index.ts` | `AppState` 加 `frameworkOutlineData`；`OutlineMode` 加 `'framework'` |
| 6 | `useAppState.ts` | 加 `updateFrameworkOutline` callback + `frameworkOutlineData` 状态 |
| 7 | `draftStorage.ts` | `DraftState` 加 `frameworkOutlineData` |
| 8 | `api.ts` | `OutlineRequest` 加 `framework_structure?: string` |
| 9 | `OutlineEdit.tsx` | **重写**：去掉 FREE 模式、去掉方案扩写；改为双区域独立生成（蓝色按钮=按评分标准，紫色按钮=按框架结构）；两个目录树独立展示、可分别编辑 |
| 10 | `App.tsx` | 透传 `commercialRequirements` / `bidFramework` / `frameworkOutlineData` / `onFrameworkOutlineGenerated` 给 OutlineEdit |

### 页面布局
```
┌──────────────────────────────────────────────────────────┐
│  📋 目录编辑                                              │
│  [技术评分要求]          [商务/价格评分要求]                 │
├──────────────────────────────────────────────────────────┤
│  📋 目录 A：按评分标准                                     │
│  [生成目录（按评分标准）]   ← 蓝色按钮                      │
│  ┌─ 1. 需求理解                                           │
│  │  ├─ 1.1 ...                                           │
│  │  └─ 1.2 ...                                           │
│  └─ 2. 系统建设总体方案                                    │
├──────────────────────────────────────────────────────────┤
│  📑 目录 B：按框架结构                                     │
│  [生成目录（按框架结构）]   ← 紫色按钮                      │
│  ┌─ 1. 资信部分                                           │
│  │  ├─ 1.1 单位介绍                                       │
│  │  │  ├─ 1.1.1 ...                                      │
│  │  │  └─ 1.1.1.1 ...   ← 四级目录                       │
│  │  └─ 1.2 类似项目业绩证明材料                            │
│  └─ 2. 技术部分                                           │
└──────────────────────────────────────────────────────────┘
```

---

## 2026-05-09 — 新增「投标文件框架结构」提取通道

**目标：** 从采购文件中提取招标方规定的投标文件框架结构（"投标文件应包含的内容"），为后续目录生成提供框架参考。

### 修改清单

| # | 文件 | 改动 | 说明 |
|---|------|------|------|
| 1 | `backend/app/models/schemas.py` | `AnalysisType` 加 `FRAMEWORK = "framework"` | 新增框架结构分析类型 |
| 2 | `backend/app/utils/prompts/analysis_prompts.py` | 加 `elif analysis_type == "framework"` 分支 | prompt 目标：提取"投标文件组成"章节 |
| 3 | `frontend/src/types/index.ts` | `AppState` 加 `bidFramework: string` | 前端状态字段 |
| 4 | `frontend/src/hooks/useAppState.ts` | 加 `updateBidFramework` callback + 初始化 + 导出 | 框架状态管理 |
| 5 | `frontend/src/utils/draftStorage.ts` | `DraftState` 加 `bidFramework` | localStorage 持久化 |
| 6 | `frontend/src/services/api.ts` | `AnalysisRequest.analysis_type` 加 `'framework'` | API 类型扩展 |
| 7 | `frontend/src/pages/DocumentAnalysis.tsx` | 加 framework Props/State/SSE/折叠区 | 第四轮 SSE + 📑 折叠面板 |
| 8 | `frontend/src/App.tsx` | 透传 `bidFramework` + `onFrameworkComplete` | 父组件桥接 |

### 当前解析流程（4 轮 SSE）
```
overview → requirements → commercial → framework
```

### 当前页面布局
```
┌──────────────────────────────────────┐
│  📄 文档上传                          │
├──────────────────────────────────────┤
│  🔍 文档分析  [解析标书]              │
│                                      │
│  📋 项目概述 ▸          （折叠）       │
│  📑 投标文件框架结构 ▸   （折叠）       │  ← 新增
│                                      │
│  ┌──────────────┐ ┌──────────────┐   │
│  │ 技术评分要求  │ │ 💰商务/价格  │   │
│  └──────────────┘ └──────────────┘   │
└──────────────────────────────────────┘
```

---

## 2026-05-09 — 标书解析拆分为「技术 + 商务/价格」双通道

**目标：** 将原来只提取技术评分要求的解析流程，改为技术/商务分通道提取，项目概述收进折叠区。

### 修改清单

| # | 文件 | 改动 | 说明 |
|---|------|------|------|
| 1 | `backend/app/models/schemas.py` | `AnalysisType` 枚举加 `COMMERCIAL = "commercial"` | 新增商业评分分析类型 |
| 2 | `backend/app/utils/prompts/analysis_prompts.py` | 加 `elif analysis_type == "commercial"` 分支 | 新增商业评分提取 prompt（报价/资质/业绩/人员/信誉） |
| 3 | `frontend/src/types/index.ts` | `AppState` 接口加 `commercialRequirements: string` | 前端状态新增字段 |
| 4 | `frontend/src/hooks/useAppState.ts` | 加 `updateCommercialRequirements` callback + 初始化 + 导出 | 商业评分状态管理 |
| 5 | `frontend/src/utils/draftStorage.ts` | `DraftState` 加 `commercialRequirements` | localStorage 持久化 |
| 6 | `frontend/src/services/api.ts` | `AnalysisRequest.analysis_type` 加 `'commercial'`；`OutlineRequest.commercial` 改可选(`?:`) | API 类型扩展；修复 OutlineEdit 编译错误 |
| 7 | `frontend/src/pages/DocumentAnalysis.tsx` | 布局重组 + 第三次 SSE 调用 | 详见下方 |
| 8 | `frontend/src/App.tsx` | 透传 `commercialRequirements` + `onCommercialComplete` | 父组件状态桥接 |

### DocumentAnalysis.tsx 改动详情

1. **Props** 新增 `commercialRequirements` / `onCommercialComplete`
2. **状态** 新增 `editingCommercial` / `draftCommercial` / `streamingCommercial` / `currentAnalysisStep` 类型扩展
3. **handleAnalysis()** 新增第三次 SSE 调用，`analysis_type='commercial'`，完成后调 `onCommercialComplete`
4. **布局**：
   - 项目概述 → `<details>` 折叠区（📋 点击展开，默认折叠）
   - 左栏 → 技术评分要求（不变）
   - 右栏 → 💰 商务/价格评分要求（替换原项目概述位置）

### 页面布局前后对比

```
【改前】                            【改后】
┌──────────────────────┐           ┌──────────────────────┐
│  📄 文档上传          │           │  📄 文档上传          │
├──────────────────────┤           ├──────────────────────┤
│  🔍 文档分析          │           │  🔍 文档分析          │
│  [解析标书]           │           │  [解析标书]           │
│                      │           │                      │
│ ┌────────┐ ┌────────┐│           │  📋 项目概述 ▸        │ ← 折叠
│ │项目概述 │ │技术要求 ││           │                      │
│ │        │ │        ││           │ ┌────────┐ ┌────────┐│
│ └────────┘ └────────┘│           │ │技术要求 │ │💰商务价││
└──────────────────────┘           │ │        │ │格要求  ││
                                   │ └────────┘ └────────┘│
                                   └──────────────────────┘
```

### 解析流程变更

```
【改前】2 次 SSE
  overview → requirements

【改后】3 次 SSE
  overview → requirements → commercial
```

---

## 2026-05-04 — 初始搭建

- 项目拉取到 `/home/wintop/OpenBidKit_Yibiao`
- venv 创建，依赖安装
- CORS 改为 `allow_origins=["*"]`
- 后端 workers=1
- Cloudflare tunnel 安装
