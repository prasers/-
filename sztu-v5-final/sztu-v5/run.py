"""
run.py - Vercel 部署入口
Vercel Python Runtime 启动 Streamlit 应用
"""
import subprocess
import sys
import os

def handler(request, response):
    """Vercel Serverless Function Handler"""
    port = int(os.environ.get("PORT", 8501))
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", "app.py",
            "--server.port", str(port),
            "--server.headless", "true",
            "--server.enableCORS", "false",
            "--server.enableXsrfProtection", "false",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {"statusCode": 200, "body": "Streamlit started"}


if __name__ == "__main__":
    # 本地直接运行：python run.py
    port = int(os.environ.get("PORT", 8501))
    os.execvp(
        sys.executable,
        [
            sys.executable, "-m", "streamlit", "run", "app.py",
            "--server.port", str(port),
            "--server.headless", "true",
        ]
    )
