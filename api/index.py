import asyncio
import json
import os
import re
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field
import httpx
from bs4 import BeautifulSoup
from loguru import logger

# ==========================================
# Logger Setup
# ==========================================
logger.remove()
logger.add(lambda msg: print(msg.strip()), format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan> - <level>{message}</level>")

# ==========================================
# FastAPI App
# ==========================================
app = FastAPI(title="FootStats API")

# ==========================================
# Supabase Client
# ==========================================
_supabase_client = None

def get_supabase():
    global _supabase_client
    if _supabase_client is None:
        try:
            from supabase import create_client
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_KEY")
            if url and key:
                _supabase_client = create_client(url, key)
                logger.info("✅ Supabase კლიენტი ინიციალიზდა")
        except Exception as e:
            logger.error(f"❌ Supabase ინიციალიზაციის შეცდომა: {e}")
    return _supabase_client

# ==========================================
# In-Memory Storage
# ==========================================
api_keys_cache = {
    "google": {"api_key": None, "selected_model": "gemini/gemini-2.5-flash"},
    "groq": {"api_key": None, "selected_model": "groq/llama-3.3-70b-versatile"}
}

matches_db: List[Dict] = []
teams_db: List[Dict] = []

# ==========================================
# API Keys Management
# ==========================================
def load_api_keys_from_db():
    """ჩატვირთავს API გასაღებებს Supabase-დან"""
    global api_keys_cache
    supabase = get_supabase()
    if not supabase:
        return
    
    try:
        response = supabase.table("api_keys").select("*").execute()
        for row in response.data:
            provider = row["provider"]
            if provider in api_keys_cache:
                api_keys_cache[provider]["api_key"] = row["api_key"]
                api_keys_cache[provider]["selected_model"] = row.get("selected_model", api_keys_cache[provider]["selected_model"])
                logger.info(f"✅ {provider} გასაღები ჩაიტვირთა DB-დან")
    except Exception as e:
        logger.error(f"❌ DB ჩატვირთვის შეცდომა: {e}")

def save_api_key_to_db(provider: str, api_key: str, selected_model: str) -> bool:
    """ინახავს API გასაღებს Supabase-ში"""
    supabase = get_supabase()
    if not supabase:
        return False
    
    try:
        data = {
            "provider": provider,
            "api_key": api_key,
            "selected_model": selected_model
        }
        
        existing = supabase.table("api_keys").select("id").eq("provider", provider).execute()
        if existing.data:
            supabase.table("api_keys").update(data).eq("provider", provider).execute()
        else:
            supabase.table("api_keys").insert(data).execute()
        
        logger.info(f"✅ {provider} გასაღები შენახულია DB-ში")
        return True
    except Exception as e:
        logger.error(f"❌ გასაღების შენახვის შეცდომა: {e}")
        return False

# ჩავტვირთოთ გასაღებები სერვერის დაწყებისას
load_api_keys_from_db()

# ==========================================
# CSV Parser for football-data.co.uk
# ==========================================
def parse_football_data_csv(csv_text: str) -> Tuple[List[Dict], List[Dict]]:
    """პარსავს football-data.co.uk ფორმატის CSV-ს"""
    lines = csv_text.strip().split('\n')
    if len(lines) < 2:
        return [], []
    
    header = lines[0].split(',')
    matches = []
    teams_set = set()
    
    for line in lines[1:]:
        if not line.strip():
            continue
        
        cols = line.split(',')
        if len(cols) < 24:
            continue
        
        try:
            match = {
                "division": cols[0],
                "date": cols[1],
                "time": cols[2],
                "home_team": cols[3],
                "away_team": cols[4],
                "home_goals": int(cols[5]) if cols[5] else 0,
                "away_goals": int(cols[6]) if cols[6] else 0,
                "result": cols[7],
                "half_time_home": int(cols[8]) if cols[8] else 0,
                "half_time_away": int(cols[9]) if cols[9] else 0,
                "half_time_result": cols[10],
                "referee": cols[11],
                "home_shots": int(cols[12]) if cols[12] else 0,
                "away_shots": int(cols[13]) if cols[13] else 0,
                "home_shots_on_target": int(cols[14]) if cols[14] else 0,
                "away_shots_on_target": int(cols[15]) if cols[15] else 0,
                "home_fouls": int(cols[16]) if cols[16] else 0,
                "away_fouls": int(cols[17]) if cols[17] else 0,
                "home_corners": int(cols[18]) if cols[18] else 0,
                "away_corners": int(cols[19]) if cols[19] else 0,
                "home_yellow": int(cols[20]) if cols[20] else 0,
                "away_yellow": int(cols[21]) if cols[21] else 0,
                "home_red": int(cols[22]) if cols[22] else 0,
                "away_red": int(cols[23]) if cols[23] else 0
            }
            matches.append(match)
            teams_set.add(match["home_team"])
            teams_set.add(match["away_team"])
        except Exception as e:
            logger.error(f"❌ სტრიქონის პარსინგის შეცდომა: {e}")
            continue
    
    teams = [{"name": team} for team in sorted(teams_set)]
    return matches, teams

# ==========================================
# AI Integration
# ==========================================
async def fetch_with_gemini(prompt: str) -> Tuple[Optional[str], str]:
    """იყენებს Google Gemini-ს"""
    api_key = api_keys_cache["google"]["api_key"]
    if not api_key:
        return None, "Google API გასაღები არ არის დაყენებული"
    
    try:
        model = api_keys_cache["google"]["selected_model"]
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, json=payload, timeout=60.0)
            if response.status_code == 200:
                data = response.json()
                text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                return text, "წარმატება"
            else:
                return None, f"Google API შეცდომა: {response.status_code}"
    except Exception as e:
        return None, f"Google შეცდომა: {str(e)}"

