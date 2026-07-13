import asyncio
import json
import os
import csv
import io
from typing import Dict, List, Tuple, Optional
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from loguru import logger

app = FastAPI()

# ==========================================
# In-Memory Storage
# ==========================================
matches_storage = []
headers_storage = []

# ==========================================
# CSV Parser - სრული მონაცემების ამოღება
# ==========================================
def parse_csv_complete(csv_text: str) -> Tuple[List[str], List[Dict]]:
    """ამოიღებს ყველა სვეტს და სტრიქონს CSV ფაილიდან"""
    try:
        # CSV reader-ის გამოყენება
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        
        # სვეტების სახელები
        headers = csv_reader.fieldnames or []
        
        # ყველა სტრიქონის წაკითხვა
        rows = []
        for row in csv_reader:
            # ცარიელი სტრიქონების გამოტოვება
            if any(row.values()):
                rows.append(row)
        
        logger.info(f"წარმატებით დამუშავდა: {len(rows)} მატჩი, {len(headers)} სვეტი")
        return headers, rows
    
    except Exception as e:
        logger.error(f"CSV პარსინგის შეცდომა: {e}")
        return [], []

# ==========================================
# API Endpoints
# ==========================================
@app.get("/")
async def root():
    return {"message": "FootStats Dashboard v4.0 - Full Data Extraction"}

@app.post("/api/import/csv")
async def import_csv(request: dict):
    """იმპორტავს CSV-ს და ინახავს მეხსიერებაში"""
    csv_data = request.get("csv_data", "")
    
    if not csv_data.strip():
        return {"success": False, "error": "CSV ცარიელია"}
    
    global matches_storage, headers_storage
    headers_storage, matches_storage = parse_csv_complete(csv_data)
    
    return {
        "success": True,
        "message": f"წარმატებით იმპორტირდა {len(matches_storage)} მატჩი",
        "matches_count": len(matches_storage),
        "columns_count": len(headers_storage),
        "headers": headers_storage
    }

