"""FastAPI server providing a global leaderboard for Bugman."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime
from os import getenv
from urllib.parse import parse_qsl

import aiosqlite
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from dotenv import load_dotenv
import logging


load_dotenv()

BOT_TOKEN = getenv("BOT_TOKEN", "")
PORT = int(getenv("PORT", "8080"))
DEBUG = getenv("DEBUG", "").lower() == "true"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bugman")

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


@app.options("/score")
async def options_score() -> Response:
    return Response(status_code=204)


class ScoreIn(BaseModel):
    initData: str
    score: int


class InitDataIn(BaseModel):
    initData: str


def verify_init_data(init_data: str) -> dict | None:
    """Validate Telegram WebApp initData string."""

    if not BOT_TOKEN:
        return None

    try:
        data = dict(parse_qsl(init_data, keep_blank_values=True))
    except ValueError:
        return None

    init_hash = data.pop("hash", None)
    if not init_hash:
        return None

    data_check_string = "\n".join(f"{k}={data[k]}" for k in sorted(data))
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


LAST_SCORES: dict[str, datetime] = {}


@app.post("/score")
async def post_score(payload: ScoreIn, request: Request):
    ip = request.client.host if request.client else "-"
    user_id = "-"
    reason = "ok"
    status = 200
    try:
        if payload.initData is None or payload.score is None:
            status = 400
            reason = "missing initData or score"
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": "bad_request",
                    "reason": reason,
                },
            )

        data = verify_init_data(payload.initData)
        if not data:
            status = 401
            reason = "invalid_init_data"
            return JSONResponse(
                status_code=401,
                content={"ok": False, "error": "invalid_init_data"},
            )

        user_json = data.get("user")
        if not user_json:
            status = 400
            reason = "missing user"
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": "bad_request",
                    "reason": reason,
                },
            )

        try:
            user = json.loads(user_json)
        except json.JSONDecodeError:
            status = 400
            reason = "invalid user"
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": "bad_request",
                    "reason": reason,
                },
            )

        user_id = str(user.get("id"))
        username = user.get("username")
        first_name = user.get("first_name")
        last_name = user.get("last_name")
        display_name = (
            username or first_name or last_name or f"Player {user_id[-4:]}"
        )

        now_dt = datetime.utcnow()
        last = LAST_SCORES.get(user_id)
        if last and (now_dt - last).total_seconds() < 1:
            status = 429
            reason = "rate_limited"
            return JSONResponse(
                status_code=429,
                content={
                    "ok": False,
                    "error": "too_many_requests",
                    "reason": reason,
                },
            )
        LAST_SCORES[user_id] = now_dt

        db = app.state.db
        async with db.execute(
            "SELECT best_score FROM players WHERE id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        prev_best = row[0] if row else 0

        now = now_dt.isoformat()
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
    except Exception:
        status = 500
        reason = "server_error"
        logger.exception("score handler error")
        return JSONResponse(
            status_code=500, content={"ok": False, "error": "server_error"}
        )
    finally:
        logger.info("%s %s user=%s reason=%s", ip, status, user_id, reason)


if DEBUG:
    @app.post("/debug/echo_user")
    async def debug_echo_user(payload: InitDataIn):
        data = verify_init_data(payload.initData)
        if not data:
            return JSONResponse(status_code=401, content={"ok": False, "error": "invalid_init_data"})
        user_json = data.get("user")
        if not user_json:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": "bad_request", "reason": "missing user"},
            )
        try:
            user = json.loads(user_json)
        except json.JSONDecodeError:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": "bad_request", "reason": "invalid user"},
            )
        user_id = str(user.get("id"))
        username = user.get("username")
        first_name = user.get("first_name")
        last_name = user.get("last_name")
        display_name = username or first_name or last_name or f"Player {user_id[-4:]}"
        return {
            "ok": True,
            "user": {
                "id": user_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
            },
            "display_name": display_name,
        }


@app.get("/health")
async def health() -> dict:
    return {"ok": True}


@app.get("/")
async def root() -> dict:
    return {"ok": True, "service": "bugman-bot"}


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

