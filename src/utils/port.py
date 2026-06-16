from __future__ import annotations

import os
import re
import subprocess
import sys


def get_listening_pids(port: int, host: str = "127.0.0.1") -> list[int]:
    """获取占用指定端口的进程 PID（Windows）。"""
    if sys.platform != "win32":
        return _get_pids_unix(port)

    result = subprocess.run(
        ["netstat", "-ano"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    pids: set[int] = set()
    # TCP    127.0.0.1:8080    0.0.0.0:0    LISTENING    12345
    pattern = re.compile(rf"TCP\s+{re.escape(host)}:{port}\s+\S+\s+LISTENING\s+(\d+)", re.I)
    for line in result.stdout.splitlines():
        match = pattern.search(line)
        if match:
            pids.add(int(match.group(1)))
    return sorted(pids)


def _get_pids_unix(port: int) -> list[int]:
    result = subprocess.run(
        ["lsof", "-ti", f":{port}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [int(p) for p in result.stdout.split() if p.strip().isdigit()]


def process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        return str(pid) in result.stdout and "No tasks" not in result.stdout
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def free_port(port: int, host: str = "127.0.0.1") -> list[int]:
    """释放端口，返回已结束的 PID 列表。"""
    killed: list[int] = []
    for pid in get_listening_pids(port, host):
        if pid <= 0:
            continue
        if not process_exists(pid):
            continue
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)],
                    capture_output=True,
                    check=False,
                )
            else:
                subprocess.run(["kill", "-9", str(pid)], capture_output=True, check=False)
            killed.append(pid)
        except OSError:
            continue
    return killed


def is_port_blocked(port: int, host: str = "127.0.0.1") -> bool:
    """端口是否被真实进程占用（忽略 netstat 僵尸 PID）。"""
    return any(process_exists(pid) for pid in get_listening_pids(port, host))
