import asyncio
import json
import os
import csv
import io
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from loguru import logger

try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False

app = FastAPI(title="FootStats API v4.0")

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
            key = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_KEY")
            
            logger.info(f"🔍 SUPABASE_URL: {'SET' if url else 'NOT SET'}")
            logger.info(f"🔍 SUPABASE_KEY: {'SET' if key else 'NOT SET'}")
            
            if url and key:
                _supabase_client = create_client(url, key)
                logger.info("✅ Supabase კლიენტი წარმატებით ინიციალიზდა")
            else:
                logger.error("❌ SUPABASE_URL ან SUPABASE_KEY არ არის დაყენებული!")
        except Exception as e:
            logger.error(f"❌ Supabase ინიციალიზაციის შეცდომა: {e}")
    return _supabase_client

# ==========================================
# In-Memory Storage
# ==========================================
matches_storage: List[Dict] = []
headers_storage: List[str] = []

# ==========================================
# 24 ძირითადი სვეტის მაპინგი (ბაზაში ჩასაწერად)
# ==========================================
COLUMN_MAP = {
    'Div': 'division',
    'Date': 'match_date',
    'Time': 'match_time',
    'HomeTeam': 'home_team',
    'AwayTeam': 'away_team',
    'Referee': 'referee',
    'FTHG': 'full_time_home_goals',
    'FTAG': 'full_time_away_goals',
    'FTR': 'full_time_result',
    'HTHG': 'half_time_home_goals',
    'HTAG': 'half_time_away_goals',
    'HTR': 'half_time_result',
    'HS': 'home_shots',
    'AS': 'away_shots',
    'HST': 'home_shots_on_target',
    'AST': 'away_shots_on_target',
    'HF': 'home_fouls',
    'AF': 'away_fouls',
    'HC': 'home_corners',
    'AC': 'away_corners',
    'HY': 'home_yellow_cards',
    'AY': 'away_yellow_cards',
    'HR': 'home_red_cards',
    'AR': 'away_red_cards'
}

NUMERIC_COLUMNS = [
    'FTHG', 'FTAG', 'HTHG', 'HTAG',
    'HS', 'AS', 'HST', 'AST', 'HF', 'AF',
    'HC', 'AC', 'HY', 'AY', 'HR', 'AR'
]

# ==========================================
# CSV Parser
# ==========================================
def parse_csv_complete(csv_text: str) -> Tuple[List[str], List[Dict]]:
    try:
        if csv_text.startswith('\ufeff'):
            csv_text = csv_text[1:]
        
        reader = csv.DictReader(io.StringIO(csv_text))
        all_headers = reader.fieldnames or []
        
        rows = []
        for row in reader:
            filtered_row = {}
            for col in all_headers:
                value = row.get(col, '').strip() if row.get(col) else ''
                if col in NUMERIC_COLUMNS:
                    try:
                        filtered_row[col] = int(float(value)) if value else 0
                    except:
                        filtered_row[col] = 0
                else:
                    filtered_row[col] = value
            rows.append(filtered_row)
        
        logger.success(f"✅ წარმატებით დამუშავდა {len(rows)} მატჩი, {len(all_headers)} სვეტი")
        return all_headers, rows
    except Exception as e:
        logger.error(f"❌ CSV პარსინგის შეცდომა: {e}")
        return [], []

# ==========================================
# API Endpoints
# ==========================================
@app.get("/")
async def root():
    return {
        "message": "FootStats API v4.0 - Database Viewer Ready",
        "status": "running",
        "matches_loaded": len(matches_storage)
    }

