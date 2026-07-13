from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Dict, List
import json

router = APIRouter()

# Dashboard-ის მონაცემების შესანახად
dashboard_data = {
    "matches": [],
    "teams": [],
    "referees": [],
    "stats": {
        "total_matches": 0,
        "total_goals": 0,
        "total_cards": 0,
        "avg_goals_per_match": 0
    }
}

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """მთავარი Dashboard გვერდი"""
    return get_dashboard_html()

@router.get("/api/dashboard/stats")
async def get_dashboard_stats():
    """Dashboard-ის სტატისტიკა"""
    return dashboard_data["stats"]

@router.get("/api/dashboard/matches")
async def get_dashboard_matches():
    """ყველა მატჩი"""
    return dashboard_data["matches"]

@router.post("/api/dashboard/import")
async def import_csv_data(request: Request):
    """CSV მონაცემების იმპორტი"""
    body = await request.json()
    csv_text = body.get("csv_text", "")
    
    if not csv_text:
        return {"success": False, "error": "CSV ტექსტი ცარიელია"}
    
    try:
        lines = csv_text.strip().split('\n')
        header = lines[0].split(',')
        
        matches = []
        teams = set()
        referees = set()
        total_goals = 0
        total_cards = 0
        
        for line in lines[1:]:
            cols = line.split(',')
            if len(cols) < 20:
                continue
            
            match = {
                "date": cols[1],
                "home_team": cols[3],
                "away_team": cols[4],
                "home_goals": int(cols[5]) if cols[5] else 0,
                "away_goals": int(cols[6]) if cols[6] else 0,
                "result": cols[7],
                "referee": cols[11] if len(cols) > 11 else "",
                "home_shots": int(cols[12]) if len(cols) > 12 and cols[12] else 0,
                "away_shots": int(cols[13]) if len(cols) > 13 and cols[13] else 0,
                "home_shots_on_target": int(cols[14]) if len(cols) > 14 and cols[14] else 0,
                "away_shots_on_target": int(cols[15]) if len(cols) > 15 and cols[15] else 0,
                "home_fouls": int(cols[16]) if len(cols) > 16 and cols[16] else 0,
                "away_fouls": int(cols[17]) if len(cols) > 17 and cols[17] else 0,
                "home_corners": int(cols[18]) if len(cols) > 18 and cols[18] else 0,
                "away_corners": int(cols[19]) if len(cols) > 19 and cols[19] else 0,
                "home_yellow": int(cols[20]) if len(cols) > 20 and cols[20] else 0,
                "away_yellow": int(cols[21]) if len(cols) > 21 and cols[21] else 0,
                "home_red": int(cols[22]) if len(cols) > 22 and cols[22] else 0,
                "away_red": int(cols[23]) if len(cols) > 23 and cols[23] else 0
            }
            
            matches.append(match)
            teams.add(match["home_team"])
            teams.add(match["away_team"])
            referees.add(match["referee"])
            
            total_goals += match["home_goals"] + match["away_goals"]
            total_cards += match["home_yellow"] + match["away_yellow"] + match["home_red"] + match["away_red"]
        
        # განვაახლოთ dashboard_data
        dashboard_data["matches"] = matches
        dashboard_data["teams"] = sorted(list(teams))
        dashboard_data["referees"] = sorted(list(referees))
        dashboard_data["stats"] = {
            "total_matches": len(matches),
            "total_goals": total_goals,
            "total_cards": total_cards,
            "avg_goals_per_match": round(total_goals / len(matches), 2) if matches else 0,
            "total_teams": len(teams),
            "total_referees": len(referees)
        }
        
        return {
            "success": True,
            "message": f"წარმატებით იმპორტირდა {len(matches)} მატჩი",
            "stats": dashboard_data["stats"]
        }
    
    except Exception as e:
        return {"success": False, "error": f"შეცდომა: {str(e)}"}

