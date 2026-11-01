"""Share Campus Market through a temporary public Cloudflare tunnel.

What it does:
  1. Generates a random admin password for this sharing session.
  2. Starts the app with Waitress on 127.0.0.1:5000.
  3. Starts a Cloudflare quick tunnel and prints a public https URL.
  4. Keeps the computer awake while sharing; Ctrl+C stops the tunnel.

The original admin password is NOT changed. While this process runs, the
admin login accepts only the share password printed below; after it stops,
the normal database password works again.

Usage:
    python share.py
    python share.py --admin-password MySharePass1
    python share.py --no-tunnel
"""

import argparse
import ctypes
import os
import platform
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 5000
LOCAL_URL = f"http://{HOST}:{PORT}/"
URL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"


def random_password(length: int = 12) -> str:
    return "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(length))


def port_is_open() -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((HOST, PORT)) == 0


def page_is_ready() -> bool:
    try:
        with urllib.request.urlopen(LOCAL_URL, timeout=1.0) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def ensure_database() -> bool:
    configured = os.environ.get("DATABASE")
    database = (
        Path(configured)
        if configured
        else BASE_DIR / "instance" / "campus_market.db"
    )
    if database.exists():
        return True
    print("首次分享：正在生成演示数据……", flush=True)
    result = subprocess.run(
        [sys.executable, "seed.py", "--reset"], cwd=BASE_DIR, check=False
    )
    return result.returncode == 0 and database.exists()


def cloudflared_path() -> Path | None:
    configured = os.environ.get("CLOUDFLARED")
    if configured and Path(configured).is_file():
        return Path(configured)
    on_path = shutil.which("cloudflared")
    if on_path:
        return Path(on_path)
    local = (
        Path(os.environ.get("LOCALAPPDATA", Path.home()))
        / "CampusMarket"
        / "cloudflared.exe"
    )
    return local if local.is_file() else None