async def fetch_with_groq(prompt: str) -> Tuple[Optional[str], str]:
    """იყენებს Groq-ს"""
    api_key = api_keys_cache["groq"]["api_key"]
    if not api_key:
        return None, "Groq API გასაღები არ არის დაყენებული"
    
    try:
        model = api_keys_cache["groq"]["selected_model"]
        api_url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, headers=headers, json=payload, timeout=60.0)
            if response.status_code == 200:
                data = response.json()
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return text, "წარმატება"
            else:
                return None, f"Groq API შეცდომა: {response.status_code}"
    except Exception as e:
        return None, f"Groq შეცდომა: {str(e)}"

# ==========================================
# API Endpoints
# ==========================================
@app.get("/")
async def root():
    return {"message": "FootStats API is running!", "endpoints": ["/dashboard", "/api/stats", "/api/matches"]}

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
            @keyframes slideIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
            .log-entry { animation: slideIn 0.3s ease-out; }
            .glass-panel { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); }
            .tab-active { background-color: #10b981; color: white; }
            .tab-inactive { background-color: #374151; color: #9ca3af; }
        </style>
    </head>
    <body class="bg-gradient-to-br from-[#0B0F19] to-[#1a1f2e] text-[#E2E8F0] font-sans min-h-screen">
        <nav class="border-b border-gray-800 bg-[#0F172A] px-6 py-4">
            <div class="max-w-7xl mx-auto flex justify-between items-center">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 bg-emerald-600 rounded-lg flex items-center justify-center text-xl font-bold">⚽</div>
                    <h1 class="text-xl font-bold text-white">FootStats Dashboard</h1>
                </div>
                <div class="flex gap-4 text-sm">
                    <a href="/dashboard" class="text-emerald-400 font-semibold">მთავარი</a>
                    <a href="#import" class="text-gray-400 hover:text-white">იმპორტი</a>
                    <a href="#settings" class="text-gray-400 hover:text-white">პარამეტრები</a>
                </div>
            </div>
        </nav>

        <main class="max-w-7xl mx-auto p-6 space-y-6">
            <!-- Stats Cards -->
            <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div class="glass-panel rounded-xl p-5">
                    <p class="text-gray-400 text-sm">სულ მატჩი</p>
                    <p class="text-3xl font-bold text-white mt-1" id="stat-matches">0</p>
                </div>
                <div class="glass-panel rounded-xl p-5">
                    <p class="text-gray-400 text-sm">სულ გოლი</p>
                    <p class="text-3xl font-bold text-emerald-400 mt-1" id="stat-goals">0</p>
                </div>
                <div class="glass-panel rounded-xl p-5">
                    <p class="text-gray-400 text-sm">გუნდები</p>
                    <p class="text-3xl font-bold text-blue-400 mt-1" id="stat-teams">0</p>
                </div>
                <div class="glass-panel rounded-xl p-5">
                    <p class="text-gray-400 text-sm">საშუალო გოლი/მატჩი</p>
                    <p class="text-3xl font-bold text-purple-400 mt-1" id="stat-avg">0</p>
                </div>
            </div>

            <!-- Tabs -->
            <div class="flex gap-2">
                <button onclick="switchTab('matches')" id="tab-matches" class="tab-active px-6 py-3 rounded-lg font-semibold">📊 მატჩები</button>
                <button onclick="switchTab('import')" id="tab-import" class="tab-inactive px-6 py-3 rounded-lg font-semibold">📥 იმპორტი</button>
                <button onclick="switchTab('settings')" id="tab-settings" class="tab-inactive px-6 py-3 rounded-lg font-semibold">⚙️ პარამეტრები</button>
            </div>

            <!-- Matches Tab -->
            <div id="section-matches" class="glass-panel rounded-xl p-6">
                <h2 class="text-2xl font-bold text-white mb-4">მატჩების ცხრილი</h2>
                <div class="overflow-x-auto max-h-[600px]">
                    <table class="w-full text-sm text-left">
                        <thead class="text-xs text-gray-400 uppercase bg-[#0F172A] sticky top-0">
                            <tr>
                                <th class="px-4 py-3">თარიღი</th>
                                <th class="px-4 py-3">მასპინძელი</th>
                                <th class="px-4 py-3 text-center">ანგარიში</th>
                                <th class="px-4 py-3">სტუმარი</th>
                                <th class="px-4 py-3 text-center">შედეგი</th>
                                <th class="px-4 py-3">მსაჯი</th>
                                <th class="px-4 py-3 text-center">დარტყმები</th>
                                <th class="px-4 py-3 text-center">კუთხურები</th>
                                <th class="px-4 py-3 text-center">ბარათები</th>
                            </tr>
                        </thead>
                        <tbody id="matches-table" class="divide-y divide-gray-700">
                            <tr>
                                <td colspan="9" class="px-4 py-8 text-center text-gray-500">
                                    მონაცემები ჯერ არ არის იმპორტირებული
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Import Tab -->
            <div id="section-import" class="hidden glass-panel rounded-xl p-6">
                <h2 class="text-2xl font-bold text-white mb-4">CSV იმპორტი</h2>
                <p class="text-gray-400 mb-4">ჩასვით football-data.co.uk ფორმატის CSV ფაილის შიგთავსი</p>
                <textarea id="csv-input" rows="15" placeholder="Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR..." class="w-full bg-[#0B0F19] border border-gray-700 rounded-lg p-4 text-emerald-400 font-mono text-xs resize-none focus:outline-none focus:border-emerald-500"></textarea>
                <div class="flex gap-3 mt-4">
                    <button onclick="importCSV()" id="import-btn" class="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-3 rounded-lg">📥 იმპორტი</button>
                    <button onclick="clearCSV()" class="px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg">🗑️ გასუფთავება</button>
                </div>
            </div>

            <!-- Settings Tab -->
            <div id="section-settings" class="hidden glass-panel rounded-xl p-6">
                <h2 class="text-2xl font-bold text-white mb-4">API გასაღებები</h2>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="bg-[#0B0F19] border border-gray-700 rounded-lg p-4">
                        <h3 class="font-bold text-white mb-2">🔵 Google Gemini</h3>
                        <input id="google-key" type="password" placeholder="API გასაღები" class="w-full bg-[#0F172A] border border-gray-700 rounded p-2 text-sm text-emerald-400 mb-2">
                        <button onclick="saveKey('google')" class="w-full bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded text-sm font-semibold">💾 შენახვა</button>
                        <p id="google-status" class="text-xs text-gray-400 mt-2">სტატუსი: ⏸️ არ არის დაყენებული</p>
                    </div>
                    <div class="bg-[#0B0F19] border border-gray-700 rounded-lg p-4">
                        <h3 class="font-bold text-white mb-2">🟠 Groq</h3>
                        <input id="groq-key" type="password" placeholder="API გასაღები" class="w-full bg-[#0F172A] border border-gray-700 rounded p-2 text-sm text-emerald-400 mb-2">
                        <button onclick="saveKey('groq')" class="w-full bg-orange-600 hover:bg-orange-500 text-white px-4 py-2 rounded text-sm font-semibold">💾 შენახვა</button>
                        <p id="groq-status" class="text-xs text-gray-400 mt-2">სტატუსი: ⏸️ არ არის დაყენებული</p>
                    </div>
                </div>
            </div>

            <!-- Logs -->
            <div class="glass-panel rounded-xl p-6">
                <div class="flex justify-between items-center mb-4">
                    <h3 class="text-lg font-bold text-white">📜 ლოგები</h3>
                    <button onclick="clearLogs()" class="text-xs text-gray-400 hover:text-white">გასუფთავება</button>
                </div>
                <div id="terminal" class="bg-[#020617] border border-gray-800 rounded-lg p-4 h-64 overflow-y-auto font-mono text-xs space-y-2">
                    <div class="text-gray-500">// სისტემა მზად არის...</div>
                </div>
            </div>
        </main>

        <script>
            async function loadStats() {
                try {
                    const response = await fetch('/api/stats');
                    const stats = await response.json();
                    document.getElementById('stat-matches').textContent = stats.total_matches || 0;
                    document.getElementById('stat-goals').textContent = stats.total_goals || 0;
                    document.getElementById('stat-teams').textContent = stats.total_teams || 0;
                    document.getElementById('stat-avg').textContent = stats.avg_goals || 0;
                } catch (error) {
                    console.error('შეცდომა:', error);
                }
            }

            async function loadMatches() {
                try {
                    const response = await fetch('/api/matches');
                    const matches = await response.json();
                    
                    const tbody = document.getElementById('matches-table');
                    if (matches.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="9" class="px-4 py-8 text-center text-gray-500">მონაცემები ჯერ არ არის იმპორტირებული</td></tr>';
                        return;
                    }
                    
                    tbody.innerHTML = matches.map(m => {
                        const resultColor = m.result === 'H' ? 'text-emerald-400' : (m.result === 'A' ? 'text-red-400' : 'text-yellow-400');
                        const resultText = m.result === 'H' ? 'მასპინძელი' : (m.result === 'A' ? 'სტუმარი' : 'ფრე');
                        const totalCards = (m.home_yellow || 0) + (m.away_yellow || 0) + (m.home_red || 0) + (m.away_red || 0);
                        
                        return `
                            <tr class="hover:bg-[#0F172A]">
                                <td class="px-4 py-3">${m.date}</td>
                                <td class="px-4 py-3 font-semibold">${m.home_team}</td>
                                <td class="px-4 py-3 text-center font-bold text-lg">${m.home_goals} - ${m.away_goals}</td>
                                <td class="px-4 py-3 font-semibold">${m.away_team}</td>
                                <td class="px-4 py-3 text-center font-bold ${resultColor}">${resultText}</td>
                                <td class="px-4 py-3 text-gray-400 text-xs">${m.referee}</td>
                                <td class="px-4 py-3 text-center">${m.home_shots || 0} - ${m.away_shots || 0}</td>
                                <td class="px-4 py-3 text-center">${m.home_corners || 0} - ${m.away_corners || 0}</td>
                                <td class="px-4 py-3 text-center">${totalCards}</td>
                            </tr>
                        `;
                    }).join('');
                } catch (error) {
                    console.error('შეცდომა:', error);
                }
            }

            function switchTab(tab) {
                ['matches', 'import', 'settings'].forEach(t => {
                    document.getElementById('tab-' + t).className = tab === t ? 'tab-active px-6 py-3 rounded-lg font-semibold' : 'tab-inactive px-6 py-3 rounded-lg font-semibold';
                    document.getElementById('section-' + t).classList.toggle('hidden', tab !== t);
                });
            }

            async function importCSV() {
                const csv = document.getElementById('csv-input').value;
                const btn = document.getElementById('import-btn');
                
                if (!csv.trim()) {
                    addLog('❌ CSV ცარიელია', 'error');
                    return;
                }
                
                btn.disabled = true;
                btn.textContent = '⏳ იმპორტი მიმდინარეობს...';
                addLog('📥 იმპორტი იწყება...', 'info');
                
                try {
                    const response = await fetch('/api/import/csv', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ csv_data: csv })
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        addLog(`✅ ${result.message}`, 'success');
                        await loadStats();
                        await loadMatches();
                        switchTab('matches');
                    } else {
                        addLog(`❌ ${result.error}`, 'error');
                    }
                } catch (error) {
                    addLog(`❌ ${error.message}`, 'error');
                } finally {
                    btn.disabled = false;
                    btn.textContent = '📥 იმპორტი';
                }
            }

            function clearCSV() {
                document.getElementById('csv-input').value = '';
            }

            async function saveKey(provider) {
                const key = document.getElementById(provider + '-key').value;
                if (!key) {
                    addLog('❌ გასაღები ცარიელია', 'error');
                    return;
                }
                
                try {
                    const response = await fetch('/api/vault/set-key', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ provider, api_key: key })
                    });
                    
                    const result = await response.json();
                    if (result.success) {
                        addLog(`✅ ${provider} გასაღები შენახულია`, 'success');
                        document.getElementById(provider + '-status').textContent = 'სტატუსი: ✅ შენახულია';
                    } else {
                        addLog(`❌ ${result.error}`, 'error');
                    }
                } catch (error) {
                    addLog(`❌ ${error.message}`, 'error');
                }
            }

            function addLog(message, type = 'info') {
                const terminal = document.getElementById('terminal');
                const log = document.createElement('div');
                log.className = 'log-entry';
                const colors = { 'info': 'text-blue-400', 'success': 'text-emerald-400', 'error': 'text-red-400' };
                const timestamp = new Date().toLocaleTimeString('ka-GE');
                log.innerHTML = `<span class="text-gray-600">[${timestamp}]</span> <span class="${colors[type]}">${message}</span>`;
                terminal.appendChild(log);
                terminal.scrollTop = terminal.scrollHeight;
            }

            function clearLogs() {
                document.getElementById('terminal').innerHTML = '<div class="text-gray-500">// გასუფთავდა</div>';
            }

            // ჩატვირთვისას
            loadStats();
            loadMatches();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/api/stats")
