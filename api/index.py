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
# In-Memory Storage
# ==========================================
matches_storage: List[Dict] = []
headers_storage: List[str] = []

# ==========================================
# CSV Parser - გამართული ვერსია
# ==========================================
def parse_csv_complete(csv_text: str) -> Tuple[List[str], List[Dict]]:
    """პარსავს CSV-ს და ამოიღებს ყველა სვეტს"""
    try:
        # ვშლით BOM-ს თუ არის
        if csv_text.startswith('\ufeff'):
            csv_text = csv_text[1:]
        
        # ვიყენებთ csv.reader-ს ნაცვლად DictReader-ისა
        lines = csv_text.strip().split('\n')
        
        if len(lines) < 2:
            logger.error("CSV ფაილი ცარიელია ან არასრულია")
            return [], []
        
        # პირველი სტრიქონი არის header
        header_line = lines[0]
        headers = [h.strip() for h in header_line.split(',')]
        
        logger.info(f"ნაპოვნია {len(headers)} სვეტი")
        
        # დანარჩენი სტრიქონები არის მონაცემები
        matches = []
        for i, line in enumerate(lines[1:], start=1):
            if not line.strip():
                continue
            
            # ვყოფთ მძიმით
            values = [v.strip() for v in line.split(',')]
            
            # ვქმნით dictionary-ს
            match_data = {}
            for j, header in enumerate(headers):
                if j < len(values):
                    value = values[j]
                    # ვცდილობთ რიცხვად კონვერტაციას
                    if value:
                        try:
                            if '.' in value:
                                match_data[header] = float(value)
                            else:
                                match_data[header] = int(value)
                        except ValueError:
                            match_data[header] = value
                    else:
                        match_data[header] = None
                else:
                    match_data[header] = None
            
            matches.append(match_data)
        
        logger.success(f"წარმატებით დამუშავდა {len(matches)} მატჩი")
        return headers, matches
    
    except Exception as e:
        logger.error(f"CSV პარსინგის შეცდომა: {e}")
        return [], []

# ==========================================
# API Endpoints
# ==========================================
@app.get("/")
async def root():
    return {
        "message": "FootStats API v4.0 - Full CSV Parser",
        "status": "running",
        "matches_loaded": len(matches_storage)
    }

@app.post("/api/import/csv")
async def import_csv(request: Request):
    """იმპორტავს CSV-ს"""
    global matches_storage, headers_storage
    
    try:
        body = await request.json()
        csv_data = body.get("csv_data", "")
        
        if not csv_data.strip():
            return {"success": False, "error": "CSV ცარიელია"}
        
        logger.info(f"CSV იმპორტი იწყება ({len(csv_data)} სიმბოლო)")
        
        headers_storage, matches_storage = parse_csv_complete(csv_data)
        
        if not matches_storage:
            return {"success": False, "error": "მონაცემები ვერ მოიძებნა"}
        
        # სტატისტიკა
        total_matches = len(matches_storage)
        total_goals = sum(
            (m.get("FTHG") or 0) + (m.get("FTAG") or 0) 
            for m in matches_storage
        )
        
        return {
            "success": True,
            "message": f"წარმატებით იმპორტირდა {total_matches} მატჩი",
            "matches_count": total_matches,
            "columns_count": len(headers_storage),
            "total_goals": total_goals,
            "headers": headers_storage[:10]  # პირველი 10 სვეტი
        }
    
    except Exception as e:
        logger.error(f"იმპორტის შეცდომა: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/matches/all")
async def get_all_matches():
    """აბრუნებს ყველა მატჩს"""
    return {
        "success": True,
        "count": len(matches_storage),
        "headers": headers_storage,
        "data": matches_storage[:100]  # პირველი 100 მატჩი
    }

