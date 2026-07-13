import asyncio
import json
import os
import re
from typing import Dict, List, Tuple, Optional
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
import httpx
from loguru import logger

app = FastAPI()

# ==========================================
# In-Memory Storage
# ==========================================
all_matches_data = []

# ==========================================
# CSV Parser - სრული მონაცემების ამოღება
# ==========================================
def parse_csv_complete(csv_text: str) -> List[Dict]:
    """ამოიღებს ყველა მონაცემს CSV ფაილიდან"""
    lines = csv_text.strip().split('\n')
    if len(lines) < 2:
        return []
    
    # სათაურების ამოღება
    headers = lines[0].split(',')
    matches = []
    
    for line_num, line in enumerate(lines[1:], start=1):
        if not line.strip():
            continue
        
        cols = line.split(',')
        match_data = {"row": line_num}
        
        # ყველა სვეტის დამუშავება
        for i, header in enumerate(headers):
            if i < len(cols):
                value = cols[i].strip()
                
                # ტიპის კონვერტაცია
                if value and value not in ['', ' ']:
                    try:
                        # რიცხვები
                        if '.' in value:
                            match_data[header] = float(value)
                        else:
                            match_data[header] = int(value)
                    except ValueError:
                        # ტექსტი
                        match_data[header] = value
                else:
                    match_data[header] = None
        
        matches.append(match_data)
    
    return matches

# ==========================================
# API Endpoints
# ==========================================
@app.get("/")
async def root():
    return {"message": "FootStats API v5.0 - Full Data Extraction"}

