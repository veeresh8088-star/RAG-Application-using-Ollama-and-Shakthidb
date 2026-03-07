from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy import create_engine, Column, Integer, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func
import requests
import os
import tempfile
import PyPDF2
from gtts import gTTS
from uuid import uuid4
import json
import time
import asyncio
import psutil
from datetime import datetime, timezone
from collections import deque
import threading

app = FastAPI(title="AI Chat API", version="2.0.0")

# =========================
# DATABASE CONFIG
# =========================

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise Exception("DATABASE_URL not found in environment variables")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class ChatHistory(Base):
    __tablename__ = "chat_history"
    id           = Column(Integer, primary_key=True, index=True)
    user_message = Column(Text)
    bot_response = Column(Text)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())


Base.metadata.create_all(bind=engine)

# =========================
# CORS
# =========================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL      = "tinyllama"  # faster than phi3:mini

# =========================
# OBSERVABILITY — IN-MEMORY METRICS
# =========================

class Metrics:
    def __init__(self):
        self.lock              = threading.Lock()
        self.total_requests    = 0
        self.successful        = 0
        self.failed            = 0
        self.pdf_requests      = 0
        self.chat_requests     = 0
        self.tts_requests      = 0
        self.total_latency_ms  = 0.0
        self.recent_latencies  = deque(maxlen=50)   # last 50 request latencies
        self.recent_errors     = deque(maxlen=20)   # last 20 errors
        self.start_time        = time.time()

    def record_request(self, req_type: str, latency_ms: float, success: bool, error: str = None):
        with self.lock:
            self.total_requests   += 1
            self.total_latency_ms += latency_ms
            self.recent_latencies.append(latency_ms)

            if success:
                self.successful += 1
            else:
                self.failed += 1
                if error:
                    self.recent_errors.append({
                        "time": datetime.now(timezone.utc).isoformat(),
                        "type": req_type,
                        "error": error
                    })

            if req_type == "pdf":
                self.pdf_requests += 1
            elif req_type == "chat":
                self.chat_requests += 1
            elif req_type == "tts":
                self.tts_requests += 1

    def snapshot(self) -> dict:
        with self.lock:
            uptime_s   = time.time() - self.start_time
            avg_lat    = (self.total_latency_ms / self.total_requests) if self.total_requests else 0
            p95_lat    = sorted(self.recent_latencies)[int(len(self.recent_latencies) * 0.95)] if self.recent_latencies else 0
            success_rt = (self.successful / self.total_requests * 100) if self.total_requests else 100

            cpu    = psutil.cpu_percent(interval=None)
            mem    = psutil.virtual_memory()
            disk   = psutil.disk_usage("/")

            return {
                "uptime_seconds":      round(uptime_s),
                "uptime_human":        _fmt_uptime(uptime_s),
                "total_requests":      self.total_requests,
                "successful":          self.successful,
                "failed":              self.failed,
                "success_rate_pct":    round(success_rt, 2),
                "chat_requests":       self.chat_requests,
                "pdf_requests":        self.pdf_requests,
                "tts_requests":        self.tts_requests,
                "avg_latency_ms":      round(avg_lat, 1),
                "p95_latency_ms":      round(p95_lat, 1),
                "cpu_percent":         cpu,
                "memory_used_pct":     mem.percent,
                "memory_used_mb":      round(mem.used / 1024 / 1024),
                "memory_total_mb":     round(mem.total / 1024 / 1024),
                "disk_used_pct":       round(disk.used / disk.total * 100, 1),
                "disk_free_gb":        round(disk.free / 1024 / 1024 / 1024, 2),
                "recent_errors":       list(self.recent_errors),
                "timestamp":           datetime.now(timezone.utc).isoformat(),
            }


def _fmt_uptime(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}h {m}m {s}s"


metrics = Metrics()

# SSE subscribers for real-time history push
history_subscribers: list[asyncio.Queue] = []

# =========================
# REAL-TIME HISTORY HELPER
# =========================

def push_history_event(chat_id: int, user_message: str, bot_response: str, created_at: str):
    """Broadcast a new chat entry to all SSE subscribers."""
    payload = json.dumps({
        "id":           chat_id,
        "user_message": user_message,
        "bot_response": bot_response,
        "created_at":   created_at,
    })
    dead = []
    for q in history_subscribers:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        history_subscribers.remove(q)


# =========================
# HEALTH CHECK
# =========================

@app.get("/health")
def health():
    """Basic liveness probe."""
    ollama_ok = False
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        ollama_ok = r.status_code == 200
    except Exception:
        pass

    db_ok = False
    try:
        db = SessionLocal()
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db.close()
        db_ok = True
    except Exception:
        pass

    status = "healthy" if (ollama_ok and db_ok) else "degraded"

    return {
        "status":     status,
        "ollama":     "up" if ollama_ok else "down",
        "database":   "up" if db_ok else "down",
        "model":      MODEL,
        "timestamp":  datetime.now(timezone.utc).isoformat(),
    }


# =========================
# OBSERVABILITY — METRICS
# =========================

