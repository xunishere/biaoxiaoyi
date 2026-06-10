# biaoxiaoyi Windows 运行说明

这个文件说明如何在 Windows 上运行根项目 `biaoxiaoyi`：前端 React 页面 + 后端 FastAPI 服务。

> 这个 README 对应仓库根目录。`model` 里的数据集切分/映射工具请看 [`model/README_FOR_WINDOWS.md`](model/README_FOR_WINDOWS.md)。

## 1. 需要安装的软件

| 软件 | 建议版本 | 用途 |
|------|----------|------|
| Git | 最新稳定版 | 拉取代码 |
| Python | 3.11 或 3.12 | 后端 FastAPI |
| Node.js | 18 LTS 或 20 LTS | 前端 React |
| VS Build Tools | 可选 | 少数 Python 包需要本地编译时使用 |

建议把项目放在没有空格和中文的路径，例如：

```powershell
C:\workspace\biaoxiaoyi
```

## 2. 拉取代码

```powershell
cd C:\workspace
git clone https://github.com/xunishere/biaoxiaoyi.git
cd biaoxiaoyi
```

如果已经有代码，直接进入项目目录即可：

```powershell
cd C:\workspace\biaoxiaoyi
```

## 3. 安装后端依赖

在项目根目录执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r backend\requirements.txt
```

如果 PowerShell 不允许激活虚拟环境，先执行一次：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

然后重新执行：

```powershell
.\.venv\Scripts\Activate.ps1
```

## 4. 安装前端依赖

```powershell
cd frontend
npm install
```

如果国内网络安装慢，可以换 npm 镜像：

```powershell
npm config set registry https://registry.npmmirror.com
npm install
```

## 5. 配置前端访问后端

在 `frontend` 目录创建 `.env`：

```powershell
copy .env.example .env
notepad .env
```

推荐内容：

```ini
REACT_APP_API_URL=http://localhost:8000
PORT=3000
```

如果 `3000` 被占用，可以把 `PORT` 改成 `3001` 或其他端口。

## 6. 启动开发环境

需要开两个 PowerShell 窗口。

第一个窗口启动后端：

```powershell
cd C:\workspace\biaoxiaoyi
.\.venv\Scripts\Activate.ps1
python backend\run.py
```

看到类似下面内容说明后端启动成功：

```text
Uvicorn running on http://0.0.0.0:8000
```

第二个窗口启动前端：

```powershell
cd C:\workspace\biaoxiaoyi\frontend
npm start
```

浏览器打开：

```text
http://localhost:3000
```

后端接口文档：

```text
http://localhost:8000/docs
```

## 7. 配置大模型 Key

根项目的大模型配置不依赖 `.env`，在页面左侧或配置面板里填写：

| 字段 | 示例 |
|------|------|
| API Key | `sk-...` |
| Base URL | `https://api.openai.com/v1` 或其他 OpenAI 兼容地址 |
| Model | `gpt-4o` / `qwen-plus` / `deepseek-chat` 等 |

保存后会写到当前 Windows 用户目录：

```text
%USERPROFILE%\.ai_write_helper\user_config.json
```

## 8. 单端口运行，可选

开发时推荐第 6 节的双端口方式。需要只开一个端口时，可以先构建前端，再由后端托管静态页面：

```powershell
cd C:\workspace\biaoxiaoyi\frontend
npm run build

cd ..
python -c "import shutil; shutil.copytree('frontend/build', 'backend/static', dirs_exist_ok=True)"

.\.venv\Scripts\Activate.ps1
python backend\run.py
```

然后访问：

```text
http://localhost:8000
```

仓库里也有 `single_port.bat`，但里面的 Python 路径可能是本机固定路径。若要用它，需要先把脚本中的 Python 路径改成你的虚拟环境路径，例如：

```text
C:\workspace\biaoxiaoyi\.venv\Scripts\python.exe
```

## 9. 常见问题

### 9.1 `python` 或 `py` 找不到

重新安装 Python，并勾选：

```text
Add python.exe to PATH
```

然后重新打开 PowerShell。

### 9.2 `npm` 找不到

安装 Node.js LTS，安装后重新打开 PowerShell：

```powershell
node -v
npm -v
```

### 9.3 前端请求失败

检查后端是否在运行：

```text
http://localhost:8000/docs
```

检查 `frontend\.env` 是否是：

```ini
REACT_APP_API_URL=http://localhost:8000
```

修改 `.env` 后需要重启 `npm start`。

### 9.4 端口被占用

查看占用端口的进程：

```powershell
netstat -ano | findstr :8000
netstat -ano | findstr :3000
```

结束进程：

```powershell
taskkill /PID 进程号 /F
```

### 9.5 文档上传失败

根项目后端默认上传大小是 10 MB，配置在：

```text
backend\app\config.py
```

如果要处理更大的文件，可以调整：

```python
max_file_size: int = 10 * 1024 * 1024
```

### 9.6 大模型报错

优先检查三件事：

1. API Key 是否正确。
2. Base URL 是否以 `/v1` 结尾，取决于模型服务商要求。
3. Model 名称是否是服务商支持的真实模型名。

## 10. 关闭服务

在两个 PowerShell 窗口分别按：

```text
Ctrl + C
```