@app.post("/api/import/csv")
async def import_csv(request: Request):
    global matches_storage, headers_storage
    
    try:
        body = await request.json()
        csv_data = body.get("csv_data", "")
        
        if not csv_data.strip():
            return {"success": False, "error": "CSV ცარიელია"}
        
        headers_storage, matches_storage = parse_csv_complete(csv_data)
        
        total_goals = sum(
            (m.get("FTHG", 0) or 0) + (m.get("FTAG", 0) or 0) 
            for m in matches_storage
        )
        
        return {
            "success": True,
            "message": f"წარმატებით იმპორტირდა {len(matches_storage)} მატჩი",
            "matches_count": len(matches_storage),
            "columns_count": len(headers_storage),
            "total_goals": total_goals
        }
    except Exception as e:
        logger.error(f"❌ იმპორტის შეცდომა: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/matches/all")
async def get_all_matches():
    return {
        "success": True,
        "count": len(matches_storage),
        "headers": headers_storage,
        "data": matches_storage
    }

@app.post("/api/save/to-database")
async def save_to_database():
    logger.info("💾 ვიწყებ ბაზაში ჩაწერას...")
    
    if not HAS_SUPABASE:
        return {"success": False, "error": "Supabase არ არის დაყენებული"}
    
    supabase = get_supabase()
    if not supabase:
        return {"success": False, "error": "Supabase კლიენტი არ არის ინიციალიზებული"}
    
    if not matches_storage:
        return {"success": False, "error": "მონაცემები ცარიელია"}
    
    try:
        db_records = []
        for match in matches_storage:
            record = {}
            for csv_col, db_col in COLUMN_MAP.items():
                value = match.get(csv_col)
                if csv_col in NUMERIC_COLUMNS:
                    record[db_col] = int(value) if value else 0
                else:
                    record[db_col] = value if value else None
            db_records.append(record)
        
        logger.info(f"📝 მზად არის {len(db_records)} მატჩი ჩასაწერად (24 სვეტი)")
        
        batch_size = 50
        total_inserted = 0
        
        for i in range(0, len(db_records), batch_size):
            batch = db_records[i:i + batch_size]
            try:
                supabase.table("premier_league_2025_2026").insert(batch).execute()
                total_inserted += len(batch)
                logger.info(f"✅ ჩაიწერა {total_inserted}/{len(db_records)} მატჩი")
            except Exception as e:
                logger.error(f"❌ ბატჩის ჩაწერის შეცდომა: {e}")
                for record in batch:
                    try:
                        supabase.table("premier_league_2025_2026").insert(record).execute()
                        total_inserted += 1
                    except Exception as e2:
                        logger.error(f"❌ მატჩის ჩაწერის შეცდომა: {e2}")
        
        logger.success(f"🎉 წარმატებით ჩაიწერა {total_inserted} მატჩი")
        
        return {
            "success": True,
            "message": f"წარმატებით ჩაიწერა {total_inserted} მატჩი Supabase-ში",
            "inserted": total_inserted,
            "total": len(db_records)
        }
    except Exception as e:
        logger.error(f"❌ კრიტიკული შეცდომა: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/database/data")
