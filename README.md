# Bugman Leaderboard

FastAPI server providing a global leaderboard for the Bugman Telegram mini game.

## Run locally

```
pip install -r requirements.txt
echo -e "BOT_TOKEN=<твой токен>\nPORT=8080" > .env
uvicorn server:app --host 0.0.0.0 --port $PORT --reload
```

## Deploy on Render

The repository already contains a `Procfile` compatible with Render:

```
web: uvicorn server:app --host 0.0.0.0 --port $PORT
```

Create a new Web Service on Render pointing to the repo. After deployment the
server will be reachable at the URL provided by Render, e.g.
`https://bugman-bot.onrender.com`.