def get_dashboard_html():
    """Dashboard-ის HTML"""
    return """
    <!DOCTYPE html>
    <html lang="ka">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FootStats Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            body {
                background: linear-gradient(135deg, #0B0F19 0%, #1a1f2e 100%);
                min-height: 100vh;
            }
            .glass-panel {
                background: rgba(30, 41, 59, 0.7);
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            .stat-card {
                transition: all 0.3s ease;
            }
            .stat-card:hover {
                transform: translateY(-5px);
                box-shadow: 0 10px 30px rgba(16, 185, 129, 0.2);
            }
            .match-row:hover {
                background: rgba(16, 185, 129, 0.1);
            }
            .result-h { color: #10b981; }
            .result-d { color: #f59e0b; }
            .result-a { color: #ef4444; }
        </style>
    </head>
    <body class="text-gray-100">
        <!-- Navigation -->
        <nav class="bg-gray-900 border-b border-gray-800">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="flex items-center justify-between h-16">
                    <div class="flex items-center">
                        <div class="flex-shrink-0">
                            <span class="text-2xl font-bold text-emerald-400">⚽ FootStats</span>
                        </div>
                        <div class="ml-10 flex items-baseline space-x-4">
                            <a href="/dashboard" class="bg-gray-900 text-white px-3 py-2 rounded-md text-sm font-medium">Dashboard</a>
                            <a href="/admin/scout" class="text-gray-300 hover:bg-gray-700 hover:text-white px-3 py-2 rounded-md text-sm font-medium">Scout</a>
                        </div>
                    </div>
                </div>
            </div>
        </nav>

        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <!-- Header -->
            <div class="mb-8">
                <h1 class="text-4xl font-bold text-white mb-2">📊 FootStats Dashboard</h1>
                <p class="text-gray-400">საფეხბურთო სტატისტიკის ანალიტიკური პლატფორმა</p>
            </div>

            <!-- Stats Cards -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                <div class="stat-card glass-panel rounded-xl p-6">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-gray-400 text-sm">სულ მატჩი</p>
                            <p class="text-3xl font-bold text-white mt-1" id="stat-matches">0</p>
                        </div>
                        <div class="text-4xl">🏟️</div>
                    </div>
                </div>
                <div class="stat-card glass-panel rounded-xl p-6">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-gray-400 text-sm">სულ გოლი</p>
                            <p class="text-3xl font-bold text-emerald-400 mt-1" id="stat-goals">0</p>
                        </div>
                        <div class="text-4xl">⚽</div>
                    </div>
                </div>
                <div class="stat-card glass-panel rounded-xl p-6">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-gray-400 text-sm">საშუალო გოლი/მატჩი</p>
                            <p class="text-3xl font-bold text-blue-400 mt-1" id="stat-avg-goals">0</p>
                        </div>
                        <div class="text-4xl">📈</div>
                    </div>
                </div>
                <div class="stat-card glass-panel rounded-xl p-6">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-gray-400 text-sm">გუნდები</p>
                            <p class="text-3xl font-bold text-purple-400 mt-1" id="stat-teams">0</p>
                        </div>
                        <div class="text-4xl">🏆</div>
                    </div>
                </div>
            </div>

            <!-- Import Section -->
            <div class="glass-panel rounded-xl p-6 mb-8">
                <h2 class="text-2xl font-bold text-white mb-4">📥 CSV მონაცემების იმპორტი</h2>
                <p class="text-gray-400 mb-4">ჩასვით football-data.co.uk-ის ფორმატის CSV მონაცემები</p>
                <textarea 
                    id="csv-input" 
                    rows="10" 
                    class="w-full bg-gray-800 border border-gray-700 rounded-lg p-4 text-gray-100 font-mono text-sm focus:outline-none focus:border-emerald-500"
                    placeholder="Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HTHG,HTAG,HTR,Referee,HS,AS,HST,AST,HF,AF,HC,AC,HY,AY,HR,AR...&#10;E0,15/08/2025,20:00,Liverpool,Bournemouth,4,2,H,1,0,H,A Taylor,19,10,10,3,7,10,6,7,1,2,0,0..."></textarea>
                <div class="flex gap-4 mt-4">
                    <button 
                        onclick="importCSV()" 
                        id="import-btn"
                        class="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold px-6 py-3 rounded-lg transition">
                        🚀 იმპორტი
                    </button>
                    <button 
                        onclick="clearCSV()" 
                        class="bg-gray-700 hover:bg-gray-600 text-white font-semibold px-6 py-3 rounded-lg transition">
                        🗑️ გასუფთავება
                    </button>
                </div>
            </div>

            <!-- Matches Table -->
            <div class="glass-panel rounded-xl p-6">
                <h2 class="text-2xl font-bold text-white mb-4">📋 მატჩების სია</h2>
                <div class="overflow-x-auto">
                    <table class="w-full text-sm text-left">
                        <thead class="text-xs text-gray-400 uppercase bg-gray-800">
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
        </div>

        <script>
            async function importCSV() {
                const csvText = document.getElementById('csv-input').value;
                const btn = document.getElementById('import-btn');
                
                if (!csvText.trim()) {
                    alert('გთხოვთ ჩასვათ CSV მონაცემები');
                    return;
                }
                
                btn.disabled = true;
                btn.textContent = '⏳ იმპორტი მიმდინარეობს...';
                
                try {
                    const response = await fetch('/api/dashboard/import', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ csv_text: csvText })
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        alert(result.message);
                        await loadStats();
                        await loadMatches();
                    } else {
                        alert('შეცდომა: ' + result.error);
                    }
                } catch (error) {
                    alert('შეცდომა: ' + error.message);
                } finally {
                    btn.disabled = false;
                    btn.textContent = '🚀 იმპორტი';
                }
            }
            
            function clearCSV() {
                document.getElementById('csv-input').value = '';
            }
            
            async function loadStats() {
                try {
                    const response = await fetch('/api/dashboard/stats');
                    const stats = await response.json();
                    
                    document.getElementById('stat-matches').textContent = stats.total_matches || 0;
                    document.getElementById('stat-goals').textContent = stats.total_goals || 0;
                    document.getElementById('stat-avg-goals').textContent = stats.avg_goals_per_match || 0;
                    document.getElementById('stat-teams').textContent = stats.total_teams || 0;
                } catch (error) {
                    console.error('შეცდომა სტატისტიკის ჩატვირთვისას:', error);
                }
            }
            
            async function loadMatches() {
                try {
                    const response = await fetch('/api/dashboard/matches');
                    const matches = await response.json();
                    
                    const tbody = document.getElementById('matches-table');
                    
                    if (matches.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="9" class="px-4 py-8 text-center text-gray-500">მონაცემები ჯერ არ არის იმპორტირებული</td></tr>';
                        return;
                    }
                    
                    tbody.innerHTML = matches.map(match => {
                        const resultClass = match.result === 'H' ? 'result-h' : match.result === 'D' ? 'result-d' : 'result-a';
                        const resultText = match.result === 'H' ? 'მასპინძელი' : match.result === 'D' ? 'ფრე' : 'სტუმარი';
                        const totalCards = (match.home_yellow || 0) + (match.away_yellow || 0) + (match.home_red || 0) + (match.away_red || 0);
                        
                        return `
                            <tr class="match-row">
                                <td class="px-4 py-3">${match.date}</td>
                                <td class="px-4 py-3 font-semibold">${match.home_team}</td>
                                <td class="px-4 py-3 text-center font-bold text-lg">${match.home_goals} - ${match.away_goals}</td>
                                <td class="px-4 py-3 font-semibold">${match.away_team}</td>
                                <td class="px-4 py-3 text-center font-bold ${resultClass}">${resultText}</td>
                                <td class="px-4 py-3 text-gray-400">${match.referee}</td>
                                <td class="px-4 py-3 text-center">${match.home_shots || 0} - ${match.away_shots || 0}</td>
                                <td class="px-4 py-3 text-center">${match.home_corners || 0} - ${match.away_corners || 0}</td>
                                <td class="px-4 py-3 text-center">${totalCards}</td>
                            </tr>
                        `;
                    }).join('');
                } catch (error) {
                    console.error('შეცდომა მატჩების ჩატვირთვისას:', error);
                }
            }
            
            // გვერდის ჩატვირთვისას
            document.addEventListener('DOMContentLoaded', async () => {
                await loadStats();
                await loadMatches();
            });
        </script>
    </body>
    </html>
    """