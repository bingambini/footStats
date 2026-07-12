import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from supabase import create_client, Client

app = FastAPI()

url: str = os.environ.get("SUPABASE_URL", "")
key: str = os.environ.get("SUPABASE_ANON_KEY", "")
supabase: Client = create_client(url, key) if (url and key) else None

class PlayerInput(BaseModel):
    shirt_number: Optional[int] = None
    first_name: str
    last_name: str
    primary_position: str
    birth_date: Optional[str] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None

@app.post("/api/import_players")
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