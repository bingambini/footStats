import asyncio
import json
import os
import csv
import io
from typing import Dict, List, Tuple, Optional
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
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
# CSV Parser - მხოლოდ ძირითადი მონაცემები (კოეფიციენტების გარეშე)
# ==========================================
def parse_csv_matches(csv_text: str) -> List[Dict]:
    """ამოიღებს მხოლოდ ძირითად მონაცემებს CSV ფაილიდან"""
    try:
        reader = csv.DictReader(io.StringIO(csv_text))
        matches = []
        
        for row in reader:
            # მხოლოდ ძირითადი სვეტები (24 სვეტი)
            match_data = {
                "division": row.get("Div", "").strip(),
                "date": row.get("Date", "").strip(),
                "time": row.get("Time", "").strip(),
                "home_team": row.get("HomeTeam", "").strip(),
                "away_team": row.get("AwayTeam", "").strip(),
                "referee": row.get("Referee", "").strip(),
                "full_time_home_goals": int(row.get("FTHG", 0) or 0),
                "full_time_away_goals": int(row.get("FTAG", 0) or 0),
                "full_time_result": row.get("FTR", "").strip(),
                "half_time_home_goals": int(row.get("HTHG", 0) or 0),
                "half_time_away_goals": int(row.get("HTAG", 0) or 0),
                "half_time_result": row.get("HTR", "").strip(),
                "home_shots": int(row.get("HS", 0) or 0),
                "away_shots": int(row.get("AS", 0) or 0),
                "home_shots_on_target": int(row.get("HST", 0) or 0),
                "away_shots_on_target": int(row.get("AST", 0) or 0),
                "home_fouls": int(row.get("HF", 0) or 0),
                "away_fouls": int(row.get("AF", 0) or 0),
                "home_corners": int(row.get("HC", 0) or 0),
                "away_corners": int(row.get("AC", 0) or 0),
                "home_yellow_cards": int(row.get("HY", 0) or 0),
                "away_yellow_cards": int(row.get("AY", 0) or 0),
                "home_red_cards": int(row.get("HR", 0) or 0),
                "away_red_cards": int(row.get("AR", 0) or 0)
            }
            
            # მხოლოდ იმ რიგების დამატება, რომლებსაც აქვთ გუნდები
            if match_data["home_team"] and match_data["away_team"]:
                matches.append(match_data)
        
        logger.info(f"✅ წარმატებით დამუშავდა {len(matches)} მატჩი (24 სვეტი)")
        return matches
    
    except Exception as e:
        logger.error(f"❌ CSV პარსინგის შეცდომა: {e}")
        return []

# ==========================================
# API Endpoints
# ==========================================
@app.get("/")
async def root():
    return {"message": "FootStats API v3.0 - Premier League 2025/2026"}

@app.post("/api/import/csv")
async def import_csv(request: Request):
    """იმპორტავს CSV-ს და ინახავს მეხსიერებაში"""
    global matches_storage
    
    try:
        body = await request.json()
        csv_data = body.get("csv_data", "")
        
        if not csv_data.strip():
            return {"success": False, "error": "CSV ცარიელია"}
        
        matches_storage = parse_csv_matches(csv_data)
        
        # სტატისტიკა
        total_matches = len(matches_storage)
        total_goals = sum(m["full_time_home_goals"] + m["full_time_away_goals"] for m in matches_storage)
        home_wins = sum(1 for m in matches_storage if m["full_time_result"] == "H")
        away_wins = sum(1 for m in matches_storage if m["full_time_result"] == "A")
        draws = sum(1 for m in matches_storage if m["full_time_result"] == "D")
        
        return {
            "success": True,
            "message": f"წარმატებით იმპორტირდა {total_matches} მატჩი",
            "total_matches": total_matches,
            "total_goals": total_goals,
            "home_wins": home_wins,
            "away_wins": away_wins,
            "draws": draws,
            "avg_goals": round(total_goals / total_matches, 2) if total_matches > 0 else 0
        }
    except Exception as e:
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
    """ინახავს მონაცემებს Supabase-ში (ჯერ არ არის განხორციელებული)"""
    if not matches_storage:
        return {"success": False, "error": "მონაცემები ჯერ არ არის იმპორტირებული"}
    
    # აქ მომავალში იქნება Supabase-ში ჩაწერის ლოგიკა
    return {
        "success": False,
        "message": "ბაზაში ჩაწერა ჯერ არ არის განხორციელებული. ეს ფუნქცია დამატებით მომავალ ეტაპზე."
    }