async def get_stats():
    """აბრუნებს სტატისტიკას"""
    total_matches = len(matches_db)
    total_goals = sum(m["home_goals"] + m["away_goals"] for m in matches_db)
    total_teams = len(teams_db)
    avg_goals = round(total_goals / total_matches, 2) if total_matches > 0 else 0
    
    return {
        "total_matches": total_matches,
        "total_goals": total_goals,
        "total_teams": total_teams,
        "avg_goals": avg_goals
    }

@app.get("/api/matches")
async def get_matches():
    """აბრუნებს ყველა მატჩს"""
    return matches_db

@app.post("/api/import/csv")
async def import_csv(request: Request):
    """იმპორტავს CSV მონაცემებს"""
    try:
        body = await request.json()
        csv_data = body.get("csv_data", "")
        
        if not csv_data.strip():
            return {"success": False, "error": "CSV ცარიელია"}
        
        matches, teams = parse_football_data_csv(csv_data)
        
        global matches_db, teams_db
        matches_db = matches
        teams_db = teams
        
        return {
            "success": True,
            "message": f"წარმატებით იმპორტირდა {len(matches)} მატჩი და {len(teams)} გუნდი",
            "matches_count": len(matches),
            "teams_count": len(teams)
        }
    except Exception as e:
        return {"success": False, "error": f"შეცდომა: {str(e)}"}

@app.post("/api/vault/set-key")
async def set_api_key(request: Request):
    """ინახავს API გასაღებს"""
    try:
        body = await request.json()
        provider = body.get("provider")
        api_key = body.get("api_key")
        
        if not provider or not api_key:
            return {"success": False, "error": "provider და api_key აუცილებელია"}
        
        api_keys_cache[provider]["api_key"] = api_key
        selected_model = api_keys_cache[provider]["selected_model"]
        
        # შევინახოთ DB-ში
        save_api_key_to_db(provider, api_key, selected_model)
        
        return {"success": True, "message": f"{provider} გასაღები შენახულია"}
    except Exception as e:
        return {"success": False, "error": f"შეცდომა: {str(e)}"}

@app.get("/api/vault/status")
async def get_vault_status():
    """აბრუნებს API გასაღებების სტატუსს"""
    return {
        provider: {
            "has_key": bool(config["api_key"]),
            "selected_model": config["selected_model"]
        }
        for provider, config in api_keys_cache.items()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)