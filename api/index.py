import asyncio
import json
import os
import csv
import io
from typing import Dict, List
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from loguru import logger

app = FastAPI()

# ==========================================
# In-Memory Storage
# ==========================================
all_matches_data = []
all_headers = []

# ==========================================
# CSV Parser - ყველა სვეტის ამოღება
# ==========================================
def parse_csv_all_columns(csv_text: str) -> tuple[List[str], List[Dict]]:
    """ამოიღებს ყველა სვეტს CSV ფაილიდან"""
    try:
        reader = csv.DictReader(io.StringIO(csv_text))
        headers = reader.fieldnames or []
        
        rows = []
        for row in reader:
            # ცარიელი სტრიქონების გამოტოვება
            if any(v and v.strip() for v in row.values()):
                # ყველა სვეტის შენარჩუნება
                clean_row = {}
                for key, value in row.items():
                    clean_row[key] = value.strip() if value else None
                rows.append(clean_row)
        
        logger.info(f"✅ წარმატებით დამუშავდა: {len(rows)} მატჩი, {len(headers)} სვეტი")
        return headers, rows
    
    except Exception as e:
        logger.error(f"❌ CSV პარსინგის შეცდომა: {e}")
        return [], []

# ==========================================
# API Endpoints
# ==========================================
@app.get("/")
async def root():
    return {"message": "FootStats API - Full Column Parser"}

