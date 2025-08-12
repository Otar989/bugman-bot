"""FastAPI server providing a global leaderboard for Bugman."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime
from os import getenv

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


def check_telegram_auth_raw(init_data: str, tokens: list[str]) -> Tuple[bool, Optional[dict], str]:
    try:
        # 1) Разбираем "сырые" пары без URL‑декодирования
        #    НЕЛЬЗЯ применять unquote_plus до расчёта подписи.
        raw_pairs = init_data.split("&")
        recv_hash = None
        kv_raw = []
        for p in raw_pairs:
            if not p:
                continue
            if p.startswith("hash="):
                recv_hash = p.split("=", 1)[1]
            else:
                kv_raw.append(p)  # ключ=значение как есть

        if not recv_hash:
            return False, None, "no_hash"

        # 2) Отсортировать по ключу (часть до '=') лексикографически
        kv_raw.sort(key=lambda s: s.split("=", 1)[0])

        # 3) Собрать data_check_string из "сырых" пар через \n
        data_check_string = "\n".join(kv_raw)

        # 4) user нужно распарсить уже ПОСЛЕ вычисления подписи
        #    но для самого хеша используем сырую строку; тут вытащим 'user=' ещё раз
        user_raw = next((s.split("=",1)[1] for s in kv_raw if s.split("=",1)[0] == "user"), None)

        # 5) Пробуем каждый токен
        for t in tokens:
            secret_key = hmac.new(b"WebAppData", t.encode(), hashlib.sha256).digest()
            calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
            if hmac.compare_digest(calc_hash, recv_hash):
                # подпись ок — теперь можно безопасно декодить user
                user = json.loads(bytes(user_raw, "utf-8").decode("utf-8")) if user_raw else None
                return True, user, "ok"
        return False, None, "hash_mismatch"
    except Exception:
        return False, None, "exception"


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

        tokens = []
        env_tokens = os.getenv("BOT_TOKENS")
        if env_tokens:
            tokens = [t.strip() for t in env_tokens.split(",") if t.strip()]
        else:
            t = os.getenv("BOT_TOKEN")
            if t:
                tokens = [t]

        ok, user, reason_resp = check_telegram_auth_raw(payload.initData, tokens)
        if not ok or not user or "id" not in user:
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
        logger.info(
            "%s %s user=%s reason=%s init_len=%s",
            ip,
            status,
            user_id,
            reason,
            init_len,
        )


if DEBUG:
    @app.post("/debug/verify")
    async def debug_verify(payload: InitDataIn):
        tokens = []
        env_tokens = os.getenv("BOT_TOKENS")
        if env_tokens:
            tokens = [t.strip() for t in env_tokens.split(",") if t.strip()]
        else:
            t = os.getenv("BOT_TOKEN")
            if t:
                tokens = [t]

        ok, user, reason = check_telegram_auth_raw(payload.initData, tokens)
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=PORT)

