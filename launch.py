"""One-click launcher for the Campus Market demo.

Local mode (default):
    python launch.py
    Starts Flask on 127.0.0.1:5000 and opens the PC browser.

LAN mode (phone on the same Wi-Fi):
    python launch.py --lan
    Starts Waitress on 0.0.0.0 and prints http://<your-LAN-IP>:<port>/.
    Open that address in the phone browser.

Closing the console window stops the server when it was started here.
"""

import argparse
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_PORT = 5000
OPEN_BROWSER = "--no-browser" not in sys.argv


def port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def page_is_ready(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1.0) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"


def ensure_database() -> None:
    import os

    configured = os.environ.get("DATABASE")
    database = (
        Path(configured)
        if configured
        else BASE_DIR / "instance" / "campus_market.db"
    )
    if database.exists():
        return
    print("首次启动：正在生成演示数据……", flush=True)
    subprocess.run(
        [sys.executable, "seed.py", "--reset"],
        cwd=BASE_DIR,
        check=False,
    )


def choose_port(start: int) -> int:
    for port in range(start, start + 10):
        if not port_is_open(port):
            return port
    return start


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--lan",
        action="store_true",
        help="listen on 0.0.0.0 and print a phone-on-same-Wi-Fi URL",
    )
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    import os

    os.chdir(BASE_DIR)
    port = choose_port(DEFAULT_PORT) if args.lan else DEFAULT_PORT
    local_url = f"http://127.0.0.1:{port}/"

    if page_is_ready(local_url):
        print(f"校园集市已在运行：{local_url}", flush=True)
        if not args.no_browser:
            webbrowser.open(local_url)
        return 0

    if port_is_open(port):
        print(f"端口 {port} 已被占用。请关闭占用它的程序后重试。", flush=True)
        if sys.stdin.isatty():
            input("按回车关闭……")
        return 1

    ensure_database()
    print("正在启动校园集市……", flush=True)

    process = None
    if args.lan:
        try:
            from waitress import serve
        except ImportError:
            print("缺少 waitress，请先运行：pip install -r requirements.txt", flush=True)
            return 1
        from app import create_app

        app = create_app()
        threading.Thread(
            target=lambda: serve(
                app, host="0.0.0.0", port=port, threads=8
            ),
            daemon=True,
        ).start()
    else:
        process = subprocess.Popen([sys.executable, "run.py"], cwd=BASE_DIR)

    ready = False
    for _ in range(60):
        if page_is_ready(local_url):
            ready = True
            break
        if process is not None and process.poll() is not None:
            break
        time.sleep(0.5)

    if not ready:
        print("服务器未能启动。请查看上方错误信息。", flush=True)
        if sys.stdin.isatty():
            input("按回车关闭……")
        return 1

    print(f"电脑打开：{local_url}", flush=True)
    if args.lan:
        phone_url = f"http://{lan_ip()}:{port}/"
        print(f"手机同 Wi-Fi 打开：{phone_url}", flush=True)
        print("手机和电脑必须连接同一个 Wi-Fi；如果 Windows 弹出防火墙提示，请允许。", flush=True)
    print("关闭此窗口即可停止服务。", flush=True)

    if not args.no_browser:
        webbrowser.open(local_url)

    try:
        if process is not None:
            process.wait()
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        if process is not None:
            process.terminate()
            process.wait(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
