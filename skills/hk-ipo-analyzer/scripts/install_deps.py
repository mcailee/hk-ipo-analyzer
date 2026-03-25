#!/usr/bin/env python3
"""检查并安装 hk-ipo-analyzer 所需的 Python 依赖。"""

import subprocess
import sys
from pathlib import Path

REQUIRED = {
    "click": "click>=8.1",
    "rich": "rich>=13.0",
    "requests": "requests>=2.31",
    "bs4": "beautifulsoup4>=4.12",
    "pdfplumber": "pdfplumber>=0.10",
    "matplotlib": "matplotlib>=3.8",
    "jinja2": "jinja2>=3.1",
    "yaml": "pyyaml>=6.0",
}


def check_and_install():
    missing = []
    for import_name, pip_name in REQUIRED.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_name)

    if not missing:
        print("✅ 所有依赖已安装。")
        return True

    print(f"📦 缺少依赖: {', '.join(missing)}")
    print("正在安装...")

    req_file = Path(__file__).parent / "requirements.txt"
    cmd = [sys.executable, "-m", "pip", "install", "--user", "-r", str(req_file)]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print("✅ 依赖安装成功。")
        return True
    else:
        print(f"❌ 安装失败:\n{result.stderr}")
        return False


if __name__ == "__main__":
    success = check_and_install()
    sys.exit(0 if success else 1)
