"""
服务管理：把一堆黑窗口收进面板里。

- 每个服务 = 一个配置项（key/name/port/cmd/cwd/auto）
- 状态靠端口判断（TCP 连得上即在线），pid 从 netstat 反查
- 启动：subprocess.Popen 起在后台，输出重定向到 logs/<key>.log
- 停止：taskkill /F /T /PID（连同子进程）
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent
LOG_DIR = BASE / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 本进程自己（面板后端）不通过 subprocess 管，只做状态展示
SELF_KEY = "panel"


def port_alive(port: int, host: str = "127.0.0.1", timeout: float = 0.35) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except Exception:
        return False


def pid_on_port(port: int) -> int | None:
    """用 netstat 反查监听该端口的 pid（Windows）。"""
    try:
        out = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True, text=True, timeout=6,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout
    except Exception:
        return None
    tag = f":{port}"
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        if parts[1].endswith(tag) and parts[3].upper() == "LISTENING":
            try:
                return int(parts[4])
            except ValueError:
                pass
    return None


def _log_path(key: str) -> Path:
    return LOG_DIR / f"{key}.log"


def tail_log(key: str, lines: int = 120) -> str:
    p = _log_path(key)
    if not p.exists():
        return ""
    try:
        data = p.read_bytes()
    except Exception:
        return ""
    text = data.decode("utf-8", "replace")
    rows = text.splitlines()
    return "\n".join(rows[-max(1, min(lines, 800)):])


class ServiceManager:
    def __init__(self, services: list[dict[str, Any]]):
        self.specs = {s["key"]: s for s in services if s.get("key")}
        self.procs: dict[str, subprocess.Popen] = {}

    # ── 查询 ──────────────────────────────────────────────
    def status(self, key: str) -> dict[str, Any]:
        spec = self.specs.get(key) or {}
        port = int(spec.get("port") or 0)
        alive = port_alive(port) if port else False
        pid = pid_on_port(port) if port else None
        proc = self.procs.get(key)
        return {
            "key": key,
            "name": spec.get("name", key),
            "desc": spec.get("desc", ""),
            "port": port,
            "alive": alive,
            "pid": pid,
            "managed": key != SELF_KEY,
            "auto": bool(spec.get("auto")),
            "spawned": bool(proc and proc.poll() is None),
            "log": str(_log_path(key)),
        }

    def all_status(self) -> list[dict[str, Any]]:
        return [self.status(k) for k in self.specs]

    # ── 启停 ──────────────────────────────────────────────
    def start(self, key: str) -> dict[str, Any]:
        spec = self.specs.get(key)
        if not spec:
            return {"ok": False, "error": f"未知服务 {key}"}
        if key == SELF_KEY:
            return {"ok": False, "error": "面板后端就是我自己，重启请用启动脚本"}
        port = int(spec.get("port") or 0)
        if port and port_alive(port):
            return {"ok": True, "skipped": True, "msg": "已在运行"}

        cwd = spec.get("cwd") or str(BASE)
        cmd = spec.get("cmd") or ""
        if not cmd:
            return {"ok": False, "error": "没有配置启动命令"}

        log = _log_path(key)
        f = open(log, "ab")
        f.write(f"\n\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} start =====\n".encode())
        f.flush()

        flags = 0
        if os.name == "nt":
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

        try:
            proc = subprocess.Popen(
                cmd, cwd=cwd, shell=True, stdout=f, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, creationflags=flags, close_fds=True,
            )
        except Exception as e:
            return {"ok": False, "error": f"启动失败：{e}"}
        self.procs[key] = proc

        # 等端口起来（最多 ~12 秒）
        for _ in range(24):
            if not port or port_alive(port):
                break
            time.sleep(0.5)
        st = self.status(key)
        st.update({"ok": True, "started": True})
        return st

    def stop(self, key: str) -> dict[str, Any]:
        if key == SELF_KEY:
            return {"ok": False, "error": "面板后端就是我自己，不能从这里停"}
        spec = self.specs.get(key) or {}
        port = int(spec.get("port") or 0)
        pid = pid_on_port(port) if port else None
        proc = self.procs.get(key)

        killed = False
        if pid:
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                               capture_output=True, timeout=10,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                killed = True
            except Exception:
                pass
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                killed = True
            except Exception:
                pass
        self.procs.pop(key, None)

        for _ in range(10):
            if not port or not port_alive(port):
                break
            time.sleep(0.4)
        st = self.status(key)
        st.update({"ok": True, "stopped": killed})
        return st

    def restart(self, key: str) -> dict[str, Any]:
        self.stop(key)
        time.sleep(0.6)
        return self.start(key)

    def autostart(self) -> list[str]:
        """开机时把标记 auto 的服务拉起来（端口已通就跳过）。"""
        started = []
        for key, spec in self.specs.items():
            if not spec.get("auto") or key == SELF_KEY:
                continue
            port = int(spec.get("port") or 0)
            if port and port_alive(port):
                continue
            r = self.start(key)
            if r.get("ok"):
                started.append(key)
        return started
