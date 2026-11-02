"""
SCHALE Panel BFF —— 蔚蓝档案风格面板的后端聚合层

职责：
  1. 登录鉴权（本地密码 → JWT，浏览器只持有 BFF 签发的 token，永不接触 AstrBot 的 JWT）
  2. 把 AstrBot 的碎 API + 只能读文件的插件数据，聚合成前端要的形状
  3. 局域网访问（默认只监听 127.0.0.1:7870；要给别人访问就把 host 改成 0.0.0.0，并把密码设复杂）

启动：python main.py（默认 127.0.0.1:7870，可用 SCHALE_HOST / SCHALE_PORT 覆盖）
"""
from __future__ import annotations

import asyncio
import base64
import shutil
import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from typing import Any

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import Body, Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from services import ServiceManager, tail_log as _tail_log

BASE = Path(__file__).resolve().parent
CONFIG = BASE / "config.json"
EXAMPLE = BASE / "config.example.json"
if not CONFIG.exists() and EXAMPLE.exists():
    shutil.copyfile(EXAMPLE, CONFIG)
    print("=" * 62)
    print(" 首次启动：已生成 backend/config.json")
    print(" 请改成你自己的设置，最少要填这 3 项：")
    print("   data_dir   AstrBot 的 data 目录，例如 D:/AstrBot/data")
    print("   password   面板登录密码（现在还是 CHANGE_ME）")
    print("   onebot     想从面板发 QQ 消息时才需要填")
    print("=" * 62)
try:
    CFG = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
except json.JSONDecodeError as e:
    print("=" * 62)
    print(f"[x] {CONFIG} 不是合法的 JSON：{e}")
    print("    最常见的原因：多写了一个逗号，或者用了中文引号 “” 。")
    print("    可以贴到 https://jsonlint.com 检查一下。")
    print("=" * 62)
    raise SystemExit(1)

PASSWORD: str = os.environ.get("SCHALE_PASSWORD") or str(CFG.get("password") or "change-me")
if PASSWORD in ("CHANGE_ME", "change-me"):
    print("[warn] password 还是默认占位符，任何人都能登录。改完 config.json 再重启。")
SECRET: bytes = (os.environ.get("SCHALE_JWT_SECRET") or CFG.get("jwt_secret")
                 or hashlib.sha256(os.urandom(32)).hexdigest()).encode()
TOKEN_HOURS: int = int(CFG.get("token_hours", 720))
DATA_DIR = Path(os.environ.get("SCHALE_DATA_DIR") or CFG.get("data_dir") or "./data")
ASTRBOT = CFG.get("astrbot_base", "http://127.0.0.1:6185").rstrip("/")

# 服务管理器（编队页用）
SERVICES = ServiceManager(CFG.get("services") or [])

# 今日调用软上限（能量条）
CALL_CAP = 200

app = FastAPI(title="SCHALE Panel BFF", version="0.1.0", docs_url=None, redoc_url=None)