@app.post("/api/import/csv")
async def import_csv(request: Request):
    """იმპორტავს CSV-ს ყველა სვეტით"""
    global all_matches_data, all_headers
    
    try:
        body = await request.json()
        csv_data = body.get("csv_data", "")
        
        if not csv_data.strip():
            return {"success": False, "error": "CSV ცარიელია"}
        
        all_headers, all_matches_data = parse_csv_all_columns(csv_data)
        
        return {
            "success": True,
            "message": f"წარმატებით იმპორტირდა {len(all_matches_data)} მატჩი",
            "matches_count": len(all_matches_data),
            "columns_count": len(all_headers),
            "headers": all_headers
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

@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    html_content = """
    <!DOCTYPE html>
    <html lang="ka">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FootStats Dashboard - Full Data</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            .glass { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); }
            .table-container { overflow-x: auto; max-height: 600px; }
            table { font-size: 0.7rem; }
            th { position: sticky; top: 0; background: #1e293b; z-index: 10; }
        </style>
    </head>
    <body class="bg-gradient-to-br from-[#0B0F19] to-[#1a1f2e] text-[#E2E8F0] font-sans min-h-screen">
        <div class="max-w-full mx-auto p-6">
            <div class="text-center mb-8">
                <h1 class="text-4xl font-bold text-white mb-2">📊 FootStats Dashboard</h1>
                <p class="text-gray-400">ყველა 132 სვეტი - შენ გადაწყვიტე რა შეინახო</p>
            </div>

            <!-- სტატისტიკა -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
                <div class="glass rounded-xl p-5">
                    <p class="text-gray-400 text-sm">სულ მატჩი</p>
                    <p class="text-3xl font-bold text-white mt-1" id="stat-matches">0</p>
                </div>
                <div class="glass rounded-xl p-5">
                    <p class="text-gray-400 text-sm">სვეტები</p>
                    <p class="text-3xl font-bold text-emerald-400 mt-1" id="stat-columns">0</p>
                </div>
                <div class="glass rounded-xl p-5">
                    <p class="text-gray-400 text-sm">მოქმედება</p>
                    <button onclick="exportJSON()" class="mt-1 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded font-semibold">💾 JSON ექსპორტი</button>
                </div>
            </div>

            <!-- იმპორტი -->
            <div class="glass rounded-xl p-6 mb-8">
                <h2 class="text-xl font-bold text-white mb-4">📥 CSV იმპორტი (ყველა სვეტით)</h2>
                <textarea id="csvInput" rows="8" placeholder="ჩასვი CSV ფაილი აქ..." class="w-full bg-[#0B0F19] border border-gray-700 rounded p-3 text-emerald-400 font-mono text-xs resize-none"></textarea>
                <div class="flex gap-3 mt-4">
                    <button onclick="importCSV()" id="importBtn" class="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-3 rounded">🚀 დამუშავება</button>
                    <button onclick="document.getElementById('csvInput').value=''" class="px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded">🗑️</button>
                </div>
            </div>

            <!-- ცხრილი -->
            <div class="glass rounded-xl p-6">
                <h2 class="text-xl font-bold text-white mb-4">📋 ყველა მონაცემი (<span id="tableCount">0</span> მატჩი × <span id="colCount">0</span> სვეტი)</h2>
                <div class="table-container border border-gray-700 rounded">
                    <table class="w-full text-left">
                        <thead class="text-xs text-gray-400 uppercase bg-[#0F172A]">
                            <tr id="tableHeader">
                                <th class="px-2 py-2">იტვირთება...</th>
                            </tr>
                        </thead>
                        <tbody id="tableBody">
                            <tr>
                                <td class="px-2 py-4 text-center text-gray-500">ჩასვი CSV და დააჭირე "დამუშავება"-ს</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <script>
            let allData = [];
            let allHeaders = [];

            async function importCSV() {
                const csv = document.getElementById('csvInput').value;
                const btn = document.getElementById('importBtn');
                
                if (!csv.trim()) {
                    alert('ჩასვი CSV ჯერ');
                    return;
                }
                
                btn.disabled = true;
                btn.textContent = '⏳ მუშაობს...';
                
                try {
                    const response = await fetch('/api/import/csv', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ csv_data: csv })
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        alert(`✅ ${result.message}\\n📊 სვეტები: ${result.columns_count}`);
                        document.getElementById('stat-matches').textContent = result.matches_count;
                        document.getElementById('stat-columns').textContent = result.columns_count;
                        await loadData();
                    } else {
                        alert('❌ ' + result.error);
                    }
                } catch (error) {
                    alert('❌ ' + error.message);
                } finally {
                    btn.disabled = false;
                    btn.textContent = '🚀 დამუშავება';
                }
            }

            async function loadData() {
                try {
                    const response = await fetch('/api/matches/all');
                    const result = await response.json();
                    
                    if (result.success && result.data.length > 0) {
                        allData = result.data;
                        allHeaders = result.headers;
                        
                        document.getElementById('tableCount').textContent = result.count;
                        document.getElementById('colCount').textContent = allHeaders.length;
                        
                        renderTable();
                    }
                } catch (error) {
                    console.error('შეცდომა:', error);
                }
            }

            function renderTable() {
                const header = document.getElementById('tableHeader');
                const tbody = document.getElementById('tableBody');
                
                // სათაური - ყველა სვეტი
                header.innerHTML = '<tr>' + allHeaders.map(h => 
                    `<th class="px-2 py-2 whitespace-nowrap">${h}</th>`
                ).join('') + '</tr>';
                
                // სხეული - ყველა სტრიქონი
                tbody.innerHTML = allData.map(row => 
                    '<tr class="border-b border-gray-800 hover:bg-[#1E293B]">' + 
                    allHeaders.map(h => {
                        const value = row[h] || '-';
                        return `<td class="px-2 py-1 whitespace-nowrap">${value}</td>`;
                    }).join('') + '</tr>'
                ).join('');
            }

            function exportJSON() {
                if (allData.length === 0) {
                    alert('ჯერ იმპორტირე მონაცემები');
                    return;
                }
                
                const exportData = {
                    headers: allHeaders,
                    matches: allData,
                    exported_at: new Date().toISOString()
                };
                
                const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `footstats_all_${new Date().toISOString().split('T')[0]}.json`;
                a.click();
                URL.revokeObjectURL(url);
                
                alert('✅ JSON ექსპორტი წარმატებულია');
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)