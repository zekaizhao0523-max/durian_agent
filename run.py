"""榴莲 Agent 统一启动入口。

用法:
    python run.py              # 默认 8080，自动释放占用
    python run.py --port 8080
    python run.py --no-kill    # 不自动结束占用端口的进程
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import uvicorn
from dotenv import load_dotenv

load_dotenv()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
os.environ.setdefault("PYTHONUTF8", "1")


def main() -> None:
    from src.config.settings import get_settings
    from src.utils.port import free_port, is_port_blocked

    get_settings.cache_clear()
    settings = get_settings()

    parser = argparse.ArgumentParser(description="榴莲 Agent 服务")
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", type=int, default=settings.port)
    parser.add_argument("--reload", action="store_true", help="开发模式热重载")
    parser.add_argument("--no-kill", action="store_true", help="不自动释放端口")
    args = parser.parse_args()

    if not args.no_kill and is_port_blocked(args.port, args.host):
        print(f"端口 {args.host}:{args.port} 被占用，正在释放...")
        killed = free_port(args.port, args.host)
        if killed:
            print(f"已结束进程: {killed}")
            time.sleep(2)
        if is_port_blocked(args.port, args.host):
            print(
                f"无法释放端口 {args.port}。\n"
                "请手动在任务管理器结束对应 Python 进程后重试。",
                file=sys.stderr,
            )
            sys.exit(1)

    print(f"启动服务: http://{args.host}:{args.port}")
    print(f"数据库: {settings.database_url.split('@')[-1] if '@' in settings.database_url else settings.database_url}")

    uvicorn.run(
        "src.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
