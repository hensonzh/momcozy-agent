from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any


KEY_ERROR = "error"
KEY_TEXT = "text"
KEY_PROCESS_L = "process_l"
KEY_PROCESS_R = "process_r"
KEY_PROCESS_ALL = "process_all"
TICKS_PER_SEC = 20


class LogDrivenSessionManager:
    """Log-backed pump progress calculator compatible with the source API."""

    def __init__(self, json_dir: str | Path = "configs", log_dir: str | Path = "logs") -> None:
        self._json_dir = Path(json_dir)
        self._log_dir = Path(log_dir)
        self._json_dir.mkdir(parents=True, exist_ok=True)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, asyncio.Lock] = {}
        self._meta_lock = asyncio.Lock()

    async def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        user_id = str(payload.get("user_id", "") or "").strip()
        if not user_id:
            raise ValueError("请求缺少 user_id 字段")

        tasks: dict[str, asyncio.Task[tuple[int, str]]] = {}
        if isinstance(payload.get("device_left"), dict):
            tasks["left"] = asyncio.create_task(self._process_side(user_id, "left", payload["device_left"]))
        if isinstance(payload.get("device_right"), dict):
            tasks["right"] = asyncio.create_task(self._process_side(user_id, "right", payload["device_right"]))
        if not tasks:
            raise ValueError("device_left or device_right is required")

        result: dict[str, Any] = {"user_id": user_id}
        values: list[int] = []
        texts: list[str] = []
        error = 0
        for side, task in tasks.items():
            key = KEY_PROCESS_L if side == "left" else KEY_PROCESS_R
            try:
                process, text = await task
                result[key] = process
                if process >= 0:
                    values.append(process)
                if text:
                    texts.append(f"[{'左' if side == 'left' else '右'}] {text}")
            except Exception as exc:
                error = -1
                result[key] = -1
                texts.append(f"[{'左' if side == 'left' else '右'}] 计算异常: {exc}")

        result[KEY_ERROR] = error
        result[KEY_TEXT] = "; ".join(texts)
        result[KEY_PROCESS_ALL] = int(round(sum(values) / len(values))) if values else -1
        return result

    async def remove_session(self, user_id: str) -> None:
        for side in ("left", "right"):
            async with self._meta_lock:
                self._locks.pop(self._lock_key(user_id, side), None)

    async def _process_side(self, user_id: str, side: str, device: dict[str, Any]) -> tuple[int, str]:
        lock = await self._get_lock(user_id, side)
        async with lock:
            step = str(device.get("step", "") or "").strip().lower()
            if step not in {"start", "running", "pause", "stop", "offline"}:
                raise ValueError("step must be one of start, running, pause, stop, offline")

            config = self._load_config(user_id, side)
            log_path = self._log_path(user_id, side)
            previous = None if step == "start" else self._read_last_row(log_path)
            previous_output = previous.get("output", {}) if isinstance(previous, dict) else {}
            previous_process = int(previous_output.get("process", 0) or 0)

            if step in {"pause", "stop", "offline"}:
                process = previous_process
                text = ""
            else:
                cap_data = device.get("cap_data")
                if not isinstance(cap_data, list):
                    raise ValueError("cap_data must be an array of integers")
                if len(cap_data) != TICKS_PER_SEC:
                    raise ValueError(f"cap_data 长度须为 {TICKS_PER_SEC}，当前为 {len(cap_data)}")
                process, text = self._advance_process(previous_process, cap_data, device, config)

            row = {
                "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "step": step,
                "cap_data": device.get("cap_data") if isinstance(device.get("cap_data"), list) else [],
                "milk_reel": device.get("milk_reel"),
                "bandpower": device.get("bandpower"),
                "milk": device.get("milk"),
                "output": {"process": process, "text": text},
                "sm_state": {"process": process},
            }
            self._append_log(log_path, row)

        if step == "stop":
            async with self._meta_lock:
                self._locks.pop(self._lock_key(user_id, side), None)
        return process, text

    def _advance_process(self, previous: int, cap_data: list[Any], device: dict[str, Any], config: dict[str, Any]) -> tuple[int, str]:
        signal = sum(abs(float(value)) for value in cap_data) / max(len(cap_data), 1)
        milk_reel = int(device.get("milk_reel", 0) or 0)
        milk = max(0, int(device.get("milk", 0) or 0))
        bandpower = max(0, int(device.get("bandpower", 0) or 0))
        base_increment = float(config.get("base_increment", 1.0) or 1.0)
        signal_scale = float(config.get("signal_scale", 0.02) or 0.02)
        milk_scale = float(config.get("milk_scale", 0.05) or 0.05)
        bandpower_scale = float(config.get("bandpower_scale", 0.01) or 0.01)

        increment = base_increment + signal * signal_scale + milk * milk_scale + bandpower * bandpower_scale
        if milk_reel & 0b1:
            increment += float(config.get("milk_reel_increment", 1.0) or 1.0)
        if milk_reel & 0b10:
            increment += float(config.get("letdown_increment", 2.0) or 2.0)
        process = max(0, min(100, int(round(previous + increment))))
        text = "检测到奶阵信号" if milk_reel & 0b10 else ""
        return process, text

    def _load_config(self, user_id: str, side: str) -> dict[str, Any]:
        candidates = [
            self._json_dir / f"{user_id}_{side}.json",
            self._json_dir / f"st_001_{side}.json",
        ]
        for path in candidates:
            if path.exists():
                with path.open("r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
                return loaded if isinstance(loaded, dict) else {}
        raise FileNotFoundError(f"参数文件未找到: {candidates[0].resolve()}")

    def _lock_key(self, user_id: str, side: str) -> str:
        return f"{user_id}:{side}"

    async def _get_lock(self, user_id: str, side: str) -> asyncio.Lock:
        key = self._lock_key(user_id, side)
        async with self._meta_lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            return self._locks[key]

    def _log_path(self, user_id: str, side: str) -> Path:
        return self._log_dir / f"{user_id}_{datetime.now().strftime('%Y%m%d')}_{side}.jsonl"

    def _read_last_row(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        last = ""
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last = line
        if not last:
            return {}
        try:
            loaded = json.loads(last)
            return loaded if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _append_log(self, path: Path, row: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
