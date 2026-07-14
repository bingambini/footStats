import asyncio
import json
import os
import csv
import io
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from loguru import logger

try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False

app = FastAPI(title="FootStats API")

# ==========================================
# Logger
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
all_matches_data: List[Dict] = []

# ==========================================
# CSV Parser - ყველა სვეტის ამოღება
# ==========================================
def parse_csv_complete(csv_text: str) -> List[Dict]:
    """ამოიღებს ყველა სვეტს CSV ფაილიდან, ზუსტად იგივე სახელებით"""
    try:
        reader = csv.DictReader(io.StringIO(csv_text))
        matches = []
        
        for row in reader:
            # CSV DictReader ავტომატურად იყენებს სათაურის სახელებს
            # ამიტომ key-ები იქნება: Div, Date, Time, HomeTeam, AwayTeam, FTHG, FTAG, FTR, ...
            match_data = {}
            for key, value in row.items():
                if key:  # გამოტოვეთ ცარიელი key-ები
                    match_data[key.strip()] = value.strip() if value else ""
            
            # მხოლოდ იმ რიგების დამატება, რომლებსაც აქვთ HomeTeam და AwayTeam
            if match_data.get("HomeTeam") and match_data.get("AwayTeam"):
                matches.append(match_data)
        
        logger.info(f"✅ წარმატებით დამუშავდა {len(matches)} მატჩი")
        return matches
    
    except Exception as e:
        logger.error(f"❌ CSV პარსინგის შეცდომა: {e}")
        return []

# ==========================================
# API Endpoints
# ==========================================
@app.get("/")
async def root():
    return {"message": "FootStats API v2.0 - Fixed"}