@app.get("/api/matches/all")
async def get_all_matches():
    """აბრუნებს ყველა მატჩს სრული მონაცემებით"""
    return {
        "success": True,
        "count": len(matches_storage),
        "headers": headers_storage,
        "data": matches_storage
    }

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
            .glass-panel { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); }
            
            /* ცხრილის სტილები */
            .table-container {
                overflow-x: auto;
                overflow-y: auto;
                max-height: 600px;
                border: 1px solid #374151;
                border-radius: 0.5rem;
            }
            .data-table {
                width: 100%;
                border-collapse: collapse;
                font-size: 0.75rem;
            }
            .data-table thead {
                position: sticky;
                top: 0;
                background-color: #0F172A;
                z-index: 10;
            }
            .data-table th {
                padding: 0.5rem 0.75rem;
                text-align: left;
                font-weight: 600;
                color: #9CA3AF;
                border-bottom: 2px solid #374151;
                white-space: nowrap;
            }
            .data-table td {
                padding: 0.5rem 0.75rem;
                border-bottom: 1px solid #374151;
                white-space: nowrap;
                color: #E2E8F0;
            }
            .data-table tr:hover {
                background-color: rgba(16, 185, 129, 0.1);
            }
        </style>
    </head>
    <body class="bg-gradient-to-br from-[#0B0F19] to-[#1a1f2e] text-[#E2E8F0] font-sans min-h-screen">
        <div class="max-w-full mx-auto p-6">
            <div class="text-center mb-8">
                <h1 class="text-4xl font-bold text-white mb-2">📊 FootStats Dashboard v4.0</h1>
                <p class="text-gray-400">სრული მონაცემთა ამოღება - ყველა 133 სვეტი</p>
            </div>

            <!-- სტატისტიკის ბარათები -->
            <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
                <div class="glass-panel rounded-xl p-5">
                    <p class="text-gray-400 text-sm">სულ მატჩი</p>
                    <p class="text-3xl font-bold text-white mt-1" id="stat-matches">0</p>
                </div>
                <div class="glass-panel rounded-xl p-5">
                    <p class="text-gray-400 text-sm">სვეტები</p>
                    <p class="text-3xl font-bold text-emerald-400 mt-1" id="stat-columns">0</p>
                </div>
                <div class="glass-panel rounded-xl p-5">
                    <p class="text-gray-400 text-sm">ექსპორტი</p>
                    <button onclick="exportJSON()" class="mt-1 px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg text-sm font-semibold">💾 JSON</button>
                </div>
                <div class="glass-panel rounded-xl p-5">
                    <p class="text-gray-400 text-sm">ექსპორტი</p>
                    <button onclick="exportCSV()" class="mt-1 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-semibold">📄 CSV</button>
                </div>
            </div>

            <!-- CSV იმპორტის სექცია -->
            <div class="glass-panel rounded-xl p-6 mb-8">
                <h2 class="text-2xl font-bold text-white mb-4">📥 CSV ფაილის იმპორტი</h2>
                <p class="text-gray-400 mb-4">ჩასვით football-data.co.uk ფორმატის CSV ფაილი. სისტემა ამოიღებს ყველა 133 სვეტს.</p>
                <textarea id="csvInput" rows="10" placeholder="Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR..." class="w-full bg-[#0B0F19] border border-gray-700 rounded-lg p-4 text-emerald-400 font-mono text-xs resize-none focus:outline-none focus:border-emerald-500"></textarea>
                <div class="flex gap-3 mt-4">
                    <button onclick="importCSV()" id="importBtn" class="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-3 rounded-lg transition">🚀 დამუშავება</button>
                    <button onclick="document.getElementById('csvInput').value=''" class="px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg">🗑️ გასუფთავება</button>
                </div>
            </div>

            <!-- მონაცემთა ცხრილი -->
            <div class="glass-panel rounded-xl p-6 mb-8">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-2xl font-bold text-white">📊 სრული მონაცემთა ცხრილი</h2>
                    <div class="flex gap-2">
                        <span class="px-3 py-1 bg-gray-800 rounded text-sm text-gray-400" id="tableInfo">0 მატჩი × 0 სვეტი</span>
                    </div>
                </div>
                
                <div class="table-container">
                    <table class="data-table">
                        <thead id="tableHeader">
                            <tr>
                                <th>მონაცემები ჯერ არ არის იმპორტირებული</th>
                            </tr>
                        </thead>
                        <tbody id="tableBody">
                            <tr>
                                <td>ჩასვით CSV და დააჭირეთ "დამუშავება"-ს</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- ლოგები -->
            <div class="glass-panel rounded-xl p-6">
                <div class="flex justify-between items-center mb-4">
                    <h3 class="text-lg font-bold text-white">📜 ლოგები</h3>
                    <button onclick="clearLogs()" class="text-xs text-gray-400 hover:text-white">გასუფთავება</button>
                </div>
                <div id="terminal" class="bg-[#020617] border border-gray-800 rounded-lg p-4 h-64 overflow-y-auto font-mono text-xs space-y-2">
                    <div class="text-gray-500">// სისტემა მზად არის...</div>
                </div>
            </div>
        </div>

        <script>
            let allMatchesData = [];
            let allHeaders = [];

            async function importCSV() {
                const csvData = document.getElementById('csvInput').value;
                const btn = document.getElementById('importBtn');
                
                if (!csvData.trim()) {
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
                        body: JSON.stringify({ csv_data: csvData })
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        addLog(`✅ ${result.message}`, 'success');
                        addLog(`📊 სვეტები: ${result.columns_count}`, 'info');
                        
                        // სტატისტიკის განახლება
                        document.getElementById('stat-matches').textContent = result.matches_count;
                        document.getElementById('stat-columns').textContent = result.columns_count;
                        
                        // მონაცემების ჩატვირთვა
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
                addLog('🔄 მონაცემების ჩატვირთვა...', 'info');
                
                try {
                    const response = await fetch('/api/matches/all');
                    const result = await response.json();
                    
                    if (result.success) {
                        allMatchesData = result.data;
                        allHeaders = result.headers;
                        
                        addLog(`✅ ჩაიტვირთა ${allMatchesData.length} მატჩი`, 'success');
                        
                        // ცხრილის აგება
                        renderTable();
                    }
                } catch (error) {
                    addLog(`❌ ${error.message}`, 'error');
                }
            }

            function renderTable() {
                if (allMatchesData.length === 0 || allHeaders.length === 0) {
                    addLog('⚠️ მონაცემები ცარიელია', 'warning');
                    return;
                }
                
                const header = document.getElementById('tableHeader');
                const tbody = document.getElementById('tableBody');
                
                // სათაური - ყველა სვეტი
                header.innerHTML = '<tr>' + allHeaders.map(h => `<th>${h}</th>`).join('') + '</tr>';
                
                // სხეული - ყველა სტრიქონი
                tbody.innerHTML = allMatchesData.map(row => 
                    '<tr>' + allHeaders.map(h => `<td>${row[h] || '-'}</td>`).join('') + '</tr>'
                ).join('');
                
                // ინფო განახლება
                document.getElementById('tableInfo').textContent = `${allMatchesData.length} მატჩი × ${allHeaders.length} სვეტი`;
                
                addLog(`📊 ცხრილი აგებულია: ${allMatchesData.length} × ${allHeaders.length}`, 'success');
            }

            function exportJSON() {
                if (allMatchesData.length === 0) {
                    alert('ჯერ იმპორტირეთ მონაცემები');
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
                a.download = `footstats_${new Date().toISOString().split('T')[0]}.json`;
                a.click();
                URL.revokeObjectURL(url);
                
                addLog('💾 JSON ექსპორტი წარმატებულია', 'success');
            }

            function exportCSV() {
                if (allMatchesData.length === 0 || allHeaders.length === 0) {
                    alert('ჯერ იმპორტირეთ მონაცემები');
                    return;
                }
                
                // CSV სათაური
                let csvContent = allHeaders.join(',') + '\\n';
                
                // CSV სხეული
                allMatchesData.forEach(row => {
                    const line = allHeaders.map(h => {
                        const value = row[h] || '';
                        return value.includes(',') ? `"${value}"` : value;
                    }).join(',');
                    csvContent += line + '\\n';
                });
                
                const blob = new Blob([csvContent], { type: 'text/csv' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `footstats_${new Date().toISOString().split('T')[0]}.csv`;
                a.click();
                URL.revokeObjectURL(url);
                
                addLog('📄 CSV ექსპორტი წარმატებულია', 'success');
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