# model Windows 运行说明

这个文件说明如何在 Windows 上运行 `model` 数据集构建工具，也就是：

```text
model\openai-rfp-response-analyzer
```

它提供 `http://localhost:5001` 页面，用于上传采购文件、投标文件、最终得分文件，并生成：

| 输出 | 文件 |
|------|------|
| 采购评分细则 | `model\dataset_extraction_output\procurement_scoring_criteria.json` |
| 投标响应片段 | `model\dataset_extraction_output\bid_response_fragments.json` |
| 采购-投标映射 | `model\dataset_extraction_output\procurement_bid_mapping.json` |
| 响应文本特征 | `model\dataset_extraction_output\criterion_response_features.json` |
| 得分点/扣分点分析 | `model\dataset_extraction_output\score_point_analysis.json` |

## 1. 运行方式建议

| 方式 | 适合场景 | 说明 |
|------|----------|------|
| Windows 原生运行 | 开发、演示、小文件测试 | 可以跑 Flask、MiMo、PDF/Word 文本处理；PP-StructureV3 CPU 会比较慢 |
| WSL2 Ubuntu 运行 | 正式跑 PP-StructureV3/GPU | 更接近当前开发环境，PaddleOCR/GPU/Poppler 更稳定 |

如果只是先把页面跑起来，用 Windows 原生即可。  
如果要长时间跑采购评分表 OCR，建议用 WSL2。

## 2. 需要安装的软件

| 软件 | 建议版本 | 用途 |
|------|----------|------|
| Python | 3.12 | Flask + 数据处理流水线 |
| Poppler | 最新稳定版 | `pdfinfo` / `pdftotext` / `pdftoppm` |
| Visual C++ Redistributable / Build Tools | 可选 | 安装部分 Python 包时备用 |
| CUDA | 可选 | 如果要尝试 GPU PaddleOCR |

建议项目路径不要带空格，例如：

```powershell
C:\workspace\biaoxiaoyi
```

## 3. 安装 Poppler

Poppler 必须能在 PowerShell 中直接调用：

```powershell
pdfinfo -v
pdftotext -v
pdftoppm -v
```

如果这些命令不存在，任选一种方式安装。

方式 A：使用 Chocolatey：

```powershell
choco install poppler
```

方式 B：使用 winget：

```powershell
winget install -e --id oschwartz10612.Poppler
```

方式 C：手动下载 Poppler Windows 版本，把 `bin` 目录加入系统 `PATH`。

加入 PATH 后，重新打开 PowerShell 再检查：

```powershell
pdfinfo -v
```

## 4. 创建 Python 虚拟环境

在仓库根目录执行：

```powershell
cd C:\workspace\biaoxiaoyi
cd model

py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip setuptools wheel
```

如果 PowerShell 不允许激活虚拟环境：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
```

## 5. 安装基础依赖

```powershell
pip install -r openai-rfp-response-analyzer\requirements.txt
```

这些依赖只包含 Flask、OpenAI SDK、PDF/图片基础库。  
要跑 PP-StructureV3，还需要额外安装 PaddleOCR。

## 6. 安装 PaddleOCR / PP-StructureV3

先装 CPU 版本，最稳：

```powershell
pip install paddleocr
pip install paddlepaddle
```

检查：

```powershell
python -c "from paddleocr import PPStructureV3; print('PPStructureV3 OK')"
```

如果你要用 GPU，请按你的 CUDA 版本去 PaddlePaddle 官方安装页选择对应命令。当前项目在 Linux/WSL2 环境里验证过 `CUDA 12.6 + paddlepaddle-gpu`，Windows 原生 GPU 组合更容易受驱动、CUDA、Paddle 版本影响。

GPU 不稳定时，先用 CPU 跑通流程。

## 7. 配置 MiMo / OpenAI 兼容模型

编辑：

```powershell
notepad .env
```

写入：

```ini
MIMO_API_KEY=你的key
MIMO_BASE_URL=https://你的OpenAI兼容地址/v1
MIMO_MODEL=deepseek-v4-pro

# 可选：首次下载 PaddleOCR/HuggingFace 模型慢时使用
HF_ENDPOINT=https://hf-mirror.com
```

注意：`.env` 放在 `model\.env`，不是 `model\openai-rfp-response-analyzer\.env`。

如果使用 DeepSeek 官方 API，推荐：

```ini
MIMO_BASE_URL=https://api.deepseek.com/v1
MIMO_MODEL=deepseek-v4-pro
```

`deepseek-v4-pro` 质量更好，适合评分细则标注、映射判断、得扣分归因。  
如果更在意速度和成本，可以换成：

```ini
MIMO_MODEL=deepseek-v4-flash
```

如果暂时不想消耗模型 API，可以在页面勾选：

```text
跳过 MiMo，只使用规则结果
```

但映射和得扣分分析质量会下降。

## 8. 启动 Web 页面

在 `model` 目录已激活虚拟环境的情况下执行：

```powershell
cd C:\workspace\biaoxiaoyi\model\openai-rfp-response-analyzer
..\.venv\Scripts\python.exe main.py
```

浏览器打开：

```text
http://localhost:5001
```

默认会绑定：

```text
0.0.0.0:5001
```

也就是同一内网的其他机器可以通过本机 IPv4 访问：

```text
http://你的电脑IPv4:5001
```

查看本机 IPv4：

```powershell
ipconfig
```

找无线网卡或以太网卡下的 `IPv4 地址`，例如：

```text
192.168.1.23
```

其他机器访问：

```text
http://192.168.1.23:5001
```

### 8.1 Windows 内网启动脚本，推荐

也可以直接运行：

```powershell
cd C:\workspace\biaoxiaoyi\model\openai-rfp-response-analyzer
.\start_windows_lan.bat
```

这个脚本会做三件事：

1. 设置 `HOST=0.0.0.0`、`PORT=5001`。
2. 尝试添加 Windows 防火墙入站规则，放行 TCP `5001`。
3. 打印本机可用的内网访问地址。

如果添加防火墙规则失败，用管理员身份重新运行这个脚本，或者手动执行：

```powershell
netsh advfirewall firewall add rule name="Biaoxiaoyi Model 5001" dir=in action=allow protocol=TCP localport=5001
```

如果要换端口：

```powershell
$env:PORT=5002
..\.venv\Scripts\python.exe main.py
```

然后打开：

```text
http://localhost:5002
```

## 9. 页面怎么用

左侧上传三个区域：

| 上传区 | 是否必填 | 支持 |
|--------|----------|------|
| 采购文件 | 必填，可多选 | PDF / Word / 图片等相关文档 |
| 投标技术文件 | 必填，可多选 | PDF / Word / 图片等相关文档 |
| 最终得分文件 | 可选 | JSON / PDF / Word / Excel / 图片 |

点击：

```text
运行切分/标注/映射
```

输出会保存到：

```text
model\dataset_extraction_output
```

页面上的“刷新结果报告”会读取这个目录里的结果。

## 10. 命令行运行流水线，可选

如果不走 Web 页面，可以直接跑：

```powershell
cd C:\workspace\biaoxiaoyi\model
.\.venv\Scripts\python.exe run_extraction_pipeline.py
```

常用参数：

```powershell
# 不调用 MiMo，只用规则
.\.venv\Scripts\python.exe run_extraction_pipeline.py --skip-mimo

