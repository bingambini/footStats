import os
from fastapi import FastAPI
from supabase import create_client, Client

app = FastAPI()

url: str = os.environ.get("SUPABASE_URL", "")
key: str = os.environ.get("SUPABASE_ANON_KEY", "")
supabase: Client = create_client(url, key) if (url and key) else None

@app.get("/api/status")
def get_status():
    return {
        "status": "online",
        "architecture": "Vercel Native Multi-File Serverless",
        "database_connected": supabase is not None
    }