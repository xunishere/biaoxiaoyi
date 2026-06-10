# biaoxiaoyi — AI智能标书写作助手

基于大模型的智能标书写作工具，支持采购文件解析、双模式目录生成、正文撰写、缺口分析、智能评分、内容优化和合并导出全流程。

## 技术栈

- 前端：React + TypeScript + Tailwind CSS
- 后端：FastAPI + Python
- AI：OpenAI 兼容 SDK（支持 DeepSeek / 通义千问 / 智谱AI / 月之暗面 / SiliconFlow / OpenAI）

## 快速开始

```bash
# 后端
cd backend
pip install -r requirements.txt
python run.py

# 前端
cd frontend
npm install
npm start
```

## 项目结构

```
├── backend/                 # FastAPI 后端
│   └── app/
│       ├── routers/         # API 路由
│       ├── services/        # 业务逻辑
│       ├── models/          # 数据模型
│       └── utils/           # 工具（OpenAI SDK封装、prompts、SSE）
└── frontend/                # React 前端
    └── src/
        ├── pages/           # 页面组件
        ├── components/      # 通用组件
        ├── services/        # API 客户端
        ├── hooks/           # React Hooks
        └── utils/           # 工具（localStorage/IndexedDB持久化）
```

## 工作流

1. **标书解析** — 上传招标文件（Word/PDF），4轮SSE提取：项目概述→技术评分→商务评分→框架结构
2. **目录编辑** — 双模式生成：目录A（按评分标准）+ 目录B（按框架结构），可手动编辑
3. **正文编辑** — 生成正文（5并发）→ 缺口分析 → 评分表 → 优化薄弱章节 → 合并 → 导出Word

## License

MIT
