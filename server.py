"""FastAPI server providing a global leaderboard for Bugman."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime
from os import getenv
from urllib.parse import parse_qsl

import aiosqlite
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv


load_dotenv()

BOT_TOKEN = getenv("BOT_TOKEN", "")
PORT = int(getenv("PORT", "8080"))

DATABASE = "leaderboard.db"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS players (
  id TEXT PRIMARY KEY,
  username TEXT,
  display_name TEXT,
  best_score INTEGER DEFAULT 0,
  updated_at TEXT
);
"""


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScoreIn(BaseModel):
    initData: str
    score: int


def verify_init_data(init_data: str) -> dict | None:
    """Validate Telegram WebApp initData string."""

    if not BOT_TOKEN:
        return None

    data = dict(parse_qsl(init_data, strict_parsing=True))
    init_hash = data.pop("hash", None)
    if not init_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, init_hash):
        return None

    return data


@app.on_event("startup")
async def startup() -> None:
    app.state.db = await aiosqlite.connect(DATABASE)
    await app.state.db.execute(CREATE_TABLE_SQL)
    await app.state.db.commit()


@app.on_event("shutdown")
async def shutdown() -> None:
    await app.state.db.close()


@app.post("/score")
async def post_score(payload: ScoreIn):
    data = verify_init_data(payload.initData)
    if not data:
        raise HTTPException(status_code=401, detail="Invalid initData")

    user_json = data.get("user")
    if not user_json:
        raise HTTPException(status_code=400, detail="User missing")

    user = json.loads(user_json)
    user_id = str(user.get("id"))
    username = user.get("username")
    first_name = user.get("first_name")
    display_name = username or first_name or f"Player {user_id[-4:]}"

    db = app.state.db
    async with db.execute(
        "SELECT best_score FROM players WHERE id = ?", (user_id,)
    ) as cur:
        row = await cur.fetchone()
    prev_best = row[0] if row else 0

    now = datetime.utcnow().isoformat()
    if payload.score > prev_best:
        query = (
            "INSERT INTO players (id, username, display_name, best_score, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "username=excluded.username, display_name=excluded.display_name, "
            "best_score=excluded.best_score, updated_at=excluded.updated_at"
        )
        params = (user_id, username, display_name, payload.score, now)
        best = payload.score
    else:
        query = (
            "INSERT INTO players (id, username, display_name, best_score, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "username=excluded.username, display_name=excluded.display_name"
        )
        params = (user_id, username, display_name, prev_best, now)
        best = prev_best

    await db.execute(query, params)
    await db.commit()

    me = {
        "id": user_id,
        "display_name": display_name,
        "username": username,
        "best_score": best,
    }
    return {"ok": True, "me": me}


@app.get("/leaderboard")
async def get_leaderboard(limit: int = 100, offset: int = 0):
    if limit > 200:
        limit = 200

    db = app.state.db
    async with db.execute(
        "SELECT display_name, username, best_score FROM players ORDER BY best_score DESC "
        "LIMIT ? OFFSET ?",
        (limit, offset),
    ) as cur:
        rows = await cur.fetchall()

    items = [
        {"display_name": d, "username": u, "best_score": s} for d, u, s in rows
    ]
    return {"items": items}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=PORT)

