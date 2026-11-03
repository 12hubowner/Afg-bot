import aiosqlite
import secrets
import time

DB_PATH = "keyhub.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        with open("schema.sql") as f:
            await db.executescript(f.read())
        await db.commit()

def generate_key() -> str:
    hex_str = secrets.token_hex(8).upper()
    return f"{hex_str[:4]}-{hex_str[4:8]}-{hex_str[8:12]}-{hex_str[12:16]}"

async def create_key(discord_id: int, key_days: int | None, note: str = "") -> str:
    key = generate_key()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO keys (key, discord_id, key_days, note) VALUES (?, ?, ?, ?)",
            (key, discord_id, key_days, note),
        )
        await db.commit()
    return key

async def get_key(key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM keys WHERE key = ?", (key,)) as cur:
            return await cur.fetchone()

async def get_user_key(discord_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM keys WHERE discord_id = ? ORDER BY rowid DESC LIMIT 1",
            (discord_id,),
        ) as cur:
            return await cur.fetchone()

async def bind_hwid(key: str, hwid: str):
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        row = await (await db.execute(
            "SELECT key_days FROM keys WHERE key = ?", (key,)
        )).fetchone()
        key_days = row[0] if row else None
        expire = now + key_days * 86400 if key_days else None
        await db.execute(
            "UPDATE keys SET hwid = ?, activated_at = ?, auth_expire = ? WHERE key = ?",
            (hwid, now, expire, key),
        )
        await db.commit()

async def reset_hwid(discord_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE keys SET hwid = NULL, activated_at = NULL, auth_expire = NULL "
            "WHERE discord_id = ?",
            (discord_id,),
        )
        await db.commit()
        return cur.rowcount > 0

async def blacklist_user(discord_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE keys SET blacklisted = 1 WHERE discord_id = ?",
            (discord_id,),
        )
        await db.commit()
        return cur.rowcount

async def delete_user_keys(discord_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "DELETE FROM keys WHERE discord_id = ?", (discord_id,)
        )
        await db.commit()
        return cur.rowcount

async def delete_specific_key(key: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM keys WHERE key = ?", (key,))
        await db.commit()
        return cur.rowcount > 0

async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        await db.commit()

async def get_setting(key: str, default: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else default

async def get_all_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM keys") as cur:
            total = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM keys WHERE hwid IS NOT NULL") as cur:
            active = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM keys WHERE blacklisted = 1") as cur:
            blacklisted = (await cur.fetchone())[0]
        return total, active, blacklisted
