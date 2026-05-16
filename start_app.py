import subprocess
import os
import sys
import time

def start_server():
    # 设置编码
    if sys.platform.startswith('win'):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        
    print("🚀 正在通过 UV 环境启动 QuantStock-AI 系统...")
    
    # 强制 UTF-8 编码，防止 Windows 上的表情符号崩溃
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    
    # 构建命令
    cmd = ["uv", "run", "python", "app.py"]
    
    try:
        # 使用 subprocess.Popen 启动后台进程
        # Windows 特有标志: CREATE_NEW_PROCESS_GROUP 允许断开连接后继续运行
        process = subprocess.Popen(
            cmd,
            env=env,
            creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0,
            stdout=open("server_log.txt", "a", encoding="utf-8"),
            stderr=subprocess.STDOUT
        )
        
        print(f"✅ 系统已在后台启动！(PID: {process.pid})")
        print("🔗 访问地址: http://127.0.0.1:5000")
        print("📝 日志已重定向至: server_log.txt")
        
        # 简单等 2 秒看是否立刻挂了
        time.sleep(2)
        if process.poll() is not None:
            print("❌ 启动似乎失败了，请检查 server_log.txt")
        else:
            print("🚀 服务运行稳健。")
            
    except Exception as e:
        print(f"❌ 启动过程中发生错误: {e}")

if __name__ == "__main__":
    start_server()
