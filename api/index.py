import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from supabase import create_client, Client

app = FastAPI()

# ინიციალიზაცია
url: str = os.environ.get("SUPABASE_URL", "")
key: str = os.environ.get("SUPABASE_ANON_KEY", "")

# ბაზასთან კავშირი (მხოლოდ თუ გასაღებები არსებობს)
supabase: Client = None
if url and key:
    supabase = create_client(url, key)

class PlayerInput(BaseModel):
    shirt_number: Optional[int] = None
    first_name: str
    last_name: str
    primary_position: str
    birth_date: Optional[str] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None

# მთავარი გვერდისთვის (რომ საიტზე შესვლისას 404 არ დაგვხვდეს)
@app.get("/")
@app.get("/api")
def read_root():
    return {
        "message": "Welcome to Football Analytics API Engine!",
        "endpoints": {
            "status": "/api/status",
            "import_players": "/api/import-players"
        }
    }

# სტატუსის შემოწმება (მულტი-მარშრუტით)
@app.get("/status")
@app.get("/api/status")
def get_status():
    return {
        "status": "online",
        "engine": "Python + FastAPI on Vercel",
        "database_connected": supabase is not None
    }

# მოთამაშეების იმპორტი
@app.post("/import-players")
@app.post("/api/import-players")
def import_players(players: List[PlayerInput]):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase კავშირი არ არის კონფიგურირებული Vercel-ში")
        
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
            errors.append(f"შეცდომა: {p.first_name} {p.last_name} - {str(e)}")

    return {
        "message": "იმპორტის პროცესი დასრულდა",
        "inserted_players": inserted_count,
        "errors": errors
    }