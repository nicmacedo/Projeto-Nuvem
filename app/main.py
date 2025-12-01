import json
import asyncio
import os
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Servindo arquivos estáticos
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Lista de conexões WebSocket
connections: List[WebSocket] = []

# Mensagens em memória (reinicia ao escalar/instância reiniciar)
messages = []

pid = os.getpid()

async def broadcast_local(message: dict):
    """Envia mensagem para todos os WebSockets conectados nesta instância"""
    data = json.dumps(message)
    to_remove = []
    for ws in connections:
        try:
            await ws.send_text(data)
        except:
            to_remove.append(ws)

    for ws in to_remove:
        if ws in connections:
            connections.remove(ws)

@app.get("/", response_class=HTMLResponse)
async def get_index():
    return FileResponse("app/static/index.html")

@app.get("/dashboard")
async def dashboard():
    return FileResponse("app/static/dashboard.html")

@app.get("/info")
async def info():
    return {
        "pid": pid,
        "connections": len(connections),
        "messages_saved": len(messages)
    }

@app.get("/api/messages")
async def get_messages(limit: int = 100):
    """Retorna as mensagens armazenadas em RAM"""
    return messages[-limit:]

@app.post("/api/messages")
async def post_message(payload: dict):
    """Recebe mensagem via REST e envia aos WebSockets"""
    author = payload.get("author")
    text = payload.get("text")

    if not author or not text:
        raise HTTPException(status_code=400, detail="author and text required")

    msg = {
        "author": author,
        "text": text,
        "created_at": asyncio.get_event_loop().time()
    }

    messages.append(msg)
    await broadcast_local(msg)

    return msg

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connections.append(ws)

    # Mensagem inicial
    await ws.send_text(json.dumps({"system": f"connected to instance {pid}", "pid": pid}))

    try:
        while True:
            data = await ws.receive_text()
            try:
                obj = json.loads(data)
                author = obj.get("author")
                text = obj.get("text")
            except:
                await ws.send_text(json.dumps({"error": "invalid json"}))
                continue

            msg = {
                "author": author,
                "text": text,
                "created_at": asyncio.get_event_loop().time()
            }

            messages.append(msg)
            await broadcast_local(msg)

    except WebSocketDisconnect:
        if ws in connections:
            connections.remove(ws)
