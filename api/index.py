import asyncio
import json
import os
import csv
import io
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
# Logger
# ==========================================
logger.remove()
logger.add(lambda msg: print(msg.strip()), format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan> - <level>{message}</level>")

# ==========================================
# Supabase Client
# ==========================================
_supabase = None
def get_supabase():
    global _supabase
    if _supabase is None:
        try:
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_KEY")
            if url and key:
                _supabase = create_client(url, key)
                logger.info("✅ Supabase კლიენტი ინიციალიზდა")
        except Exception as e:
            logger.error(f"❌ Supabase შეცდომა: {e}")
    return _supabase

# ==========================================
# In-Memory Storage
# ==========================================
all_matches_data = []
all_headers = []

# ==========================================
# CSV Parser - მხოლოდ 24 ძირითადი სვეტი
# ==========================================
# სვეტები რომლებიც უნდა ჩაიწეროს (კოეფიციენტების გარეშე)
REQUIRED_COLUMNS = [
    "Div", "Date", "Time", "HomeTeam", "AwayTeam", "Referee",
    "FTHG", "FTAG", "FTR", "HTHG", "HTAG", "HTR",
    "HS", "AS", "HST", "AST", "HF", "AF",
    "HC", "AC", "HY", "AY", "HR", "AR"
]

# CSV სათაურიდან DB სვეტებზე მაპინგი
COLUMN_MAP = {
    "Div": "division",
    "Date": "match_date",
    "Time": "match_time",
    "HomeTeam": "home_team",
    "AwayTeam": "away_team",
    "Referee": "referee",
    "FTHG": "full_time_home_goals",
    "FTAG": "full_time_away_goals",
    "FTR": "full_time_result",
    "HTHG": "half_time_home_goals",
    "HTAG": "half_time_away_goals",
    "HTR": "half_time_result",
    "HS": "home_shots",
    "AS": "away_shots",
    "HST": "home_shots_on_target",
    "AST": "away_shots_on_target",
    "HF": "home_fouls",
    "AF": "away_fouls",
    "HC": "home_corners",
    "AC": "away_corners",
    "HY": "home_yellow_cards",
    "AY": "away_yellow_cards",
    "HR": "home_red_cards",
    "AR": "away_red_cards"
}

# რიცხვითი სვეტები
NUMERIC_COLUMNS = [
    "FTHG", "FTAG", "HTHG", "HTAG",
    "HS", "AS", "HST", "AST", "HF", "AF",
    "HC", "AC", "HY", "AY", "HR", "AR"
]

def parse_csv_for_db(csv_text: str) -> List[Dict]:
    """პარსავს CSV-ს და ამოიღებს მხოლოდ 24 ძირითად სვეტს"""
    try:
        reader = csv.DictReader(io.StringIO(csv_text))
        csv_headers = reader.fieldnames or []
        
        records = []
        skipped = 0
        
        for row in reader:
            record = {}
            valid = True
            
            for csv_col in REQUIRED_COLUMNS:
                if csv_col not in csv_headers:
                    continue
                
                db_col = COLUMN_MAP.get(csv_col)
                if not db_col:
                    continue
                
                value = row.get(csv_col, "").strip()
                
                if csv_col in NUMERIC_COLUMNS:
                    if value:
                        try:
                            record[db_col] = int(float(value))
                        except:
                            record[db_col] = 0
                    else:
                        record[db_col] = 0
                else:
                    record[db_col] = value if value else None
            
            if record.get("home_team") and record.get("away_team"):
                records.append(record)
            else:
                skipped += 1
        
        logger.info(f"✅ დამუშავდა {len(records)} მატჩი, გამოტოვებული: {skipped}")
        return records
    
    except Exception as e:
        logger.error(f"❌ CSV პარსინგის შეცდომა: {e}")
        return []

def parse_csv_all_columns(csv_text: str) -> Tuple[List[str], List[Dict]]:
    """პარსავს CSV-ს ყველა სვეტით (ვიზუალიზაციისთვის)"""
    try:
        reader = csv.DictReader(io.StringIO(csv_text))
        headers = reader.fieldnames or []
        
        rows = []
        for row in reader:
            if any(v and v.strip() for v in row.values()):
                rows.append({k: v.strip() if v else None for k, v in row.items()})
        
        return headers, rows
    except Exception as e:
        logger.error(f"❌ შეცდომა: {e}")
        return [], []

# ==========================================
# API Endpoints
# ==========================================
@app.get("/")
async def root():
    return {"message": "FootStats API v8.0 - No Odds"}

@app.post("/api/import/csv")
async def import_csv(request: Request):
    """იმპორტავს CSV-ს ყველა სვეტით (ვიზუალიზაციისთვის)"""
    global all_matches_data, all_headers
    
    try:
        body = await request.json()
        csv_data = body.get("csv_data", "")
        
        if not csv_data.strip():
            return {"success": False, "error": "CSV ცარიელია"}
        
        all_headers, all_matches_data = parse_csv_all_columns(csv_data)
        
        # სტატისტიკა
        total_goals = 0
        for m in all_matches_data:
            try:
                total_goals += int(m.get("FTHG", 0) or 0) + int(m.get("FTAG", 0) or 0)
            except:
                pass
        
        return {
            "success": True,
            "message": f"წარმატებით იმპორტირდა {len(all_matches_data)} მატჩი",
            "matches_count": len(all_matches_data),
            "columns_count": len(all_headers),
            "total_goals": total_goals
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/matches/all")
async def get_all_matches():
    """აბრუნებს ყველა მატჩს ყველა სვეტით"""
    return {
        "success": True,
        "count": len(all_matches_data),
        "headers": all_headers,
        "data": all_matches_data
    }

@app.post("/api/save/to-database")
async def save_to_database():
    """ინახავს მონაცემებს Supabase-ში - მხოლოდ 24 ძირითადი სვეტი, კოეფიციენტების გარეშე"""
    global all_matches_data
    
    if not HAS_SUPABASE:
        return {"success": False, "error": "Supabase არ არის დაყენებული"}
    
    supabase = get_supabase()
    if not supabase:
        return {"success": False, "error": "Supabase კლიენტი არ არის ინიციალიზებული"}
    
    if not all_matches_data:
        return {"success": False, "error": "მონაცემები ჯერ არ არის იმპორტირებული"}
    
    try:
        # ვიღებთ ორიგინალურ CSV-ს მეხსიერებიდან და ვპარსავთ მხოლოდ 24 სვეტს
        # რადგან all_matches_data შეიცავს ყველა სვეტს, ჩვენ ხელახლა ვპარსავთ
        # ამიტომ საჭიროა CSV ტექსტი შევინახოთ
        
        # ალტერნატიულად, all_matches_data-დან ვიღებთ მხოლოდ საჭირო ველებს
        records_to_save = []
        for match in all_matches_data:
            record = {}
            for csv_col, db_col in COLUMN_MAP.items():
                value = match.get(csv_col)
                if csv_col in NUMERIC_COLUMNS:
                    try:
                        record[db_col] = int(float(value)) if value else 0
                    except:
                        record[db_col] = 0
                else:
                    record[db_col] = value if value else None
            
            if record.get("home_team") and record.get("away_team"):
                records_to_save.append(record)
        
        logger.info(f"📝 მზად არის {len(records_to_save)} მატჩი ჩასაწერად (24 სვეტი, კოეფიციენტების გარეშე)")
        
        # ბატჩური ჩაწერა (50 მატჩი)
        batch_size = 50
        total_inserted = 0
        errors = []
        
        for i in range(0, len(records_to_save), batch_size):
            batch = records_to_save[i:i + batch_size]
            try:
                supabase.table("premier_league_2025_2026").insert(batch).execute()
                total_inserted += len(batch)
                logger.info(f"✅ ჩაიწერა {total_inserted}/{len(records_to_save)} მატჩი")
            except Exception as e:
                error_msg = f"ბატჩი {i//batch_size + 1}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"❌ {error_msg}")
        
        result = {
            "success": True,
            "message": f"წარმატებით ჩაიწერა {total_inserted} მატჩი Supabase-ში",
            "inserted": total_inserted,
            "total": len(records_to_save),
            "columns_saved": 24,
            "columns_skipped": len(all_headers) - 24 if all_headers else 0
        }
        
        if errors:
            result["errors"] = errors
        
        return result
    
    except Exception as e:
        logger.error(f"❌ კრიტიკული შეცდომა: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/database/stats")
async def get_database_stats():
    """აბრუნებს ბაზაში ჩაწერილი მონაცემების სტატისტიკას"""
    supabase = get_supabase()
    if not supabase:
        return {"success": False, "error": "Supabase არ არის"}
    
    try:
        response = supabase.table("premier_league_2025_2026").select("id", count="exact").execute()
        return {
            "success": True,
            "total_matches": response.count
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
        <title>FootStats Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            @keyframes slideIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
            .log-entry { animation: slideIn 0.3s ease-out; }
            .glass { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); }
            .btn-disabled { opacity: 0.5; cursor: not-allowed; }
        </style>
    </head>
    <body class="bg-gradient-to-br from-[#0B0F19] to-[#1a1f2e] text-[#E2E8F0] font-sans min-h-screen">
        <div class="max-w-7xl mx-auto p-6">
            <div class="text-center mb-8">
                <h1 class="text-4xl font-bold text-white mb-2">⚽ FootStats Dashboard</h1>
                <p class="text-gray-400">Premier League 2025/2026 - 24 ძირითადი სვეტი (კოეფიციენტების გარეშე)</p>
            </div>

            <!-- სტატისტიკის ბარათები -->
            <div class="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
                <div class="glass rounded-xl p-5">
                    <p class="text-gray-400 text-sm">იმპორტირებული</p>
                    <p class="text-3xl font-bold text-white mt-1" id="stat-imported">0</p>
                </div>
                <div class="glass rounded-xl p-5">
                    <p class="text-gray-400 text-sm">სვეტები</p>
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
                <div class="glass rounded-xl p-5 flex items-center justify-center">
                    <button onclick="saveToDatabase()" id="saveBtn" class="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 px-4 rounded-lg btn-disabled" disabled>
                        💾 ბაზაში შენახვა
                    </button>
                </div>
            </div>

            <!-- CSV იმპორტი -->
            <div class="glass rounded-xl p-6 mb-8">
                <h2 class="text-xl font-bold text-white mb-4">📥 CSV ფაილის იმპორტი</h2>
                <p class="text-gray-400 text-sm mb-3">ჩასვი football-data.co.uk ფორმატის CSV ტექსტი. სისტემა ავტომატურად ამოიღებს 24 ძირითად სვეტს (კოეფიციენტების გარეშე).</p>
                <textarea id="csvInput" rows="8" placeholder="Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR..." class="w-full bg-[#0B0F19] border border-gray-700 rounded-lg p-4 text-emerald-400 font-mono text-xs resize-none focus:outline-none focus:border-emerald-500"></textarea>
                <div class="flex gap-3 mt-4">
                    <button onclick="importCSV()" id="importBtn" class="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-3 rounded-lg">🚀 დამუშავება</button>
                    <button onclick="document.getElementById('csvInput').value=''; resetUI()" class="px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg">🗑️ გასუფთავება</button>
                </div>
            </div>

            <!-- მონაცემთა ცხრილი -->
            <div class="glass rounded-xl p-6 mb-8">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-xl font-bold text-white">📋 მონაცემების გადახედვა</h2>
                    <span class="px-3 py-1 bg-gray-800 rounded text-sm text-gray-400" id="tableInfo">0 მატჩი</span>
                </div>
                <div class="overflow-x-auto max-h-[500px] border border-gray-700 rounded-lg">
                    <table class="w-full text-xs text-left">
                        <thead class="text-xs text-gray-400 uppercase bg-[#0F172A] sticky top-0">
                            <tr id="tableHeader">
                                <th class="px-3 py-2">იტვირთება...</th>
                            </tr>
                        </thead>
                        <tbody id="tableBody">
                            <tr><td class="px-3 py-4 text-center text-gray-500">ჩასვი CSV და დააჭირე "დამუშავება"-ს</td></tr>
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
            let dataLoaded = false;

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
                        addLog(`📊 სვეტები: ${result.columns_count}`, 'info');
                        addLog(`⚽ სულ გოლი: ${result.total_goals}`, 'info');
                        
                        document.getElementById('stat-imported').textContent = result.matches_count;
                        document.getElementById('stat-columns').textContent = result.columns_count;
                        document.getElementById('stat-goals').textContent = result.total_goals;
                        
                        dataLoaded = true;
                        enableSaveButton();
                        await loadTable();
                        await loadDBStats();
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

            async function saveToDatabase() {
                if (!dataLoaded) {
                    addLog('⚠️ ჯერ დაამუშავე CSV', 'warning');
                    return;
                }
                
                const btn = document.getElementById('saveBtn');
                btn.disabled = true;
                btn.textContent = '⏳ ჩაწერა მიმდინარეობს...';
                addLog('💾 ბაზაში ჩაწერა იწყება (24 სვეტი, კოეფიციენტების გარეშე)...', 'info');
                
                try {
                    const response = await fetch('/api/save/to-database', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        addLog(`✅ ${result.message}`, 'success');
                        addLog(`📊 ჩაწერილი: ${result.inserted}/${result.total} მატჩი`, 'info');
                        addLog(`📋 სვეტები: ${result.columns_saved} (გამოტოვებული: ${result.columns_skipped} კოეფიციენტი)`, 'info');
                        
                        if (result.errors && result.errors.length > 0) {
                            addLog(`⚠️ ${result.errors.length} შეცდომა`, 'warning');
                        }
                        
                        await loadDBStats();
                    } else {
                        addLog(`❌ ${result.error}`, 'error');
                    }
                } catch (error) {
                    addLog(`❌ ${error.message}`, 'error');
                } finally {
                    btn.disabled = false;
                    btn.textContent = '💾 ბაზაში შენახვა';
                }
            }

            function enableSaveButton() {
                const btn = document.getElementById('saveBtn');
                btn.disabled = false;
                btn.classList.remove('btn-disabled');
                btn.classList.add('animate-pulse');
                setTimeout(() => btn.classList.remove('animate-pulse'), 3000);
            }

            async function loadTable() {
                try {
                    const response = await fetch('/api/matches/all');
                    const result = await response.json();
                    
                    if (result.success && result.data.length > 0) {
                        // ვაჩვენებთ მხოლოდ 24 ძირითად სვეტს
                        const mainCols = ["Date","HomeTeam","FTHG","FTAG","FTR","HTHG","HTAG","HTR","Referee","HS","AS","HST","AST","HF","AF","HC","AC","HY","AY","HR","AR"];
                        
                        document.getElementById('tableHeader').innerHTML = '<tr>' + mainCols.map(c => `<th class="px-3 py-2 whitespace-nowrap">${c}</th>`).join('') + '</tr>';
                        
                        document.getElementById('tableBody').innerHTML = result.data.slice(0, 100).map(m => {
                            const resultColor = m.FTR === 'H' ? 'text-emerald-400' : m.FTR === 'A' ? 'text-red-400' : 'text-yellow-400';
                            return `<tr class="border-b border-gray-800 hover:bg-[#1E293B]">
                                ${mainCols.map(c => {
                                    const val = m[c] || '-';
                                    const cls = c === 'FTR' ? resultColor + ' font-bold' : '';
                                    return `<td class="px-3 py-2 whitespace-nowrap ${cls}">${val}</td>`;
                                }).join('')}
                            </tr>`;
                        }).join('');
                        
                        document.getElementById('tableInfo').textContent = `${result.data.length} მატჩი (ნაჩვენებია პირველი 100)`;
                        addLog(`📋 ცხრილი აგებულია: ${result.data.length} მატჩი`, 'success');
                    }
                } catch (error) {
                    addLog(`❌ ${error.message}`, 'error');
                }
            }

            async function loadDBStats() {
                try {
                    const response = await fetch('/api/database/stats');
                    const result = await response.json();
                    if (result.success) {
                        document.getElementById('stat-db').textContent = result.total_matches;
                    }
                } catch (error) {
                    console.error(error);
                }
            }

            function resetUI() {
                dataLoaded = false;
                const btn = document.getElementById('saveBtn');
                btn.disabled = true;
                btn.classList.add('btn-disabled');
                document.getElementById('stat-imported').textContent = '0';
                document.getElementById('stat-columns').textContent = '0';
                document.getElementById('stat-goals').textContent = '0';
                document.getElementById('tableHeader').innerHTML = '<tr><th class="px-3 py-2">იტვირთება...</th></tr>';
                document.getElementById('tableBody').innerHTML = '<tr><td class="px-3 py-4 text-center text-gray-500">ჩასვი CSV და დააჭირე "დამუშავება"-ს</td></tr>';
                document.getElementById('tableInfo').textContent = '0 მატჩი';
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

            // ჩატვირთვისას
            loadDBStats();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)