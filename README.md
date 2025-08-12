# Bugman Leaderboard

FastAPI server providing a global leaderboard for the Bugman Telegram mini game.

## Run locally

```
pip install -r requirements.txt
# create .env with your bot token(s)
cat > .env <<'EOF'
# one token
BOT_TOKEN=123:ABC
# or multiple (comma-separated)
BOT_TOKENS=123:ABC,456:DEF
PORT=8080
DEBUG=true
EOF
uvicorn server:app --host 0.0.0.0 --port $PORT --reload
```

Для успешной проверки подписи `BOT_TOKEN`/`BOT_TOKENS` должны соответствовать тому
боту, из которого открывается Mini App.

## Deploy on Render

The repository already contains a `Procfile` compatible with Render:

```
web: uvicorn server:app --host 0.0.0.0 --port $PORT
```

Create a new Web Service on Render pointing to the repo. After deployment the
server will be reachable at the URL provided by Render, e.g.
`https://bugman-bot.onrender.com`.

## Troubleshooting

When `DEBUG=true` in your `.env`, you can verify raw init data:

```bash
curl -X POST http://localhost:8080/debug/verify \
  -H 'Content-Type: application/json' \
  -d '{"initData":"<real-init-data>"}'
```

Example error responses from `/score`:

- Missing fields: `{"ok":false,"error":"bad_request","reason":"missing initData or score"}`
- Invalid init data: `{"ok":false,"error":"invalid_init_data"}`
- Too many requests: `{"ok":false,"error":"too_many_requests","reason":"rate_limited"}`

