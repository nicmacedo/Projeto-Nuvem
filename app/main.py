import os
import json
import asyncio
import signal
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import asyncpg
import aioredis

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Configs
DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")
REDIS_CHANNEL = "chat_messages"

# Simple state
connections: List[WebSocket] = []
pid = os.getpid()

# Optional DB pool
db_pool = None

async def init_db_pool():
    global db_pool
    if DATABASE_URL:
        db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
        # ensure table
        async with db_pool.acquire() as conn:
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                author TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
            );
            """)

# Optional Redis client and subscriber loop
redis = None
async def get_redis():
    global redis
    if not REDIS_URL:
        return None
    if redis is None:
        redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    return redis

async def publish_message(msg: dict):
    r = await get_redis()
    if r:
        await r.publish(REDIS_CHANNEL, json.dumps(msg))

async def redis_subscriber_loop():
    r = await get_redis()
    if not r:
        return
    pubsub = r.pubsub()
    await pubsub.subscribe(REDIS_CHANNEL)
    async for m in pubsub.listen():
        if m is None:
            continue
        if m.get("type") == "message":
            try:
                payload = json.loads(m.get("data"))
                # broadcast to local connections
                await broadcast_local(payload)
            except Exception:
                continue

# helper to broadcast to connected websockets in this instance
async def broadcast_local(message: dict):
    data = json.dumps(message)
    to_remove = []
    for ws in list(connections):
        try:
            await ws.send_text(data)
        except Exception:
            to_remove.append(ws)
    for r in to_remove:
        if r in connections:
            connections.remove(r)

@app.on_event("startup")
async def startup():
    # init db if provided
    await init_db_pool()
    # start redis subscriber if REDIS_URL provided
    if REDIS_URL:
        asyncio.create_task(redis_subscriber_loop())

@app.on_event("shutdown")
async def shutdown():
    global db_pool, redis
    if db_pool:
        await db_pool.close()
    if redis:
        await redis.close()

# Serve frontend index
@app.get("/", response_class=HTMLResponse)
async def get_index():
    return FileResponse("app/static/index.html")

# Dashboard
@app.get("/dashboard")
async def dashboard():
    return FileResponse("app/static/dashboard.html")

# info endpoint to show instance data
@app.get("/info")
async def info():
    return {"pid": pid, "connections": len(connections)}

# messages history
@app.get("/api/messages")
async def get_messages(limit: int = 100):
    if db_pool:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, author, text, created_at FROM messages ORDER BY created_at DESC LIMIT $1", limit)
            rows = list(reversed(rows))
            return [dict(r) for r in rows]
    else:
        return []

# post message via REST (also publishes to redis)
@app.post("/api/messages")
async def post_message(payload: dict):
    author = payload.get("author")
    text = payload.get("text")
    if not author or not text:
        raise HTTPException(status_code=400, detail="author and text required")
    msg = {"author": author, "text": text, "created_at": asyncio.get_event_loop().time()}
    # persist if db
    if db_pool:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("INSERT INTO messages(author, text) VALUES($1, $2) RETURNING id, created_at", author, text)
            msg["id"] = row["id"]
            msg["created_at"] = row["created_at"].isoformat()
    # publish to redis for other instances
    await publish_message(msg)
    # also broadcast locally
    await broadcast_local(msg)
    return msg

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connections.append(ws)
    # send welcome with instance info
    await ws.send_text(json.dumps({"system": f"connected to instance {pid}", "pid": pid}))
    try:
        while True:
            data = await ws.receive_text()
            try:
                obj = json.loads(data)
                author = obj.get("author")
                text = obj.get("text")
            except Exception:
                await ws.send_text(json.dumps({"error":"invalid json"}))
                continue
            # persist if possible
            if db_pool:
                async with db_pool.acquire() as conn:
                    row = await conn.fetchrow("INSERT INTO messages(author, text) VALUES($1, $2) RETURNING id, created_at", author, text)
                    msg = {"id": row["id"], "author": author, "text": text, "created_at": row["created_at"].isoformat()}
            else:
                msg = {"author": author, "text": text, "created_at": asyncio.get_event_loop().time()}
            # publish to redis so other instances broadcast
            await publish_message(msg)
            # broadcast locally (so local clients see quickly)
            await broadcast_local(msg)
    except WebSocketDisconnect:
        if ws in connections:
            connections.remove(ws)
    except Exception:
        if ws in connections:
            connections.remove(ws)
