import os
import logging
import traceback
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
from supabase import create_client, Client

# 1. ლოგერის კონფიგურაცია Vercel-ის კონსოლისთვის
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("football-debug")

app = FastAPI()

# 2. 🔍 დებაგერ მიდლვეარი (Middleware)
# ეს ფუნქცია დაიჭერს აბსოლუტურად ყველა რექვესტს და დაბეჭდავს მისამართებს
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f" 🚀 [INBOUND] მეთოდი: {request.method} | მისამართი: {request.url.path} | სრული URL: {request.url}")
    logger.info(f" 📋 [HEADERS] {dict(request.headers)}")
    
    try:
        response = await call_next(request)
        logger.info(f" ✅ [OUTBOUND] სტატუსი: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f" ❌ [CRITICAL ERROR IN MIDDLEWARE]: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"error": "სერვერის შიდა შეცდომა", "details": str(e), "path": request.url.path}
        )

# 3. 🛑 გლობალური შეცდომების დამჭერი (Global Exception Handler)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f" 💥 [CRASH] მისამართზე {request.url.path} მოხდა შეცდომა: {str(exc)}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": str(exc),
            "traceback": traceback.format_exc().splitlines()
        }
    )

# --- Supabase კონფიგურაცია ---
url: str = os.environ.get("SUPABASE_URL", "")
key: str = os.environ.get("SUPABASE_ANON_KEY", "")
supabase: Client = None

if url and key:
    supabase = create_client(url, key)
else:
    logger.warning(" ⚠️ [WARN] Supabase-ის გარემოს ცვლადები (Variables) ვერ მოიძებნა!")

class PlayerInput(BaseModel):
    shirt_number: Optional[int] = None
    first_name: str
    last_name: str
    primary_position: str
    birth_date: Optional[str] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None

# --- მარშრუტები (Routes) ყველა შესაძლო ვარიაციით ---

@app.get("/")
@app.get("/api")
def read_root(request: Request):
    logger.info(f" 🎯 ჰიტი Root ენდპოინტზე! მოთხოვნილი გზა: {request.url.path}")
    return {
        "message": "Welcome to Football Analytics API Engine!",
        "current_path": request.url.path,
        "supabase_connected": supabase is not None
    }

@app.get("/status")
@app.get("/api/status")
def get_status(request: Request):
    logger.info(f" 🎯 ჰიტი Status ენდპოინტზე! მოთხოვნილი გზა: {request.url.path}")
    return {
        "status": "online",
        "engine": "Python + FastAPI on Vercel",
        "database_connected": supabase is not None,
        "path_resolved": request.url.path
    }

@app.post("/import-players")
@app.post("/api/import-players")
def import_players(players: List[PlayerInput]):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase კავშირი არ არის აქტიური.")
        
    inserted_count = 0
    errors = []
    for p in players:
        player_data = {
            "first_name": p.first_name,
            "last_name": p.last_name,
            "primary_position": p.primary_position,
            "birth_date": p.birth_date,
            "height_cm": p.height_cm,
            "weight_kg": p.weight_kg
        }
        try:
            response = supabase.table("players").insert(player_data).execute()
            if response.data:
                inserted_count += 1
        except Exception as e:
            errors.append(f"შეცდომა: {p.first_name} - {str(e)}")

    return {"inserted_players": inserted_count, "errors": errors}