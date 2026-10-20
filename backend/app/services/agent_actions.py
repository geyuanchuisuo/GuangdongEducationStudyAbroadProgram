"""Agent 对话内指令式业务处理共用工具（v6.11.59）。

对话即办理：学生/员工 Agent 会话中的写指令，由 Dify 在回复里输出 ```json 代码块
（{"action_type": ..., "params": {...}, "summary": ...}），后端解析后直接落库
（复用既有业务服务，防重/校验规则不变），用户看到的是自然语言说明 + 执行回执。

流式扣留（ActionStreamExtractor）：逐 token 下发时把 ```json 围栏块整体扣留，
块闭合即交给调用方执行，回执文本另行下发——前端不会闪现原始 JSON。
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime

_FENCE_RE = re.compile(r"```[a-zA-Z]*\s*(\{.*?\})\s*```", re.S)


def _parse_action(obj: object) -> dict | None:
    """校验 JSON 对象是否为合法 action（含 action_type 字符串字段）。

    兼容结构漂移：顶层、{"action": {...}} 包装层里找 action_type。
    """
    if not isinstance(obj, dict):
        return None
    if isinstance(obj.get("action_type"), str):
        return obj
    inner = obj.get("action")
    if isinstance(inner, dict) and isinstance(inner.get("action_type"), str):
        return inner
    return None


def extract_action(text: str) -> tuple[str, list[dict]]:
    """一次性提取回复中的 action JSON（非流式路径）。

    返回 (去掉 action 块后的自然语言文本, actions 列表)。
    围栏块 ```json …``` 优先；无围栏时兜底尝试整段裸 JSON。
    """
    actions: list[dict] = []

    def _sub(m: re.Match) -> str:
        try:
            act = _parse_action(json.loads(m.group(1)))
        except Exception:
            return m.group(0)  # 非 JSON 或解析失败，原样保留（交给 _strip_agent_json 兜底）
        if act is None:
            return m.group(0)
        actions.append(act)
        return ""

    visible = _FENCE_RE.sub(_sub, text).strip()
    if not actions:
        cand = (text or "").strip()
        if cand.startswith("{") or cand.startswith("["):
            try:
                act = _parse_action(json.loads(cand))
                if act is not None:
                    actions.append(act)
                    visible = ""
            except Exception:
                pass
    return visible, actions


class ActionStreamExtractor:
    """流式扣留状态机：feed 逐 token，返回可立即下发的文本；```json 围栏块被扣留。

    - 非围栏文本逐字下发（尾部保留 3 字符防 ``` 被 token 边界切断）；
    - 进入围栏后整体扣留，闭合后解析：含 action_type → 计入 actions（不下发），
      否则整块按普通文本补发；
    - 流结束调 flush()：未闭合的围栏按普通文本补发（容错）。
    """

    _FENCE = "```"

    def __init__(self) -> None:
        self._buf = ""
        self._in_fence = False
        self._fence_body = ""
        self.actions: list[dict] = []

    def feed(self, token: str) -> str:
        self._buf += token or ""
        out: list[str] = []
        while True:
            if not self._in_fence:
                idx = self._buf.find(self._FENCE)
                if idx < 0:
                    keep = len(self._FENCE)  # 保留 fence 长度防 ``` 被 token 边界切断
                    if len(self._buf) > keep:
                        out.append(self._buf[:-keep])
                        self._buf = self._buf[-keep:]
                    break
                out.append(self._buf[:idx])
                self._buf = self._buf[idx + len(self._FENCE):]
                self._in_fence = True
                self._fence_body = ""
            else:
                # 围栏内闭合检测必须覆盖跨界情况：``` 可能被 token 边界切碎，
                # 一部分在 _fence_body 尾部、一部分在 _buf 头部（v6.11.59 修复）
                combined = self._fence_body + self._buf
                idx = combined.find(self._FENCE)
                if idx < 0:
                    self._fence_body = combined
                    self._buf = ""
                    break
                self._fence_body = combined[:idx]
                self._buf = combined[idx + len(self._FENCE):]
                self._in_fence = False
                body = self._fence_body.strip()
                # 剥掉首行语言标识（json / JSON）
                if "\n" in body and body.split("\n", 1)[0].strip().lower() in ("json", "jsonc", ""):
                    body = body.split("\n", 1)[1]
                act = None
                try:
                    act = _parse_action(json.loads(body))
                except Exception:
                    act = None
                if act is not None:
                    self.actions.append(act)  # 扣留，不下发
                else:
                    out.append(f"\n{body}\n")  # 非 action 块按普通文本补发
        return "".join(out)

    def flush(self) -> str:
        """流结束收尾：未闭合围栏补发（容错），返回剩余可下发文本。"""
        rest = ""
        if self._in_fence:
            rest = self._fence_body + self._buf
            self._in_fence = False
            self._fence_body = ""
            self._buf = ""
        else:
            rest = self._buf
            self._buf = ""
        return rest


def parse_dt(value: object, *, end_of_day: bool = False) -> datetime | None:
    """宽松解析日期/时间字符串为 datetime（对齐前端提交口径）。

    接受 "2026-10-22"、"2026-10-22T09:00:00"、"2026-10-22 09:00"；
    纯日期按 00:00:00 起（end_of_day=True 时 23:59:59）。
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day,
                        23, 59, 59) if end_of_day else datetime(value.year, value.month, value.day)
    if not isinstance(value, str):
        return None
    s = value.strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
        except ValueError:
            continue
        if fmt == "%Y-%m-%d" and end_of_day:
            dt = dt.replace(hour=23, minute=59, second=59)
        return dt
    return None
