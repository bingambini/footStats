import asyncio
import json
import os
import csv
import io
from typing import Dict, List, Tuple, Optional
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from loguru import logger

app = FastAPI()

# ==========================================
# In-Memory Storage
# ==========================================
matches_storage: List[Dict] = []
headers_storage: List[str] = []

# ==========================================
# CSV Parser - ყველა სვეტის ამოღება
# ==========================================
def parse_csv_complete(csv_text: str) -> Tuple[List[str], List[Dict]]:
    """ამოიღებს ყველა სვეტს CSV ფაილიდან"""
    try:
        if csv_text.startswith('\ufeff'):
            csv_text = csv_text[1:]
        
        lines = csv_text.strip().split('\n')
        
        if len(lines) < 2:
            return [], []
        
        header_line = lines[0]
        headers = [h.strip() for h in header_line.split(',')]
        
        logger.info(f"ნაპოვნია {len(headers)} სვეტი")
        
        matches = []
        for i, line in enumerate(lines[1:], start=1):
            if not line.strip():
                continue
            
            values = [v.strip() for v in line.split(',')]
            
            match_data = {}
            for j, header in enumerate(headers):
                if j < len(values):
                    value = values[j]
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
    return {"message": "FootStats API v6.0 - All 132 Columns"}

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
            "headers": headers_storage,
            "total_goals": total_goals
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/matches/all")
async def get_all_matches():
    return {
        "success": True,
        "count": len(matches_storage),
        "headers": headers_storage,
        "data": matches_storage
    }

