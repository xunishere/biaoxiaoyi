"""后端服务启动脚本"""
import uvicorn
import os
import multiprocessing

if __name__ == "__main__":
    # 确保在正确的目录中运行
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # 允许外部设备访问
        port=8000,
        reload=False,  # 多进程模式下不支持reload
        log_level="info",
        workers=1  # 单 worker，开发/演示够用
    )