# ==========================================
# Dashboard HTML
# ==========================================
@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    html_content = """
    <!DOCTYPE html>
    <html lang="ka">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FootStats Dashboard v3.0</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            @keyframes slideIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
            .log-entry { animation: slideIn 0.3s ease-out; }
            .glass { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); }
            .table-container { max-height: 600px; overflow: auto; }
            .result-h { color: #10b981; font-weight: bold; }
            .result-a { color: #ef4444; font-weight: bold; }
            .result-d { color: #f59e0b; font-weight: bold; }
        </style>
    </head>
    <body class="bg-gradient-to-br from-[#0B0F19] to-[#1a1f2e] text-[#E2E8F0] font-sans min-h-screen">
        <div class="max-w-full mx-auto p-6">
            <div class="text-center mb-8">
                <h1 class="text-4xl font-bold text-white mb-2">⚽ FootStats Dashboard v3.0</h1>
                <p class="text-gray-400">Premier League 2025/2026 - 24 ძირითადი სვეტი (კოეფიციენტების გარეშე)</p>
            </div>

            <!-- სტატისტიკის ბარათები -->
            <div class="grid grid-cols-1 md:grid-cols-6 gap-4 mb-8">
                <div class="glass rounded-xl p-5">
                    <p class="text-gray-400 text-sm">სულ მატჩი</p>
                    <p class="text-3xl font-bold text-white mt-1" id="stat-matches">0</p>
                </div>
                <div class="glass rounded-xl p-5">
                    <p class="text-gray-400 text-sm">სულ გოლი</p>
                    <p class="text-3xl font-bold text-emerald-400 mt-1" id="stat-goals">0</p>
                </div>
                <div class="glass rounded-xl p-5">
                    <p class="text-gray-400 text-sm">საშუალო გოლი</p>
                    <p class="text-3xl font-bold text-blue-400 mt-1" id="stat-avg">0</p>
                </div>
                <div class="glass rounded-xl p-5">
                    <p class="text-gray-400 text-sm">მასპინძლის მოგება</p>
                    <p class="text-3xl font-bold text-green-400 mt-1" id="stat-home">0</p>
                </div>
                <div class="glass rounded-xl p-5">
                    <p class="text-gray-400 text-sm">სტუმრის მოგება</p>
                    <p class="text-3xl font-bold text-red-400 mt-1" id="stat-away">0</p>
                </div>
                <div class="glass rounded-xl p-5">
                    <p class="text-gray-400 text-sm">ფრე</p>
                    <p class="text-3xl font-bold text-yellow-400 mt-1" id="stat-draws">0</p>
                </div>
            </div>

            <!-- იმპორტის სექცია -->
            <div class="glass rounded-xl p-6 mb-8">
                <h2 class="text-xl font-bold text-white mb-4">📥 CSV იმპორტი</h2>
                <textarea id="csvInput" rows="8" placeholder="ჩასვი football-data.co.uk ფორმატის CSV ტექსტი აქ..." class="w-full bg-[#0B0F19] border border-gray-700 rounded-lg p-4 text-emerald-400 font-mono text-xs resize-none focus:outline-none focus:border-emerald-500"></textarea>
                <div class="flex gap-3 mt-4">
                    <button onclick="importCSV()" id="importBtn" class="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-3 rounded-lg">🚀 იმპორტი და დამუშავება</button>
                    <button onclick="saveToDatabase()" id="saveBtn" class="flex-1 bg-blue-600 hover:bg-blue-500 text-white font-semibold py-3 rounded-lg" disabled>💾 ბაზაში ჩაწერა</button>
                    <button onclick="document.getElementById('csvInput').value=''" class="px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg">🗑️</button>
                </div>
            </div>

            <!-- მონაცემთა ცხრილი -->
            <div class="glass rounded-xl p-6 mb-8">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-xl font-bold text-white">📊 მატჩების ცხრილი (<span id="matchCount">0</span> მატჩი)</h2>
                </div>
                <div class="table-container border border-gray-700 rounded-lg">
                    <table class="w-full text-xs text-left">
                        <thead class="text-xs text-gray-400 uppercase bg-[#0F172A] sticky top-0">
                            <tr>
                                <th class="px-2 py-2">თარიღი</th>
                                <th class="px-2 py-2">მასპინძელი</th>
                                <th class="px-2 py-2 text-center">FT</th>
                                <th class="px-2 py-2">სტუმარი</th>
                                <th class="px-2 py-2 text-center">შედეგი</th>
                                <th class="px-2 py-2 text-center">HT</th>
                                <th class="px-2 py-2 text-center">დარტყმები</th>
                                <th class="px-2 py-2 text-center">კარში</th>
                                <th class="px-2 py-2 text-center">ჯარიმები</th>
                                <th class="px-2 py-2 text-center">კუთხურები</th>
                                <th class="px-2 py-2 text-center">🟨</th>
                                <th class="px-2 py-2 text-center">🟥</th>
                                <th class="px-2 py-2">მსაჯი</th>
                            </tr>
                        </thead>
                        <tbody id="matchesTable">
                            <tr>
                                <td colspan="13" class="px-4 py-8 text-center text-gray-500">ჩასვი CSV და დააჭირე "იმპორტი"-ს</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- ლოგები -->
            <div class="glass rounded-xl p-6">
                <div class="flex justify-between items-center mb-4">
                    <h3 class="text-lg font-bold text-white">📜 ლაივ ლოგები</h3>
                    <button onclick="clearLogs()" class="text-xs text-gray-400 hover:text-white">გასუფთავება</button>
                </div>
                <div id="terminal" class="bg-[#020617] border border-gray-800 rounded-lg p-4 h-64 overflow-y-auto font-mono text-xs space-y-1">
                    <div class="text-gray-500">// სისტემა მზად არის...</div>
                </div>
            </div>
        </div>

        <script>
            async function importCSV() {
                const csv = document.getElementById('csvInput').value;
                const btn = document.getElementById('importBtn');
                
                if (!csv.trim()) {
                    addLog('❌ CSV ცარიელია', 'error');
                    return;
                }
                
                btn.disabled = true;
                btn.textContent = '⏳ მუშაობს...';
                addLog('📥 CSV იმპორტი იწყება...', 'info');
                
                try {
                    const response = await fetch('/api/import/csv', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ csv_data: csv })
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        addLog(`✅ ${result.message}`, 'success');
                        addLog(`⚽ სულ გოლი: ${result.total_goals}`, 'info');
                        addLog(`📊 საშუალო: ${result.avg_goals} გოლი/მატჩი`, 'info');
                        addLog(`🏠 მასპინძლის მოგება: ${result.home_wins}`, 'info');
                        addLog(`✈️ სტუმრის მოგება: ${result.away_wins}`, 'info');
                        addLog(`🤝 ფრე: ${result.draws}`, 'info');
                        
                        document.getElementById('stat-matches').textContent = result.total_matches;
                        document.getElementById('stat-goals').textContent = result.total_goals;
                        document.getElementById('stat-avg').textContent = result.avg_goals;
                        document.getElementById('stat-home').textContent = result.home_wins;
                        document.getElementById('stat-away').textContent = result.away_wins;
                        document.getElementById('stat-draws').textContent = result.draws;
                        
                        document.getElementById('saveBtn').disabled = false;
                        
                        await loadMatches();
                    } else {
                        addLog(`❌ ${result.error}`, 'error');
                    }
                } catch (error) {
                    addLog(`❌ ${error.message}`, 'error');
                } finally {
                    btn.disabled = false;
                    btn.textContent = '🚀 იმპორტი და დამუშავება';
                }
            }

            async function loadMatches() {
                try {
                    const response = await fetch('/api/matches/all');
                    const result = await response.json();
                    
                    if (result.success && result.data.length > 0) {
                        document.getElementById('matchCount').textContent = result.count;
                        renderTable(result.data);
                    }
                } catch (error) {
                    addLog(`❌ ${error.message}`, 'error');
                }
            }

            function renderTable(matches) {
                const tbody = document.getElementById('matchesTable');
                
                tbody.innerHTML = matches.map(m => {
                    const resultClass = m.full_time_result === 'H' ? 'result-h' : m.full_time_result === 'A' ? 'result-a' : 'result-d';
                    const resultText = m.full_time_result === 'H' ? 'მასპინძელი' : m.full_time_result === 'A' ? 'სტუმარი' : 'ფრე';
                    const totalCards = m.home_yellow_cards + m.away_yellow_cards;
                    const totalRed = m.home_red_cards + m.away_red_cards;
                    
                    return `
                        <tr class="border-b border-gray-800 hover:bg-[#1E293B]">
                            <td class="px-2 py-2 text-gray-400">${m.date}</td>
                            <td class="px-2 py-2 font-semibold text-white">${m.home_team}</td>
                            <td class="px-2 py-2 text-center font-bold">${m.full_time_home_goals} - ${m.full_time_away_goals}</td>
                            <td class="px-2 py-2 font-semibold text-white">${m.away_team}</td>
                            <td class="px-2 py-2 text-center ${resultClass}">${resultText}</td>
                            <td class="px-2 py-2 text-center text-gray-400">${m.half_time_home_goals}-${m.half_time_away_goals}</td>
                            <td class="px-2 py-2 text-center">${m.home_shots}/${m.away_shots}</td>
                            <td class="px-2 py-2 text-center">${m.home_shots_on_target}/${m.away_shots_on_target}</td>
                            <td class="px-2 py-2 text-center">${m.home_fouls}/${m.away_fouls}</td>
                            <td class="px-2 py-2 text-center">${m.home_corners}/${m.away_corners}</td>
                            <td class="px-2 py-2 text-center">${totalCards} 🟨</td>
                            <td class="px-2 py-2 text-center">${totalRed} 🟥</td>
                            <td class="px-2 py-2 text-gray-400 text-xs">${m.referee}</td>
                        </tr>
                    `;
                }).join('');
                
                addLog(`📋 ცხრილი აგებულია: ${matches.length} მატჩი`, 'success');
            }

            async function saveToDatabase() {
                addLog('💾 ბაზაში ჩაწერა იწყება...', 'info');
                
                try {
                    const response = await fetch('/api/save/to-database', {
                        method: 'POST'
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        addLog(`✅ ${result.message}`, 'success');
                    } else {
                        addLog(`⚠️ ${result.message || result.error}`, 'warning');
                    }
                } catch (error) {
                    addLog(`❌ ${error.message}`, 'error');
                }
            }

            function addLog(message, type = 'info') {
                const terminal = document.getElementById('terminal');
                const log = document.createElement('div');
                log.className = 'log-entry';
                
                const colors = { 'info': 'text-blue-400', 'success': 'text-emerald-400', 'warning': 'text-yellow-400', 'error': 'text-red-400' };
                const timestamp = new Date().toLocaleTimeString('ka-GE');
                
                log.innerHTML = `<span class="text-gray-600">[${timestamp}]</span> <span class="${colors[type]}">${message}</span>`;
                terminal.appendChild(log);
                terminal.scrollTop = terminal.scrollHeight;
            }

            function clearLogs() {
                document.getElementById('terminal').innerHTML = '<div class="text-gray-500">// გასუფთავდა</div>';
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)