# 面板是给同一局域网内的自己用的；允许跨源方便将来把前端拆到别的端口
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------- JWT (HS256)
def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64d(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def make_token(sub: str = "laoshi") -> str:
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64(
        json.dumps(
            {"sub": sub, "iat": int(time.time()), "exp": int(time.time()) + TOKEN_HOURS * 3600},
            separators=(",", ":"),
        ).encode()
    )
    signing = f"{header}.{payload}".encode()
    sig = _b64(hmac.new(SECRET, signing, hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


def read_token(token: str) -> dict[str, Any] | None:
    try:
        header, payload, sig = token.split(".")
        signing = f"{header}.{payload}".encode()
        expect = _b64(hmac.new(SECRET, signing, hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expect):
            return None
        data = json.loads(_b64d(payload))
        if int(data.get("exp", 0)) < time.time():
            return None
        return data
    except Exception:
        return None


async def require_auth(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="需要登录")
    data = read_token(authorization[7:].strip())
    if data is None:
        raise HTTPException(status_code=401, detail="登录已失效，请重新进入")
    return data


# ------------------------------------------------------------------- 入参模型
class LoginBody(BaseModel):
    password: str = ""


# --------------------------------------------------------------------- 路由
@app.post("/api/login")
async def login(body: LoginBody):
    if not hmac.compare_digest(body.password or "", PASSWORD):
        # 故意统一错误文案，不给暴力猜测提供信息
        raise HTTPException(status_code=401, detail="密码不对")
    return {"ok": True, "token": make_token(), "expires_in": TOKEN_HOURS * 3600}


@app.get("/api/me")
async def me(claims: dict[str, Any] = Depends(require_auth)):
    return {"ok": True, "sub": claims.get("sub"), "exp": claims.get("exp")}


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "service": "schale-bff",
        "version": "0.1.0",
        "astrbot": ASTRBOT,
        "data_dir": str(DATA_DIR),
        "data_dir_exists": DATA_DIR.exists(),
    }


# ------------------------------------------------------------------- 数据聚合
@app.get("/api/notice")
async def notice(claims: dict[str, Any] = Depends(require_auth)):
    """公告栏三份数据：公告 / 活动 / 异常通知。"""
    import collect

    try:
        stat = await asyncio.to_thread(collect.plugin_stat, ASTRBOT, DATA_DIR)
    except Exception:
        stat = None
    key = collect.deepseek_key(DATA_DIR)
    return await asyncio.to_thread(collect.build_notice, DATA_DIR, key, stat)


@app.get("/api/overview")
async def overview(claims: dict[str, Any] = Depends(require_auth)):
    """主界面顶部资源条 + 右侧两卡。"""
    import collect

    def build() -> dict[str, Any]:
        key = collect.deepseek_key(DATA_DIR)
        use = collect.usage_today(DATA_DIR)
        bal = collect.deepseek_balance(key)
        svc = collect.services()
        stat = collect.plugin_stat(ASTRBOT, DATA_DIR)
        log = collect.scan_log(DATA_DIR)
        ad = collect.active_days(DATA_DIR)

        # 群数：companions.json 里的 groups
        groups = 0
        comp = DATA_DIR / collect.COMPANION_FILE
        d = collect._read_json(comp, {}) or {}
        g = d.get("groups")
        if isinstance(g, dict):
            groups = len(g)
        elif isinstance(g, list):
            groups = len(g)

        todo = []
        if bal and bal["total"] < 10:
            todo.append({"tone": "warn", "text": f"余额只剩 ¥{bal['total']:.2f}", "note": "考虑充值或切免费通道"})
        if log["error"]:
            todo.append({"tone": "error", "text": f"今天 {log['error']} 条错误", "note": "点左侧公告看详情"})
        if not svc["ollama"]["up"]:
            todo.append({"tone": "warn", "text": "向量服务离线", "note": "Ollama 11434 没在跑"})
        if not todo:
            todo.append({"tone": "ok", "text": "一切正常", "note": "没有需要你管的事"})

        return {
            "ok": True,
            "res": {
                "ap": max(0, CALL_CAP - use["calls"]),
                "apMax": CALL_CAP,
                "apUsed": use["calls"],
                "gem": round(bal["total"], 2) if bal else 0,
                "credit": use["total"],
                "creditText": collect._fmt_tok(use["total"]),
            },
            "lv": {
                "days": ad["days"],
                "exp": round(ad["today_hours"], 1),
                "expMax": 24,
                "first": ad["first"],
            },
            "todo": todo[:4],
            "now": {
                "online": bool(svc["gateway"]["up"] and svc["router"]["up"]),
                "groups": groups,
                "plugins": stat.get("active", 0),
                "pluginsTotal": stat.get("total", 0),
                "tokens": use["calls"],
            },
        }

    return await asyncio.to_thread(build)


@app.get("/api/cafe")
async def cafe(claims: dict[str, Any] = Depends(require_auth)):
    """咖啡厅：群卡座 / 常客 / 她的心情。"""
    import collect

    return await asyncio.to_thread(collect.cafe_data, DATA_DIR)


@app.get("/api/shop")
async def shop(_: dict[str, Any] = Depends(require_auth)):
    """商店：模型供应商 / 今日消耗 / 近七日消耗 / 余额。"""
    import collect

    return {"ok": True, **await asyncio.to_thread(collect.shop_data, DATA_DIR)}


@app.get("/api/mail")
async def api_mail(_: dict = Depends(require_auth)):
    import collect

    return {"ok": True, **await asyncio.to_thread(collect.mail_data, DATA_DIR)}


@app.get("/api/daily")
async def api_daily(_: dict = Depends(require_auth)):
    """日程：她今天的安排 / 状态 / 梦 / 日记。"""
    import collect

    return {"ok": True, **await asyncio.to_thread(collect.daily_data, DATA_DIR)}


@app.get("/api/persona/{key}")
async def api_persona_get(key: str):
    import collect
    return collect.persona_get(DATA_DIR, key)


@app.post("/api/persona/{key}")
async def api_persona_save(key: str, payload: dict = Body(...)):
    import collect
    return collect.persona_save(
        DATA_DIR, key,
        str(payload.get("text") or ""),
        str(payload.get("extra") or ""),
    )


@app.get("/api/member/{key}")
async def api_member(key: str, force: int = 0):
    import collect
    return collect.member_detail(DATA_DIR, key, bool(force))


@app.get("/api/members")
async def api_members(_: dict = Depends(require_auth)):
    """成员：全部群成员（含好感、情绪、所属群）。"""
    import collect

    return {"ok": True, **await asyncio.to_thread(collect.mail_data, DATA_DIR, True)}


@app.post("/api/mail/think")
async def api_mail_think(payload: dict, _: dict = Depends(require_auth)):
    import collect

    pid = str(payload.get("id") or "")
    return await asyncio.to_thread(collect.mail_think, DATA_DIR, pid)

@app.get("/api/avatar/{qq}")
async def api_avatar(qq: str):
    import collect
    from fastapi.responses import FileResponse

    p = await asyncio.to_thread(collect.fetch_avatar, DATA_DIR, qq)
    if not p or not p.exists():
        raise HTTPException(status_code=404, detail="没有头像")
    return FileResponse(str(p), media_type="image/jpeg", headers={"Cache-Control": "max-age=604800"})

@app.get("/api/hello")
async def api_hello(scene: str = "home", _: dict = Depends(require_auth)):
    import collect

    return {"ok": True, **await asyncio.to_thread(collect.hello, DATA_DIR, scene)}



@app.get("/api/groups")
async def api_groups(_: dict = Depends(require_auth)):
    import collect

    return {"ok": True, **await asyncio.to_thread(collect.groups_data, DATA_DIR)}


@app.get("/api/gavatar/{gid}")
async def api_gavatar(gid: str):
    import collect

    p = await asyncio.to_thread(collect.group_avatar, DATA_DIR, gid)
    if not p:
        raise HTTPException(status_code=404, detail="没有群头像")
    return FileResponse(str(p), media_type="image/jpeg", headers={"Cache-Control": "max-age=604800"})

@app.get("/api/qq/requests")
async def api_qq_requests(_: dict = Depends(require_auth)):
    import collect

    return {"ok": True, **await asyncio.to_thread(collect.qq_requests, DATA_DIR)}


@app.post("/api/qq/decide")
async def api_qq_decide(payload: dict, _: dict = Depends(require_auth)):
    import collect

    qq = str(payload.get("qq") or "")
    accept = bool(payload.get("accept"))
    if not qq:
        raise HTTPException(400, "缺少 QQ 号")
    return {"ok": True, **await asyncio.to_thread(collect.qq_decide, DATA_DIR, qq, accept)}


@app.post("/api/qq/apply")
async def api_qq_apply(payload: dict, _: dict = Depends(require_auth)):
    import collect

    qq = str(payload.get("qq") or "")
    name = str(payload.get("name") or "")
    if not qq.isdigit():
        raise HTTPException(400, "QQ 号只能是数字")
    return {"ok": True, **await asyncio.to_thread(collect.qq_apply, DATA_DIR, qq, name)}


@app.get("/api/prefs")
async def api_prefs_get(_: dict = Depends(require_auth)):
    import collect

    return {"ok": True, **await asyncio.to_thread(collect.prefs_load, DATA_DIR)}


@app.post("/api/prefs")
async def api_prefs_set(payload: dict, _: dict = Depends(require_auth)):
    import collect

    return {"ok": True, **await asyncio.to_thread(collect.prefs_save, DATA_DIR, payload)}


@app.post("/api/qq/cancel")
async def api_qq_cancel(payload: dict, _: dict = Depends(require_auth)):
    """撤回自己发出的好友申请。"""
    import collect

    qq = str(payload.get("qq") or "").strip()
    if not qq:
        raise HTTPException(400, "缺少 QQ 号")
    return {"ok": True, **await asyncio.to_thread(collect.qq_cancel, DATA_DIR, qq)}


@app.get("/api/qq/profile")
async def api_qq_profile(qq: str, _: dict = Depends(require_auth)):
    import collect

    return {"ok": True, **await asyncio.to_thread(collect.qq_profile, DATA_DIR, qq)}


@app.get("/api/tasks")
async def api_tasks(_: dict = Depends(require_auth)):
    import collect

    return {"ok": True, **await asyncio.to_thread(collect.tasks_data, DATA_DIR)}


@app.post("/api/tasks/upsert")
async def api_task_upsert(payload: dict, _: dict = Depends(require_auth)):
    import collect

    return {"ok": True, **await asyncio.to_thread(collect.task_upsert, DATA_DIR, payload)}


@app.post("/api/tasks/delete")
async def api_task_delete(payload: dict, _: dict = Depends(require_auth)):
    import collect

    return {"ok": True, **await asyncio.to_thread(collect.task_delete, DATA_DIR, str(payload.get("id") or ""))}


@app.post("/api/tasks/toggle")
async def api_task_toggle(payload: dict, _: dict = Depends(require_auth)):
    import collect

    return {"ok": True, **await asyncio.to_thread(collect.task_toggle, DATA_DIR, str(payload.get("id") or ""))}


@app.exception_handler(HTTPException)
async def _http_error(_: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": exc.detail})


# ── 服务管理（大厅 → 编队）──────────────────────────────
@app.get("/api/services")
async def api_services(user: str = Depends(require_auth)):
    return {"ok": True, "list": SERVICES.all_status()}


@app.post("/api/services/{key}/{action}")
async def api_service_action(key: str, action: str, user: str = Depends(require_auth)):
    import collect
    if action not in ("start", "stop", "restart"):
        raise HTTPException(400, "action 只能是 start/stop/restart")
    fn = getattr(SERVICES, action)
    res = fn(key)
    res["list"] = SERVICES.all_status()
    return res


@app.get("/api/services/{key}/log")
async def api_service_log(key: str, lines: int = 120, user: str = Depends(require_auth)):
    return {"ok": True, "key": key, "text": _tail_log(key, lines)}


@app.on_event("startup")
async def _boot_services():
    try:
        got = SERVICES.autostart()
        if got:
            print("[services] 自动拉起:", ", ".join(got))
    except Exception as e:
        print("[services] autostart 失败:", e)


# ── 桃信 · 专属对话框 ───────────────────────────────────
@app.post("/api/chat/{qq}/send")
async def api_chat_send_real(qq: str, body: dict = Body(...), _=Depends(require_auth)):
    """面板里输入的内容，真实发到 QQ（给了 group_id 就发群，否则发私聊）。"""
    import collect
    text = (body.get("text") or "").strip()
    group_id = (str(body.get("group_id")).strip() or None) if body.get("group_id") else None
    if not text:
        return {"ok": False, "error": "空消息"}
    res = collect.chat_send_smart(DATA_DIR, qq, text, group_id=group_id, at=bool(body.get("at")))
    if res.get("ok"):
        res["thread"] = collect.chat_append_real(DATA_DIR, qq, "me", text)
        res["thread"]["target"] = res.get("target")
    return res


@app.post("/api/chat/{qq}/speak")
async def api_chat_speak(qq: str, body: dict = Body(default={}), _=Depends(require_auth)):
    """让 bot 主动说一句：先由模型想内容，再真实发出。"""
    import collect
    group_id = (str(body.get("group_id")).strip() or None) if body.get("group_id") else None
    gen = collect.chat_speak(DATA_DIR, qq)
    if not gen.get("ok"):
        return gen
    res = collect.chat_send_smart(DATA_DIR, qq, gen["text"], group_id=group_id, at=bool(body.get("at")))
    if res.get("ok"):
        res["text"] = gen["text"]
        res["thread"] = collect.chat_append_real(DATA_DIR, qq, "me", gen["text"])
        res["thread"]["target"] = res.get("target")
    else:
        res["text"] = gen["text"]
    return res


@app.get("/api/chat/{qq}")
async def api_chat_get(qq: str, _: dict = Depends(require_auth)):
    import collect
    return collect.chat_get(DATA_DIR, qq)


class ChatIn(BaseModel):
    text: str = ""
    aside: str = ""


@app.post("/api/chat/{qq}")
async def api_chat_send(qq: str, body: ChatIn, _: dict = Depends(require_auth)):
    import collect
    return collect.chat_send(DATA_DIR, qq, body.text, body.aside)


# ---------------------------------------------------------------- 前端托管
_DIST = (BASE.parent / "frontend" / "dist").resolve()
if _DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def _spa(full_path: str):
        target = (_DIST / full_path).resolve()
        if full_path and target.is_file() and str(target).startswith(str(_DIST)):
            return FileResponse(target)
        return FileResponse(_DIST / "index.html")


if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("SCHALE_HOST") or CFG.get("host") or "127.0.0.1"
    port = int(os.environ.get("SCHALE_PORT") or CFG.get("port") or 7870)
    print(f"[boot] http://{host}:{port}/")
    uvicorn.run(app, host=host, port=port, log_level="info")
