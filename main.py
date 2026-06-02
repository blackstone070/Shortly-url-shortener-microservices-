import httpx
import redis
import models
import os 
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, AnyHttpUrl
from sqlalchemy.orm import Session
from database import engine, SessionLocal
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from user_agents import parse

# 1. Initialize Database Tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# 2. Connect to Redis - supports both Railway (REDIS_URL) and Docker (REDIS_HOST)
REDIS_URL = os.getenv("REDIS_URL")
if REDIS_URL:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=5, socket_timeout=5)
else:
    redis_client = redis.Redis(host=os.getenv("REDIS_HOST", "redis"), port=int(os.getenv("REDIS_PORT", 6379)), decode_responses=True)

# Test Redis connection on startup
try:
    redis_client.ping()
    print("✅ Redis connected successfully")
except Exception as e:
    print(f"❌ Redis connection failed: {e}")

# --- BACKGROUND TASK FOR ANALYTICS ---
async def track_click_metadata(short_code: str, ip: str, user_agent: str):
    ua = parse(user_agent)
    device = "Mobile" if ua.is_mobile else "Tablet" if ua.is_tablet else "Desktop"
    redis_client.hincrby(f"stats:{short_code}:devices", device, 1)

    # Fix 2: Always call ipinfo - never skip based on IP range (Railway uses 10.x.x.x internally)
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(f"https://ipinfo.io/{ip}/json", timeout=5)
            data = res.json()
            country = data.get("country", "Unknown")
            state = data.get("region", "Unknown State")
    except:
        country, state = "Other", "Other"

    redis_client.hincrby(f"stats:{short_code}:countries", country, 1)
    redis_client.hincrby(f"stats:{short_code}:states", state, 1)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class URLRequest(BaseModel):
    target_url: AnyHttpUrl

@app.get("/")
async def read_index():
    return FileResponse('static/index.html')

@app.post("/shorten")
async def shorten(request: Request, payload: URLRequest, db: Session = Depends(get_db)):
    new_url = models.URLModel(original_url=str(payload.target_url), short_code="TEMP")
    db.add(new_url)
    db.commit()
    db.refresh(new_url)

    async with httpx.AsyncClient() as client:
        try:
            ENCODER_BASE_URL = os.getenv("ENCODER_URL", "http://encoder:18080/encode/")
            service_url = f"{ENCODER_BASE_URL}{new_url.id}"
            response = await client.get(service_url)
            response.raise_for_status()
            short_code = response.text.strip()
        except Exception as e:
            db.delete(new_url)
            db.commit()
            raise HTTPException(status_code=500, detail=f"C++ Engine unreachable: {e}")

    new_url.short_code = short_code
    db.commit()

    redis_client.set(short_code, str(payload.target_url), ex=3600)

    host_header = request.headers.get("host", "localhost:8000")
    protocol = "https" if "localhost" not in host_header else "http"

    return {"short_url": f"{protocol}://{host_header}/{short_code}", "id": new_url.id}

@app.get("/stats/{short_code}")
async def get_stats(short_code: str):
    total = redis_client.get(f"clicks:{short_code}:total")
    countries = redis_client.hgetall(f"stats:{short_code}:countries")
    states = redis_client.hgetall(f"stats:{short_code}:states")
    devices = redis_client.hgetall(f"stats:{short_code}:devices")

    return {
        "short_code": short_code,
        "total_clicks": int(total) if total else 0,
        "analytics": {
            "countries": countries,
            "states": states,
            "devices": devices
        }
    }

@app.get("/{short_code}")
async def redirect(short_code: str, request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    cached_url = redis_client.get(short_code)

    if not cached_url:
        db_url = db.query(models.URLModel).filter(models.URLModel.short_code == short_code).first()
        if not db_url:
            raise HTTPException(status_code=404, detail="Short link not found")
        cached_url = db_url.original_url
        redis_client.set(short_code, cached_url, ex=3600)

    # Fix 3: Get real client IP from X-Forwarded-For header (Railway proxy)
    forwarded_for = request.headers.get("X-Forwarded-For")
    user_ip = forwarded_for.split(",")[0].strip() if forwarded_for else request.client.host

    user_agent = request.headers.get("user-agent", "")
    background_tasks.add_task(track_click_metadata, short_code, user_ip, user_agent)
    redis_client.incr(f"clicks:{short_code}:total")

    return RedirectResponse(url=cached_url, status_code=302)
