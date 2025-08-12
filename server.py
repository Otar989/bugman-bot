"""FastAPI server providing a global leaderboard for Bugman."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
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
from typing import Tuple, Optional


load_dotenv()

PORT = int(getenv("PORT", "8080"))
DEBUG = getenv("DEBUG", "").lower() == "true"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bugman")

DATABASE = "leaderboard.db"
RATE_LIMIT_SECONDS = 4

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



def get_tokens() -> list[str]:
    env_tokens = os.getenv("BOT_TOKENS")
    if env_tokens:
        return [t.strip() for t in env_tokens.split(",") if t.strip()]
    t = os.getenv("BOT_TOKEN")
    return [t] if t else []


def check_telegram_auth(init_data: str, tokens: list[str]) -> Tuple[bool, Optional[dict], str, str]:
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=False))
        recv_hash = pairs.pop("hash", None)
        if not recv_hash:
            return False, None, "no_hash", ""
        data_check_string = "\n".join(
            f"{k}={pairs[k]}" for k in sorted(pairs.keys())
        )
        for t in tokens:
            secret_key = hmac.new(b"WebAppData", t.encode(), hashlib.sha256).digest()
            calc = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
            if hmac.compare_digest(calc, recv_hash):
                user_json = pairs.get("user")
                if not user_json:
                    return False, None, "no_user", data_check_string
                try:
                    user = json.loads(user_json)
                except Exception:
                    return False, None, "no_user", data_check_string
                if "id" not in user:
                    return False, None, "no_user", data_check_string
                return True, user, "ok", data_check_string
        return False, None, "hash_mismatch", data_check_string
    except Exception:
        return False, None, "exception", ""


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
    init_len = len(payload.initData) if payload.initData else 0
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

        tokens = get_tokens()
        ok, user, reason_resp, _ = check_telegram_auth(payload.initData, tokens)
        if not ok:
            status = 401
            reason = reason_resp
            return JSONResponse(
                {"ok": False, "error": "invalid_init_data", "reason": reason_resp},
                status_code=401,
            )

        user_id = str(user.get("id"))
        username = user.get("username")
        first_name = user.get("first_name")
        last_name = user.get("last_name")
        display_name = (
            username or first_name or last_name or f"Player {user_id[-4:]}"
        )
        if len(display_name) > 24:
            display_name = display_name[:23] + "…"

        db = app.state.db
        now_dt = datetime.utcnow()
        last = LAST_SCORES.get(user_id)
        if last and (now_dt - last).total_seconds() < RATE_LIMIT_SECONDS:
            reason = "rate_limited"
            async with db.execute(
                "SELECT best_score FROM players WHERE id = ?", (user_id,)
            ) as cur:
                row = await cur.fetchone()
            best = row[0] if row else 0
            me = {
                "id": user_id,
                "display_name": display_name,
                "username": username,
                "best_score": best,
            }
            headers = {"Retry-After": str(RATE_LIMIT_SECONDS)}
            return JSONResponse(
                status_code=200,
                content={"ok": True, "rate_limited": True, "me": me},
                headers=headers,
            )
        LAST_SCORES[user_id] = now_dt

        async with db.execute(
            "SELECT best_score FROM players WHERE id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        prev_best = row[0] if row else 0

        best = prev_best
        if row is None or payload.score > prev_best:
            now = now_dt.isoformat()
            query = (
                "INSERT INTO players (id, username, display_name, best_score, updated_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET "
                "username=excluded.username, display_name=excluded.display_name, "
                "best_score=excluded.best_score, updated_at=excluded.updated_at"
            )
            params = (user_id, username, display_name, payload.score, now)
            await db.execute(query, params)
            await db.commit()
            best = payload.score

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
        logger.info(
            "%s %s user=%s reason=%s init_len=%s",
            ip,
            status,
            user_id,
            reason,
            init_len,
        )


if DEBUG:
    @app.get("/auth_check")
    async def auth_check(initData: str, echo: str | None = None):
        tokens = get_tokens()
        ok, user, reason, data_check_string = check_telegram_auth(initData, tokens)
        if echo == "1":
            return {
                "data_check_string": data_check_string,
                "note": "for debugging only",
            }
        if not ok:
            return JSONResponse(status_code=401, content={"ok": False, "error": reason})
        user_id = str(user.get("id"))
        username = user.get("username")
        first_name = user.get("first_name")
        last_name = user.get("last_name")
        display_name = username or first_name or last_name or f"Player {user_id[-4:]}"
        resp = {"ok": True, "user": user, "display_name": display_name}
        return resp


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


@app.get("/scoreboard")
async def get_scoreboard():
    db = app.state.db
    async with db.execute(
        "SELECT display_name, username, best_score FROM players ORDER BY best_score DESC LIMIT 100"
    ) as cur:
        rows = await cur.fetchall()

    items = [
        {"display_name": d, "username": u, "best_score": s} for d, u, s in rows
    ]
    return {"items": items}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=PORT)