@app.get("/api/matches/stats")
async def get_matches_stats():
    """აბრუნებს სტატისტიკას"""
    if not matches_storage:
        return {"success": False, "error": "მონაცემები არ არის"}
    
    total_matches = len(matches_storage)
    total_goals = sum(
        (m.get("FTHG") or 0) + (m.get("FTAG") or 0) 
        for m in matches_storage
    )
    
    return {
        "success": True,
        "total_matches": total_matches,
        "total_goals": total_goals,
        "avg_goals": round(total_goals / total_matches, 2) if total_matches > 0 else 0
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
        <title>FootStats Dashboard v4.0</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            @keyframes slideIn { 
                from { opacity: 0; transform: translateY(10px); } 
                to { opacity: 1; transform: translateY(0); } 
            }
            .log-entry { animation: slideIn 0.3s ease-out; }
            .glass { 
                background: rgba(30, 41, 59, 0.7); 
                backdrop-filter: blur(10px); 
                border: 1px solid rgba(255, 255, 255, 0.1); 
            }
            .table-container { 
                max-height: 600px; 
                overflow: auto; 
            }
            table { 
                font-size: 0.7rem; 
            }
            th { 
                position: sticky; 
                top: 0; 
                background: #1e293b; 
                z-index: 10; 
            }
        </style>
    </head>
    <body class="bg-gradient-to-br from-[#0B0F19] to-[#1a1f2e] text-[#E2E8F0] font-sans min-h-screen">
        <div class="max-w-full mx-auto p-6">
            <div class="text-center mb-8">
                <h1 class="text-4xl font-bold text-white mb-2">⚽ FootStats Dashboard v4.0</h1>
                <p class="text-gray-400">სრული 132 სვეტიანი მონაცემთა ბაზა</p>
            </div>

            <!-- სტატისტიკის ბარათები -->
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
                    <p class="text-gray-400 text-sm">საშუალო გოლი</p>
                    <p class="text-3xl font-bold text-blue-400 mt-1" id="stat-avg">0</p>
                </div>
                <div class="glass rounded-xl p-5">
                    <p class="text-gray-400 text-sm">სვეტები</p>
                    <p class="text-3xl font-bold text-purple-400 mt-1" id="stat-columns">0</p>
                </div>
            </div>

            <!-- CSV იმპორტი -->
            <div class="glass rounded-xl p-6 mb-8">
                <h2 class="text-xl font-bold text-white mb-4">📥 CSV იმპორტი</h2>
                <textarea id="csvInput" rows="10" placeholder="ჩასვი CSV ფაილის შიგთავსი აქ..." class="w-full bg-[#0B0F19] border border-gray-700 rounded-lg p-4 text-emerald-400 font-mono text-xs resize-none focus:outline-none focus:border-emerald-500"></textarea>
                <div class="flex gap-3 mt-4">
                    <button onclick="importCSV()" id="importBtn" class="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-3 rounded-lg">🚀 იმპორტი</button>
                    <button onclick="document.getElementById('csvInput').value=''" class="px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg">🗑️ გასუფთავება</button>
                </div>
            </div>

            <!-- მონაცემთა ცხრილი -->
            <div class="glass rounded-xl p-6 mb-8">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-xl font-bold text-white">📊 მონაცემთა ცხრილი</h2>
                    <span class="px-3 py-1 bg-gray-800 rounded text-sm text-gray-400" id="tableInfo">0 მატჩი</span>
                </div>
                <div class="table-container border border-gray-700 rounded-lg">
                    <table class="w-full text-left">
                        <thead class="text-xs text-gray-400 uppercase bg-[#0F172A]">
                            <tr id="tableHeader">
                                <th class="px-2 py-2">იტვირთება...</th>
                            </tr>
                        </thead>
                        <tbody id="tableBody">
                            <tr>
                                <td class="px-2 py-4 text-center text-gray-500">ჩასვი CSV და დააჭირე "იმპორტი"-ს</td>
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
                        addLog(`📊 სვეტები: ${result.columns_count}`, 'info');
                        
                        document.getElementById('stat-matches').textContent = result.matches_count;
                        document.getElementById('stat-goals').textContent = result.total_goals;
                        document.getElementById('stat-columns').textContent = result.columns_count;
                        
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

            async function loadMatches() {
                addLog('🔄 მონაცემების ჩატვირთვა...', 'info');
                
                try {
                    const response = await fetch('/api/matches/all');
                    const result = await response.json();
                    
                    if (result.success && result.data.length > 0) {
                        addLog(`✅ ჩაიტვირთა ${result.count} მატჩი`, 'success');
                        renderTable(result.data, result.headers);
                    } else {
                        addLog('⚠️ მონაცემები არ არის', 'warning');
                    }
                } catch (error) {
                    addLog(`❌ ${error.message}`, 'error');
                }
            }

            function renderTable(matches, headers) {
                const header = document.getElementById('tableHeader');
                const tbody = document.getElementById('tableBody');
                
                // ვირჩევთ ძირითად სვეტებს
                const mainHeaders = ['Date', 'HomeTeam', 'FTHG', 'FTAG', 'FTR', 'HTHG', 'HTAG', 'Referee', 'HS', 'AS', 'HC', 'AC', 'HY', 'AY', 'HR', 'AR'];
                
                // სათაური
                header.innerHTML = '<tr>' + mainHeaders.map(h => 
                    `<th class="px-2 py-2">${h}</th>`
                ).join('') + '</tr>';
                
                // სხეული
                tbody.innerHTML = matches.map(m => {
                    const resultColor = m.FTR === 'H' ? 'text-emerald-400' : m.FTR === 'A' ? 'text-red-400' : 'text-yellow-400';
                    const resultText = m.FTR === 'H' ? 'მასპ' : m.FTR === 'A' ? 'სტუმ' : 'ფრე';
                    
                    return `
                        <tr class="border-b border-gray-800 hover:bg-[#1E293B]">
                            <td class="px-2 py-2">${m.Date || '-'}</td>
                            <td class="px-2 py-2 font-semibold text-white">${m.HomeTeam || '-'}</td>
                            <td class="px-2 py-2 text-center font-bold text-lg">${m.FTHG || 0}</td>
                            <td class="px-2 py-2 text-center font-bold text-lg">${m.FTAG || 0}</td>
                            <td class="px-2 py-2 text-center font-bold ${resultColor}">${resultText}</td>
                            <td class="px-2 py-2 text-center text-gray-400">${m.HTHG || 0}</td>
                            <td class="px-2 py-2 text-center text-gray-400">${m.HTAG || 0}</td>
                            <td class="px-2 py-2 text-gray-400 text-xs">${m.Referee || '-'}</td>
                            <td class="px-2 py-2 text-center">${m.HS || 0}/${m.AS || 0}</td>
                            <td class="px-2 py-2 text-center">${m.HC || 0}/${m.AC || 0}</td>
                            <td class="px-2 py-2 text-center">${m.HY || 0}/${m.AY || 0}</td>
                            <td class="px-2 py-2 text-center">${m.HR || 0}/${m.AR || 0}</td>
                        </tr>
                    `;
                }).join('');
                
                document.getElementById('tableInfo').textContent = `${matches.length} მატჩი × ${headers.length} სვეტი`;
                addLog(`📋 ცხრილი აგებულია`, 'success');
            }

            function addLog(message, type = 'info') {
                const terminal = document.getElementById('terminal');
                const log = document.createElement('div');
                log.className = 'log-entry';
                
                const colors = { 
                    'info': 'text-blue-400', 
                    'success': 'text-emerald-400', 
                    'warning': 'text-yellow-400', 
                    'error': 'text-red-400' 
                };
                
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