@app.post("/api/import/csv")
async def import_csv(request: Request):
    """იმპორტავს CSV-ს და ინახავს მეხსიერებაში"""
    try:
        body = await request.json()
        csv_data = body.get("csv_data", "")
        
        if not csv_data.strip():
            return {"success": False, "error": "CSV ცარიელია"}
        
        # პარსინგი
        matches = parse_csv_complete(csv_data)
        
        # შენახვა მეხსიერებაში
        global all_matches_data
        all_matches_data = matches
        
        # სტატისტიკა
        stats = {
            "total_matches": len(matches),
            "total_columns": len(matches[0].keys()) if matches else 0,
            "columns": list(matches[0].keys()) if matches else []
        }
        
        return {
            "success": True,
            "message": f"წარმატებით იმპორტირდა {len(matches)} მატჩი",
            "stats": stats
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/matches/all")
async def get_all_matches():
    """აბრუნებს ყველა მატჩს სრული მონაცემებით"""
    if not all_matches_data:
        return {"success": False, "error": "მონაცემები ჯერ არ არის იმპორტირებული"}
    
    return {
        "success": True,
        "count": len(all_matches_data),
        "data": all_matches_data
    }

@app.get("/api/matches/stats")
async def get_matches_stats():
    """აბრუნებს სტატისტიკას"""
    if not all_matches_data:
        return {"success": False, "error": "მონაცემები ჯერ არ არის იმპორტირებული"}
    
    # ძირითადი სტატისტიკა
    total_matches = len(all_matches_data)
    total_goals = sum(m.get('FTHG', 0) + m.get('FTAG', 0) for m in all_matches_data if m.get('FTHG') and m.get('FTAG'))
    
    # გუნდების სია
    teams = set()
    for m in all_matches_data:
        if m.get('HomeTeam'):
            teams.add(m['HomeTeam'])
        if m.get('AwayTeam'):
            teams.add(m['AwayTeam'])
    
    # მსაჯების სია
    referees = set(m.get('Referee') for m in all_matches_data if m.get('Referee'))
    
    # სვეტების რაოდენობა
    columns = list(all_matches_data[0].keys()) if all_matches_data else []
    
    return {
        "success": True,
        "total_matches": total_matches,
        "total_goals": total_goals,
        "avg_goals": round(total_goals / total_matches, 2) if total_matches > 0 else 0,
        "total_teams": len(teams),
        "teams": sorted(list(teams)),
        "total_referees": len(referees),
        "referees": sorted(list(referees)),
        "total_columns": len(columns),
        "columns": columns
    }

@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    html_content = """
    <!DOCTYPE html>
    <html lang="ka">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FootStats Dashboard v5.0</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            @keyframes slideIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
            .log-entry { animation: slideIn 0.3s ease-out; }
            .glass-panel { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); }
            .tab-active { background-color: #10b981; color: white; }
            .tab-inactive { background-color: #374151; color: #9ca3af; }
            .match-row:hover { background-color: rgba(16, 185, 129, 0.1); }
        </style>
    </head>
    <body class="bg-gradient-to-br from-[#0B0F19] to-[#1a1f2e] text-[#E2E8F0] font-sans min-h-screen">
        <div class="max-w-7xl mx-auto p-6">
            <!-- Header -->
            <div class="text-center mb-8">
                <h1 class="text-4xl font-bold text-white mb-2">📊 FootStats Dashboard v5.0</h1>
                <p class="text-gray-400">სრული მონაცემთა ამოღება და ვიზუალიზაცია</p>
            </div>

            <!-- Stats Cards -->
            <div class="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
                <div class="glass-panel rounded-xl p-5">
                    <p class="text-gray-400 text-sm">სულ მატჩი</p>
                    <p class="text-3xl font-bold text-white mt-1" id="stat-matches">0</p>
                </div>
                <div class="glass-panel rounded-xl p-5">
                    <p class="text-gray-400 text-sm">სულ გოლი</p>
                    <p class="text-3xl font-bold text-emerald-400 mt-1" id="stat-goals">0</p>
                </div>
                <div class="glass-panel rounded-xl p-5">
                    <p class="text-gray-400 text-sm">საშუალო გოლი</p>
                    <p class="text-3xl font-bold text-blue-400 mt-1" id="stat-avg">0</p>
                </div>
                <div class="glass-panel rounded-xl p-5">
                    <p class="text-gray-400 text-sm">გუნდები</p>
                    <p class="text-3xl font-bold text-purple-400 mt-1" id="stat-teams">0</p>
                </div>
                <div class="glass-panel rounded-xl p-5">
                    <p class="text-gray-400 text-sm">სვეტები</p>
                    <p class="text-3xl font-bold text-yellow-400 mt-1" id="stat-columns">0</p>
                </div>
            </div>

            <!-- Tabs -->
            <div class="flex gap-2 mb-6">
                <button onclick="switchTab('import')" id="tab-import" class="tab-active px-6 py-3 rounded-lg font-semibold">📥 იმპორტი</button>
                <button onclick="switchTab('matches')" id="tab-matches" class="tab-inactive px-6 py-3 rounded-lg font-semibold">📊 მატჩები</button>
                <button onclick="switchTab('columns')" id="tab-columns" class="tab-inactive px-6 py-3 rounded-lg font-semibold">📋 სვეტები</button>
            </div>

            <!-- Import Tab -->
            <div id="section-import" class="glass-panel rounded-xl p-6 mb-8">
                <h2 class="text-2xl font-bold text-white mb-4">📥 CSV იმპორტი</h2>
                <p class="text-gray-400 mb-4">ჩასვით football-data.co.uk ფორმატის CSV ფაილი. სისტემა ამოიღებს ყველა მონაცემს.</p>
                <textarea id="csvInput" rows="10" placeholder="Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR..." class="w-full bg-[#0B0F19] border border-gray-700 rounded-lg p-4 text-emerald-400 font-mono text-xs resize-none focus:outline-none focus:border-emerald-500"></textarea>
                <div class="flex gap-3 mt-4">
                    <button onclick="importCSV()" id="importBtn" class="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-3 rounded-lg">🚀 იმპორტი</button>
                    <button onclick="document.getElementById('csvInput').value=''" class="px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg">🗑️ გასუფთავება</button>
                </div>
            </div>

            <!-- Matches Tab -->
            <div id="section-matches" class="hidden glass-panel rounded-xl p-6 mb-8">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-2xl font-bold text-white">📊 მატჩების ცხრილი</h2>
                    <div class="flex gap-2">
                        <button onclick="loadMatches()" class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm">🔄 განახლება</button>
                        <button onclick="exportJSON()" class="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg text-sm">💾 JSON ექსპორტი</button>
                    </div>
                </div>
                <div id="matchesTableContainer" class="overflow-x-auto max-h-[600px] border border-gray-700 rounded-lg">
                    <table class="w-full text-sm text-left">
                        <thead class="text-xs text-gray-400 uppercase bg-[#0F172A] sticky top-0">
                            <tr id="matchesTableHeader">
                                <th class="px-4 py-3">იტვირთება...</th>
                            </tr>
                        </thead>
                        <tbody id="matchesTableBody" class="divide-y divide-gray-700">
                            <tr>
                                <td colspan="10" class="px-4 py-8 text-center text-gray-500">ჯერ არ არის მონაცემები</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Columns Tab -->
            <div id="section-columns" class="hidden glass-panel rounded-xl p-6 mb-8">
                <h2 class="text-2xl font-bold text-white mb-4">📋 სვეტების სია</h2>
                <p class="text-gray-400 mb-4">ყველა სვეტი, რაც ამოიღო სისტემამ</p>
                <div id="columnsList" class="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div class="text-gray-500">ჯერ არ არის მონაცემები</div>
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
        </div>

        <script>
            let currentTab = 'import';

            function switchTab(tab) {
                currentTab = tab;
                ['import', 'matches', 'columns'].forEach(t => {
                    document.getElementById('tab-' + t).className = tab === t ? 'tab-active px-6 py-3 rounded-lg font-semibold' : 'tab-inactive px-6 py-3 rounded-lg font-semibold';
                    document.getElementById('section-' + t).classList.toggle('hidden', tab !== t);
                });
                
                if (tab === 'matches') loadMatches();
                if (tab === 'columns') loadColumns();
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
                        addLog(`📊 სვეტები: ${result.stats.total_columns}`, 'info');
                        await loadStats();
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

            async function loadStats() {
                try {
                    const response = await fetch('/api/matches/stats');
                    const stats = await response.json();
                    
                    if (stats.success) {
                        document.getElementById('stat-matches').textContent = stats.total_matches;
                        document.getElementById('stat-goals').textContent = stats.total_goals;
                        document.getElementById('stat-avg').textContent = stats.avg_goals;
                        document.getElementById('stat-teams').textContent = stats.total_teams;
                        document.getElementById('stat-columns').textContent = stats.total_columns;
                    }
                } catch (error) {
                    console.error('შეცდომა:', error);
                }
            }

            async function loadMatches() {
                addLog('🔄 მატჩების ჩატვირთვა...', 'info');
                
                try {
                    const response = await fetch('/api/matches/all');
                    const result = await response.json();
                    
                    if (result.success) {
                        const matches = result.data;
                        addLog(`✅ ჩაიტვირთა ${matches.length} მატჩი`, 'success');
                        
                        // ცხრილის აგება
                        const header = document.getElementById('matchesTableHeader');
                        const tbody = document.getElementById('matchesTableBody');
                        
                        // ძირითადი სვეტები
                        const mainColumns = ['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR', 'Referee', 'HS', 'AS', 'HC', 'AC'];
                        
                        // სათაური
                        header.innerHTML = mainColumns.map(col => `<th class="px-4 py-3">${col}</th>`).join('');
                        
                        // სტრიქონები
                        tbody.innerHTML = matches.slice(0, 100).map(m => {
                            return `<tr class="match-row">
                                ${mainColumns.map(col => `<td class="px-4 py-3">${m[col] || '-'}</td>`).join('')}
                            </tr>`;
                        }).join('');
                        
                        if (matches.length > 100) {
                            addLog(`⚠️ ნაჩვენებია პირველი 100 მატჩი (სულ ${matches.length})`, 'warning');
                        }
                    } else {
                        addLog(`❌ ${result.error}`, 'error');
                    }
                } catch (error) {
                    addLog(`❌ ${error.message}`, 'error');
                }
            }

            async function loadColumns() {
                try {
                    const response = await fetch('/api/matches/stats');
                    const stats = await response.json();
                    
                    if (stats.success && stats.columns) {
                        const columnsList = document.getElementById('columnsList');
                        columnsList.innerHTML = stats.columns.map(col => {
                            return `<div class="bg-[#0B0F19] border border-gray-700 rounded-lg p-3 text-sm">
                                <span class="text-emerald-400 font-mono">${col}</span>
                            </div>`;
                        }).join('');
                        
                        addLog(`📋 სვეტები: ${stats.columns.length}`, 'info');
                    }
                } catch (error) {
                    console.error('შეცდომა:', error);
                }
            }

            async function exportJSON() {
                try {
                    const response = await fetch('/api/matches/all');
                    const result = await response.json();
                    
                    if (result.success) {
                        const blob = new Blob([JSON.stringify(result.data, null, 2)], { type: 'application/json' });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = 'footstats_matches.json';
                        a.click();
                        URL.revokeObjectURL(url);
                        
                        addLog('💾 JSON ექსპორტი წარმატებულია', 'success');
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

            // ჩატვირთვისას
            loadStats();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)