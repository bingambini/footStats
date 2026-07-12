import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from supabase import create_client, Client

app = FastAPI()

# ინიციალიზაცია
url: str = os.environ.get("SUPABASE_URL", "")
key: str = os.environ.get("SUPABASE_ANON_KEY", "")

if not url or not key:
    # ლოკალური დეველოპმენტისთვის ან თუ ცვლადები ჯერ არ ჩაჯდა
    url = "YOUR_SUPABASE_URL"
    key = "YOUR_SUPABASE_ANON_KEY"

supabase: Client = create_client(url, key)

# Pydantic მოდელი მონაცემების ვალიდაციისთვის
class PlayerInput(BaseModel):
    shirt_number: Optional[int] = None
    first_name: str
    last_name: str
    primary_position: str
    birth_date: Optional[str] = None # YYYY-MM-DD ფორმატში
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None

@app.get("/api/status")
def get_status():
    return {
        "status": "online",
        "engine": "Python + FastAPI on Vercel",
        "database": "Supabase PostgreSQL Linked"
    }

@app.post("/api/import-players")
def import_players(players: List[PlayerInput]):
    inserted_count = 0
    errors = []

    for p in players:
        # ვამზადებთ მონაცემებს Supabase-ის ცხრილისთვის
        player_data = {
            "first_name": p.first_name,
            "last_name": p.last_name,
            "primary_position": p.primary_position,
            "birth_date": p.birth_date,
            "height_cm": p.height_cm,
            "weight_kg": p.weight_kg
        }
        
        try:
            # ვწერთ `players` ცხრილში
            response = supabase.table("players").insert(player_data).execute()
            if response.data:
                inserted_count += 1
        except Exception as e:
            errors.append(f"შეცდომა მოთამაშეზე {p.first_name} {p.last_name}: {str(e)}")

    if errors and inserted_count == 0:
        raise HTTPException(status_code=400, detail={"message": "იმპორტი ჩაიშალა", "errors": errors})

    return {
        "message": "იმპორტი წარმატებით დასრულდა",
        "inserted_players": inserted_count,
        "errors_encountered": errors
    }