@app.get("/metrics")
def get_metrics():
    """Full observability snapshot — CPU, memory, request stats, latency."""
    return metrics.snapshot()


@app.get("/metrics/errors")
def get_recent_errors():
    """Last 20 errors with timestamps."""
    return {"errors": list(metrics.recent_errors)}


# =========================
# CHAT HISTORY — REST
# =========================

@app.get("/chat-history")
def get_chat_history(limit: int = 50):
    db = SessionLocal()
    chats = db.query(ChatHistory).order_by(ChatHistory.id.desc()).limit(limit).all()
    db.close()
    return [
        {
            "id":           c.id,
            "user_message": c.user_message,
            "bot_response": c.bot_response,
            "created_at":   c.created_at.isoformat() if c.created_at else "",
        }
        for c in chats
    ]


# =========================
# REAL-TIME HISTORY — SSE
# =========================

@app.get("/chat-history/stream")
async def stream_history(request: Request):
    """
    Server-Sent Events endpoint.
    Frontend connects once; new chat entries are pushed instantly.

    Frontend usage:
        const es = new EventSource('/api/chat-history/stream');
        es.onmessage = (e) => {
            const chat = JSON.parse(e.data);
            // prepend to your history list
        };
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=50)
    history_subscribers.append(queue)

    async def event_generator():
        # Send a heartbeat immediately so the connection stays alive
        yield "data: {\"type\":\"connected\"}\n\n"
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=20)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat every 20s to keep connection alive
                    yield "data: {\"type\":\"heartbeat\"}\n\n"
        finally:
            if queue in history_subscribers:
                history_subscribers.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


# =========================
# PDF HELPER
# =========================

def extract_pdf_text(file_path: str, max_chars: int = 1800) -> str:
    """Fast single-pass PDF extraction capped for tinyllama context."""
    try:
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            full_text = ""
            for page in reader.pages:
                full_text += (page.extract_text() or "") + "\n"
                if len(full_text) >= max_chars:
                    break
        return full_text.strip()[:max_chars]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF error: {str(e)}")


# =========================
# OLLAMA STREAMING
# =========================

def stream_ollama(prompt: str, user_message: str, req_type: str, num_predict: int = 250):
    full_response = ""
    t_start = time.time()
    success = True
    err_msg = None

    try:
        with requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "num_predict":    num_predict,
                    "temperature":    0.2,
                    "top_p":          0.85,
                    "repeat_penalty": 1.1,
                }
            },
            stream=True,
            timeout=120
        ) as r:
            for line in r.iter_lines():
                if line:
                    try:
                        data = json.loads(line.decode("utf-8"))
                        if "response" in data:
                            chunk = data["response"]
                            full_response += chunk
                            yield chunk
                        if data.get("done"):
                            break
                    except Exception:
                        continue

    except Exception as e:
        err_msg = str(e)
        success = False
        yield f"\nError: {err_msg}"

    finally:
        latency_ms = (time.time() - t_start) * 1000
        metrics.record_request(req_type, latency_ms, success, err_msg)

    # Save to DB + push SSE event
    try:
        db = SessionLocal()
        chat = ChatHistory(user_message=user_message, bot_response=full_response)
        db.add(chat)
        db.commit()
        db.refresh(chat)
        created_str = chat.created_at.isoformat() if chat.created_at else datetime.now(timezone.utc).isoformat()
        push_history_event(chat.id, user_message, full_response, created_str)
        db.close()
    except Exception as e:
        print("DB Error:", e)


# =========================
# CHAT STREAM ENDPOINT
# =========================

@app.post("/chat-stream")
async def chat_stream(
    message: str = Form(...),
    file: UploadFile | None = File(None)
):
    # ── PDF PATH ──
    if file:
        contents = await file.read()
        if len(contents) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large (max 10MB)")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(contents)
            file_path = tmp.name

        try:
            text = extract_pdf_text(file_path, max_chars=1800)
        finally:
            os.remove(file_path)

        user_message = message or "Summarize this document"
        prompt = f"""Summarize the key points of this document in clear bullet points. Be concise.

Document:
{text}

Summary:"""

        return StreamingResponse(
            stream_ollama(prompt, user_message, "pdf", num_predict=300),
            media_type="text/plain"
        )

    # ── NORMAL CHAT PATH ──
    prompt = f"Answer briefly and clearly.\n\nQuestion: {message}\n\nAnswer:"
    return StreamingResponse(
        stream_ollama(prompt, message, "chat", num_predict=200),
        media_type="text/plain"
    )


# =========================
# TEXT TO SPEECH
# =========================

@app.post("/text-to-speech")
async def text_to_speech(text: str = Form(...)):
    t_start = time.time()
    try:
        filename = f"tts_{uuid4().hex}.mp3"
        filepath = os.path.join(tempfile.gettempdir(), filename)
        gTTS(text=text).save(filepath)
        metrics.record_request("tts", (time.time() - t_start) * 1000, True)
        return FileResponse(filepath, media_type="audio/mpeg", filename="response.mp3")
    except Exception as e:
        metrics.record_request("tts", (time.time() - t_start) * 1000, False, str(e))
        raise HTTPException(status_code=500, detail=str(e))
