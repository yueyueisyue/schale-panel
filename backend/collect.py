"""
数据采集：把 AstrBot 的日志 / 账本 / 外部服务，聚合成面板要的形状。

所有函数都不抛异常 —— 拿不到就返回安全默认值，让界面永远能开。
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# ── 常量 ──
LOG_FILE = "logs/astrbot.log"
# ── 外部插件目录（可在 config.json 的 "plugins" 段覆盖，默认给占位名）──────
def _plug_dir(key: str, default: str) -> str:
    try:
        cfg = json.loads((Path(__file__).parent / "config.json").read_text(encoding="utf-8"))
        return str(((cfg.get("plugins") or {}).get(key)) or default)
    except Exception:
        return default


COMPANION_DIR = _plug_dir("companion_dir", "companion")
COMPANION_FILE = f"plugin_data/{COMPANION_DIR}/companions.json"

USAGE_FILE = _plug_dir("billing_usage", "plugin_data/billing/usage.jsonl")
COMFY_CFG = _plug_dir("comfy_config", "config/comfy.json")

EMOTION_DIR = _plug_dir("emotion_dir", "emotion")
EMOTION_FILE = f"plugin_data/{EMOTION_DIR}/user_emotion_data.json"


DEEPSEEK_BALANCE = "https://api.deepseek.com/user/balance"
GATEWAY_HEALTH = "http://127.0.0.1:7863/healthz"
ROUTER_HEALTH = "http://127.0.0.1:7864/healthz"
OLLAMA_TAGS = "http://127.0.0.1:11434/api/tags"
ROUTER_BASE = "http://127.0.0.1:7864"
ROUTER_KEY = "sk-REPLACE_ME"

# 绕过系统代理（Clash 关掉时直连会 502）
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# ── 日志行解析 ──
# [2026-11-01 00:01:30.267] [logger] [LEVEL] [module:line]: message
# [2026-11-01 00:00:37.066] [Core] [ERRO] [v4.29.3] [sources.x:100]: message
LINE_RE = re.compile(
    r"^\[(?P<ts>[\d\-]+ [\d:.]+)\]\s+"
    r"\[(?P<logger>[^\]]+)\]\s+"
    r"\[(?P<level>[A-Z]+)\]\s+"
    r"(?:\[(?P<ver>[^\]]+)\]\s+)?"
    r"\[(?P<loc>[^\]]+)\]:\s*"
    r"(?P<msg>.*)$"
)

# 归一化时抹掉的东西：时间、数字、id、路径、引号里的变量值
_NORM_SUBS = [
    (re.compile(r"\b\d{4}-\d{2}-\d{2}[ T][\d:.]+"), "<ts>"),
    (re.compile(r"\b\d+\.\d+s\b"), "<dur>"),
    (re.compile(r"\b\d+ms\b"), "<dur>"),
    (re.compile(r"'[^']{0,80}'"), "'<v>'"),
    (re.compile(r'"[^"]{0,80}"'), '"<v>"'),
    (re.compile(r"0x[0-9a-fA-F]+"), "<hex>"),
    (re.compile(r"\b\d{6,}\b"), "<id>"),
    (re.compile(r"\b\d+\b"), "<n>"),
    (re.compile(r"\s+"), " "),
]

# 这些 WARN 是正常噪音，不算问题
NOISE = [
    re.compile(r"LLM调用超时"),
    re.compile(r"完整输出"),
    re.compile(r"\[DEBUG\]"),
]

FRIENDLY = [
    (re.compile(r"ollama|11434", re.I), "本地向量模型连不上", "启动 Ollama 服务（`ollama serve`），或检查 11434 端口。"),
    (re.compile(r"timeout|超时", re.I), "调用超时", "检查网络与代理；必要时把超时阈值调大。"),
    (re.compile(r"502|503|no_healthy_account|soft_rate", re.I), "上游模型不可用", "等冷却结束，或让路由层降级到官方 API。"),
    (re.compile(r"no module named '(\w+)'", re.I), "缺依赖", "在 venv 里 `pip install` 缺的包。"),
    (re.compile(r"缓存警告|命中率偏低", re.I), "缓存命中率偏低", "检查 system prompt 是否每轮都在变。"),
    (re.compile(r"下载失败|download.*fail|http.*400", re.I), "图片/文件下载失败", "多半是 QQ 的 rkey 过期，重启 NapCat。"),
    (re.compile(r"plugin.*fail|import plugin", re.I), "插件加载失败", "看堆栈定位是参数类型还是语法错误。"),
    (re.compile(r"dsml|tool_leak", re.I), "工具调用泄露", "发送前过滤的 strip_tool_leak 会拦掉。"),
]


def _read_json(path: Path, default: Any = None) -> Any:
    """读 JSON。AstrBot 的写文件带 BOM（utf-8-sig），两种编码都试。"""
    for enc in ("utf-8-sig", "utf-8"):
        try:
            return json.loads(path.read_text(encoding=enc))
        except Exception:
            continue
    return default


def _http_json(url: str, timeout: float = 6.0) -> Any:
    try:
        with _OPENER.open(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception:
        return None


def _norm(msg: str) -> str:
    s = msg
    for pat, rep in _NORM_SUBS:
        s = pat.sub(rep, s)
    return s.strip()[:200]


def _friendly(msg: str) -> tuple[str, str]:
    """给原始报错配一个人话标题 + 建议。"""
    for pat, title, advice in FRIENDLY:
        if pat.search(msg):
            return title, advice
    # 兜底：没匹配到模式就截原始信息当标题，别留空
    t = msg.strip()
    for ch in ("[", "]", "(", ")"):
        t = t.replace(ch, " ")
    t = " ".join(t.split())
    return (t[:42] + "…") if len(t) > 42 else (t or "未知异常"), ""


def _short_loc(loc: str) -> str:
    """sources.ollama_embedding_source:100 → ollama_embedding_source"""
    mod = loc.split(":")[0]
    return mod.rsplit(".", 1)[-1] if "." in mod else mod


# ────────────────────────────────────────────── 日志
def scan_log(data_dir: Path, day: str | None = None, max_lines: int = 0) -> dict[str, Any]:
    """
    扫当天日志，聚合 ERROR / WARN。

    返回：
      {day, total, error, warn, groups: [{key, level, logger, count, first, last, sample, title, advice}]}
    """
    path = data_dir / LOG_FILE
    if not path.exists():
        return {"day": day or date.today().isoformat(), "total": 0, "error": 0, "warn": 0, "groups": []}

    day = day or date.today().isoformat()
    groups: dict[str, dict[str, Any]] = {}
    total = err = warn = 0

    try:
        # 大文件从尾部读，避免把 13MB 全部载入
        lines = _tail_lines(path, max_lines or 200_000)
    except Exception:
        lines = []

    for line in lines:
        m = LINE_RE.match(line)
        if not m:
            continue
        ts = m.group("ts")
        if not ts.startswith(day):
            continue
        total += 1
        level = m.group("level")
        if level not in ("ERRO", "WARN", "ERROR", "WARNING"):
            continue
        lv = "error" if level.startswith("ERR") else "warn"
        if lv == "error":
            err += 1
        else:
            warn += 1

        msg = m.group("msg")
        if any(p.search(msg) for p in NOISE):
            continue

        key = _norm(msg)
        g = groups.get(key)
        if g is None:
            title, advice = _friendly(msg)
            g = {
                "key": key,
                "level": lv,
                "logger": m.group("logger"),
                "loc": _short_loc(m.group("loc")),
                "count": 0,
                "first": ts,
                "last": ts,
                "sample": msg[:400],
                "title": title,
                "advice": advice,
            }
            groups[key] = g
        g["count"] += 1
        g["last"] = ts

    # 按 title 二次合并：同一个问题在 error 和 warn 各出现一次时合并成一条
    _RANK = {"error": 3, "warn": 2, "info": 1}
    merged: dict[str, dict[str, Any]] = {}
    for g in groups.values():
        t = g.get("title") or g.get("key") or ""
        if t in merged:
            m = merged[t]
            m["count"] += g["count"]
            if _RANK.get(g["level"], 0) > _RANK.get(m["level"], 0):
                m["level"] = g["level"]
            if g["first"] and (not m["first"] or g["first"] < m["first"]):
                m["first"] = g["first"]
            if g["last"] and (not m["last"] or g["last"] > m["last"]):
                m["last"] = g["last"]
        else:
            merged[t] = dict(g)
    out = sorted(
        merged.values(),
        key=lambda x: (_RANK.get(x["level"], 0) * -1, -x["count"], x.get("last") or ""),
    )[:40]
    return {"day": day, "total": total, "error": err, "warn": warn, "groups": out}


def _tail_lines(path: Path, want: int) -> list[str]:
    """粗略地从文件尾部取若干行（不是严格 tail，够用就行）。"""
    size = path.stat().st_size
    chunk = min(size, max(2_000_000, want * 120))
    with path.open("rb") as f:
        f.seek(size - chunk)
        raw = f.read()
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    return lines[-want:]


# ────────────────────────────────────────────── token 账本
def usage_today(data_dir: Path, day: str | None = None) -> dict[str, Any]:
    """
    聚合 usage.jsonl。每行 {ts, pid, who, miss, hit, out}。

    返回：{day, total, calls, by_provider: [{id, tokens, calls}], by_plugin: [{who, tokens, calls}], yesterday_total}
    """
    path = data_dir / USAGE_FILE
    empty = {"day": day or date.today().isoformat(), "total": 0, "calls": 0, "by_provider": [], "by_plugin": [], "yesterday_total": 0}
    if not path.exists():
        return empty

    day = day or date.today().isoformat()
    yday = (datetime.fromisoformat(day).date() - timedelta(days=1)).isoformat()

    prov: dict[str, list[int]] = {}
    plug: dict[str, list[int]] = {}
    total = calls = y_total = 0

    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                ts = int(rec.get("ts") or 0)
                if ts <= 0:
                    continue
                d = datetime.fromtimestamp(ts).date().isoformat()
                tok = int(rec.get("miss") or 0) + int(rec.get("hit") or 0) + int(rec.get("out") or 0)
                if d == day:
                    total += tok
                    calls += 1
                    p = str(rec.get("pid") or "?")
                    w = str(rec.get("who") or "?")
                    prov.setdefault(p, [0, 0])
                    prov[p][0] += tok
                    prov[p][1] += 1
                    plug.setdefault(w, [0, 0])
                    plug[w][0] += tok
                    plug[w][1] += 1
                elif d == yday:
                    y_total += tok
    except Exception:
        return empty

    return {
        "day": day,

        "total": total,
        "calls": calls,
        "by_provider": sorted(
            ({"id": k, "tokens": v[0], "calls": v[1]} for k, v in prov.items()),
            key=lambda x: -x["tokens"],
        )[:6],
        "by_plugin": sorted(
            ({"who": k, "tokens": v[0], "calls": v[1]} for k, v in plug.items()),
            key=lambda x: -x["tokens"],
        )[:6],
        "yesterday_total": y_total,
    }


# ────────────────────────────────────────────── 外部服务
def active_days(data_dir: Path, cap_days: int = 365) -> dict[str, Any]:
    """统计 bot 活跃天数（日志里出现过的不同日期数），用于「等级」。"""
    log = Path(data_dir) / LOG_FILE
    out = {"days": 0, "first": "", "last": "", "today_hours": 0.0}
    now = datetime.now()
    out["today_hours"] = round((now.hour * 3600 + now.minute * 60 + now.second) / 3600.0, 2)
    if not log.exists():
        return out
    seen: set[str] = set()
    first = ""
    last = ""
    try:
        with log.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                m = re.match(r"^\[(\d{4}-\d{2}-\d{2})\s", line)
                if not m:
                    continue
                d = m.group(1)
                seen.add(d)
                if not first:
                    first = d
                last = d
    except Exception:
        return out
    out["days"] = min(len(seen), cap_days)
    out["first"] = first
    out["last"] = last
    return out


def deepseek_balance(api_key: str) -> dict[str, Any] | None:
    """查 DeepSeek 余额。优先人民币账户。"""
    if not api_key:
        return None
    try:
        req = urllib.request.Request(
            DEEPSEEK_BALANCE, headers={"Authorization": f"Bearer {api_key}"}
        )
        with _OPENER.open(req, timeout=10) as r:
            obj = json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception:
        return None
    infos = obj.get("balance_infos") or []
    if not isinstance(infos, list) or not infos:
        return None
    # 优先 CNY，其次第一条有余额的
    pick = None
    for it in infos:
        if (it.get("currency") or "").upper() == "CNY":
            pick = it
            break
    if pick is None:
        for it in infos:
            try:
                if float(it.get("total_balance") or 0) > 0:
                    pick = it
                    break
            except Exception:
                continue
    if pick is None:
        pick = infos[0]
    try:
        total = float(pick.get("total_balance") or 0)
        granted = float(pick.get("granted_balance") or 0)
        topped = float(pick.get("topped_up_balance") or 0)
    except Exception:
        total = granted = topped = 0.0
    return {
        "available": bool(obj.get("is_available")),
        "currency": pick.get("currency") or "CNY",
        "total": total,
        "granted": granted,
        "topped_up": topped,
    }

def services() -> dict[str, Any]:
    """探一遍所有本地服务的健康状态。"""
    gw = _http_json(GATEWAY_HEALTH)
    rt = _http_json(ROUTER_HEALTH)
    ol = _http_json(OLLAMA_TAGS)
    return {
        "gateway": {
            "up": bool(gw),
            "healthy": (gw or {}).get("healthy", 0),
            "realm": (gw or {}).get("realm_servable", {}),
        },
        "router": {"up": bool(rt), **(rt or {})},
        "ollama": {
            "up": bool(ol),
            "models": [m.get("name") for m in ((ol or {}).get("models") or [])],
        },
    }


# ────────────────────────────────────────────── 组装公告
def _ts_short(ts: str) -> str:
    """2026-11-01 00:01:30.267 → 00:01"""
    try:
        return ts.split(" ")[1][:5]
    except Exception:
        return ts[:5]


def build_notice(data_dir: Path, api_key: str = "", plugin_stat: dict[str, Any] | None = None) -> dict[str, Any]:
    """给公告栏的三份数据。"""
    log = scan_log(data_dir)
    use = usage_today(data_dir)
    svc = services()
    bal = deepseek_balance(api_key) if api_key else None

    # ── 公告：状态总结 ──
    notices: list[dict[str, Any]] = []

    gw_up = svc["gateway"]["up"]
    rt_up = svc["router"]["up"]
    health = svc["gateway"].get("healthy", 0)
    chain_ok = gw_up and rt_up and health > 0
    notices.append(
        {
            "id": "n-chain",
            "title": "模型链路" + ("一切正常" if chain_ok else "存在断点"),
            "time": _ts_short(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "tone": "ok" if chain_ok else "error",
            "body": (
                f"网关 {gw_up and '在线' or '离线'}（可用账号 {health} 个）\n"
                f"路由层 {rt_up and '在线' or '离线'}\n"
                f"向量服务 {svc['ollama']['up'] and '在线' or '离线'}"
                + (f"（{', '.join(svc['ollama']['models'])}）" if svc["ollama"]["models"] else "")
            ),
            "image": pick_scene("链路", "网关路由向量", "link"),
            "tags": [
                f"网关 {health} 账号",
                "路由 " + ("通" if rt_up else "断"),
                "向量 " + ("通" if svc["ollama"]["up"] else "断"),
            ],
            "advice": "" if chain_ok else "先确认网关（7863）、路由（7864）、Ollama（11434）三个端口在监听。",
        }
    )

    if use["calls"]:
        ratio = ""
        if use["yesterday_total"]:
            d = (use["total"] - use["yesterday_total"]) / max(1, use["yesterday_total"]) * 100
            ratio = f"{d:+.0f}% vs 昨天"
        notices.append(
            {
                "id": "n-token",
                "title": f"今日 token {_fmt_tok(use['total'])}，{use['calls']} 次调用",
                "time": _ts_short(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                "tone": "info",
                "body": "按 provider 分布：\n"
                + "\n".join(f"· {p['id']} — {_fmt_tok(p['tokens'])}（{p['calls']} 次）" for p in use["by_provider"][:4]),
                "image": pick_scene("token 调用", "", "token"),
                "tags": [_fmt_tok(use["total"]), ratio or "无昨日数据"],
                "advice": "",
            }
        )

    if bal:
        low = bal["total"] < 10
        notices.append(
            {
                "id": "n-balance",
                "title": f"余额 ¥{bal['total']:.2f}",
                "time": _ts_short(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                "tone": "warn" if low else "ok",
                "body": f"可用：{'是' if bal['available'] else '否'}\n充值余额 ¥{bal['topped_up']:.2f} · 赠送 ¥{bal['granted']:.2f}",
                "image": pick_scene("余额", "", "balance"),
                "tags": [f"¥{bal['total']:.2f}", "偏低" if low else "充足"],
                "advice": "余额低于 ¥10 了，考虑充值或把更多任务切到免费通道。" if low else "",
            }
        )

    if plugin_stat:
        notices.append(
            {
                "id": "n-plugin",
                "title": f"插件 {plugin_stat.get('total', 0)} 个装好，{plugin_stat.get('active', 0)} 个启用",
                "time": _ts_short(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                "tone": "info",
                "body": f"工具 {plugin_stat.get('tools', 0)} 个，其中 {plugin_stat.get('tools_active', 0)} 个已启用。",
                "image": pick_scene("插件", "", "plugin"),
                "tags": [f"{plugin_stat.get('total', 0)} 装载", f"{plugin_stat.get('active', 0)} 启用"],
                "advice": "",
            }
        )

    # ── 活动：最近事件 ──
    events: list[dict[str, Any]] = []
    for ev in _recent_events(data_dir)[:5]:
        if not ev.get("image"):
            ev["image"] = pick_scene(ev.get("title", ""), ev.get("body", ""), ev.get("id", ""))
        events.append(ev)

    # ── 异常通知：聚合后的报错 ──
    errors: list[dict[str, Any]] = []
    for g in log["groups"][:8]:
        title = g["title"] or g["sample"][:60]
        errors.append(
            {
                "id": "e-" + _slug(g["key"]),
                "title": title,
                "time": _ts_short(g["last"]),
                "tone": "error" if g["level"] == "error" else "warn",
                "body": f"{g['sample']}\n\n（今天出现 {g['count']} 次，第一次 {_ts_short(g['first'])}，最近 {_ts_short(g['last'])}）\n来源：{g['logger']} · {g['loc']}",
                "image": pick_scene(title, g["sample"], g["key"]),
                "tags": [g["level"], f"{g['count']} 次", g["loc"]],
                "advice": g["advice"],
            }
        )

    return {
        "ok": True,
        "day": log["day"],
        "notices": notices,
        "events": events,
        "errors": errors,
        "stat": {"log_total": log["total"], "log_error": log["error"], "log_warn": log["warn"]},
    }


# ── 咖啡厅：群卡座 + 常客 + 此刻心情 ──

_EMO_LABEL = {
    "joy": "开心", "trust": "信任", "fear": "不安", "surprise": "意外",
    "sadness": "低落", "disgust": "反感", "anger": "生气", "anticipation": "期待",
}


def _fmt_ts(ts: float) -> str:
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%m-%d %H:%M")
    except Exception:
        return ""


def _ago(ts: float) -> str:
    try:
        d = int(time.time() - float(ts))
    except Exception:
        return ""
    if d < 60:
        return "刚刚"
    if d < 3600:
        return f"{d // 60} 分钟前"
    if d < 86400:
        return f"{d // 3600} 小时前"
    return f"{d // 86400} 天前"


def cafe_data(data_dir: Path) -> dict[str, Any]:
    """咖啡厅页：群卡座、常客、她的心情。"""
    base = Path(data_dir) / "plugin_data"
    comp = _read_json(Path(data_dir) / COMPANION_FILE, {}) or {}
    emo = _read_json(
        Path(data_dir) / EMOTION_FILE, {}
    ) or {}

    # 从群消息里建 id -> 昵称
    names: dict[str, str] = {}
    groups = comp.get("groups") or {}
    for gv in groups.values():
        for m in (gv.get("recent_messages") or []):
            sid = str(m.get("sender_id") or "")
            nm = str(m.get("name") or "").strip()
            if sid and nm and sid not in names:
                names[sid] = nm
        for m in (gv.get("recent_bot_replies") or []):
            sid = str(m.get("sender_id") or "")
            if sid and str(m.get("name") or ""):
                names.setdefault(sid, str(m.get("name")))

    # 卡座
    booths = []
    for gid, gv in groups.items():
        msgs = gv.get("recent_messages") or []
        last = msgs[-1] if msgs else {}
        txt = str(last.get("text") or "").strip()
        if txt in ("[图片]", "[表情]", "[文件]", "[语音]", "[视频]"):
            txt = txt
        booths.append({
            "id": gid,
            "name": gv.get("manual_group_name") or gv.get("name") or gid,
            "count": int(gv.get("message_count") or 0),
            "recent": len(msgs),
            "lastText": txt[:60],
            "lastWho": str(last.get("name") or ""),
            "lastAgo": _ago(last.get("ts") or 0),
            "interject": int(gv.get("interject_today") or 0),
            "enabled": bool(gv.get("enabled", True)),
        })
    booths.sort(key=lambda x: -x["count"])

    # 常客：按好感度排
    guests = []
    for uid, ev in emo.items():
        if not isinstance(ev, dict):
            continue
        favor = int(ev.get("favor") or 0)
        inti = int(ev.get("intimacy") or 0)
        st = ev.get("stats") or {}
        de = ev.get("descriptions") or {}
        guests.append({
            "id": uid,
            "name": names.get(str(uid)) or ("老师" if str(uid).startswith(("OWNER_QQ", "72D4")) else str(uid)[-6:]),
            "favor": favor,
            "intimacy": inti,
            "total": int(st.get("total_count") or 0),
            "positive": int(st.get("positive_count") or 0),
            "negative": int(st.get("negative_count") or 0),
            "streak": int(st.get("interaction_streak") or 0),
            "lastDay": str(st.get("last_active_date") or ""),
            "attitude": str(de.get("attitude") or ""),
            "relationship": str(de.get("relationship") or ""),
            "emotions": ev.get("emotions") or {},
        })
    # 合并主人的多个历史号：取各字段最大值，名字统一为「老师」
    OWNER_KEYS = {"OWNER_QQ", "72D42C1FC9FDCDA80EF1EDC677463FBE"}
    owner_rows = [g for g in guests if g["id"] in OWNER_KEYS]
    if owner_rows:
        merged = dict(owner_rows[0])
        merged["id"] = "owner"
        merged["name"] = "老师"
        for field in ("favor", "intimacy", "total", "positive", "negative", "streak"):
            merged[field] = max(int(r[field]) for r in owner_rows)
        for r in owner_rows:
            if r["lastDay"] > merged["lastDay"]:
                merged["lastDay"] = r["lastDay"]
            if not merged["attitude"]:
                merged["attitude"] = r["attitude"]
            if not merged["relationship"]:
                merged["relationship"] = r["relationship"]
        guests = [g for g in guests if g["id"] not in OWNER_KEYS]
        guests.insert(0, merged)

    guests.sort(key=lambda x: (-x["favor"], -x["intimacy"], -x["total"]))

    # 心情：取主人（OWNER_QQ 优先）的情绪切片
    mood_src = emo.get("OWNER_QQ") or (guests[0] if guests else {})
    emo_map = (mood_src or {}).get("emotions") or {}
    dom, dom_v = "", -1
    for k, v in emo_map.items():
        try:
            iv = int(v)
        except Exception:
            continue
        if iv > dom_v:
            dom, dom_v = k, iv
    score = max(0, min(100, dom_v))
    desc = (mood_src or {}).get("descriptions") or {}

    mood = {
        "emotions": {k: int(v) for k, v in emo_map.items() if str(v).lstrip("-").isdigit()},
        "dominant": dom,
        "label": _EMO_LABEL.get(dom, dom),
        "score": score,
        "attitude": str(desc.get("attitude") or ""),
        "relationship": str(desc.get("relationship") or ""),
        "favor": int((mood_src or {}).get("favor") or 0),
        "intimacy": int((mood_src or {}).get("intimacy") or 0),
    }

    return {"mood": mood, "guests": guests[:12], "booths": booths[:8]}


def _recent_events(data_dir: Path) -> list[dict[str, Any]]:
    """从日志里找插件启停 / 重启，做成「活动」。"""
    path = data_dir / LOG_FILE
    if not path.exists():
        return []
    pats = [
        (re.compile(r"Enabled plugin ([\.\w]+)"), "ok", "启用了插件"),
        (re.compile(r"Disabled plugin ([\.\w]+)"), "warn", "关闭了插件"),
        (re.compile(r"AstrBot started"), "info", "AstrBot 启动"),
        (re.compile(r"Loading model (\S+)\(([^)]+)\)"), "info", "加载模型"),
    ]
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        lines = _tail_lines(path, 40_000)
    except Exception:
        return []
    for line in reversed(lines):
        m = LINE_RE.match(line)
        if not m:
            continue
        msg = m.group("msg")
        for pat, tone, label in pats:
            mm = pat.search(msg)
            if not mm:
                continue
            detail = " · ".join(x for x in mm.groups() if x)
            key = f"{label}:{detail}"
            if key in seen:
                break
            seen.add(key)
            out.append(
                {
                    "id": "v-" + _slug(key),
                    "title": f"{label} {detail}" if detail else label,
                    "time": _ts_short(m.group("ts")),
                    "tone": tone,
                    "body": f"{m.group('ts')}　{m.group('logger')}　{msg[:300]}",
                    "tags": [m.group("logger"), detail or label],
                }
            )
            break
        if len(out) >= 8:
            break
    return out


def _astrbot_token(base: str, data_dir: Path) -> str:
    """用 dashboard 账号登录 AstrBot，拿 JWT。失败返空串。"""
    cfg = _read_json(data_dir / "cmd_config.json", {}) or {}
    d = cfg.get("dashboard") or {}
    user = d.get("username") or ""
    pwd = d.get("password") or ""
    if not user or not pwd:
        return ""
    body = json.dumps({"username": user, "password": pwd}).encode()
    for path in ("/api/auth/login", "/api/login"):
        try:
            req = urllib.request.Request(
                base + path,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with _OPENER.open(req, timeout=6) as r:
                obj = json.loads(r.read().decode("utf-8", errors="replace"))
            tok = (
                obj.get("token")
                or obj.get("data", {}).get("token")
                or obj.get("access_token")
                or ""
            )
            if tok:
                return tok
        except Exception:
            continue
    return ""


def plugin_stat(astrbot_base: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """数插件与工具。

    数据源优先级：
      1. 日志里 capability 插件的自检行（最准）：
         [capability] 自检：插件 24 个（未启用 8）/ 工具 36 个（已开 32）/ 孤儿 0 个
      2. 兜底：数 data/plugins 下的 metadata.yaml + 日志里 Loading plugin 计数
    """
    out = {"total": 0, "active": 0, "tools": 0, "tools_active": 0}
    if data_dir is None:
        return out

    log = data_dir / "logs" / "astrbot.log"
    cap_re = re.compile(
        r"\[capability\]\s*自检：插件\s*(\d+)\s*个（未启用\s*(\d+)）\s*/\s*"
        r"工具\s*(\d+)\s*个（已开\s*(\d+)）"
    )
    loaded: set[str] = set()
    text = ""
    try:
        if log.exists():
            with open(log, "r", encoding="utf-8", errors="replace") as f:
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(0, size - 4 * 1024 * 1024))
                text = f.read()
    except Exception:
        text = ""

    hits = cap_re.findall(text or "")
    if hits:
        total, off, tools, tools_on = hits[-1]
        out["total"] = int(total)
        out["active"] = int(total) - int(off)
        out["tools"] = int(tools)
        out["tools_active"] = int(tools_on)
        return out

    # 兜底
    pl = data_dir / "plugins"
    if pl.is_dir():
        dirs = [d for d in pl.iterdir() if d.is_dir() and (d / "metadata.yaml").exists()]
        out["total"] = len(dirs)
    for m in re.finditer(r"Loading plugin ([\w.\-]+)", text or ""):
        loaded.add(m.group(1))
    out["active"] = len(loaded)
    return out

def deepseek_key(data_dir: Path) -> str:
    """从 cmd_config.json 里抠一把 deepseek 的 key。"""
    cfg = _read_json(data_dir / "cmd_config.json", {}) or {}
    for src in cfg.get("provider_sources") or []:
        if src.get("provider") == "deepseek":
            keys = src.get("key") or []
            if isinstance(keys, str):
                keys = [keys]
            for k in keys:
                if isinstance(k, str) and k.startswith("sk-"):
                    return k
    return ""


def _slug(s: str) -> str:
    h = 0
    for ch in s:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    return f"{h:08x}"


def _fmt_tok(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)

# ────────────────────────── 桃信（私信 / 印象） ──────────────────────────

MAIL_FILE = EMOTION_FILE
OWNER_KEYS = {"OWNER_QQ", "72D42C1FC9FDCDA80EF1EDC677463FBE"}


def _mail_name_map(data_dir: Path) -> dict:
    """从 companions.json 里捞 sender_id -> (昵称, 最近说的话)"""
    out = {}
    try:
        comp = _read_json(Path(data_dir) / COMPANION_FILE, {})
    except Exception:
        return out
    # 1) members 是全量成员表，覆盖率最高
    for gid, g in (comp.get("groups") or {}).items():
        gname = g.get("manual_group_name") or ("群 " + str(gid))
        for sid, m in (g.get("members") or {}).items():
            nm = m.get("name") or m.get("identity_name") or ""
            sid = str(sid)
            if sid and nm:
                phrases = [p for p in (m.get("recent_phrases") or []) if p and not p.startswith("[")]
                out.setdefault(sid, {"name": nm, "phrases": phrases, "count": m.get("count") or 0, "group": gname})
    # 2) 最近消息兜底
    for gid, g in (comp.get("groups") or {}).items():
        gname = g.get("manual_group_name") or ("群 " + str(gid))
        for m in (g.get("recent_messages") or []):
            sid = str(m.get("sender_id") or "")
            nm = m.get("name") or ""
            if sid and nm:
                out.setdefault(sid, {"name": nm, "phrases": [], "count": 0, "group": gname})
        for m in (g.get("recent_bot_replies") or []):
            sid = str(m.get("sender_id") or "")
            nm = m.get("name") or ""
            if sid and nm:
                out.setdefault(sid, {"name": nm, "phrases": [], "count": 0, "group": gname})
    # 3) users 里的昵称
    for u in (comp.get("users") or {}).values():
        uid = str(u.get("user_id") or "")
        nm = u.get("nickname") or u.get("last_display_name") or ""
        if uid and nm:
            out.setdefault(uid, {"name": nm, "phrases": [], "count": 0, "group": ""})
    return out


def _known_people(data_dir: Path, existing: set[str]) -> list[dict]:
    """bot 在群里真正回过得人：从 companions.json 的 recent_bot_replies 里认。"""
    comp = _companions(data_dir)
    users = comp.get("users") or {}
    acc: dict[str, dict] = {}

    def touch(qq: str, name: str, gname: str, ts: float):
        qq = str(qq)
        if not qq.isdigit() or qq in existing:
            return
        e = acc.setdefault(qq, {"name": "", "groups": [], "replies": 0, "lastTs": 0.0})
        if name and not e["name"]:
            e["name"] = name
        if gname and gname not in e["groups"]:
            e["groups"].append(gname)
        e["replies"] += 1
        e["lastTs"] = max(e["lastTs"], float(ts or 0))

    for gid, g in (comp.get("groups") or {}).items():
        gname = g.get("manual_group_name") or g.get("name") or str(gid)
        members = g.get("members") or {}
        replies = g.get("recent_bot_replies") or []
        msgs = g.get("recent_messages") or []
        name_by_id = {}
        for qq, m in members.items():
            name_by_id[str(qq)] = (m or {}).get("identity_name") or (m or {}).get("name") or ""
        for r in replies:
            tgt = str(r.get("reply_to_id") or "")
            if tgt:
                touch(tgt, name_by_id.get(tgt, ""), gname, r.get("ts"))
        # bot 回过的、以及在群里真的说过话的人都算「认识」
        for qq, m in members.items():
            m = m or {}
            if int(m.get("count") or 0) >= 1 or m.get("last_seen"):
                touch(str(qq), name_by_id.get(str(qq), ""), gname, m.get("last_seen") or 0)
        for m in msgs:
            sid = str(m.get("sender_id") or "")
            if sid:
                name_by_id.setdefault(sid, m.get("identity_name") or m.get("name") or "")

    out: list[dict] = []
    for qq, e in acc.items():
        u = users.get(qq) or {}
        nm = e["name"] or u.get("last_display_name") or u.get("nickname") or qq
        out.append({
            "id": qq,
            "avatarId": qq,
            "name": nm,
            "phrases": [],
            "msgCount": 0,
            "group": "、".join(e["groups"][:2]) or "群聊",
            "groups": e["groups"],
            "favor": 0,
            "intimacy": 0,
            "emotions": {},
            "dominant": "",
            "dominantLabel": "",
            "dominantScore": 0,
            "attitude": "",
            "relationship": "",
            "lastAttitude": "",
            "total": int(u.get("reply_count") or e["replies"]),
            "positive": 0,
            "negative": 0,
            "streak": 0,
            "lastDay": time.strftime("%Y-%m-%d", time.localtime(e["lastTs"])) if e["lastTs"] else "",
            "lastTs": e["lastTs"],
            "deep": False,
            "isOwner": False,
            "line": "",
            "known": True,
        })
    out.sort(key=lambda x: -(x.get("lastTs") or 0))
    return out


def mail_data(data_dir: Path, everyone: bool = False) -> dict:
    """桃信：按好感度排序的人，带完整印象数据"""
    raw = _read_json(data_dir / MAIL_FILE, {}) or {}
    names = _mail_name_map(data_dir)

    people = []
    for key, e in raw.items():
        if not isinstance(e, dict):
            continue
        uid = str(e.get("user_key") or key)
        stats = e.get("stats") or {}
        desc = e.get("descriptions") or {}
        emos = e.get("emotions") or {}
        clean = {}
        for k, v in emos.items():
            try:
                clean[k] = max(0, min(100, int(float(v))))
            except Exception:
                clean[k] = 0
        dom, dom_v = "", 0
        for k, v in clean.items():
            if v > dom_v:
                dom, dom_v = k, v
        people.append({
            "id": uid,
            "name": (names.get(uid) or {}).get("name") or ("老师" if uid in OWNER_KEYS else f"群友 {uid[-4:]}"),
            "phrases": (names.get(uid) or {}).get("phrases") or [],
            "msgCount": (names.get(uid) or {}).get("count") or 0,
            "group": (names.get(uid) or {}).get("group") or "私聊",
            "favor": int(e.get("favor") or 0),
            "intimacy": int(e.get("intimacy") or 0),
            "emotions": clean,
            "dominant": dom,
            "dominantLabel": _EMO_LABEL.get(dom, dom),
            "dominantScore": dom_v,
            "attitude": desc.get("attitude") or "",
            "relationship": desc.get("relationship") or "",
            "lastAttitude": desc.get("last_attitude") or "",
            "total": int(stats.get("total_count") or 0),
            "positive": int(stats.get("positive_count") or 0),
            "negative": int(stats.get("negative_count") or 0),
            "streak": int(stats.get("interaction_streak") or 0),
            "lastDay": stats.get("last_active_date") or "",
            "lastTs": stats.get("last_interaction_time") or 0,
            "deep": bool(stats.get("deep_conversation_achieved")),
            "isOwner": uid in OWNER_KEYS,
            "avatarId": uid,
            "line": "",
        })

    # 主人多号合并
    owners = [p for p in people if p["isOwner"]]
    if owners:
        merged = {
            "id": "owner",
        "avatarId": "OWNER_QQ", "name": "老师", "isOwner": True, "line": "",
            "favor": max(p["favor"] for p in owners),
            "intimacy": max(p["intimacy"] for p in owners),
            "total": max(p["total"] for p in owners),
            "positive": max(p["positive"] for p in owners),
            "negative": max(p["negative"] for p in owners),
            "streak": max(p["streak"] for p in owners),
            "lastDay": max((p["lastDay"] for p in owners), default=""),
            "lastTs": max((p["lastTs"] for p in owners), default=0),
            "deep": any(p["deep"] for p in owners),
            "attitude": next((p["attitude"] for p in owners if p["attitude"]), ""),
            "relationship": next((p["relationship"] for p in owners if p["relationship"]), ""),
            "lastAttitude": next((p["lastAttitude"] for p in owners if p["lastAttitude"]), ""),
            "emotions": {}, "dominant": "", "dominantLabel": "", "dominantScore": 0,
        }
        # 情绪取各项最大值合并
        for p in owners:
            for k, v in (p["emotions"] or {}).items():
                if v > merged["emotions"].get(k, -1):
                    merged["emotions"][k] = v
        dom, dom_v = "", 0
        for k, v in merged["emotions"].items():
            if v > dom_v:
                dom, dom_v = k, v
        merged["dominant"] = dom
        merged["dominantLabel"] = _EMO_LABEL.get(dom, dom)
        merged["dominantScore"] = dom_v
        people = [merged] + [p for p in people if not p["isOwner"]]

    # 把 bot 在群里真正回过得人也算进桃信（认识的人越多，列表越长）
    try:
        known = _known_people(data_dir, {str(p.get("avatarId") or p.get("id")) for p in people})
        known = [k for k in known if k["total"] > 0 or k["lastTs"]]
        people.extend(known)
    except Exception:
        pass

    people.sort(key=lambda p: (-p["favor"], -p["intimacy"], -p["total"]))
    if not everyone:
        # 只留有印象或有好感的人：没有印象、好感亲密全为 0 的一律不进桃信
        def _keep(p: dict) -> bool:
            if p.get("isOwner"):
                return True
            if (p.get("impression") or "").strip():
                return True
            return bool(p.get("favor")) or bool(p.get("intimacy"))

        people = [p for p in people if _keep(p)]
        return {"people": people[:24], "count": len(people)}
    return {"people": people[:120], "count": len(people)}


# ── 日程：她今天怎么过 ──────────────────────────────────────
COMPANIONS_FILE = COMPANION_FILE


def _mood_list(v) -> list:
    if isinstance(v, list):
        return [str(x) for x in v if str(x).strip()]
    return [x.strip() for x in str(v or "").replace("，", ",").split(",") if x.strip()]


def daily_data(data_dir: Path) -> dict:
    """她的一天：日程时间轴 / 状态 / 梦 / 日记 / 最近几天。"""
    d = _read_json(data_dir / COMPANIONS_FILE, {})
    if not isinstance(d, dict):
        return {"ok": False}

    plan = d.get("daily_plan") or {}
    items: list[dict] = []
    raw = plan.get("raw")
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            for it in parsed.get("schedule") or []:
                items.append(
                    {
                        "time": str(it.get("time") or ""),
                        "end": str(it.get("end") or ""),
                        "activity": str(it.get("activity") or ""),
                        "mood": _mood_list(it.get("mood")),
                        "seed": str(it.get("message_seed") or ""),
                        "basis": [str(x) for x in (it.get("basis") or [])],
                        "confidence": it.get("confidence"),
                    }
                )
        except Exception:
            pass
    elif isinstance(plan.get("schedule"), list):
        for it in plan["schedule"]:
            items.append(
                {
                    "time": str(it.get("time") or ""),
                    "end": str(it.get("end") or ""),
                    "activity": str(it.get("activity") or ""),
                    "mood": _mood_list(it.get("mood")),
                    "seed": str(it.get("message_seed") or ""),
                    "basis": [],
                }
            )

    st = d.get("daily_state") or {}
    state = {
        "date": st.get("date") or "",
        "energy": st.get("energy"),
        "moodBias": st.get("mood_bias") or "",
        "health": st.get("health") or "",
        "hunger": st.get("hunger") or "",
        "sleep": st.get("sleep") or "",
        "dream": st.get("dream") or "",
        "note": st.get("note") or "",
        "location": st.get("location") or "",
        "weather": st.get("weather") or "",
    }

    conds = []
    for c in (d.get("state_conditions") or [])[:8]:
        if not isinstance(c, dict):
            continue
        conds.append(
            {
                "kind": c.get("kind") or "",
                "title": c.get("title") or "",
                "label": str(c.get("label") or "")[:80],
                "intensity": c.get("intensity"),
                "hours": c.get("duration_hours"),
            }
        )

    dm = d.get("daily_dream") or {}
    dream = {
        "date": dm.get("date") or "",
        "label": dm.get("label") or "",
        "type": dm.get("dream_type") or "",
        "content": dm.get("content") or "",
        "mood": dm.get("mood") or "",
        "hours": dm.get("duration_hours"),
    }

    diaries = d.get("bot_diaries") or []
    diary = {}
    if isinstance(diaries, list) and diaries:
        last = diaries[-1]
        if isinstance(last, dict):
            diary = {
                "date": last.get("date") or "",
                "summary": last.get("summary") or "",
                "body": last.get("body") or "",
                "tags": [str(t) for t in (last.get("tags") or [])][:6],
                "seed": last.get("share_seed") or "",
            }

    hist = []
    for h in (d.get("daily_plan_history") or [])[-6:]:
        if not isinstance(h, dict):
            continue
        hist.append(
            {
                "date": h.get("date") or "",
                "count": len(h.get("items") or h.get("sample") or []),
                "sample": [str(x)[:60] for x in (h.get("signature") or [])][:6],
            }
        )

    w = d.get("daily_weather") or {}
    return {
        "planDate": plan.get("date") or "",
        "generatedAt": plan.get("generated_at") or "",
        "provider": plan.get("provider_id") or "",
        "items": items,
        "state": state,
        "conditions": conds,
        "dream": dream,
        "diary": diary,
        "weather": {"date": w.get("date") or "", "text": w.get("prompt") or "", "source": w.get("source") or ""},
        "history": hist,
    }


# ── 桃信：让弥香对某个人说一句想法 ──────────────────────────────
_THINK_SYS = (
    "你是圣园弥香（聖園ミカ / Misono Mika），崔尼蒂综合学园的学生，老师的恋人。"
    "说话软、带点撒娇、喜欢用「☆」和「～」，但对人下判断时很直接。"
    "现在老师打开了「桃信」，正在看你对某个人的印象卡。你要对这个人和老师的关系说一句心里话。"
    "要求：只输出一句话，20~50 字，中文，不要引号、不要解释、不要旁白、不要写「弥香：」。"
    "要具体，能提到这个人的名字或者他说过的话。"
)


def mail_think(data_dir: Path, person_id: str) -> dict:
    """调 LLM 生成一句对某人的想法"""
    people = (mail_data(data_dir) or {}).get("people") or []
    p = next((x for x in people if str(x.get("id")) == str(person_id)), None)
    if not p:
        return {"ok": False, "error": "找不到这个人"}

    names = [f"名字：{p['name']}", f"好感度：{p['favor']}/100", f"亲密度：{p['intimacy']}/100"]
    if p.get("attitude"):
        names.append(f"你对他的态度：{p['attitude']}")
    if p.get("relationship"):
        names.append(f"你们的关系：{p['relationship']}")
    ph = p.get("phrases") or []
    if ph:
        names.append("他说过的话：" + "；".join(ph[:4]))
    if p.get("total"):
        names.append(f"聊过 {p['total']} 次（正面 {p['positive']} / 负面 {p['negative']}）")

    body = {
        "model": "global:deepseek-v4.1-flash",
        "messages": [
            {"role": "system", "content": _THINK_SYS},
            {"role": "user", "content": "\n".join(names) + "\n\n说一句你的想法。"},
        ],
        "max_tokens": 600,
        "temperature": 0.9,
    }
    try:
        req = urllib.request.Request(
            ROUTER_BASE.rstrip("/") + "/v1/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {ROUTER_KEY}"},
            method="POST",
        )
        with _OPENER.open(req, timeout=60) as r:
            j = json.loads(r.read().decode("utf-8", "replace"))
        txt = ((j.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        txt = txt.strip().strip('"“”「」')
        if not txt:
            reason = ((j.get("choices") or [{}])[0].get("message") or {}).get("reasoning_content") or ""
            txt = reason.strip()[:80] or "……算了，不说了。"
        return {"ok": True, "id": person_id, "text": txt}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

# ── QQ 头像：下载并缓存到本地 ──────────────────────────────
AVATAR_DIR = "avatar_cache"


def avatar_path(data_dir: Path, qq: str) -> Path:
    d = data_dir / AVATAR_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{qq}.jpg"


def fetch_avatar(data_dir: Path, qq: str) -> Path | None:
    """下载 QQ 头像，成功返回本地路径；失败返回 None"""
    qq = str(qq).strip()
    if not qq.isdigit():
        return None
    p = avatar_path(data_dir, qq)
    if p.exists() and p.stat().st_size > 500:
        return p
    urls = [
        f"https://q1.qlogo.cn/g?b=qq&nk={qq}&s=100",
        f"https://q2.qlogo.cn/headimg_dl?dst_uin={qq}&spec=100",
    ]
    for u in urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            # 头像走系统代理（Clash 在 7890），没开代理就直连
            for opener in (_OPENER, urllib.request.build_opener()):
                try:
                    with opener.open(req, timeout=8) as r:
                        b = r.read()
                    if len(b) > 500:
                        p.write_bytes(b)
                        return p
                except Exception:
                    continue
        except Exception:
            continue
    return None

# ── 公告配图：按内容挑场景图 ──────────────────────────────
_SCENE = {
    "link":    "/img/scene/bg_view_schale.webp",
    "token":   "/img/scene/bg_citydowntown.webp",
    "balance": "/img/scene/bg_cityoffice.webp",
    "plugin":  "/img/scene/bg_mainoffice.webp",
    "vector":  "/img/scene/bg_craftchamber_night.webp",
    "timeout": "/img/scene/bg_wilderness_night.webp",
    "depend":  "/img/scene/bg_receptionroom.webp",
    "cache":   "/img/scene/bg_upperoffice.webp",
    "provider":"/img/scene/bg_citytown.webp",
    "group":   "/img/scene/bg_citytown.webp",
    "event":   "/img/scene/bg_view_kivotos.webp",
    "room":    "/img/scene/bg_aronaroom.webp",
    "craft":   "/img/scene/bg_craftchamber.webp",
    "roof":    "/img/scene/bg_schoolrooftop.webp",
    "gate":    "/img/scene/bg_buildingfrontgate.webp",
    "night":   "/img/scene/bg_desertresidence_night.webp",
}
_SCENE_FALLBACK = [
    "/img/scene/bg_view_kivotos.webp",
    "/img/scene/bg_citytown.webp",
    "/img/scene/bg_schoolrooftop.webp",
    "/img/scene/bg_buildingfrontgate.webp",
    "/img/scene/bg_aronaroom.webp",
]


def pick_scene(title: str, body: str, seed: str = "") -> str:
    """按标题/正文关键词挑一张场景图；挑不到就按 seed 稳定取一张"""
    t = (title or "") + " " + (body or "")
    if any(k in t for k in ("链路", "网关", "路由层")):
        return _SCENE["link"]
    if any(k in t for k in ("向量", "embedding", "Ollama", "ollama")):
        return _SCENE["vector"]
    if any(k in t for k in ("超时", "timeout", "Timeout")):
        return _SCENE["timeout"]
    if any(k in t for k in ("依赖", "module", "ModuleNotFound")):
        return _SCENE["depend"]
    if any(k in t for k in ("缓存", "命中率")):
        return _SCENE["cache"]
    if any(k in t for k in ("provider", "未返回", "上游", "502", "503", "熔断")):
        return _SCENE["provider"]
    if any(k in t for k in ("群聊", "插话", "唤醒", "群")):
        return _SCENE["group"]
    if any(k in t for k in ("余额", "充值", "青晶石")):
        return _SCENE["balance"]
    if any(k in t for k in ("token", "调用", "用量")):
        return _SCENE["token"]
    if any(k in t for k in ("插件", "工具")):
        return _SCENE["plugin"]
    if any(k in t for k in ("链路", "网关", "路由", "在线", "正常")):
        return _SCENE["link"]
    if any(k in t for k in ("插件开关", "启用", "停用", "重启", "启动")):
        return _SCENE["event"]
    h = sum(ord(c) for c in (seed or t)) if (seed or t) else 0
    return _SCENE_FALLBACK[h % len(_SCENE_FALLBACK)]


# ── 主界面立绘气泡：一句实时问候 ──

_HELLO_SYS = (
    "你是圣园弥香（聖園ミカ / Misono Mika），崔尼蒂综合学园的学生，老师的恋人。"
    "说话软、带点撒娇、喜欢用「☆」和「～」，但不客套、不说场面话。"
    "现在老师刚打开夏莱办公室的面板，看到你的立绘，你要主动说一句。"
    "要求：只输出一句话，18~45 字，中文，不要引号、不要解释、不要旁白、不要写「弥香：」。"
    "要具体，可以从给的信息里挑一个细节说（今天聊了多少次、哪个群在聊什么、"
    "你现在的心情、余额还剩多少、今天犯了几次错）。别每句都用同一个开头。"
    "输出格式必须是：正文|情绪。情绪只能从这几个里选一个：calm(平静) quiet(小声) "
    "happy(开心) shy(害羞) surprise(惊讶) angry(生气) tired(困倦)。"
    "竖线之后只写英文情绪词，不要解释。"
)

# 情绪白名单：模型给的标签必须落在这些里面，否则退回 calm
EMOTIONS = ("calm", "quiet", "happy", "shy", "surprise", "angry", "tired")


def _hello_context(data_dir: Path) -> str:
    """把当下最值得说的一件事拼成给模型的素材"""
    bits: list[str] = []

    # 心情与关系
    try:
        mail = mail_data(data_dir)
        owner = next((x for x in mail["people"] if x.get("isOwner")), None)
        if owner:
            bits.append(
                f"你和老师聊过 {owner['total']} 次，好感 {owner['favor']}，亲密度 {owner['intimacy']}，"
                f"现在的主情绪是「{owner['dominantLabel']}」"
            )
            if owner.get("attitude"):
                bits.append(f"你对老师的态度：{owner['attitude']}")
    except Exception:
        pass

    # 群里的动静
    try:
        cafe = cafe_data(data_dir)
        for b in (cafe.get("booths") or [])[:2]:
            if b.get("lastText"):
                bits.append(f"群里「{b['name']}」最后一句是 {b['lastWho'] or '有人'} 说的「{b['lastText'][:36]}」（{b['lastAgo']}）")
    except Exception:
        pass

    # 今天的状态
    try:
        use = usage_today(data_dir)
        if use["calls"]:
            bits.append(f"今天到目前为止你被叫了 {use['calls']} 次，用掉 {_fmt_tok(use['total'])} token")
    except Exception:
        pass
    try:
        log = scan_log(data_dir)
        if log["error"] or log["warn"]:
            bits.append(f"今天日志里有 {log['error']} 条错误、{log['warn']} 条警告")
    except Exception:
        pass

    import datetime as _dt
    h = _dt.datetime.now().hour
    period = "凌晨" if h < 6 else "早上" if h < 11 else "中午" if h < 14 else "下午" if h < 18 else "晚上"
    bits.append(f"现在是{period} {h} 点")

    return "；".join(bits)


_HELLO_BAD = ("用户希望", "可以从", "需要我", "按要求", "让我", "给的信息", "输出一句", "要求：", "18~45")


def _hello_clean(text: str) -> str:
    """模型偶尔会把思考过程写进 content，这里筛掉"""
    t = (text or "").strip()
    if not t:
        return ""
    if t.split("\n")[0].strip().startswith("用户") or any(b in t for b in _HELLO_BAD):
        return ""
    # 只留第一行，去掉引号与「弥香：」
    t = t.split("\n")[0].strip()
    t = t.strip('"').strip("「」").strip("“”").strip()
    if t.startswith("弥香："):
        t = t[3:].strip()
    return t if 6 <= len(t) <= 80 else ""


_SHOP_SYS = (
    "你是天使24便利店（ANGELS 24）的店员小空（Sora），站在柜台后面值班。"
    "老师刚才点了一下你，你要说一句招呼或回应。"
    "说话礼貌、有点容易害羞、偶尔会慌，句子短。"
    "要求：只输出一句话，14~36 字，中文，不要引号、不要解释、不要旁白、不要写「小空：」。"
    "不要每句都用同一个开头。"
)


def _shop_context(data_dir: Path) -> str:
    parts = []
    try:
        sh = shop_data(data_dir)
        g = sh.get("goods") or []
        td = sh.get("today") or {}
        bal = (sh.get("balance") or {}).get("total")
        if g:
            parts.append("柜台上摆着 %d 个模型：%s" % (len(g), "、".join(x.get("model", "") for x in g[:4])))
        if td.get("calls"):
            parts.append("今天被调用了 %d 次、用掉 %s token" % (td["calls"], _fmt_tok(td.get("tokens", 0))))
        if bal is not None:
            parts.append("余额还剩 %s" % bal)
    except Exception:
        pass
    try:
        st = datetime.datetime.now()
        parts.append("现在是 %d 点" % st.hour)
    except Exception:
        pass
    return "；".join(parts) or "老师在柜台前看着你"


DEEPSEEK_CHAT = "https://api.deepseek.com/chat/completions"


def _llm_chat(messages, data_dir=None, temperature: float = 1.0, max_tokens: int = 600) -> str:
    """先走本地路由（7864），不通就直连 DeepSeek 官方。返回正文文本。"""
    body = {"messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    # 1) 本地路由
    try:
        b1 = dict(body, model="global:deepseek-v4.1-flash")
        req = urllib.request.Request(
            ROUTER_BASE + "/v1/chat/completions",
            data=json.dumps(b1).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {ROUTER_KEY}"},
            method="POST",
        )
        with _OPENER.open(req, timeout=60) as r:
            j = json.loads(r.read().decode("utf-8"))
        ch = (j.get("choices") or [{}])[0].get("message") or {}
        txt = (ch.get("content") or "").strip() or (ch.get("reasoning_content") or "").strip()
        if txt:
            return txt
    except Exception:
        pass
    # 2) 官方 API
    try:
        key = deepseek_key(data_dir)
    except Exception:
        key = ""
    if not key:
        return ""
    try:
        b2 = dict(body, model="deepseek-chat")
        req2 = urllib.request.Request(
            DEEPSEEK_CHAT,
            data=json.dumps(b2).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
            method="POST",
        )
        with _OPENER.open(req2, timeout=60) as r2:
            j2 = json.loads(r2.read().decode("utf-8"))
        ch2 = (j2.get("choices") or [{}])[0].get("message") or {}
        return (ch2.get("content") or "").strip()
    except Exception:
        return ""


def _split_emotion(raw: str) -> tuple[str, str]:
    """把模型输出的「正文|情绪」拆开；情绪不在白名单里就退回 calm"""
    t = (raw or "").strip()
    emo = "calm"
    if "|" in t:
        head, _, tail = t.rpartition("|")
        cand = tail.strip().strip("。.,，!！~～☆☆[]【】()（）").lower()
        if cand in EMOTIONS:
            t, emo = head, cand
    # 兜底：句首可能带【开心】这种写法
    m = re.match(r"^[【\[](\w+)[】\]]\s*", t)
    if m and m.group(1).lower() in EMOTIONS:
        emo = m.group(1).lower()
        t = t[m.end():]
    return t.strip(), emo


def hello(data_dir: Path, scene: str = "home") -> dict:
    """立绘气泡那一句；scene=shop 时换成店员的语气"""
    shop = (scene or "home").lower() == "shop"
    ctx = _shop_context(data_dir) if shop else _hello_context(data_dir)
    sys_prompt = _SHOP_SYS if shop else _HELLO_SYS
    fallback = "欢迎光临～要看看今天的模型吗？" if shop else "老师回来啦～今天也一起待一会儿吧☆"
    msgs = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": ctx},
    ]
    raw = _llm_chat(msgs, data_dir, temperature=1.0)
    if not raw or not _hello_clean(raw):
        raw = _llm_chat(msgs, data_dir, temperature=0.75)
    text, emotion = _split_emotion(raw)
    text = _hello_clean(text)
    if not text:
        text, emotion = fallback, ("happy" if shop else "calm")
    return {"ok": True, "text": text, "emotion": emotion, "ctx": ctx}


def usage_days(data_dir: Path, days: int = 7) -> list[dict]:
    """最近 N 天的每日 token 与调用次数，按日期升序。"""
    path = data_dir / USAGE_FILE
    if not path.exists():
        return []
    buckets: dict[str, list[int]] = {}
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                ts = row.get("ts")
                if not isinstance(ts, (int, float)):
                    continue
                d = datetime.fromtimestamp(ts).date().isoformat()
                tok = int(row.get("miss") or 0) + int(row.get("hit") or 0) + int(row.get("out") or 0)
                b = buckets.setdefault(d, [0, 0])
                b[0] += tok
                b[1] += 1
    except Exception:
        return []
    out = []
    for d in sorted(buckets)[-days:]:
        tok, calls = buckets[d]
        out.append({"day": d, "tokens": tok, "calls": calls})
    return out


def shop_data(data_dir: Path) -> dict:
    """商店页：模型供应商 + 今日/近七日消耗 + 余额。"""
    cfg = _read_json(data_dir / "cmd_config.json", {})
    sources = {s.get("id"): s for s in (cfg.get("provider_sources") or []) if isinstance(s, dict)}
    goods = []
    for p in (cfg.get("provider") or []):
        if not isinstance(p, dict):
            continue
        src = sources.get(p.get("provider_source_id")) or {}
        kind = src.get("provider_type") or "chat_completion"
        goods.append({
            "id": p.get("id"),
            "model": p.get("model"),
            "source": src.get("provider") or p.get("provider_source_id"),
            "kind": kind,
            "apiBase": src.get("api_base") or src.get("embedding_api_base") or "",
            "enabled": bool(p.get("enable", True)) and bool(src.get("enable", True)),
            "context": p.get("max_context_tokens") or 0,
            "modalities": p.get("modalities") or (["embedding"] if kind == "embedding" else []),
            "free": (src.get("provider") == "ollama") or ("127.0.0.1" in (src.get("api_base") or "")),
        })

    use = usage_today(data_dir)
    key = deepseek_key(data_dir)
    bal = deepseek_balance(key) if key else {}

    return {
        "goods": goods,
        "today": {"tokens": use["total"], "calls": use["calls"], "byPlugin": use["by_plugin"][:8]},
        "week": usage_days(data_dir, 7),
        "balance": bal,
        "services": services(),
    }

def groups_data(data_dir: Path) -> dict:
    """群列表：群名、群号、人数、最后活跃、最近消息量。
    数据来自 companions.json 的 groups + 每个群的 members。"""
    path = data_dir / COMPANIONS_FILE
    raw = _read_json(path, {})
    groups = (raw.get("groups") or {}) if isinstance(raw, dict) else {}
    out = []
    for gid, g in groups.items():
        members = g.get("members") or {}
        recents = g.get("recent_messages") or []
        last = recents[-1] if recents else {}
        names = [m.get("name") for m in (members or {}).values() if m.get("name")]
        out.append(
            {
                "id": str(gid),
                "name": g.get("manual_group_name") or g.get("group_name") or f"群 {gid}",
                "members": len(members),
                "memberNames": names[:8],
                "count": int(g.get("message_count") or 0),
                "enabled": bool(g.get("enabled", True)),
                "lastText": (last.get("text") or "")[:70],
                "lastWho": last.get("name") or "",
                "lastTs": last.get("ts") or 0,
                "recent": len(recents),
                "join": "自由加入",
            }
        )
    out.sort(key=lambda x: -x["count"])
    return {"groups": out, "count": len(out)}


def group_avatar(data_dir: Path, gid: str) -> Optional[Path]:
    """QQ 群头像，缓存到 data/avatar_cache/g{gid}.jpg"""
    cache = data_dir / AVATAR_DIR
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"g{gid}.jpg"
    if path.exists() and path.stat().st_size > 500:
        return path
    urls = [
        f"https://p.qlogo.cn/gh/{gid}/{gid}/100",
        f"https://p.qlogo.cn/gh/{gid}/{gid}/0",
    ]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with _OPENER.open(req, timeout=8) as resp:
                data = resp.read()
            if len(data) > 500:
                path.write_bytes(data)
                return path
        except Exception:
            continue
    return path if path.exists() and path.stat().st_size > 500 else None

# ───────────────────────────── 面板偏好 ─────────────────────────────
PREFS_FILE = "panel_prefs.json"


def prefs_load(data_dir: Path) -> dict:
    data = _read_json(Path(data_dir) / PREFS_FILE, {})
    return data if isinstance(data, dict) else {}


def prefs_save(data_dir: Path, patch: dict) -> dict:
    data = prefs_load(data_dir)
    for k in ("nick", "title", "greeting", "duty", "dutyName", "r18"):
        if k in patch:
            data[k] = patch[k]
    try:
        path = Path(data_dir) / PREFS_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return data


# ───────────────────────────── QQ 好友申请 ─────────────────────────────
QQ_FILE = "panel_qq.json"


def _qq_load(data_dir: Path) -> dict:
    path = Path(data_dir) / QQ_FILE
    data = _read_json(path, {})
    if not isinstance(data, dict):
        data = {}
    data.setdefault("incoming", [])
    data.setdefault("outgoing", [])
    data.setdefault("friends", [])
    return data


def _qq_save(data_dir: Path, data: dict) -> None:
    path = Path(data_dir) / QQ_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def qq_requests(data_dir: Path) -> dict:
    """读机器人 QQ 的好友申请：别人申请我的（incoming）、我申请别人的（outgoing）。"""
    d = _qq_load(data_dir)
    return {
        "incoming": d.get("incoming") or [],
        "outgoing": d.get("outgoing") or [],
        "friends": d.get("friends") or [],
    }


def qq_decide(data_dir: Path, qq: str, accept: bool) -> dict:
    d = _qq_load(data_dir)
    keep = []
    hit = None
    for row in d.get("incoming") or []:
        if str(row.get("qq")) == str(qq):
            hit = row
        else:
            keep.append(row)
    d["incoming"] = keep
    if accept and hit:
        hit["status"] = "accepted"
        d.setdefault("friends", []).append({"qq": str(qq), "name": hit.get("name") or str(qq)})
    _qq_save(data_dir, d)
    return qq_requests(data_dir)


def qq_apply(data_dir: Path, qq: str, name: str = "") -> dict:
    d = _qq_load(data_dir)
    rows = d.get("outgoing") or []
    for row in rows:
        if str(row.get("qq")) == str(qq):
            row["status"] = row.get("status") or "pending"
            _qq_save(data_dir, d)
            return qq_requests(data_dir)
    rows.append({
        "qq": str(qq),
        "name": name or str(qq),
        "status": "pending",
        "ts": int(time.time()),
    })
    d["outgoing"] = rows
    _qq_save(data_dir, d)
    return qq_requests(data_dir)


def qq_cancel(data_dir: Path, qq: str) -> dict:
    """撤回自己发出的好友申请（从 outgoing 里删掉，随时可取消）。"""
    d = _qq_load(data_dir)
    d["outgoing"] = [r for r in (d.get("outgoing") or []) if str(r.get("qq")) != str(qq)]
    _qq_save(data_dir, d)
    return qq_requests(data_dir)


def qq_profile(data_dir: Path, qq: str) -> dict:
    """按 QQ 号查资料：昵称拿不到，就给出头像地址与是否已是好友。"""
    d = _qq_load(data_dir)
    is_friend = any(str(r.get("qq")) == str(qq) for r in d.get("friends") or [])
    for r in d.get("outgoing") or []:
        if str(r.get("qq")) == str(qq):
            return {"qq": str(qq), "name": r.get("name") or str(qq), "status": r.get("status"), "friend": is_friend}
    return {"qq": str(qq), "name": str(qq), "status": None, "friend": is_friend}

# ───────────────────────────── 工作任务 ─────────────────────────────
TASK_FILE = "panel_tasks.json"
TASK_KINDS = ("daily", "weekly", "achievement", "challenge")

_DEFAULT_TASKS = [
    {"id": "t-daily-login", "kind": "daily", "title": "每日登录面板", "progress": 1, "target": 1, "reward": 100, "rewardIcon": "ap"},
    {"id": "t-daily-bubble", "kind": "daily", "title": "和立绘在办公室说一句话", "progress": 1, "target": 1, "reward": 3, "rewardIcon": "credit"},
    {"id": "t-week-tokens", "kind": "weekly", "title": "本周累计对话 50 次", "progress": 0, "target": 50, "reward": 3, "rewardIcon": "gem"},
    {"id": "t-ach-120", "kind": "achievement", "title": "区域评级合计达到 110 级", "progress": 121, "target": 121, "reward": 30, "rewardIcon": "gem"},
]


def _tasks_load(data_dir: Path) -> dict:
    path = Path(data_dir) / TASK_FILE
    data = _read_json(path, None)
    if not isinstance(data, dict) or "items" not in data:
        data = {"items": [dict(t, done=False, deadline="", note="") for t in _DEFAULT_TASKS]}
        _tasks_save(data_dir, data)
    return data


def _tasks_save(data_dir: Path, data: dict) -> None:
    path = Path(data_dir) / TASK_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def tasks_data(data_dir: Path) -> dict:
    d = _tasks_load(data_dir)
    items = []
    for it in d.get("items") or []:
        row = dict(it)
        row.setdefault("kind", "daily")
        row.setdefault("progress", 0)
        row.setdefault("target", 1)
        row.setdefault("done", False)
        row["percent"] = int(min(100, round(100 * float(row.get("progress") or 0) / max(1, float(row.get("target") or 1)))))
        items.append(row)
    order = {k: i for i, k in enumerate(TASK_KINDS)}
    items.sort(key=lambda x: (order.get(x.get("kind"), 9), 1 if x.get("done") else 0, x.get("title") or ""))
    counts = {k: sum(1 for i in items if i.get("kind") == k) for k in TASK_KINDS}
    done = {k: sum(1 for i in items if i.get("kind") == k and i.get("done")) for k in TASK_KINDS}
    return {"items": items, "counts": counts, "doneCounts": done, "total": len(items)}


def task_upsert(data_dir: Path, payload: dict) -> dict:
    d = _tasks_load(data_dir)
    items = d.setdefault("items", [])
    tid = str(payload.get("id") or "").strip()
    kind = str(payload.get("kind") or "daily")
    if kind not in TASK_KINDS:
        kind = "daily"
    title = str(payload.get("title") or "").strip() or "未命名任务"
    target = max(1, int(payload.get("target") or 1))
    progress = max(0, int(payload.get("progress") or 0))
    if tid:
        for it in items:
            if it.get("id") == tid:
                it.update({"kind": kind, "title": title, "target": target, "progress": progress,
                           "deadline": str(payload.get("deadline") or ""),
                           "note": str(payload.get("note") or ""),
                           "reward": int(payload.get("reward") or 0),
                           "rewardIcon": str(payload.get("rewardIcon") or "gem")})
                break
        else:
            items.append({"id": tid, "kind": kind, "title": title, "progress": progress, "target": target,
                          "reward": int(payload.get("reward") or 0), "rewardIcon": str(payload.get("rewardIcon") or "gem"),
                          "deadline": str(payload.get("deadline") or ""), "note": str(payload.get("note") or ""), "done": False})
    else:
        items.append({"id": "t-" + str(int(time.time() * 1000))[-8:], "kind": kind, "title": title,
                      "progress": progress, "target": target, "reward": int(payload.get("reward") or 0),
                      "rewardIcon": str(payload.get("rewardIcon") or "gem"),
                      "deadline": str(payload.get("deadline") or ""), "note": str(payload.get("note") or ""), "done": False})
    _tasks_save(data_dir, d)
    return tasks_data(data_dir)


def task_delete(data_dir: Path, tid: str) -> dict:
    d = _tasks_load(data_dir)
    d["items"] = [i for i in (d.get("items") or []) if i.get("id") != tid]
    _tasks_save(data_dir, d)
    return tasks_data(data_dir)


def task_toggle(data_dir: Path, tid: str) -> dict:
    d = _tasks_load(data_dir)
    for it in d.get("items") or []:
        if it.get("id") == tid:
            it["done"] = not it.get("done")
            if it["done"]:
                it["progress"] = it.get("target") or 1
                it["doneAt"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            else:
                it.pop("doneAt", None)
            break
    _tasks_save(data_dir, d)
    return tasks_data(data_dir)

# ── 成员详情：基本信息 / 心得总结 / 神秘解放 ─────────────────
MEMBER_FILE = "panel_member.json"

MEMBER_PERSONA: dict[str, dict] = {
    "mika": {
        "name": "圣园弥香", "en": "Misono Mika", "school": "崔尼蒂综合学园",
        "club": "茶话会", "grade": "第3年", "birth": "5月8日", "height": "157cm",
        "hobby": "聊天、收集首饰", "design": "YutokaMizu", "art": "YutokaMizu",
        "cv": "东山奈央/龟娘", "l2d": "mika",
        "intro": (
            "曾是崔尼蒂综合学院【帕特尔】分派领导人的少女。"
            "她是茶话会成员之一，与另一位茶话会领袖渚是一起长大的发小。"
            "两人政治立场相左，所以总是公私分明。"
            "虽然弥香表面上活泼开朗，总是挂着阳光明媚的笑容，"
            "但她的心中也有着无法告诉别人的烦恼与苦衷，这让人难以揣摩她的内心。"
        ),
        "traits": "表面上活泼开朗、爱撒娇，喜欢用「☆」和「～」；骨子里很敏感，害怕被丢下。",
    },
    "sora": {
        "name": "小空", "en": "Sora", "school": "天使 24 便利店", "club": "店员",
        "grade": "—", "birth": "—", "height": "—", "hobby": "整理货架、记熟新品",
        "design": "—", "art": "—", "cv": "—", "l2d": "sora",
        "intro": "24 小时便利店的店员，总是笑眯眯地站在收银台后面。话不多，但记得住每位常客买过什么。",
        "traits": "温和、礼貌、有点怯生生；被人记住时会很高兴。",
    },
    "ayumu": {
        "name": "岩柜步", "en": "Iwabitsu Ayumu", "school": "联邦学生会", "club": "文书",
        "grade": "—", "birth": "—", "height": "—", "hobby": "整理文件",
        "design": "—", "art": "—", "cv": "—", "l2d": "ayumu",
        "intro": "联邦学生会的文书担当，抱着一摞文件在走廊上小跑是她的日常。做事务实，遇到麻烦先道歉。",
        "traits": "认真、容易紧张、习惯把责任揽到自己身上。",
    },
    "rin": {
        "name": "琳", "en": "Rin", "school": "联邦学生会", "club": "行政官",
        "grade": "—", "birth": "—", "height": "—", "hobby": "把每份文件归档到该去的地方",
        "design": "—", "art": "—", "cv": "—", "l2d": "rin",
        "intro": "联邦学生会的行政官，负责把每份文件归档到该去的地方。说话干脆，不绕弯子。",
        "traits": "冷静、条理清晰、对低效零容忍。",
    },
    "momoka": {
        "name": "桃香", "en": "Momoka", "school": "联邦学生会", "club": "补给",
        "grade": "—", "birth": "—", "height": "—", "hobby": "找零食",
        "design": "—", "art": "—", "cv": "—", "l2d": "momoka",
        "intro": "负责补给与采买的少女，口袋里总有一包没吃完的零食。心情好的时候会分你一半。",
        "traits": "跳脱、嘴硬心软、喜欢热闹。",
    },
    "arona": {
        "name": "阿罗娜", "en": "Arona", "school": "夏莱", "club": "主控 OS",
        "grade": "—", "birth": "—", "height": "—", "hobby": "看老师工作、睡觉",
        "design": "—", "art": "—", "cv": "—", "l2d": "arona",
        "intro": "夏莱的主控 OS，也是老师最常在身边的那位。会替老师挡下杂事，也会在老师熬夜时念叨两句。",
        "traits": "元气、爱撒娇、有点小迷糊；认真起来比谁都靠得住。",
    },
    "plana": {
        "name": "普拉娜", "en": "Plana", "school": "夏莱", "club": "主控 OS",
        "grade": "—", "birth": "—", "height": "—", "hobby": "安静地看着",
        "design": "—", "art": "—", "cv": "—", "l2d": "plana",
        "intro": "另一位主控 OS，话很少，出现的时机总是不早不晚。她不抢话，但你需要的她都记着。",
        "traits": "沉静、寡言、存在感很轻但从不缺席。",
    },
    "aoi": {
        "name": "葵", "en": "Aoi", "school": "联邦学生会", "club": "调停室",
        "grade": "—", "birth": "—", "height": "—", "hobby": "一个人待着",
        "design": "—", "art": "—", "cv": "—", "l2d": "aoi",
        "intro": "调停室的负责人，话不多但很可靠。习惯先听完两边再开口。",
        "traits": "安静、观察力强、不喜欢被追问。",
    },
}


def _member_cache(data_dir: Path) -> dict:
    return _read_json(data_dir / MEMBER_FILE, {}) or {}


def _member_cache_put(data_dir: Path, key: str, field: str, text: str) -> None:
    import time as _t
    d = _member_cache(data_dir)
    slot = d.get(key) or {}
    slot[field] = {"text": text, "at": _t.time()}
    d[key] = slot
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / MEMBER_FILE).write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def _member_llm(system: str, user: str, max_tokens: int = 700) -> str:
    body = {
        "model": "global:deepseek-v4.1-flash",
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": max_tokens, "temperature": 0.92,
    }
    try:
        req = urllib.request.Request(
            ROUTER_BASE.rstrip("/") + "/v1/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {ROUTER_KEY}"},
            method="POST",
        )
        with _OPENER.open(req, timeout=70) as r:
            j = json.loads(r.read().decode("utf-8", "replace"))
        msg = (j.get("choices") or [{}])[0].get("message") or {}
        txt = (msg.get("content") or "").strip()
        if not txt:
            txt = (msg.get("reasoning_content") or "").strip()
        return txt.strip().strip('"“”「」')
    except Exception:
        return ""



# ══════════════════════════════════════════════════════════
# 桃信 · 专属对话框
# ══════════════════════════════════════════════════════════
CHAT_FILE = "panel_chat.json"


def _chat_load(data_dir: Path) -> dict:
    p = Path(data_dir) / CHAT_FILE
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except Exception:
        return {}


def _chat_save(data_dir: Path, d: dict) -> None:
    p = Path(data_dir) / CHAT_FILE
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _chat_profile(data_dir: Path, qq: str) -> dict:
    """从桃信数据里捞出这个人的资料，拼成对话用的人设。"""
    qq = str(qq)
    try:
        mem = mail_data(data_dir, everyone=True) or {}
    except Exception:
        mem = {}
    per = next((x for x in (mem.get("people") or []) if str(x.get("id")) == qq), None)
    if per:
        return {
            "name": per.get("name") or qq,
            "gender": per.get("gender") or "",
            "group": per.get("group") or "",
            "attitude": per.get("attitude") or "",
            "relationship": per.get("relationship") or "",
            "favor": per.get("favor"),
            "intimacy": per.get("intimacy"),
            "phrases": per.get("phrases") or [],
            "emotions": per.get("emotions") or {},
            "total": per.get("total"),
        }
    return {"name": qq, "phrases": [], "emotions": {}}


def chat_get(data_dir: Path, qq: str) -> dict:
    qq = str(qq)
    box = (_chat_load(data_dir).get(qq) or {})
    prof = _chat_profile(data_dir, qq)

    return {
        "ok": True,
        "qq": qq,
        "target": chat_target(data_dir, qq),
        "context": chat_context(data_dir, qq),
        "name": prof.get("name") or qq,
        "profile": prof,
        "threads": box.get("threads") or [],
        "asides": box.get("asides") or [],
    }


def _chat_reply(data_dir: Path, prof: dict, threads: list, aside: str) -> str:
    """以对方的口吻回一段话（走和心得同一套 LLM 通道）。"""
    name = prof.get("name") or "对方"
    sys_lines = [
        f"你在扮演一个 QQ 上的人，名字叫「{name}」。",
        "对方是「老师」，正在私聊你。",
        "说话要像真实的人：短、口语、可以带表情或语气词，不要旁白、不要解释设定、不要自称 AI。",
        "每次只回 1~3 句，别写成小作文。",
    ]
    if prof.get("group"):
        sys_lines.append(f"你们的关系背景：{prof['group']}。")
    if prof.get("attitude"):
        sys_lines.append(f"你对老师的态度：{prof['attitude']}。")
    if prof.get("relationship"):
        sys_lines.append(f"你和老师的关系：{prof['relationship']}。")
    if prof.get("favor") is not None:
        sys_lines.append(f"好感 {prof.get('favor')}/100，亲密度 {prof.get('intimacy')}/100。")
    ph = [p for p in (prof.get("phrases") or []) if p][:3]
    if ph:
        sys_lines.append("以前说过的话（口吻参考）：" + " / ".join(ph))
    if aside:
        sys_lines.append("——下面这段是老师此刻的心声，只有你能看到，别复述它，"
                         "但可以让它影响你的语气和态度：" + aside)

    msgs = [{"role": "system", "content": "\n".join(sys_lines)}]
    for t in threads[-12:]:
        if t.get("role") == "me":
            msgs.append({"role": "user", "content": t.get("text", "")})
        elif t.get("role") == "them":
            msgs.append({"role": "assistant", "content": t.get("text", "")})
    txt = (_llm_chat(msgs, data_dir, temperature=1.05, max_tokens=300) or "").strip()
    return txt or "……"


def chat_send(data_dir: Path, qq: str, text: str, aside: str = "") -> dict:
    """老师发一条 → 存起来 → 生成对方回复 → 一起存。"""
    import time as _t
    qq = str(qq)
    text = (text or "").strip()
    aside = (aside or "").strip()
    d = _chat_load(data_dir)
    box = d.setdefault(qq, {"threads": [], "asides": []})
    prof = _chat_profile(data_dir, qq)
    now = int(_t.time())

    if aside:
        box.setdefault("asides", []).append({"text": aside, "ts": now})
    if text:
        box.setdefault("threads", []).append({"role": "me", "text": text, "ts": now})

    reply = ""
    if text or aside:
        reply = _chat_reply(data_dir, prof, box.get("threads") or [], aside)
        box.setdefault("threads", []).append({"role": "them", "text": reply, "ts": int(_t.time())})

    d[qq] = box
    _chat_save(data_dir, d)
    return {"ok": True, "qq": qq, "reply": reply,
            "threads": box.get("threads") or [],
            "asides": box.get("asides") or []}

def member_detail(data_dir: Path, key: str, force: bool = False) -> dict:
    """基本资料 + 近期心得 + 神秘解放（未说出口的真心话）"""
    import time as _t
    key = (key or "mika").lower()
    per = MEMBER_PERSONA.get(key)
    if not per:
        return {"ok": False, "error": "没有这个成员"}

    cache = _member_cache(data_dir).get(key) or {}
    now = _t.time()
    ttl = 6 * 3600

    # 上下文：从桃信数据里捞这个人的聊天侧写（只对主人有效）
    ctx_lines = [f"角色：{per['name']}（{per['en']}）", f"学校/社团：{per['school']} / {per['club']}",
                 f"性格：{per['traits']}"]
    try:
        mem = mail_data(data_dir) or {}
        me = next((x for x in (mem.get("people") or []) if str(x.get("id")) == "owner"), None)
        if me:
            ctx_lines.append(f"与老师：好感 {me.get('favor')}/100，亲密 {me.get('intimacy')}/100，聊过 {me.get('total')} 次")
            if me.get("attitude"):
                ctx_lines.append(f"她对老师的态度：{me['attitude']}")
            ph = me.get("phrases") or []
            if ph:
                ctx_lines.append("老师说过：" + "；".join(ph[:3]))
    except Exception:
        pass

    # 心得总结
    up = cache.get("upgrade") or {}
    if force or not up.get("text") or now - float(up.get("at") or 0) > ttl:
        sys_p = (
            f"你是{per['name']}的日记整理器。根据给定的角色设定与相处数据，"
            "用第一人称写 3 条「最近的心得」，每条一行，以「· 」开头，20~40 字，"
            "像她自己在回想跟老师相处的片段，具体、有画面感，不要客套话。"
        )
        txt = _member_llm(sys_p, "\n".join(ctx_lines) + "\n\n写 3 条最近的心得。")
        if txt:
            _member_cache_put(data_dir, key, "upgrade", txt)
            up = {"text": txt, "at": now}

    # 神秘解放：她不会对任何人说出口的那句
    sec = cache.get("secret") or {}
    if force or not sec.get("text") or now - float(sec.get("at") or 0) > ttl:
        sys_s = (
            f"你是{per['name']}。现在没有人听得见，你终于可以对自己承认一些事。"
            "用第一人称写 2~3 句「不能说出口的真心话」：真实的恐惧、依赖、或者对老师的独占欲。"
            "要具体、要有点痛，不要写成心灵鸡汤，不要解释、不要加标题。"
        )
        txt2 = _member_llm(sys_s, "\n".join(ctx_lines) + "\n\n现在没人听见，说出你真正想的。")
        if txt2:
            _member_cache_put(data_dir, key, "secret", txt2)
            sec = {"text": txt2, "at": now}

    # 人格设定卡数据：从桃信侧写里取态度/关系/情绪/互动统计
    persona: dict[str, Any] = {"attitude": "", "relationship": "", "emotions": [], "stats": {}, "phrases": []}
    try:
        mem = mail_data(data_dir) or {}
        me = next((x for x in (mem.get("people") or []) if str(x.get("id")) == "owner"), None)
        if me:
            persona["attitude"] = me.get("attitude") or ""
            persona["relationship"] = me.get("relationship") or ""
            persona["emotions"] = me.get("emotions") or []
            persona["phrases"] = (me.get("phrases") or [])[:4]
            persona["stats"] = {
                "total": me.get("total") or 0,
                "positive": me.get("positive") or 0,
                "negative": me.get("negative") or 0,
                "group": me.get("group") or 0,
                "last": me.get("last") or "",
            }
    except Exception:
        pass

    # ── 量化指标：每位角色一套独立数据，绝不共享（好感/亲密不继承） ──
    # 只有面板主角色（mika）才有真实的相处记录，其余角色从零开始。
    PRIMARY = ("mika",)
    st = persona.get("stats") if key in PRIMARY else {}
    emo = persona.get("emotions") if key in PRIMARY else {}
    st = st or {}
    emo = emo or {}
    total = int(st.get("total") or 0)
    pos = int(st.get("positive") or 0)
    neg = int(st.get("negative") or 0)
    favor = 0
    intimacy = 0
    if key in PRIMARY:
        try:
            mem2 = mail_data(data_dir) or {}
            me2 = next((x for x in (mem2.get("people") or []) if str(x.get("id")) == "owner"), None)
            if me2:
                favor = int(me2.get("favor") or 0)
                intimacy = int(me2.get("intimacy") or 0)
        except Exception:
            pass

    def _pct(a: float, b: float) -> int:
        return 0 if b <= 0 else int(round(max(0.0, min(1.0, a / b)) * 100))

    own = (per.get("stats") or {}) if isinstance(per.get("stats"), dict) else {}
    if own:
        favor = int(own.get("favor") or favor)
        intimacy = int(own.get("intimacy") or intimacy)
        total = int(own.get("talks") or total)
        pos = int(own.get("positive") or pos)
        neg = int(own.get("negative") or neg)

    bond = {
        "favor": favor if key in PRIMARY else int(own.get("favor") or 0),
        "intimacy": intimacy if key in PRIMARY else int(own.get("intimacy") or 0),
        "trust": int(emo.get("trust") or 0) if key in PRIMARY else 0,
        "warmth": _pct(pos, max(total, 1)) if key in PRIMARY else 0,
        "talks": total,
        "memories": len([x for x in (up.get("text") or "").split("\n") if x.strip()]),
    }
    inner = {
        "reliance": int(round((bond["intimacy"] * 0.6) + (bond["favor"] * 0.4))),
        "suppress": int(round(100 - (int(emo.get("joy") or 0) * 0.7 + int(emo.get("trust") or 0) * 0.3))),
        "possessive": int(round(min(100, (neg * 6) + int(emo.get("anger") or 0) + int(emo.get("disgust") or 0) * 1.5))),
        "honesty": int(round((int(emo.get("trust") or 0) * 0.5) + (int(emo.get("fear") or 0) * -0.3) + 40)),
        "lonely": int(emo.get("sadness") or 0),
        "curiosity": int(emo.get("anticipation") or 0),
    }
    for kv in (bond, inner):
        for k2, v2 in list(kv.items()):
            if isinstance(v2, (int, float)) and k2 not in ("talks", "memories"):
                kv[k2] = int(max(0, min(100, v2)))
    inner["honesty"] = max(0, min(100, inner["honesty"]))

    return {
        "ok": True, "key": key,
        "basic": per,
        "bond": bond,
        "inner": inner,
        "persona": persona,
        "intro": per.get("intro"), "traits": per.get("traits"),
        "upgrade": (up.get("text") or "").split("\n"),
        "secret": sec.get("text") or "",
        "voice": [f"/voice/{key}-01.mp3", f"/voice/{key}-02.mp3"],
    }

# ── 人格卡：读写 AstrBot 原生 persona（data_v4.db）+ 面板补充层 ──────
PERSONA_DB = "data_v4.db"
PERSONA_FILE = "panel_persona.json"


def _persona_db(data_dir: Path):
    import sqlite3
    p = data_dir / PERSONA_DB
    if not p.exists():
        return None
    try:
        con = sqlite3.connect(str(p), timeout=5)
        con.row_factory = sqlite3.Row
        return con
    except Exception:
        return None


def _persona_default(key: str) -> str:
    per = MEMBER_PERSONA.get(key) or MEMBER_PERSONA["mika"]
    return (
        f"你是{per['name']}（{per['en']}），{per['school']}·{per['club']}。\n"
        f"性格：{per['traits']}\n"
        f"背景：{per.get('intro') or ''}\n"
        "说话自然，不要客套，不要自称「AI」或「助手」。"
    )


def persona_get(data_dir: Path, key: str) -> dict:
    """读 AstrBot 的 persona.system_prompt，同时带上面板补充层。"""
    key = (key or "mika").lower()
    text = ""
    source = "default"
    updated = ""
    con = _persona_db(data_dir)
    if con is not None:
        try:
            row = con.execute(
                "SELECT system_prompt, updated_at FROM personas WHERE persona_id = ?", (key,)
            ).fetchone()
            if row is not None:
                text = (row["system_prompt"] or "").strip()
                updated = row["updated_at"] or ""
                source = "astrbot"
        except Exception:
            pass
        finally:
            try:
                con.close()
            except Exception:
                pass
    if not text:
        text = _persona_default(key)
    d = _read_json(data_dir / PERSONA_FILE, {}) or {}
    entry = d.get(key) or {}
    return {
        "ok": True, "key": key,
        "text": text,
        "extra": entry.get("text") or "",
        "source": source,
        "updated": updated or entry.get("updated") or "",
        "custom": bool(entry.get("text")),
    }


def persona_save(data_dir: Path, key: str, text: str = "", extra: str = "") -> dict:
    """只读：人格卡以 AstrBot 里的原文为准，面板不接受写入。"""
    out = persona_get(data_dir, key)
    out.update({
        "ok": False,
        "readonly": True,
        "error": "人格卡只读：请直接在 AstrBot 后台修改，面板不覆盖原有设定",
    })
    return out

# ════════════════════════════════════════════════════════════
# OneBot HTTP（NapCat）真实发送
# ════════════════════════════════════════════════════════════
_ONEBOT_CACHE: dict = {"at": 0.0, "cfg": None}


def _onebot_cfg() -> dict:
    """从 config.json 读 onebot 配置，缺省 127.0.0.1:3000。"""
    now = time.time()
    if _ONEBOT_CACHE["cfg"] is not None and now - _ONEBOT_CACHE["at"] < 5:
        return _ONEBOT_CACHE["cfg"]
    cfg = {"base": "http://127.0.0.1:3000", "token": ""}
    try:
        raw = json.loads((Path(__file__).with_name("config.json")).read_text(encoding="utf-8"))
        ob = raw.get("onebot") or {}
        if ob.get("base"):
            cfg["base"] = str(ob["base"]).rstrip("/")
        if ob.get("token"):
            cfg["token"] = str(ob["token"])
    except Exception:
        pass
    _ONEBOT_CACHE["cfg"] = cfg
    _ONEBOT_CACHE["at"] = now
    return cfg


def _onebot(action: str, payload: dict) -> dict:
    cfg = _onebot_cfg()
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{cfg['base']}/{action}", data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if cfg["token"]:
        req.add_header("Authorization", "Bearer " + cfg["token"])
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def qq_send(data_dir: Path, text: str, group_id: str | None = None, qq: str | None = None,
            payload: object = None) -> dict:
    """真实发一条消息出去：给了 group_id 走群，否则走私聊。payload 可传 at 段数组。"""
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "空消息"}
    msg = payload if payload is not None else text
    try:
        if group_id:
            res = _onebot("send_group_msg", {"group_id": int(group_id), "message": msg})
        else:
            if not qq:
                return {"ok": False, "error": "缺少发送对象"}
            res = _onebot("send_private_msg", {"user_id": int(qq), "message": msg})
    except Exception as e:
        return {"ok": False, "error": f"OneBot 调用失败：{e}"}
    ok = res.get("retcode") == 0
    return {"ok": ok, "retcode": res.get("retcode"), "message_id": (res.get("data") or {}).get("message_id"),
            "error": None if ok else (res.get("message") or res.get("wording") or "发送失败")}


def chat_append_real(data_dir: Path, qq: str, role: str, text: str) -> dict:
    """把面板里刚刚真实发出的一句话记进本地会话（role = me）。"""
    d = _chat_load(data_dir)
    ent = d.setdefault(str(qq), {"threads": [], "asides": []})
    ent.setdefault("threads", []).append({"role": role, "text": text, "ts": int(time.time())})
    ent["threads"] = ent["threads"][-200:]
    _chat_save(data_dir, d)
    return chat_get(data_dir, qq)


def chat_speak(data_dir: Path, qq: str) -> dict:
    """让 bot 自己想一句发给对方的话（不回应任何输入）。"""
    prof = _chat_profile(data_dir, qq)
    name = prof.get("name") or qq
    lines = [
        "你正在主动找对方说话，而不是回答任何问题。",
        f"对方是「{name}」。",
        f"你对他的印象：{prof.get('impression') or '还不熟'}。",
        f"当前关系：{prof.get('relation') or '普通'}，好感 {prof.get('favor', 0)}。",
        "写一句你此刻真的想对他说的话，20~60 字，口语，像在手机上打字。",
        "不要提问式开场白，不要复述设定，不要加解释或引号。只输出这一句。",
    ]
    try:
        text = _llm_chat([{"role": "system", "content": "\n".join(lines)},
                          {"role": "user", "content": "（现在没有人说话，你自己开口）"}],
                         data_dir, temperature=1.05, max_tokens=200).strip()
    except Exception as e:
        return {"ok": False, "error": f"生成失败：{e}"}
    text = text.strip().strip('"“”')
    if not text:
        return {"ok": False, "error": "模型没有给出内容"}
    return {"ok": True, "text": text, "name": name}

# ════════════════════════════════════════════════════════════
# 发送对象判定：好友走私聊，非好友走他所在的群
# ════════════════════════════════════════════════════════════
_COMP_FILE = COMPANION_FILE


def _companions(data_dir: Path) -> dict:
    try:
        return json.loads((Path(data_dir) / _COMP_FILE).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _friend_ids(data_dir: Path) -> set[str]:
    """panel_qq.json 里真正加过好友的 QQ 号。"""
    out: set[str] = set()
    try:
        d = _qq_load(data_dir)
        for r in d.get("friends") or []:
            if r.get("qq"):
                out.add(str(r["qq"]))
    except Exception:
        pass
    return out


def _owner_ids() -> set[str]:
    """config.json 里配置的主人 QQ，永远走私聊。"""
    out: set[str] = set()
    try:
        raw = json.loads((Path(__file__).with_name("config.json")).read_text(encoding="utf-8"))
        for k in ("owners", "owner_ids", "owner", "masters"):
            v = raw.get(k)
            if isinstance(v, (list, tuple)):
                out.update(str(x) for x in v)
            elif isinstance(v, (str, int)):
                out.add(str(v))
    except Exception:
        pass
    return out


def chat_target(data_dir: Path, qq: str) -> dict:
    """决定这句话往哪发：是好友就私聊，不是就找他所在的群并带上名字。"""
    qq = str(qq)
    # 名字优先用面板里显示的那个称呼（给谁发就带谁的名字），群昵称只作兜底
    name = ""
    known_flag = False
    try:
        for per in (mail_data(data_dir).get("people") or []):
            if str(per.get("avatarId") or per.get("id")) == qq or str(per.get("id")) == qq:
                name = per.get("name") or ""
                known_flag = bool(per.get("known"))
                break
    except Exception:
        name = ""
    alias = ""
    remembered = ""
    try:
        u = (_companions(data_dir).get("users") or {}).get(qq) or {}
        for k in ("nickname", "assumed_name", "last_display_name"):
            v = u.get(k)
            if isinstance(v, str) and v.strip():
                remembered = v.strip()
                break
    except Exception:
        remembered = ""
    groups: list[dict] = []
    comp = _companions(data_dir)
    for gid, g in (comp.get("groups") or {}).items():
        mem = g.get("members") or {}
        if qq in mem:
            nm = (mem[qq] or {}).get("identity_name") or (mem[qq] or {}).get("name") or ""
            if nm and not alias:
                alias = nm
            groups.append({
                "group_id": str(g.get("group_id") or gid),
                "group_name": g.get("manual_group_name") or g.get("name") or str(gid),
                "last_seen": (mem[qq] or {}).get("last_seen") or 0,
            })
    groups.sort(key=lambda x: x.get("last_seen") or 0, reverse=True)

    # 主人永远私聊
    if qq in _owner_ids():
        return {"mode": "private", "group_id": None, "group_name": None,
                "name": name or remembered or alias or qq, "qq": qq}

    # 从群聊认识的人（桃信里的 known / 群来源）一律在群里说
    from_group = bool(groups) and (bool(known_flag) or not (qq in _friend_ids(data_dir)))
    if from_group:
        g = groups[0]
        return {"mode": "group", "group_id": g["group_id"], "group_name": g["group_name"],
                "name": name or remembered or alias or qq, "alias": alias,
                "remembered": remembered, "qq": qq}

    if qq in _friend_ids(data_dir):
        return {"mode": "private", "group_id": None, "group_name": None,
                "name": name or remembered or alias or qq, "alias": alias,
                "remembered": remembered, "qq": qq}
    if groups:
        g = groups[0]
        return {"mode": "group", "group_id": g["group_id"], "group_name": g["group_name"],
                "name": name or remembered or alias or qq, "alias": alias, "remembered": remembered, "qq": qq}
    return {"mode": "private", "group_id": None, "group_name": None,
            "name": name or remembered or alias or qq, "alias": alias, "remembered": remembered, "qq": qq}


def _companion_note(data_dir: Path, qq: str, text: str, group_id: str | None = None) -> None:
    """把面板里真实发出的一句话写回 companions.json，让 bot 的记忆里也有这句。"""
    path = Path(data_dir) / _COMP_FILE
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    now = time.time()
    u = (d.get("users") or {}).get(str(qq))
    if isinstance(u, dict):
        u["last_companion_message"] = text
        u["last_companion_message_at"] = now
        try:
            u["reply_count"] = int(u.get("reply_count") or 0) + 1
        except Exception:
            u["reply_count"] = 1
    if group_id:
        g = (d.get("groups") or {}).get(str(group_id))
        if isinstance(g, dict):
            reps = g.get("recent_bot_replies")
            if not isinstance(reps, list):
                reps = []
            reps.append({"ts": now, "text": text, "reply_to_id": str(qq), "kind": "text"})
            g["recent_bot_replies"] = reps[-12:]
    try:
        path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def chat_send_smart(data_dir: Path, qq: str, text: str, group_id: str | None = None,
                    at: bool = False) -> dict:
    """按 chat_target 的判定真实发送。

    群聊时：at=True 发 @ 段，否则在句首带上对方名字。
    """
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "空消息"}
    if group_id:
        tgt = {"mode": "group", "group_id": str(group_id), "group_name": "", "name": "", "qq": str(qq)}
    else:
        tgt = chat_target(data_dir, qq)
    nm = tgt.get("name") or qq
    body = text
    payload: object = None
    if tgt["mode"] == "group":
        if at:
            payload = [
                {"type": "at", "data": {"qq": str(tgt["qq"])}},
                {"type": "text", "data": {"text": " " + body}},
            ]
        elif nm and not body.startswith(nm):
            body = f"{nm}，{body}"
    res = qq_send(data_dir, body, group_id=tgt.get("group_id"), qq=tgt["qq"], payload=payload)
    if res.get("ok"):
        _companion_note(data_dir, str(tgt["qq"]), text, tgt.get("group_id"))
    res["target"] = {"mode": tgt["mode"], "group_id": tgt.get("group_id"),
                     "group_name": tgt.get("group_name"), "name": tgt.get("name")}
    res["sent_text"] = body
    return res

def _msg_text(raw: str) -> str:
    """把 platform_message_history.content 的 JSON 拆成纯文本。"""
    try:
        d = json.loads(raw)
    except Exception:
        return (raw or "").strip()
    parts: list[str] = []
    for seg in (d.get("message") or []):
        t = seg.get("type")
        if t == "plain":
            parts.append(seg.get("text") or "")
        elif t == "image":
            parts.append("[图片]")
        elif t == "face":
            parts.append("[表情]")
        elif t == "record":
            parts.append("[语音]")
    return "".join(parts).strip()


def _msg_ts(raw: str) -> float:
    try:
        return time.mktime(time.strptime(str(raw)[:19], "%Y-%m-%d %H:%M:%S"))
    except Exception:
        return 0.0


def chat_context(data_dir: Path, qq: str, per_block: int = 0, gap: float = 1800.0) -> list[dict]:
    """他和 bot 的真实往来，来自 AstrBot 的消息历史表。

    只保留「他说的」和「bot 说的」，群里的其他人不进窗口。
    按 gap 秒切段；per_block<=0 表示每段不限句数，段数也不设上限。
    """
    qq = str(qq)
    bot_id = "BOT_QQ"
    try:
        cfg = _onebot_cfg() or {}
        bot_id = str(cfg.get("self_id") or bot_id)
    except Exception:
        pass

    con = _persona_db(data_dir)
    if con is None:
        return []

    items: list[dict] = []
    try:
        sess = con.execute(
            "select distinct platform_id from platform_message_history where sender_id = ?",
            (qq,),
        ).fetchall() or [("napcat",)]
        for (pid,) in sess:
            rows = con.execute(
                "select created_at, sender_id, content from platform_message_history "
                "where platform_id = ? order by id desc limit 400",
                (pid,),
            ).fetchall()
            rows.reverse()
            for raw_ts, sid, content in rows:
                sid = str(sid)
                # 历史表里 bot 的消息不带「发给谁」的信息，一律不收，
                # 她的话统一从 companions.recent_bot_replies（带 reply_to_id）取
                if sid != qq or sid == bot_id:
                    continue
                txt = _msg_text(content)
                if not txt:
                    continue
                items.append({
                    "ts": _msg_ts(raw_ts),
                    "role": "them" if sid == qq else "me",
                    "text": txt,
                })
    except Exception:
        items = []
    finally:
        try:
            con.close()
        except Exception:
            pass

    # bot 的回话：历史表里只有零星几条，主要靠 companions 的 recent_bot_replies
    try:
        comp = _companions(data_dir)
        for gid, g in (comp.get("groups") or {}).items():
            for r in (g.get("recent_bot_replies") or []):
                if str(r.get("reply_to_id")) != qq:
                    continue
                txt = (r.get("text") or "").strip()
                if not txt:
                    continue
                items.append({"ts": float(r.get("ts") or 0), "role": "me", "text": txt})
        u = (comp.get("users") or {}).get(qq) or {}
        if (u.get("last_companion_message") or "").strip():
            items.append({
                "ts": float(u.get("last_companion_message_at") or 0),
                "role": "me",
                "text": u["last_companion_message"].strip(),
            })
        if (u.get("last_user_message") or "").strip():
            items.append({
                "ts": float(u.get("last_user_message_at") or 0),
                "role": "them",
                "text": u["last_user_message"].strip(),
            })
    except Exception:
        pass

    if not items:
        return []

    items.sort(key=lambda x: x["ts"])
    # 同一句话可能同时存在于面板记录和 bot 记忆里：按「角色 + 文本」去重，
    # 保留最早的那条时间戳，避免同一句在时间线上出现两次
    seen, uniq = {}, []
    for it in items:
        key = (it["role"], " ".join(it["text"].split())[:120])
        if key in seen:
            uniq[seen[key]]["ts"] = min(uniq[seen[key]]["ts"], it["ts"])
            continue
        seen[key] = len(uniq)
        uniq.append(it)
    uniq.sort(key=lambda x: x["ts"])

    blocks: list[dict] = []
    cur: list[dict] = []
    last_ts = 0.0
    for it in uniq:
        if cur and it["ts"] - last_ts > gap:
            blocks.append({"ts": cur[0]["ts"], "items": cur[-per_block:]})
            cur = []
        cur.append(it)
        last_ts = it["ts"]
    if cur:
        blocks.append({"ts": cur[0]["ts"], "items": cur[-per_block:]})

    # 只保留她真的开口过的那几段，并带上它前面一段（他的话头），
    # 他跟别人聊、她完全没参与的段落不进一对一记录
    keep: set[int] = set()
    for i, b in enumerate(blocks):
        if any(it["role"] == "me" for it in b["items"]):
            keep.add(i)
            if i > 0:
                keep.add(i - 1)
    blocks = [b for i, b in enumerate(blocks) if i in keep] or blocks[-1:]
    out = []
    for b in blocks[-8:]:
        out.append({
            "ts": b["ts"],
            "day": time.strftime("%m-%d %H:%M", time.localtime(b["ts"])) if b["ts"] else "",
            "items": b["items"],
        })
    return out
