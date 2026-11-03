import time
import os
from aiohttp import web
import db

API_SECRET = "keyhub_9f3a8c7e2b1d4056_do_not_share"
PORT = int(os.environ.get("PORT", 8080))

def load_script_body() -> str:
    try:
        with open("scripts/main.lua", "r") as f:
            return f.read()
    except FileNotFoundError:
        return '-- no script body configured'

def build_script(row, seconds_left: int) -> str:
    header = f"""-- LRM runtime vars
LRM_IsUserPremium = true
LRM_SecondsLeft = {seconds_left}
LRM_LinkedDiscordID = "{row['discord_id']}"
LRM_ScriptName = "keyhub"
-- end LRM
"""
    return header + "\n" + load_script_body()

async def handle_load(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "bad_request"}, status=400)

    if data.get("secret") != API_SECRET:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    key = str(data.get("key", "")).strip()
    hwid = str(data.get("hwid", "")).strip()

    if not key or not hwid or hwid == "UNKNOWN":
        return web.json_response({"ok": False, "error": "missing_key_or_hwid"}, status=400)

    row = await db.get_key(key)
    if not row:
        return web.json_response({"ok": False, "error": "invalid_key"}, status=404)

    if row["blacklisted"]:
        return web.json_response({"ok": False, "error": "blacklisted"}, status=403)

    if not row["hwid"]:
        await db.bind_hwid(key, hwid)
        row = await db.get_key(key)
    elif row["hwid"] != hwid:
        return web.json_response({"ok": False, "error": "hwid_mismatch"}, status=403)

    if row["auth_expire"] and int(time.time()) >= row["auth_expire"]:
        return web.json_response({"ok": False, "error": "expired"}, status=403)

    seconds_left = 0
    if row["auth_expire"]:
        seconds_left = max(0, int(row["auth_expire"]) - int(time.time()))

    return web.json_response({
        "ok": True,
        "script": build_script(row, seconds_left),
        "seconds_left": seconds_left,
    })

async def handle_loader(request: web.Request) -> web.Response:
    try:
        with open("loader.lua", "r") as f:
            return web.Response(text=f.read(), content_type="text/plain")
    except FileNotFoundError:
        return web.Response(text="-- loader missing. owner must run /setpanel", status=404)

async def start_server():
    await db.init_db()
    app = web.Application()
    app.router.add_post("/load", handle_load)
    app.router.add_get("/loader", handle_loader)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"[server] listening on :{PORT}")
    return runner