@app.post("/api/import/csv")
async def import_csv(request: Request):
    """იმპორტავს CSV-ს ყველა სვეტით"""
    global all_matches_data
    
    try:
        body = await request.json()
        csv_data = body.get("csv_data", "")
        
        if not csv_data.strip():
            return {"success": False, "error": "CSV ცარიელია"}
        
        all_matches_data = parse_csv_complete(csv_data)
        
        # სტატისტიკის გამოთვლა
        total_matches = len(all_matches_data)
        total_goals = 0
        for m in all_matches_data:
            try:
                fthg = int(m.get("FTHG", 0) or 0)
                ftag = int(m.get("FTAG", 0) or 0)
                total_goals += fthg + ftag
            except:
                pass
        
        return {
            "success": True,
            "message": f"წარმატებით იმპორტირდა {total_matches} მატჩი",
            "matches_count": total_matches,
            "total_goals": total_goals,
            "sample_keys": list(all_matches_data[0].keys()) if all_matches_data else []
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/matches/all")
async def get_all_matches():
    """აბრუნებს ყველა მატჩს"""
    return {
        "success": True,
        "count": len(all_matches_data),
        "data": all_matches_data
    }

@app.post("/api/save/to-database")
async def save_to_database():
    """ინახავს მონაცემებს Supabase-ში"""
    if not HAS_SUPABASE:
        return {"success": False, "error": "Supabase არ არის დაყენებული"}
    
    supabase = get_supabase()
    if not supabase:
        return {"success": False, "error": "Supabase კლიენტი არ არის ინიციალიზებული"}
    
    if not all_matches_data:
        return {"success": False, "error": "მონაცემები ჯერ არ არის იმპორტირებული"}
    
    try:
        # ბატჩური ჩაწერა
        batch_size = 50
        total_inserted = 0
        
        for i in range(0, len(all_matches_data), batch_size):
            batch = all_matches_data[i:i + batch_size]
            try:
                supabase.table("premier_league_2025_2026").insert(batch).execute()
                total_inserted += len(batch)
                logger.info(f"✅ ჩაიწერა {total_inserted}/{len(all_matches_data)} მატჩი")
            except Exception as e:
                logger.error(f"❌ ბატჩის ჩაწერის შეცდომა: {e}")
        
        return {
            "success": True,
            "message": f"წარმატებით ჩაიწერა {total_inserted} მატჩი Supabase-ში",
            "inserted": total_inserted
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

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
        <title>FootStats Dashboard v2.0</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            @keyframes slideIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
            .log-entry { animation: slideIn 0.3s ease-out; }
            .glass { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); }
            .btn-disabled { opacity: 0.5; cursor: not-allowed; }
            .table-container { max-height: 600px; overflow: auto; }
            th { position: sticky; top: 0; background: #1e293b; z-index: 10; }
        </style>
    </head>
    <body class="bg-gradient-to-br from-[#0B0F19] to-[#1a1f2e] text-[#E2E8F0] font-sans min-h-screen">
        <div class="max-w-full mx-auto p-6">
            <!-- Header -->
            <div class="text-center mb-8">
                <h1 class="text-4xl font-bold text-white mb-2">⚽ FootStats Dashboard v2.0</h1>
                <p class="text-gray-400">Premier League 2025/2026 - ყველა სვეტი</p>
            </div>

            <!-- Stats Cards -->
            <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
                <div class="glass rounded-xl p-5">
                    <p class="text-gray-400 text-sm">სულ მატჩი</p>
                    <p class="text-3xl font-bold text-white mt-1" id="stat-matches">0</p>
                </div>
                <div class="glass rounded-xl p-5">
                    <p class="text-gray-400 text-sm">სულ გოლი</p>
                    <p class="text-3xl font-bold text-emerald-400 mt-1" id="stat-goals">0</p>
                </div>
                <div class="glass rounded-xl p-5">
                    <p class="text-gray-400 text-sm">სვეტები</p>
                    <p class="text-3xl font-bold text-blue-400 mt-1" id="stat-columns">0</p>
                </div>
                <div class="glass rounded-xl p-5 flex flex-col justify-center">
                    <button onclick="saveToDatabase()" id="saveBtn" class="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 px-4 rounded-lg btn-disabled" disabled>
                        💾 ბაზაში ჩაწერა
                    </button>
                </div>
            </div>

            <!-- Import Section -->
            <div class="glass rounded-xl p-6 mb-8">
                <h2 class="text-xl font-bold text-white mb-4">📥 CSV იმპორტი</h2>
                <textarea id="csvInput" rows="8" placeholder="ჩასვი CSV ფაილის შიგთავსი აქ..." class="w-full bg-[#0B0F19] border border-gray-700 rounded-lg p-4 text-emerald-400 font-mono text-xs resize-none focus:outline-none focus:border-emerald-500"></textarea>
                <div class="flex gap-3 mt-4">
                    <button onclick="importCSV()" id="importBtn" class="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-3 rounded-lg">
                        🚀 დამუშავება
                    </button>
                    <button onclick="document.getElementById('csvInput').value=''" class="px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg">
                        🗑️ გასუფთავება
                    </button>
                </div>
            </div>

            <!-- Matches Table -->
            <div class="glass rounded-xl p-6 mb-8">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-xl font-bold text-white">📋 მატჩების ცხრილი</h2>
                    <span class="px-3 py-1 bg-gray-800 rounded text-sm text-gray-400" id="tableInfo">0 მატჩი</span>
                </div>
                <div class="table-container border border-gray-700 rounded-lg">
                    <table class="w-full text-sm text-left">
                        <thead class="text-xs text-gray-400 uppercase bg-[#0F172A]">
                            <tr id="tableHeader">
                                <th class="px-3 py-2">იტვირთება...</th>
                            </tr>
                        </thead>
                        <tbody id="tableBody">
                            <tr>
                                <td class="px-3 py-4 text-center text-gray-500">ჩასვი CSV და დააჭირე "დამუშავება"-ს</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Logs -->
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
            let allMatchesData = [];
            let allColumns = [];

            async function importCSV() {
                const csv = document.getElementById('csvInput').value;
                const btn = document.getElementById('importBtn');
                
                if (!csv.trim()) {
                    addLog('❌ CSV ცარიელია', 'error');
                    return;
                }
                
                btn.disabled = true;
                btn.textContent = '⏳ მუშაობს...';
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
                        addLog(`📊 სვეტები: ${result.sample_keys ? result.sample_keys.length : 0}`, 'info');
                        
                        document.getElementById('stat-matches').textContent = result.matches_count;
                        document.getElementById('stat-goals').textContent = result.total_goals;
                        document.getElementById('stat-columns').textContent = result.sample_keys ? result.sample_keys.length : 0;
                        
                        await loadMatches();
                    } else {
                        addLog(`❌ ${result.error}`, 'error');
                    }
                } catch (error) {
                    addLog(`❌ ${error.message}`, 'error');
                } finally {
                    btn.disabled = false;
                    btn.textContent = '🚀 დამუშავება';
                }
            }

            async function loadMatches() {
                try {
                    const response = await fetch('/api/matches/all');
                    const result = await response.json();
                    
                    if (result.success && result.data.length > 0) {
                        allMatchesData = result.data;
                        allColumns = Object.keys(result.data[0]);
                        
                        document.getElementById('tableInfo').textContent = `${result.count} მატჩი × ${allColumns.length} სვეტი`;
                        
                        renderTable();
                        enableSaveButton();
                    }
                } catch (error) {
                    addLog(`❌ ${error.message}`, 'error');
                }
            }

            function renderTable() {
                const header = document.getElementById('tableHeader');
                const tbody = document.getElementById('tableBody');
                
                // ძირითადი სვეტები რომლებიც ყოველთვის უნდა ვაჩვენოთ
                const mainColumns = ['Div', 'Date', 'Time', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR', 'Referee', 'HS', 'AS', 'HC', 'AC'];
                
                // სათაური
                header.innerHTML = '<tr>' + mainColumns.map(col => 
                    `<th class="px-3 py-2 whitespace-nowrap">${col}</th>`
                ).join('') + '</tr>';
                
                // სხეული - ვაჩვენებთ მხოლოდ მთავარ სვეტებს
                tbody.innerHTML = allMatchesData.slice(0, 100).map(m => {
                    const resultColor = m.FTR === 'H' ? 'text-emerald-400' : m.FTR === 'A' ? 'text-red-400' : 'text-yellow-400';
                    const resultText = m.FTR === 'H' ? 'მასპინძელი' : m.FTR === 'A' ? 'სტუმარი' : 'ფრე';
                    
                    return `<tr class="border-b border-gray-800 hover:bg-[#1E293B]">
                        <td class="px-3 py-2 text-gray-400">${m.Div || '-'}</td>
                        <td class="px-3 py-2">${m.Date || '-'}</td>
                        <td class="px-3 py-2 text-gray-400">${m.Time || '-'}</td>
                        <td class="px-3 py-2 font-semibold text-white">${m.HomeTeam || '-'}</td>
                        <td class="px-3 py-2 font-semibold text-white">${m.AwayTeam || '-'}</td>
                        <td class="px-3 py-2 text-center font-bold text-lg">${m.FTHG || 0}</td>
                        <td class="px-3 py-2 text-center font-bold text-lg">${m.FTAG || 0}</td>
                        <td class="px-3 py-2 text-center font-bold ${resultColor}">${resultText}</td>
                        <td class="px-3 py-2 text-gray-400 text-xs">${m.Referee || '-'}</td>
                        <td class="px-3 py-2 text-center">${m.HS || 0}/${m.AS || 0}</td>
                        <td class="px-3 py-2 text-center">${m.HC || 0}/${m.AC || 0}</td>
                    </tr>`;
                }).join('');
                
                if (allMatchesData.length > 100) {
                    addLog(`ℹ️ ნაჩვენებია პირველი 100 მატჩი (სულ ${allMatchesData.length})`, 'info');
                }
            }

            function enableSaveButton() {
                const btn = document.getElementById('saveBtn');
                btn.disabled = false;
                btn.classList.remove('btn-disabled');
                btn.classList.add('animate-pulse');
                setTimeout(() => btn.classList.remove('animate-pulse'), 3000);
                addLog('✅ "ბაზაში ჩაწერა" ღილაკი აქტიური გახდა', 'success');
            }

            async function saveToDatabase() {
                const btn = document.getElementById('saveBtn');
                
                if (allMatchesData.length === 0) {
                    addLog('❌ ჯერ იმპორტირეთ მონაცემები', 'error');
                    return;
                }
                
                btn.disabled = true;
                btn.textContent = '⏳ ჩაწერა მიმდინარეობს...';
                addLog('💾 ბაზაში ჩაწერა იწყება...', 'info');
                
                try {
                    const response = await fetch('/api/save/to-database', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        addLog(`✅ ${result.message}`, 'success');
                    } else {
                        addLog(`❌ ${result.error}`, 'error');
                    }
                } catch (error) {
                    addLog(`❌ ${error.message}`, 'error');
                } finally {
                    btn.disabled = false;
                    btn.textContent = '💾 ბაზაში ჩაწერა';
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