# ==========================================
# Dashboard HTML - ყველა სვეტის ჩვენებით
# ==========================================
@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    html_content = """
    <!DOCTYPE html>
    <html lang="ka">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FootStats Dashboard v6.0</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            @keyframes slideIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
            .log-entry { animation: slideIn 0.3s ease-out; }
            .glass { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); }
            
            /* ცხრილის სტილები */
            .table-scroll {
                overflow-x: auto;
                max-height: 600px;
                overflow-y: auto;
            }
            .data-table {
                border-collapse: collapse;
                font-size: 0.7rem;
                white-space: nowrap;
            }
            .data-table thead {
                position: sticky;
                top: 0;
                background: #0F172A;
                z-index: 10;
            }
            .data-table th {
                padding: 0.5rem 0.75rem;
                text-align: left;
                font-weight: 600;
                color: #9CA3AF;
                border-bottom: 2px solid #374151;
                border-right: 1px solid #1F2937;
                white-space: nowrap;
            }
            .data-table td {
                padding: 0.4rem 0.6rem;
                border-bottom: 1px solid #1F2937;
                border-right: 1px solid #1F2937;
                white-space: nowrap;
            }
            .data-table tr:hover {
                background-color: rgba(16, 185, 129, 0.1);
            }
            
            /* სვეტების ფილტრი */
            .column-filter {
                max-height: 300px;
                overflow-y: auto;
            }
            .column-checkbox {
                display: flex;
                align-items: center;
                padding: 0.25rem 0.5rem;
                cursor: pointer;
            }
            .column-checkbox:hover {
                background: rgba(16, 185, 129, 0.1);
            }
        </style>
    </head>
    <body class="bg-gradient-to-br from-[#0B0F19] to-[#1a1f2e] text-[#E2E8F0] font-sans min-h-screen">
        <div class="max-w-full mx-auto p-6">
            <!-- Header -->
            <div class="text-center mb-8">
                <h1 class="text-4xl font-bold text-white mb-2">⚽ FootStats Dashboard v6.0</h1>
                <p class="text-gray-400">ყველა 132 სვეტის ჩვენება + ფილტრი</p>
            </div>

            <!-- სტატისტიკის ბარათები -->
            <div class="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
                <div class="glass rounded-xl p-5">
                    <p class="text-gray-400 text-sm">სულ მატჩი</p>
                    <p class="text-3xl font-bold text-white mt-1" id="stat-matches">0</p>
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
                    <p class="text-gray-400 text-sm">ჩვენებული სვეტები</p>
                    <p class="text-3xl font-bold text-purple-400 mt-1" id="stat-visible">0</p>
                </div>
                <div class="glass rounded-xl p-5 flex flex-col justify-center">
                    <button onclick="exportJSON()" class="bg-blue-600 hover:bg-blue-500 text-white font-semibold py-2 rounded">💾 JSON ექსპორტი</button>
                </div>
            </div>

            <!-- CSV იმპორტი -->
            <div class="glass rounded-xl p-6 mb-8">
                <h2 class="text-xl font-bold text-white mb-4">📥 CSV იმპორტი (ყველა 132 სვეტით)</h2>
                <textarea id="csvInput" rows="6" placeholder="ჩასვი CSV ფაილის შიგთავსი აქ..." class="w-full bg-[#0B0F19] border border-gray-700 rounded-lg p-3 text-emerald-400 font-mono text-xs resize-none focus:outline-none focus:border-emerald-500"></textarea>
                <div class="flex gap-3 mt-4">
                    <button onclick="importCSV()" id="importBtn" class="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-3 rounded-lg">🚀 იმპორტი</button>
                    <button onclick="document.getElementById('csvInput').value=''" class="px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg">🗑️</button>
                </div>
            </div>

            <!-- სვეტების ფილტრი -->
            <div class="glass rounded-xl p-6 mb-8">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-xl font-bold text-white">🎛️ სვეტების ფილტრი</h2>
                    <div class="flex gap-2">
                        <button onclick="selectAllColumns()" class="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-sm">✅ ყველა</button>
                        <button onclick="deselectAllColumns()" class="px-3 py-1 bg-red-600 hover:bg-red-500 text-white rounded text-sm">❌ არცერთი</button>
                        <button onclick="selectMainColumns()" class="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white rounded text-sm">⭐ მთავარი</button>
                    </div>
                </div>
                <div class="column-filter grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2" id="columnFilter">
                    <div class="text-gray-500">ჯერ არ არის მონაცემები</div>
                </div>
            </div>

            <!-- მონაცემთა ცხრილი -->
            <div class="glass rounded-xl p-6 mb-8">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-xl font-bold text-white">📊 მონაცემთა ცხრილი (<span id="matchCount">0</span> მატჩი)</h2>
                    <div class="text-sm text-gray-400">
                        💡 გადაახვიე ჰორიზონტალურად ყველა სვეტის სანახავად
                    </div>
                </div>
                <div class="table-scroll border border-gray-700 rounded-lg">
                    <table class="data-table w-full">
                        <thead>
                            <tr id="tableHeader">
                                <th class="px-3 py-2">იტვირთება...</th>
                            </tr>
                        </thead>
                        <tbody id="tableBody">
                            <tr>
                                <td class="px-3 py-4 text-center text-gray-500">ჩასვი CSV და დააჭირე "იმპორტი"-ს</td>
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
                <div id="terminal" class="bg-[#020617] border border-gray-800 rounded-lg p-4 h-48 overflow-y-auto font-mono text-xs space-y-1">
                    <div class="text-gray-500">// სისტემა მზად არის...</div>
                </div>
            </div>
        </div>

        <script>
            let allMatchesData = [];
            let allHeaders = [];
            let visibleColumns = [];

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
                        addLog(`📊 სვეტები: ${result.columns_count}`, 'info');
                        addLog(`⚽ სულ გოლი: ${result.total_goals}`, 'info');
                        
                        document.getElementById('stat-matches').textContent = result.matches_count;
                        document.getElementById('stat-columns').textContent = result.columns_count;
                        document.getElementById('stat-goals').textContent = result.total_goals;
                        
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
                        allMatchesData = result.data;
                        allHeaders = result.headers;
                        visibleColumns = [...allHeaders]; // ყველა სვეტი ჩვენებულია
                        
                        document.getElementById('matchCount').textContent = result.count;
                        document.getElementById('stat-visible').textContent = visibleColumns.length;
                        
                        renderColumnFilter();
                        renderTable();
                        addLog(`✅ ჩაიტვირთა ${result.count} მატჩი, ${allHeaders.length} სვეტი`, 'success');
                    }
                } catch (error) {
                    addLog(`❌ ${error.message}`, 'error');
                }
            }

            function renderColumnFilter() {
                const filter = document.getElementById('columnFilter');
                filter.innerHTML = allHeaders.map(col => `
                    <label class="column-checkbox">
                        <input type="checkbox" checked onchange="toggleColumn('${col}')" class="mr-2">
                        <span class="text-xs text-gray-300">${col}</span>
                    </label>
                `).join('');
            }

            function toggleColumn(col) {
                if (visibleColumns.includes(col)) {
                    visibleColumns = visibleColumns.filter(c => c !== col);
                } else {
                    visibleColumns.push(col);
                }
                document.getElementById('stat-visible').textContent = visibleColumns.length;
                renderTable();
            }

            function selectAllColumns() {
                visibleColumns = [...allHeaders];
                document.getElementById('stat-visible').textContent = visibleColumns.length;
                renderColumnFilter();
                renderTable();
            }

            function deselectAllColumns() {
                visibleColumns = [];
                document.getElementById('stat-visible').textContent = 0;
                renderColumnFilter();
                renderTable();
            }

            function selectMainColumns() {
                const mainCols = ['Date', 'Time', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR', 'HTHG', 'HTAG', 'HTR', 
                                  'Referee', 'HS', 'AS', 'HST', 'AST', 'HF', 'AF', 'HC', 'AC', 'HY', 'AY', 'HR', 'AR'];
                visibleColumns = allHeaders.filter(h => mainCols.includes(h));
                document.getElementById('stat-visible').textContent = visibleColumns.length;
                renderColumnFilter();
                renderTable();
            }

            function renderTable() {
                const header = document.getElementById('tableHeader');
                const tbody = document.getElementById('tableBody');
                
                if (visibleColumns.length === 0) {
                    header.innerHTML = '<th class="px-3 py-2">აირჩიე სვეტები ფილტრიდან</th>';
                    tbody.innerHTML = '<tr><td class="px-3 py-4 text-center text-gray-500">სვეტები არ არის არჩეული</td></tr>';
                    return;
                }
                
                // სათაური
                header.innerHTML = '<tr>' + visibleColumns.map(col => 
                    `<th class="px-3 py-2">${col}</th>`
                ).join('') + '</tr>';
                
                // სხეული - ყველა მატჩი
                tbody.innerHTML = allMatchesData.map(m => {
                    return '<tr>' + visibleColumns.map(col => {
                        let value = m[col];
                        if (value === null || value === undefined || value === '') {
                            value = '-';
                        }
                        // FTR სვეტისთვის ფერადი
                        let cls = '';
                        if (col === 'FTR') {
                            if (value === 'H') cls = 'text-emerald-400 font-bold';
                            else if (value === 'A') cls = 'text-red-400 font-bold';
                            else if (value === 'D') cls = 'text-yellow-400 font-bold';
                        }
                        return `<td class="px-3 py-2 ${cls}">${value}</td>`;
                    }).join('') + '</tr>';
                }).join('');
            }

            function exportJSON() {
                if (allMatchesData.length === 0) {
                    alert('ჯერ იმპორტირე მონაცემები');
                    return;
                }
                
                const data = {
                    headers: allHeaders,
                    matches: allMatchesData,
                    exported_at: new Date().toISOString()
                };
                
                const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `footstats_all_${new Date().toISOString().split('T')[0]}.json`;
                a.click();
                URL.revokeObjectURL(url);
                
                addLog('💾 JSON ექსპორტი წარმატებულია', 'success');
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