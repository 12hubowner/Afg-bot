CREATE TABLE IF NOT EXISTS keys (
    key          TEXT PRIMARY KEY,
    discord_id   INTEGER NOT NULL,
    hwid         TEXT,
    auth_expire  INTEGER,
    key_days     INTEGER,
    activated_at INTEGER,
    note         TEXT,
    blacklisted  INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_discord ON keys(discord_id);
CREATE INDEX IF NOT EXISTS idx_hwid ON keys(hwid);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS projects (
    name          TEXT PRIMARY KEY,
    api_key       TEXT,
    manager_role  INTEGER,
    buyer_role    INTEGER,
    loader_script TEXT
);
