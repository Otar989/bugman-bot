from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
conn = sqlite3.connect("scores.db", check_same_thread=False)
conn.execute(
    "CREATE TABLE IF NOT EXISTS scores (user_id INTEGER PRIMARY KEY, username TEXT, score INTEGER)"
)


class Score(BaseModel):
    userId: int
    username: str
    score: int


@app.post("/score")
def post_score(s: Score):
    cur = conn.execute("SELECT score FROM scores WHERE user_id = ?", (s.userId,))
    row = cur.fetchone()
    if not row or s.score > row[0]:
        conn.execute(
            "REPLACE INTO scores (user_id, username, score) VALUES (?, ?, ?)",
            (s.userId, s.username, s.score),
        )
        conn.commit()
    return {"status": "ok"}


@app.get("/leaderboard")
def get_leaderboard(limit: int = 10):
    cur = conn.execute(
        "SELECT username, score FROM scores ORDER BY score DESC LIMIT ?", (limit,)
    )
    return [{"username": u, "score": sc} for u, sc in cur.fetchall()]