def download_cloudflared() -> Path | None:
    if platform.system() != "Windows":
        print(
            "当前分享脚本的自动下载仅支持 Windows。请安装 cloudflared 并设置 "
            "CLOUDFLARED 环境变量后重试。",
            flush=True,
        )
        return None

    target = (
        Path(os.environ.get("LOCALAPPDATA", Path.home()))
        / "CampusMarket"
        / "cloudflared.exe"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    url = (
        "https://github.com/cloudflare/cloudflared/releases/latest/download/"
        "cloudflared-windows-amd64.exe"
    )
    print("未找到 cloudflared，正在下载（约 40 MB，只需一次）……", flush=True)
    request = urllib.request.Request(
        url, headers={"User-Agent": "CampusMarket-Share/1.0"}
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            with target.open("wb") as output:
                shutil.copyfileobj(response, output)
    except (urllib.error.URLError, OSError) as exc:
        print(f"下载失败：{exc}", flush=True)
        print(
            "可以手动下载 cloudflared-windows-amd64.exe，重命名为 "
            "cloudflared.exe，放到 %LOCALAPPDATA%\\CampusMarket\\，或设置 "
            "CLOUDFLARED 环境变量。",
            flush=True,
        )
        return None

    if not target.is_file() or target.stat().st_size < 40 * 1024 * 1024:
        print("下载的文件不完整，请重试。", flush=True)
        target.unlink(missing_ok=True)
        return None

    try:
        probe = subprocess.run(
            [str(target), "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if probe.returncode != 0:
            raise RuntimeError(probe.stderr.strip() or "version check failed")
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
        print(f"cloudflared 校验失败：{exc}", flush=True)
        target.unlink(missing_ok=True)
        return None
    return target


def keep_awake(enabled: bool) -> None:
    if os.name != "nt":
        return
    try:
        if enabled:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        else:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
    except Exception:
        pass


def print_banner(public_url: str | None, admin_password: str) -> None:
    print("", flush=True)
    print("=" * 64, flush=True)
    print("校园集市已启动分享", flush=True)
    if public_url:
        print(f"公网链接   : {public_url}", flush=True)
        print("手机 / 电脑：把链接发到微信、QQ 或浏览器即可打开", flush=True)
    else:
        print(f"本机链接   : {LOCAL_URL}", flush=True)
    print("管理员账号 : admin", flush=True)
    print(f"管理员密码 : {admin_password}", flush=True)
    print("学生演示   : 2023001 / 2023002 / 2023003，密码 Demo@12345", flush=True)
    print("", flush=True)
    print("注意：任何拿到链接的人都可以注册、浏览和发布；", flush=True)
    print("      管理员只接受上面这一次的分享密码。", flush=True)
    print("      关闭窗口或按 Ctrl+C 后，公网链接立即失效。", flush=True)
    print("=" * 64, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Share Campus Market publicly.")
    parser.add_argument("--admin-password", default=None)
    parser.add_argument("--no-tunnel", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    os.chdir(BASE_DIR)
    if port_is_open():
        print(
            f"端口 {PORT} 已被占用。请先关闭本地启动的校园集市，再运行分享。",
            flush=True,
        )
        return 1

    if not ensure_database():
        print("演示数据初始化失败，请先运行 python seed.py --reset。", flush=True)
        return 1

    admin_password = args.admin_password or random_password()
    if len(admin_password) < 8:
        print("分享管理员密码至少需要 8 位。", flush=True)
        return 1

    # Must be set before importing the app/config.
    os.environ["SECRET_KEY"] = secrets.token_urlsafe(32)
    os.environ["CAMPUS_SHARE_ADMIN_HASH"] = generate_password_hash(admin_password)

    try:
        from waitress import serve
    except ImportError:
        print("缺少 waitress，请先运行：pip install -r requirements.txt", flush=True)
        return 1

    from app import create_app, db

    app = create_app()
    with app.app_context():
        admin = db.query_one(
            "SELECT id FROM users WHERE student_id = 'admin' AND role = 'admin'"
        )
        if admin is None:
            print("未找到管理员账号，请运行 python seed.py --reset。", flush=True)
            return 1

    server = threading.Thread(
        target=lambda: serve(app, host=HOST, port=PORT, threads=8),
        daemon=True,
    )
    server.start()

    ready = False
    for _ in range(30):
        if page_is_ready():
            ready = True
            break
        time.sleep(0.3)
    if not ready:
        print("本地服务器未能启动。", flush=True)
        return 1

    keep_awake(True)
    tunnel = None
    public_url = None

    try:
        if args.no_tunnel:
            print_banner(None, admin_password)
            if not args.no_browser:
                import webbrowser

                webbrowser.open(LOCAL_URL)
            while True:
                time.sleep(1)
        else:
            executable = cloudflared_path() or download_cloudflared()
            if executable is None:
                return 1

            print("正在建立 Cloudflare 公网隧道……", flush=True)
            tunnel = subprocess.Popen(
                [
                    str(executable),
                    "tunnel",
                    "--url",
                    LOCAL_URL,
                    "--no-autoupdate",
                    "--protocol",
                    "http2",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )

            state = {"url": None}

            def read_tunnel_output() -> None:
                for line in tunnel.stdout:
                    stripped = line.rstrip()
                    match = URL_PATTERN.search(stripped)
                    if match:
                        state["url"] = match.group(0)
                    if match or "ERR" in stripped or "failed" in stripped.lower():
                        print(stripped, flush=True)

            threading.Thread(target=read_tunnel_output, daemon=True).start()

            for _ in range(120):
                if state["url"] or tunnel.poll() is not None:
                    break
                time.sleep(0.5)

            public_url = state["url"]
            if not public_url:
                print(
                    "未能获取公网链接。请检查网络是否能访问 Cloudflare，"
                    "或改用同一 Wi-Fi / 云平台部署。",
                    flush=True,
                )
                return 1

            print_banner(public_url, admin_password)
            if not args.no_browser:
                import webbrowser

                webbrowser.open(public_url)

            while tunnel.poll() is None:
                time.sleep(1)
            print("隧道已退出。", flush=True)
            return tunnel.returncode or 0
    except KeyboardInterrupt:
        print("\n正在停止分享……", flush=True)
        return 0
    finally:
        keep_awake(False)
        if tunnel is not None and tunnel.poll() is None:
            tunnel.terminate()
            try:
                tunnel.wait(timeout=5)
            except subprocess.TimeoutExpired:
                tunnel.kill()


if __name__ == "__main__":
    raise SystemExit(main())