async def get_database_data():
    """იღებს მონაცემებს Supabase-იდან ვიზუალიზაციისთვის"""
    supabase = get_supabase()
    if not supabase:
        return {"success": False, "error": "Supabase კლიენტი არ არის ინიციალიზებული"}
    
    try:
        # ვიღებთ ბოლო 100 ჩანაწერს, დალაგებულს ID-ს მიხედვით
        response = supabase.table("premier_league_2025_2026").select("*").order("id", desc=True).limit(100).execute()
        
        # UI-ში ქრონოლოგიური თანმიმდევრობით რომ იყოს, შევავრცობთ სიას
        data = response.data[::-1]
        
        return {
            "success": True,
            "count": len(data),
            "data": data
        }
    except Exception as e:
        logger.error(f"❌ ბაზიდან წაკითხვის შეცდომა: {e}")
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
        <title>FootStats Dashboard v4.0</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            @keyframes slideIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
            .log-entry { animation: slideIn 0.3s ease-out; }
            .glass { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); }
            .tab-active { background-color: #10b981; color: white; }
            .tab-inactive { background-color: #374151; color: #9ca3af; }
        </style>
    </head>
    <body class="bg-gradient-to-br from-[#0B0F19] to-[#1a1f2e] text-[#E2E8F0] font-sans min-h-screen">
        <div class="max-w-full mx-auto p-6">
            <div class="text-center mb-8">
                <h1 class="text-4xl font-bold text-white mb-2">⚽ FootStats Dashboard v4.0</h1>
                <p class="text-gray-400">იმპორტი, ვიზუალიზაცია და Supabase ბაზაში შენახვა</p>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
                <div class="glass rounded-xl p-5">
                    <p class="text-gray-400 text-sm">იმპორტირებული</p>
                    <p class="text-3xl font-bold text-white mt-1" id="stat-imported">0</p>
                </div>
                <div class="glass rounded-xl p-5">
                    <p class="text-gray-400 text-sm">სულ სვეტები</p>
                    <p class="text-3xl font-bold text-emerald-400 mt-1" id="stat-columns">0</p>
                </div>
                <div class="glass rounded-xl p-5">
                    <p class="text-gray-400 text-sm">სულ გოლი</p>
                    <p class="text-3xl font-bold text-blue-400 mt-1" id="stat-goals">0</p>
                </div>
                <div class="glass rounded-xl p-5">
                    <p class="text-gray-400 text-sm">ბაზაში ჩაწერილი</p>
                    <p class="text-3xl font-bold text-purple-400 mt-1" id="stat-db">0</p>
                </div>
                <div class="glass rounded-xl p-5 flex flex-col justify-center">
                    <button onclick="saveToDatabase()" id="saveBtn" class="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed" disabled>
                        💾 ბაზაში ჩაწერა
                    </button>
                </div>
            </div>

            <div class="flex gap-2 mb-6">
                <button onclick="switchTab('import')" id="tab-import" class="tab-active px-6 py-3 rounded-lg font-semibold">📥 იმპორტი</button>
                <button onclick="switchTab('data')" id="tab-data" class="tab-inactive px-6 py-3 rounded-lg font-semibold">📊 მონაცემები</button>
                <button onclick="switchTab('database')" id="tab-database" class="tab-inactive px-6 py-3 rounded-lg font-semibold">🗄️ ბაზა</button>
            </div>

            <div id="section-import" class="glass rounded-xl p-6 mb-8">
                <h2 class="text-2xl font-bold text-white mb-4">📥 CSV იმპორტი</h2>
                <textarea id="csvInput" rows="10" placeholder="ჩასვი CSV ფაილი აქ..." class="w-full bg-[#0B0F19] border border-gray-700 rounded-lg p-4 text-emerald-400 font-mono text-xs resize-none focus:outline-none focus:border-emerald-500"></textarea>
                <div class="flex gap-3 mt-4">
                    <button onclick="importCSV()" id="importBtn" class="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-3 rounded-lg">🚀 იმპორტი</button>
                    <button onclick="document.getElementById('csvInput').value=''" class="px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg">🗑️ გასუფთავება</button>
                </div>
            </div>

            <div id="section-data" class="hidden glass rounded-xl p-6 mb-8">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-2xl font-bold text-white">📊 მონაცემთა ცხრილი (მეხსიერებიდან)</h2>
                    <span class="px-3 py-1 bg-gray-800 rounded text-sm text-gray-400" id="tableInfo">0 მატჩი</span>
                </div>
                <div class="overflow-x-auto max-h-[600px] border border-gray-700 rounded-lg">
                    <table class="w-full text-xs text-left">
                        <thead class="text-xs text-gray-400 uppercase bg-[#0F172A] sticky top-0">
                            <tr id="tableHeader"><th class="px-2 py-2">იტვირთება...</th></tr>
                        </thead>
                        <tbody id="tableBody">
                            <tr><td class="px-3 py-4 text-center text-gray-500">ჩასვი CSV და დააჭირე "იმპორტი"-ს</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div id="section-database" class="hidden glass rounded-xl p-6 mb-8">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-2xl font-bold text-white">🗄️ ბაზაში შენახული მონაცემები (Supabase)</h2>
                    <button onclick="loadDatabaseData()" class="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg text-sm font-semibold">🔄 განახლება</button>
                </div>
                <div class="overflow-x-auto max-h-[600px] border border-gray-700 rounded-lg">
                    <table class="w-full text-xs text-left">
                        <thead class="text-xs text-gray-400 uppercase bg-[#0F172A] sticky top-0">
                            <tr id="dbTableHeader">
                                <th class="px-2 py-2">დააჭირე "განახლება"-ს</th>
                            </tr>
                        </thead>
                        <tbody id="dbTableBody">
                            <tr><td class="px-3 py-4 text-center text-gray-500" colspan="24">ბაზიდან მონაცემების ჩასატვირთად დააჭირე ღილაკს.</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

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
            let dataLoaded = false;

            function switchTab(tab) {
                ['import', 'data', 'database'].forEach(t => {
                    document.getElementById('tab-' + t).className = tab === t ? 'tab-active px-6 py-3 rounded-lg font-semibold' : 'tab-inactive px-6 py-3 rounded-lg font-semibold';
                    document.getElementById('section-' + t).classList.toggle('hidden', tab !== t);
                });
                
                if (tab === 'database') {
                    loadDatabaseData();
                }
            }

            async function importCSV() {
                const csv = document.getElementById('csvInput').value;
                const btn = document.getElementById('importBtn');
                
                if (!csv.trim()) {
                    addLog('❌ CSV ცარიელია', 'error');
                    return;
                }
                
                btn.disabled = true;
                btn.textContent = '⏳ იმპორტი...';
                addLog('🚀 იმპორტი იწყება...', 'info');
                
                try {
                    const response = await fetch('/api/import/csv', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ csv_data: csv })
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        addLog(`✅ ${result.message}`, 'success');
                        addLog(`📊 სვეტები: ${result.columns_count}`, 'info');
                        addLog(`⚽ სულ გოლი: ${result.total_goals}`, 'info');
                        
                        document.getElementById('stat-imported').textContent = result.matches_count;
                        document.getElementById('stat-columns').textContent = result.columns_count;
                        document.getElementById('stat-goals').textContent = result.total_goals;
                        
                        dataLoaded = true;
                        document.getElementById('saveBtn').disabled = false;
                        
                        await loadMatches();
                    } else {
                        addLog(`❌ ${result.error}`, 'error');
                    }
                } catch (error) {
                    addLog(`❌ ${error.message}`, 'error');
                } finally {
                    btn.disabled = false;
                    btn.textContent = '🚀 იმპორტი';
                }
            }

            async function saveToDatabase() {
                const btn = document.getElementById('saveBtn');
                
                if (!dataLoaded) {
                    addLog('❌ ჯერ იმპორტირე მონაცემები', 'error');
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
                        addLog(`📊 ჩაწერილი: ${result.inserted}/${result.total} მატჩი`, 'info');
                        document.getElementById('stat-db').textContent = result.inserted;
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

            async function loadMatches() {
                addLog('🔄 მონაცემების ჩატვირთვა...', 'info');
                try {
                    const response = await fetch('/api/matches/all');
                    const result = await response.json();
                    if (result.success) {
                        renderTable(result.data, result.headers);
                        addLog(`✅ ჩაიტვირთა ${result.count} მატჩი`, 'success');
                    }
                } catch (error) {
                    addLog(`❌ ${error.message}`, 'error');
                }
            }

            async function loadDatabaseData() {
                addLog('🔄 ბაზიდან მონაცემების ჩატვირთვა...', 'info');
                try {
                    const response = await fetch('/api/database/data');
                    const result = await response.json();
                    
                    if (result.success) {
                        renderDatabaseTable(result.data);
                        document.getElementById('stat-db').textContent = result.count;
                        addLog(`✅ ბაზიდან ჩაიტვირთა ${result.count} ჩანაწერი`, 'success');
                    } else {
                        addLog(`❌ ${result.error}`, 'error');
                    }
                } catch (error) {
                    addLog(`❌ ${error.message}`, 'error');
                }
            }

            function renderTable(matches, headers) {
                const header = document.getElementById('tableHeader');
                const tbody = document.getElementById('tableBody');
                header.innerHTML = '<tr>' + headers.map(h => `<th class="px-2 py-2">${h}</th>`).join('') + '</tr>';
                tbody.innerHTML = matches.slice(0, 100).map(m => {
                    return '<tr class="border-b border-gray-800 hover:bg-[#1E293B]">' + 
                        headers.map(h => {
                            const val = m[h] !== null && m[h] !== undefined ? m[h] : '-';
                            return `<td class="px-2 py-1 whitespace-nowrap">${val}</td>`;
                        }).join('') + '</tr>';
                }).join('');
                document.getElementById('tableInfo').textContent = `${matches.length} მატჩი (ნაჩვენებია პირველი 100)`;
            }

            function renderDatabaseTable(data) {
                const header = document.getElementById('dbTableHeader');
                const tbody = document.getElementById('dbTableBody');
                
                if (!data || data.length === 0) {
                    header.innerHTML = '<th class="px-2 py-2">ბაზა ცარიელია</th>';
                    tbody.innerHTML = '<tr><td class="px-3 py-4 text-center text-gray-500" colspan="24">ბაზაში მონაცემები ჯერ არ არის ჩაწერილი.</td></tr>';
                    return;
                }
                
                const columns = ['match_date', 'home_team', 'full_time_home_goals', 'full_time_away_goals', 'full_time_result', 'half_time_home_goals', 'half_time_away_goals', 'half_time_result', 'referee', 'home_shots', 'away_shots', 'home_shots_on_target', 'away_shots_on_target', 'home_fouls', 'away_fouls', 'home_corners', 'away_corners', 'home_yellow_cards', 'away_yellow_cards', 'home_red_cards', 'away_red_cards'];
                
                const colNames = {
                    'match_date': 'თარიღი', 'home_team': 'მასპინძელი', 'full_time_home_goals': 'გოლი (ს)',
                    'full_time_away_goals': 'გოლი (სტ)', 'full_time_result': 'შედეგი', 'half_time_home_goals': 'HT გოლი (ს)',
                    'half_time_away_goals': 'HT გოლი (სტ)', 'half_time_result': 'HT შედეგი', 'referee': 'მსაჯი',
                    'home_shots': 'დარტყმები (ს)', 'away_shots': 'დარტყმები (სტ)', 'home_shots_on_target': 'კარში (ს)',
                    'away_shots_on_target': 'კარში (სტ)', 'home_fouls': 'ჯარიმა (ს)', 'away_fouls': 'ჯარიმა (სტ)',
                    'home_corners': 'კუთხური (ს)', 'away_corners': 'კუთხური (სტ)', 'home_yellow_cards': 'ყვითელი (ს)',
                    'away_yellow_cards': 'ყვითელი (სტ)', 'home_red_cards': 'წითელი (ს)', 'away_red_cards': 'წითელი (სტ)'
                };

                header.innerHTML = '<tr>' + columns.map(col => `<th class="px-2 py-2">${colNames[col] || col}</th>`).join('') + '</tr>';
                
                tbody.innerHTML = data.map(row => {
                    return '<tr class="border-b border-gray-800 hover:bg-[#1E293B]">' + 
                        columns.map(col => {
                            let val = row[col];
                            if (val === null || val === undefined) val = '-';
                            let cls = '';
                            if (col === 'full_time_result') {
                                if (val === 'H') cls = 'text-emerald-400 font-bold';
                                else if (val === 'A') cls = 'text-red-400 font-bold';
                                else if (val === 'D') cls = 'text-yellow-400 font-bold';
                            }
                            return `<td class="px-2 py-1 whitespace-nowrap ${cls}">${val}</td>`;
                        }).join('') + '</tr>';
                }).join('');
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