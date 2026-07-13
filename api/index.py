import asyncio
import json
import os
import csv
import io
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field
from loguru import logger

try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False

app = FastAPI(title="FootStats API")

# ==========================================
# Logger Setup
# ==========================================
logger.remove()
logger.add(lambda msg: print(msg.strip()), format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan> - <level>{message}</level>")

# ==========================================
# Supabase Client
# ==========================================
_supabase_client = None

def get_supabase():
    global _supabase_client
    if _supabase_client is None:
        try:
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_KEY")
            if url and key:
                _supabase_client = create_client(url, key)
                logger.info("✅ Supabase კლიენტი ინიციალიზდა")
        except Exception as e:
            logger.error(f"❌ Supabase შეცდომა: {e}")
    return _supabase_client

# ==========================================
# In-Memory Storage
# ==========================================
matches_storage: List[Dict] = []

# ==========================================
# CSV Parser - კოეფიციენტების გარეშე
# ==========================================
def parse_csv_no_odds(csv_text: str) -> List[Dict]:
    """ამოიღებს მხოლოდ ძირითად მონაცემებს, კოეფიციენტების გარეშე"""
    try:
        reader = csv.DictReader(io.StringIO(csv_text))
        matches = []
        
        for row in reader:
            # ვტოვებთ მხოლოდ საჭირო სვეტებს
            match_data = {
                "division": row.get("Div", "").strip(),
                "match_date": row.get("Date", "").strip(),
                "match_time": row.get("Time", "").strip(),
                "home_team": row.get("HomeTeam", "").strip(),
                "away_team": row.get("AwayTeam", "").strip(),
                "referee": row.get("Referee", "").strip(),
                "full_time_home_goals": int(row.get("FTHG", 0)) if row.get("FTHG") else 0,
                "full_time_away_goals": int(row.get("FTAG", 0)) if row.get("FTAG") else 0,
                "full_time_result": row.get("FTR", "").strip(),
                "half_time_home_goals": int(row.get("HTHG", 0)) if row.get("HTHG") else 0,
                "half_time_away_goals": int(row.get("HTAG", 0)) if row.get("HTAG") else 0,
                "half_time_result": row.get("HTR", "").strip(),
                "home_shots": int(row.get("HS", 0)) if row.get("HS") else 0,
                "away_shots": int(row.get("AS", 0)) if row.get("AS") else 0,
                "home_shots_on_target": int(row.get("HST", 0)) if row.get("HST") else 0,
                "away_shots_on_target": int(row.get("AST", 0)) if row.get("AST") else 0,
                "home_fouls": int(row.get("HF", 0)) if row.get("HF") else 0,
                "away_fouls": int(row.get("AF", 0)) if row.get("AF") else 0,
                "home_corners": int(row.get("HC", 0)) if row.get("HC") else 0,
                "away_corners": int(row.get("AC", 0)) if row.get("AC") else 0,
                "home_yellow_cards": int(row.get("HY", 0)) if row.get("HY") else 0,
                "away_yellow_cards": int(row.get("AY", 0)) if row.get("AY") else 0,
                "home_red_cards": int(row.get("HR", 0)) if row.get("HR") else 0,
                "away_red_cards": int(row.get("AR", 0)) if row.get("AR") else 0
            }
            matches.append(match_data)
        
        logger.info(f"✅ დამუშავდა {len(matches)} მატჩი (კოეფიციენტების გარეშე)")
        return matches
    
    except Exception as e:
        logger.error(f"❌ CSV პარსინგის შეცდომა: {e}")
        return []

# ==========================================
# API Endpoints
# ==========================================
@app.get("/")
async def root():
    return {"message": "FootStats API v1.0 - No Odds"}

@app.post("/api/import/csv")
async def import_csv(request: Request):
    """იმპორტავს CSV-ს კოეფიციენტების გარეშე"""
    global matches_storage
    
    try:
        body = await request.json()
        csv_data = body.get("csv_data", "")
        
        if not csv_data.strip():
            return {"success": False, "error": "CSV ცარიელია"}
        
        matches_storage = parse_csv_no_odds(csv_data)
        
        # სტატისტიკა
        total_matches = len(matches_storage)
        total_goals = sum(m["full_time_home_goals"] + m["full_time_away_goals"] for m in matches_storage)
        home_wins = sum(1 for m in matches_storage if m["full_time_result"] == "H")
        
        return {
            "success": True,
            "message": f"წარმატებით იმპორტირდა {total_matches} მატჩი",
            "matches_count": total_matches,
            "total_goals": total_goals,
            "home_wins": home_wins,
            "home_win_percentage": round((home_wins / total_matches) * 100, 1) if total_matches > 0 else 0
        }
    
    except Exception as e:
        logger.error(f"❌ იმპორტის შეცდომა: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/matches/all")
async def get_all_matches():
    """აბრუნებს ყველა მატჩს"""
    return {
        "success": True,
        "count": len(matches_storage),
        "data": matches_storage
    }

@app.post("/api/save/to-database")
async def save_to_database():
    """ინახავს მონაცემებს Supabase-ში"""
    if not HAS_SUPABASE:
        return {"success": False, "error": "Supabase არ არის დაყენებული"}
    
    supabase = get_supabase()
    if not supabase:
        return {"success": False, "error": "Supabase კლიენტი არ არის ინიციალიზებული"}
    
    if not matches_storage:
        return {"success": False, "error": "მონაცემები ჯერ არ არის იმპორტირებული"}
    
    try:
        # ბატჩური ჩაწერა (50 მატჩი)
        inserted = 0
        batch_size = 50
        
        for i in range(0, len(matches_storage), batch_size):
            batch = matches_storage[i:i + batch_size]
            supabase.table("premier_league_2025_2026").insert(batch).execute()
            inserted += len(batch)
            logger.info(f"📝 ჩაიწერა {inserted}/{len(matches_storage)} მატჩი")
        
        return {
            "success": True,
            "message": f"წარმატებით ჩაიწერა {inserted} მატჩი Supabase-ში",
            "inserted": inserted
        }
    
    except Exception as e:
        logger.error(f"❌ ბაზაში ჩაწერის შეცდომა: {e}")
        return {"success": False, "error": str(e)}

@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    html_content = """
    <!DOCTYPE html>
    <html lang="ka">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FootStats Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            .glass { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); }
            .log { animation: slideIn 0.3s ease-out; }
            @keyframes slideIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        </style>
    </head>
    <body class="bg-gradient-to-br from-[#0B0F19] to-[#1a1f2e] text-white min-h-screen">
        <div class="max-w-7xl mx-auto p-6">
            <div class="text-center mb-8">
                <h1 class="text-4xl font-bold mb-2">⚽ FootStats Dashboard</h1>
                <p class="text-gray-400">Premier League 2025/2026 - კოეფიციენტების გარეშე</p>
            </div>

            <!-- სტატისტიკა -->
            <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
                <div class="glass rounded-xl p-5">
                    <p class="text-gray-400 text-sm">სულ მატჩი</p>
                    <p class="text-3xl font-bold mt-1" id="stat-matches">0</p>
                </div>
                <div class="glass rounded-xl p-5">
                    <p class="text-gray-400 text-sm">სულ გოლი</p>
                    <p class="text-3xl font-bold text-emerald-400 mt-1" id="stat-goals">0</p>
                </div>
                <div class="glass rounded-xl p-5">
                    <p class="text-gray-400 text-sm">მასპინძლის მოგება</p>
                    <p class="text-3xl font-bold text-blue-400 mt-1" id="stat-home">0%</p>
                </div>
                <div class="glass rounded-xl p-5">
                    <p class="text-gray-400 text-sm">მოქმედება</p>
                    <button onclick="saveDB()" class="mt-1 px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded font-semibold">💾 ბაზაში ჩაწერა</button>
                </div>
            </div>

            <!-- იმპორტი -->
            <div class="glass rounded-xl p-6 mb-8">
                <h2 class="text-xl font-bold mb-4">📥 CSV იმპორტი</h2>
                <textarea id="csv" rows="10" placeholder="ჩასვი CSV ფაილის შიგთავსი..." class="w-full bg-[#0B0F19] border border-gray-700 rounded p-3 text-sm font-mono resize-none focus:border-emerald-500"></textarea>
                <div class="flex gap-3 mt-4">
                    <button onclick="importCSV()" class="flex-1 bg-emerald-600 hover:bg-emerald-500 py-3 rounded font-semibold">🚀 დამუშავება</button>
                    <button onclick="document.getElementById('csv').value=''" class="px-6 bg-gray-700 hover:bg-gray-600 py-3 rounded">🗑️</button>
                </div>
            </div>

            <!-- ცხრილი -->
            <div class="glass rounded-xl p-6 mb-8">
                <h2 class="text-xl font-bold mb-4">📊 მატჩების ცხრილი (<span id="count">0</span>)</h2>
                <div class="overflow-x-auto max-h-96">
                    <table class="w-full text-sm">
                        <thead class="bg-[#0F172A] sticky top-0">
                            <tr>
                                <th class="p-2">თარიღი</th>
                                <th class="p-2">მასპინძელი</th>
                                <th class="p-2 text-center">ანგარიში</th>
                                <th class="p-2">სტუმარი</th>
                                <th class="p-2 text-center">შედეგი</th>
                                <th class="p-2 text-center">დარტყმები</th>
                                <th class="p-2 text-center">კუთხურები</th>
                                <th class="p-2 text-center">ბარათები</th>
                            </tr>
                        </thead>
                        <tbody id="table"></tbody>
                    </table>
                </div>
            </div>

            <!-- ლოგები -->
            <div class="glass rounded-xl p-6">
                <div class="flex justify-between mb-4">
                    <h3 class="font-bold">📜 ლოგები</h3>
                    <button onclick="clearLogs()" class="text-xs text-gray-400">გასუფთავება</button>
                </div>
                <div id="logs" class="bg-[#020617] rounded p-4 h-48 overflow-y-auto text-xs font-mono space-y-1"></div>
            </div>
        </div>

        <script>
            async function importCSV() {
                const csv = document.getElementById('csv').value;
                if(!csv) return log('❌ ცარიელია', 'error');
                
                log('📥 იმპორტი...', 'info');
                try {
                    const r = await fetch('/api/import/csv', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({csv_data: csv})
                    });
                    const d = await r.json();
                    
                    if(d.success) {
                        log(`✅ ${d.message}`, 'success');
                        document.getElementById('stat-matches').textContent = d.matches_count;
                        document.getElementById('stat-goals').textContent = d.total_goals;
                        document.getElementById('stat-home').textContent = d.home_win_percentage + '%';
                        renderTable();
                    } else log('❌ ' + d.error, 'error');
                } catch(e) { log('❌ ' + e.message, 'error'); }
            }

            async function saveDB() {
                log('💾 ბაზაში ჩაწერა...', 'info');
                try {
                    const r = await fetch('/api/save/to-database', {method: 'POST'});
                    const d = await r.json();
                    if(d.success) log(`✅ ${d.message}`, 'success');
                    else log('❌ ' + d.error, 'error');
                } catch(e) { log('❌ ' + e.message, 'error'); }
            }

            async function renderTable() {
                const r = await fetch('/api/matches/all');
                const d = await r.json();
                
                if(d.success) {
                    document.getElementById('count').textContent = d.count;
                    document.getElementById('table').innerHTML = d.data.slice(0, 50).map(m => {
                        const resultColor = m.full_time_result === 'H' ? 'text-emerald-400' : m.full_time_result === 'A' ? 'text-red-400' : 'text-yellow-400';
                        const totalCards = m.home_yellow_cards + m.away_yellow_cards + m.home_red_cards + m.away_red_cards;
                        return `
                            <tr class="border-b border-gray-800 hover:bg-[#1E293B]">
                                <td class="p-2">${m.match_date}</td>
                                <td class="p-2 font-semibold">${m.home_team}</td>
                                <td class="p-2 text-center font-bold">${m.full_time_home_goals} - ${m.full_time_away_goals}</td>
                                <td class="p-2 font-semibold">${m.away_team}</td>
                                <td class="p-2 text-center font-bold ${resultColor}">${m.full_time_result === 'H' ? 'მასპ' : m.full_time_result === 'A' ? 'სტუმ' : 'ფრე'}</td>
                                <td class="p-2 text-center">${m.home_shots}/${m.away_shots}</td>
                                <td class="p-2 text-center">${m.home_corners}/${m.away_corners}</td>
                                <td class="p-2 text-center">${totalCards} 🟨</td>
                            </tr>
                        `;
                    }).join('');
                }
            }

            function log(msg, type) {
                const colors = {info: 'text-blue-400', success: 'text-emerald-400', error: 'text-red-400'};
                const time = new Date().toLocaleTimeString('ka-GE');
                document.getElementById('logs').innerHTML += `<div class="log"><span class="text-gray-600">[${time}]</span> <span class="${colors[type]}">${msg}</span></div>`;
                document.getElementById('logs').scrollTop = 99999;
            }

            function clearLogs() {
                document.getElementById('logs').innerHTML = '';
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)