# PP-StructureV3 结果已存在时跳过 OCR
.\.venv\Scripts\python.exe run_extraction_pipeline.py --skip-pp

# 只重新跑响应特征
.\.venv\Scripts\python.exe run_extraction_pipeline.py --features-only --force-features

# 只重新跑得扣分分析
.\.venv\Scripts\python.exe run_extraction_pipeline.py --analysis-only --force-analysis
```

## 11. 清理输出缓存

想重新开始一轮，可以删除输出目录里的 JSON/MD：

```powershell
cd C:\workspace\biaoxiaoyi\model
Remove-Item .\dataset_extraction_output\*.json -Force
Remove-Item .\dataset_extraction_output\*.md -Force
```

上传文件缓存在：

```text
model\openai-rfp-response-analyzer\uploads
```

需要时可以手动清理。

## 12. 常见问题

### 12.1 `No module named 'paddleocr'`

说明当前启动用的不是 `model\.venv`，或者没有安装 PaddleOCR。

检查：

```powershell
cd C:\workspace\biaoxiaoyi\model
.\.venv\Scripts\python.exe -m pip show paddleocr
```

没有结果就安装：

```powershell
.\.venv\Scripts\python.exe -m pip install paddleocr paddlepaddle
```

启动时必须用：

```powershell
.\.venv\Scripts\python.exe openai-rfp-response-analyzer\main.py
```

或者在 app 目录：

```powershell
..\.venv\Scripts\python.exe main.py
```

### 12.2 `pdfinfo` / `pdftotext` / `pdftoppm` 找不到

Poppler 没装好，或者 `bin` 目录没加到 PATH。

重新打开 PowerShell 后检查：

```powershell
pdfinfo -v
```

### 12.3 第一次运行特别慢

正常。PP-StructureV3 第一次会下载 OCR、版面分析、表格识别模型，可能需要 1 GB 以上缓存。

如果网络慢，可在 `model\.env` 里加：

```ini
HF_ENDPOINT=https://hf-mirror.com
```

### 12.4 MiMo API 一直消耗

页面不要同时开多个任务。当前流程会串行跑：

```text
评分表定位 -> PP-StructureV3 -> MiMo规整/标注 -> 投标切分 -> 映射 -> 特征 -> 得扣分分析
```

如果只想验证文件切分，勾选：

```text
跳过 MiMo，只使用规则结果
```

### 12.5 映射很慢

这是预期的。复杂评分项会把候选片段送给 MiMo 判断，尤其 `功能设计`、`团队综合能力` 这种 1 对多评分项会更慢。

### 12.6 端口 5001 被占用

```powershell
netstat -ano | findstr :5001
taskkill /PID 进程号 /F
```

或者换端口：

```powershell
$env:PORT=5002
..\.venv\Scripts\python.exe main.py
```

### 12.7 内网其他机器打不开 `http://你的IP:5001`

按顺序检查：

1. 服务启动时是否显示 `LAN access: http://...:5001`。
2. Windows 防火墙是否放行 TCP `5001`。
3. 两台机器是否在同一个局域网。
4. 访问的是服务器电脑的 IPv4，不是 `127.0.0.1` 或 `localhost`。
5. 公司/校园网络是否开启了 AP 隔离或客户端隔离。

手动放行防火墙：

```powershell
netsh advfirewall firewall add rule name="Biaoxiaoyi Model 5001" dir=in action=allow protocol=TCP localport=5001
```

在服务器电脑上确认端口监听：

```powershell
netstat -ano | findstr :5001
```

应该能看到类似：

```text
0.0.0.0:5001
```

### 12.8 Windows 原生 PaddleOCR/GPU 跑不通

优先使用 CPU 跑通：

```powershell
pip uninstall -y paddlepaddle-gpu
pip install paddlepaddle
```

如果必须 GPU，建议改用 WSL2 Ubuntu 跑 `model`，因为当前项目的 PP-StructureV3/GPU 路线更接近 Linux 环境。

## 13. 关闭服务

在运行 `main.py` 的 PowerShell 窗口按：

```text
Ctrl + C
```
