import asyncio
import json
import os
import re
from typing import Dict, List, Tuple, Optional
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field
import httpx
from bs4 import BeautifulSoup
from loguru import logger

try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

try:
    import litellm
    import instructor
    HAS_INSTRUCTOR = True
except ImportError:
    HAS_INSTRUCTOR = False

logger.remove()
logger.add(lambda msg: print(msg.strip()), format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>")

# ==========================================
# Pydantic Models
# ==========================================
class TeamSchema(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    short_code: str = Field(..., pattern=r"^[A-Z]{3,5}$")
    city: str = Field(default="")
    country: str = Field(default="")
    stadium: str = Field(default="")
    coach: str = Field(default="")
    logo_url: str = Field(default="")

class PlayerSchema(BaseModel):
    shirt_number: int = Field(default=0)
    name: str = Field(...)
    position: str = Field(default="უცნობი")
    nationality: str = Field(default="უცნობი")
    birth_date: str = Field(default="უცნობი")
    age: int = Field(default=0)
    height_cm: Optional[int] = Field(default=None)
    weight_kg: Optional[int] = Field(default=None)

class ParsedPlayersSchema(BaseModel):
    players: List[PlayerSchema] = Field(..., description="მოთამაშეების სია")

class MatchImportSchema(BaseModel):
    row: int
    date: str
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    result: str
    referee: str
    home_shots: int
    away_shots: int

# ==========================================
# API Vault Logic
# ==========================================
_supabase = None
def get_supabase():
    global _supabase
    if _supabase is None:
        try:
            from supabase import create_client
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_KEY")
            if url and key:
                _supabase = create_client(url, key)
                logger.info("✅ Supabase კლიენტი ინიციალიზდა")
            else:
                logger.error("❌ SUPABASE_URL ან SUPABASE_KEY არ არის დაყენებული!")
        except Exception as e:
            logger.error(f"❌ Supabase ინიციალიზაციის შეცდომა: {e}")
    return _supabase

_cache: Dict[str, Dict] = {}
_loaded = False

def _load_from_db():
    global _loaded
    providers_cache = {
        "google": {"name": "Google Gemini", "api_key": None, "selected_model": "gemini/gemini-2.5-flash"},
        "groq": {"name": "Groq", "api_key": None, "selected_model": "groq/llama-3.3-70b-versatile"}
    }
    supabase = get_supabase()
    if not supabase:
        _loaded = True
        return providers_cache
    try:
        response = supabase.table("api_keys").select("*").execute()
        for row in response.data:
            if row["provider"] in providers_cache:
                providers_cache[row["provider"]]["api_key"] = row["api_key"]
                providers_cache[row["provider"]]["selected_model"] = row.get("selected_model") or providers_cache[row["provider"]]["selected_model"]
        _loaded = True
        return providers_cache
    except Exception as e:
        logger.error(f"❌ DB ჩატვირთვის შეცდომა: {e}")
        _loaded = True
        return providers_cache

def get_vault_status():
    global _cache
    if not _loaded:
        _cache = _load_from_db()
    else:
        # Fallback if _load_from_db wasn't called but _loaded is True
        if not _cache:
            _cache = {
                "google": {"name": "Google Gemini", "api_key": os.environ.get("GOOGLE_API_KEY"), "selected_model": "gemini/gemini-2.5-flash"},
                "groq": {"name": "Groq", "api_key": os.environ.get("GROQ_API_KEY"), "selected_model": "groq/llama-3.3-70b-versatile"}
            }
    result = {}
    for provider in ["google", "groq"]:
        info = _cache.get(provider, {})
        result[provider] = {
            "has_key": bool(info.get("api_key")),
            "selected_model": info.get("selected_model"),
            "name": info.get("name", provider)
        }
    return result

def save_key_to_db(provider: str, api_key: str, selected_model: str = "") -> bool:
    global _cache
    if not _loaded:
        _cache = _load_from_db()
    
    _cache[provider] = {
        "api_key": api_key,
        "selected_model": selected_model,
        "name": "Google Gemini" if provider == "google" else "Groq"
    }
    
    supabase = get_supabase()
    if not supabase:
        return False
    try:
        data = {"provider": provider, "api_key": api_key, "selected_model": selected_model}
        existing = supabase.table("api_keys").select("id").eq("provider", provider).execute()
        if existing.data:
            supabase.table("api_keys").update(data).eq("provider", provider).execute()
        else:
            supabase.table("api_keys").insert(data).execute()
        return True
    except Exception as e:
        logger.error(f"❌ გასაღების შენახვის შეცდომა: {e}")
        return False

# ==========================================
# FastAPI App & Endpoints
# ==========================================
app = FastAPI()

@app.get("/")
async def root():
    return {"message": "FootStats API v3.2 (CSV Import Ready) is running!"}

@app.get("/api/vault/status")
async def api_vault_status():
    return get_vault_status()

@app.post("/api/vault/set-key")
async def api_set_key(request: dict):
    provider = request.get("provider")
    api_key = request.get("api_key")
    if not provider or not api_key:
        return {"success": False, "error": "მონაცემები აკლია"}
    
    status = get_vault_status()
    model = status[provider]["selected_model"]
    success = save_key_to_db(provider, api_key, model)
    
    if success:
        return {"success": True, "message": f"{provider} გასაღები შენახულია"}
    return {"success": False, "error": "შენახვის შეცდომა"}

@app.post("/api/import/csv")
async def process_csv_import(request: dict):
    """ამუშავებს ჩასმულ CSV ტექსტს და აბრუნებს სტრუქტურირებულ მონაცემებს ვიზუალიზაციისთვის"""
    raw_data = request.get("csv_data", "")
    if not raw_data.strip():
        return {"success": False, "error": "მონაცემები ცარიელია"}

    lines = raw_data.strip().split('\n')
    if len(lines) < 2:
        return {"success": False, "error": "არასაკმარისი მონაცემები (მინიმუმ სათაური და 1 სტრიქონი)"}

    parsed_matches = []
    errors = []

    try:
        for i, line in enumerate(lines[1:], start=1):
            if not line.strip():
                continue
            
            # football-data.co.uk ფორმატის მიხედვით:
            # 0:Div, 1:Date, 2:Time, 3:HomeTeam, 4:AwayTeam, 5:FTHG, 6:FTAG, 7:FTR, 8:HTHG, 9:HTAG, 10:HTR, 11:Referee, 12:HS, 13:AS
            cols = line.split(',')
            
            # უსაფრთხოების შემოწმება, რომ სვეტები საკმარისია
            if len(cols) < 14:
                errors.append(f"სტრიქონი {i}: არასაკმარისი სვეტები")
                continue

            try:
                match_data = {
                    "row": i,
                    "date": cols[1].strip(),
                    "home_team": cols[3].strip(),
                    "away_team": cols[4].strip(),
                    "home_goals": int(cols[5].strip()) if cols[5].strip() else 0,
                    "away_goals": int(cols[6].strip()) if cols[6].strip() else 0,
                    "result": cols[7].strip(),
                    "referee": cols[11].strip(),
                    "home_shots": int(cols[12].strip()) if cols[12].strip() else 0,
                    "away_shots": int(cols[13].strip()) if cols[13].strip() else 0
                }
                parsed_matches.append(match_data)
            except ValueError as ve:
                errors.append(f"სტრიქონი {i}: რიცხვითი მონაცემის შეცდომა ({ve})")

        return {
            "success": True,
            "message": f"წარმატებით დამუშავდა {len(parsed_matches)} მატჩი",
            "data": parsed_matches,
            "errors": errors
        }
    except Exception as e:
        return {"success": False, "error": f"კრიტიკული შეცდომა: {str(e)}"}


@app.get("/admin/scout", response_class=HTMLResponse)
async def get_dashboard():
    html_content = """
    <!DOCTYPE html>
    <html lang="ka">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🤖 FootStats Agent Dashboard v3.2</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            @keyframes pulse-glow { 0%, 100% { box-shadow: 0 0 5px rgba(16, 185, 129, 0.5); } 50% { box-shadow: 0 0 20px rgba(16, 185, 129, 0.8); } }
            .agent-active { animation: pulse-glow 2s infinite; }
            .log-entry { animation: slideIn 0.3s ease-out; }
            @keyframes slideIn { from { opacity: 0; transform: translateX(-10px); } to { opacity: 1; transform: translateX(0); } }
            .step-completed { border-left: 4px solid #10b981; }
            .step-active { border-left: 4px solid #f59e0b; }
            .step-pending { border-left: 4px solid #6b7280; }
            .tab-active { background-color: #10b981; color: white; }
            .tab-inactive { background-color: #374151; color: #9ca3af; }
        </style>
    </head>
    <body class="bg-gradient-to-br from-[#0B0F19] to-[#1a1f2e] text-[#E2E8F0] font-sans min-h-screen p-6">
        <div class="max-w-7xl mx-auto">
            <div class="text-center mb-8">
                <h1 class="text-4xl font-bold text-white mb-2">🤖 FootStats Agent Dashboard v3.2</h1>
                <p class="text-gray-400">CSV იმპორტი, ვიზუალური ვალიდაცია და AI აგენტები</p>
            </div>

            <!-- API Vault -->
            <div class="bg-[#0E1424] border-2 border-yellow-600 rounded-xl p-6 mb-8">
                <h3 class="text-lg font-bold text-yellow-400 mb-4">🔐 API გასაღებების საცავი</h3>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div class="bg-[#070A13] border border-gray-700 rounded-lg p-4">
                        <div class="flex items-center gap-2 mb-2">
                            <span class="text-2xl">🔵</span><h4 class="font-bold text-white">Google Gemini</h4>
                            <span id="google-status" class="ml-auto px-2 py-1 bg-gray-700 rounded text-xs">⏸️ იტვირთება...</span>
                        </div>
                        <input id="google-key" type="password" placeholder="Google API გასაღები" class="w-full bg-[#0B0F19] border border-gray-700 rounded p-2 text-sm text-emerald-400 mb-2">
                        <button onclick="setKey('google')" class="w-full bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded text-sm font-semibold">💾 შენახვა</button>
                    </div>
                    <div class="bg-[#070A13] border border-gray-700 rounded-lg p-4">
                        <div class="flex items-center gap-2 mb-2">
                            <span class="text-2xl">🟠</span><h4 class="font-bold text-white">Groq</h4>
                            <span id="groq-status" class="ml-auto px-2 py-1 bg-gray-700 rounded text-xs">⏸️ იტვირთება...</span>
                        </div>
                        <input id="groq-key" type="password" placeholder="Groq API გასაღები" class="w-full bg-[#0B0F19] border border-gray-700 rounded p-2 text-sm text-emerald-400 mb-2">
                        <button onclick="setKey('groq')" class="w-full bg-orange-600 hover:bg-orange-500 text-white px-4 py-2 rounded text-sm font-semibold">💾 შენახვა</button>
                    </div>
                </div>
            </div>

            <!-- Tabs -->
            <div class="flex gap-2 mb-4 flex-wrap">
                <button onclick="switchTab('import')" id="tab-import" class="tab-active px-6 py-3 rounded-lg font-semibold">📥 CSV იმპორტი და ვალიდაცია</button>
                <button onclick="switchTab('paste')" id="tab-paste" class="tab-inactive px-6 py-3 rounded-lg font-semibold">📋 მოთამაშეების Paste</button>
                <button onclick="switchTab('team')" id="tab-team" class="tab-inactive px-6 py-3 rounded-lg font-semibold">🏆 გუნდის URL სკაუტინგი</button>
            </div>

            <!-- CSV IMPORT SECTION -->
            <div id="section-import" class="bg-[#0E1424] border-2 border-emerald-600 rounded-xl p-6 mb-8">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-lg font-bold text-white">📥 ისტორიული მატჩების იმპორტი (football-data.co.uk)</h3>
                    <span class="px-3 py-1 bg-emerald-600 rounded-full text-xs font-bold">ვიზუალური ვალიდაცია</span>
                </div>
                <p class="text-sm text-gray-400 mb-3">ჩასვით დაკოპირებული CSV ტექსტი ქვემოთ. სისტემა მას დაშლის, დაავალიდირებს და გაჩვენებთ ცხრილს ბაზაში ჩაწერამდე.</p>
                <textarea id="csvInput" rows="8" placeholder="Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR..." class="w-full bg-[#0B0F19] border border-gray-700 rounded-lg p-3 text-emerald-400 font-mono text-xs resize-none focus:outline-none focus:border-emerald-500"></textarea>
                <div class="flex gap-3 mt-4">
                    <button onclick="processCSV()" id="processCsvBtn" class="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white px-6 py-3 rounded-lg font-semibold text-lg">⚙️ მონაცემების დამუშავება და ვალიდაცია</button>
                    <button onclick="document.getElementById('csvInput').value=''" class="px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg font-semibold">გასუფთავება</button>
                </div>
            </div>

            <!-- CSV PREVIEW SECTION (Hidden initially) -->
            <div id="section-preview" class="hidden bg-[#0E1424] border border-gray-800 rounded-xl p-6 mb-8">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-lg font-bold text-white">👁️ დამუშავებული მონაცემების გადახედვა (<span id="matchCount">0</span> მატჩი)</h3>
                    <button onclick="saveToDatabase()" id="saveDbBtn" class="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2 rounded-lg font-semibold flex items-center gap-2">
                        💾 ბაზაში ჩაწერა (მალე)
                    </button>
                </div>
                <div class="overflow-x-auto max-h-96 border border-gray-700 rounded-lg">
                    <table class="w-full text-sm text-left text-gray-300">
                        <thead class="text-xs text-gray-400 uppercase bg-[#070A13] sticky top-0">
                            <tr>
                                <th class="px-4 py-3">#</th>
                                <th class="px-4 py-3">თარიღი</th>
                                <th class="px-4 py-3">მასპინძელი</th>
                                <th class="px-4 py-3">სტუმარი</th>
                                <th class="px-4 py-3 text-center">ანგარიში</th>
                                <th class="px-4 py-3 text-center">შედეგი</th>
                                <th class="px-4 py-3">მსაჯი</th>
                                <th class="px-4 py-3 text-center">დარტყმები (H/A)</th>
                            </tr>
                        </thead>
                        <tbody id="previewTableBody" class="divide-y divide-gray-700">
                            <!-- Rows will be injected here -->
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- PASTE SECTION -->
            <div id="section-paste" class="hidden bg-[#0E1424] border border-gray-800 rounded-xl p-6 mb-8">
                <h3 class="text-lg font-bold text-white mb-4">📋 მოთამაშეების ტექსტის დამუშავება</h3>
                <textarea id="pasteText" rows="8" placeholder="ჩასვი აქ championat.com-დან დაკოპირებული მოთამაშეების სია..." class="w-full bg-[#0B0F19] border border-gray-700 rounded-lg p-3 text-purple-400 font-mono text-xs resize-none focus:outline-none focus:border-purple-500"></textarea>
                <button onclick="startPasteParsing()" id="pasteBtn" class="mt-4 w-full bg-purple-600 hover:bg-purple-500 text-white px-6 py-3 rounded-lg font-semibold text-lg">🚀 AI-ით დამუშავება</button>
            </div>

            <!-- TEAM URL SECTION -->
            <div id="section-team" class="hidden bg-[#0E1424] border border-gray-800 rounded-xl p-6 mb-8">
                <h3 class="text-lg font-bold text-white mb-4">🎯 გუნდის URL სკაუტინგი</h3>
                <div class="flex gap-3">
                    <input id="targetUrl" type="text" value="https://www.championat.com/football/_england/tournament/6592/teams/268572/" class="flex-1 bg-[#070A13] border border-gray-700 rounded-lg p-3 text-emerald-400 font-mono text-sm">
                    <button onclick="startScouting()" id="startBtn" class="bg-emerald-600 hover:bg-emerald-500 text-white px-6 py-3 rounded-lg font-semibold">🚀 გააქტიურე</button>
                </div>
            </div>

            <!-- Live Logs -->
            <div class="bg-[#0E1424] border border-gray-800 rounded-xl p-6">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-lg font-bold text-white">📜 ლაივ ლოგები</h3>
                    <button onclick="clearLogs()" class="text-xs text-gray-400 hover:text-white">გასუფთავება</button>
                </div>
                <div id="terminal" class="bg-[#070A13] border border-gray-850 rounded-lg p-4 h-80 overflow-y-auto font-mono text-xs space-y-2">
                    <div class="text-gray-500">// სისტემა მზად არის. დაელოდე ბრძანებას...</div>
                </div>
            </div>
        </div>

        <script>
            let currentProcessedData = null;

            window.addEventListener('DOMContentLoaded', async () => {
                try {
                    const response = await fetch('/api/vault/status');
                    const status = await response.json();
                    for (const provider of ['google', 'groq']) {
                        const info = status[provider];
                        const statusEl = document.getElementById(provider + '-status');
                        if (info && info.has_key) {
                            statusEl.innerHTML = '✅ მზად (' + info.selected_model + ')';
                            statusEl.className = 'ml-auto px-2 py-1 bg-emerald-600 rounded text-xs';
                        } else {
                            statusEl.innerHTML = '⏸️ არ არის';
                            statusEl.className = 'ml-auto px-2 py-1 bg-gray-700 rounded text-xs';
                        }
                    }
                } catch (error) { console.error('Status check error:', error); }
            });

            function switchTab(mode) {
                ['import', 'paste', 'team'].forEach(m => {
                    document.getElementById('tab-' + m).className = mode === m ? 'tab-active px-6 py-3 rounded-lg font-semibold' : 'tab-inactive px-6 py-3 rounded-lg font-semibold';
                    document.getElementById('section-' + m).classList.toggle('hidden', mode !== m);
                });
                if (mode !== 'import') {
                    document.getElementById('section-preview').classList.add('hidden');
                }
            }

            async function setKey(provider) {
                const apiKey = document.getElementById(provider + '-key').value;
                if (!apiKey) { alert('ჩაწერე გასაღები'); return; }
                addLog('APIVault', '💾 ' + provider + ' გასაღების შენახვა...', 'info');
                try {
                    const response = await fetch('/api/vault/set-key', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ provider, api_key: apiKey })
                    });
                    const data = await response.json();
                    if (data.success) {
                        addLog('APIVault', '✅ ' + provider + ' გასაღები შენახულია Supabase-ში', 'success');
                        document.getElementById(provider + '-status').innerHTML = '✅ შენახულია';
                        document.getElementById(provider + '-status').className = 'ml-auto px-2 py-1 bg-yellow-600 rounded text-xs';
                    } else {
                        addLog('APIVault', '❌ ' + data.error, 'error');
                    }
                } catch (error) { addLog('APIVault', '❌ ' + error.message, 'error'); }
            }

            // ==========================================
            // CSV IMPORT LOGIC
            // ==========================================
            async function processCSV() {
                const csvData = document.getElementById('csvInput').value;
                const btn = document.getElementById('processCsvBtn');
                if (!csvData.trim()) { alert('ჩასვი CSV მონაცემები'); return; }

                btn.disabled = true;
                btn.textContent = '⏳ მუშაობს...';
                document.getElementById('section-preview').classList.add('hidden');
                clearLogs();

                addLog('CSVParser', '📖 ვიწყებ CSV ტექსტის წაკითხვას...', 'info');
                await new Promise(r => setTimeout(r, 500));

                const lines = csvData.trim().split('\\n');
                addLog('CSVParser', `📊 ნაპოვნია ${lines.length} სტრიქონი (სათაურის ჩათვლით)`, 'info');
                await new Promise(r => setTimeout(r, 500));

                try {
                    addLog('CSVParser', '⚙️ ვაწარმოებ სტრიქონების პარსინგს და ვალიდაციას...', 'info');
                    const response = await fetch('/api/import/csv', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ csv_data: csvData })
                    });
                    const result = await response.json();

                    if (result.success) {
                        addLog('CSVParser', `✅ წარმატება! დამუშავდა ${result.data.length} მატჩი`, 'success');
                        if (result.errors && result.errors.length > 0) {
                            addLog('CSVParser', `⚠️ გამოტოვებულია ${result.errors.length} სტრიქონი ფორმატის შეცდომის გამო`, 'warning');
                        }
                        currentProcessedData = result.data;
                        renderPreviewTable(result.data);
                    } else {
                        addLog('CSVParser', `❌ შეცდომა: ${result.error}`, 'error');
                    }
                } catch (error) {
                    addLog('CSVParser', `❌ კრიტიკული შეცდომა: ${error.message}`, 'error');
                } finally {
                    btn.disabled = false;
                    btn.textContent = '⚙️ მონაცემების დამუშავება და ვალიდაცია';
                }
            }

            function renderPreviewTable(matches) {
                document.getElementById('section-preview').classList.remove('hidden');
                document.getElementById('matchCount').textContent = matches.length;
                const tbody = document.getElementById('previewTableBody');
                tbody.innerHTML = '';

                matches.forEach(match => {
                    const resultColor = match.result === 'H' ? 'text-emerald-400' : (match.result === 'A' ? 'text-red-400' : 'text-yellow-400');
                    const resultText = match.result === 'H' ? 'მასპინძელი' : (match.result === 'A' ? 'სტუმარი' : 'ფრე');
                    
                    const row = document.createElement('tr');
                    row.className = 'hover:bg-[#0B0F19] transition-colors';
                    row.innerHTML = `
                        <td class="px-4 py-3 text-gray-500">${match.row}</td>
                        <td class="px-4 py-3">${match.date}</td>
                        <td class="px-4 py-3 font-semibold text-white">${match.home_team}</td>
                        <td class="px-4 py-3 font-semibold text-white">${match.away_team}</td>
                        <td class="px-4 py-3 text-center font-bold text-lg">${match.home_goals} - ${match.away_goals}</td>
                        <td class="px-4 py-3 text-center font-bold ${resultColor}">${resultText}</td>
                        <td class="px-4 py-3 text-gray-400 text-xs">${match.referee}</td>
                        <td class="px-4 py-3 text-center text-gray-400">${match.home_shots} / ${match.away_shots}</td>
                    `;
                    tbody.appendChild(row);
                });
                
                addLog('UI', '👁️ ვიზუალური გადახედვის ცხრილი აგებულია. შეამოწმეთ მონაცემები.', 'success');
            }

            function saveToDatabase() {
                addLog('DBWriter', '🚧 ფუნქცია "ბაზაში ჩაწერა" ამ ეტაპზე მზადების პროცესშია. მონაცემები ვალიდირებულია და მზად არის.', 'warning');
                alert('შენიშვნა: ბაზაში ჩაწერის ლოგიკა დაემატება შემდეგ ეტაპზე. ამ ეტაპზე მხოლოდ ვიზუალური ვალიდაციაა შესაძლებელი.');
            }

            // ==========================================
            // EXISTING LOGIC STUBS (To prevent errors)
            // ==========================================
            function startPasteParsing() {
                addLog('TextParser', '🚧 მოთამაშეების პარსინგი დროებით გათიშულია CSV იმპორტის სასარგებლოდ.', 'warning');
            }
            function startScouting() {
                addLog('TeamScout', '🚧 გუნდის URL სკაუტინგი დროებით გათიშულია CSV იმპორტის სასარგებლოდ.', 'warning');
            }

            // ==========================================
            // LOGGING UTILS
            // ==========================================
            function addLog(agent, message, type = 'info') {
                const terminal = document.getElementById('terminal');
                const log = document.createElement('div');
                log.className = 'log-entry';
                const colors = { 'info': 'text-blue-400', 'success': 'text-emerald-400', 'warning': 'text-yellow-400', 'error': 'text-red-400' };
                const agentColors = { 'CSVParser': 'text-emerald-400', 'TextParser': 'text-purple-400', 'TeamScout': 'text-emerald-400', 'APIVault': 'text-yellow-400', 'UI': 'text-blue-400', 'DBWriter': 'text-yellow-400' };
                const timestamp = new Date().toLocaleTimeString('ka-GE');
                log.innerHTML = '<span class="text-gray-600">[' + timestamp + ']</span> <strong class="' + (agentColors[agent] || 'text-gray-400') + '">[' + agent + ']</strong> <span class="' + colors[type] + '">' + message + '</span>';
                terminal.appendChild(log);
                terminal.scrollTop = terminal.scrollHeight;
            }

            function clearLogs() {
                document.getElementById('terminal').innerHTML = '<div class="text-gray-500">// ლოგები გასუფთავდა</div>';
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)