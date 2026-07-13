import asyncio
import json
import os
import re
import csv
import io
from typing import Dict, List, Tuple, Optional
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field
from loguru import logger

app = FastAPI()

# ==========================================
# In-Memory Storage
# ==========================================
matches_storage: List[Dict] = []
headers_storage: List[str] = []

# ==========================================
# სვეტების გაშიფვრა (Column Dictionary)
# ==========================================
COLUMN_DICTIONARY = {
    # ძირითადი ინფორმაცია
    "Div": "დივიზიონი (E0 = ინგლისის პრემიერლიგა)",
    "Date": "მატჩის თარიღი (DD/MM/YYYY)",
    "Time": "მატჩის დაწყების დრო (HH:MM)",
    "HomeTeam": "მასპინძელი გუნდის სახელი",
    "AwayTeam": "სტუმარი გუნდის სახელი",
    "Referee": "მატჩის მსაჯის სახელი",
    
    # ანგარიში
    "FTHG": "Full Time Home Goals - მატჩის ბოლოს მასპინძლის გოლები",
    "FTAG": "Full Time Away Goals - მატჩის ბოლოს სტუმრის გოლები",
    "FTR": "Full Time Result - შედეგი (H=მასპინძელი, D=ფრე, A=სტუმარი)",
    "HTHG": "Half Time Home Goals - პირველი ტაიმის მასპინძლის გოლები",
    "HTAG": "Half Time Away Goals - პირველი ტაიმის სტუმრის გოლები",
    "HTR": "Half Time Result - პირველი ტაიმის შედეგი (H/D/A)",
    
    # სტატისტიკა
    "HS": "Home Shots - მასპინძლის დარტყმები სულ",
    "AS": "Away Shots - სტუმრის დარტყმები სულ",
    "HST": "Home Shots on Target - მასპინძლის დარტყმები კარში",
    "AST": "Away Shots on Target - სტუმრის დარტყმები კარში",
    "HF": "Home Fouls - მასპინძლის ჯარიმები",
    "AF": "Away Fouls - სტუმრის ჯარიმები",
    "HC": "Home Corners - მასპინძლის კუთხურები",
    "AC": "Away Corners - სტუმრის კუთხურები",
    "HY": "Home Yellow Cards - მასპინძლის ყვითელი ბარათები",
    "AY": "Away Yellow Cards - სტუმრის ყვითელი ბარათები",
    "HR": "Home Red Cards - მასპინძლის წითელი ბარათები",
    "AR": "Away Red Cards - სტუმრის წითელი ბარათები",
    
    # საბუკმეკერო კოეფიციენტები - შესავლის (Opening Odds)
    "B365H": "Bet365 - მასპინძლის კოეფიციენტი",
    "B365D": "Bet365 - ფრის კოეფიციენტი",
    "B365A": "Bet365 - სტუმრის კოეფიციენტი",
    "BFDH": "Betfred - მასპინძლის კოეფიციენტი",
    "BFDD": "Betfred - ფრის კოეფიციენტი",
    "BFDA": "Betfred - სტუმრის კოეფიციენტი",
    "BMGMH": "BetMGM - მასპინძლის კოეფიციენტი",
    "BMGMD": "BetMGM - ფრის კოეფიციენტი",
    "BMGMA": "BetMGM - სტუმრის კოეფიციენტი",
    "BVH": "Betvictor - მასპინძლის კოეფიციენტი",
    "BVD": "Betvictor - ფრის კოეფიციენტი",
    "BVA": "Betvictor - სტუმრის კოეფიციენტი",
    "BWH": "Betway - მასპინძლის კოეფიციენტი",
    "BWD": "Betway - ფრის კოეფიციენტი",
    "BWA": "Betway - სტუმრის კოეფიციენტი",
    "CLH": "Coral/Ladbrokes - მასპინძლის კოეფიციენტი",
    "CLD": "Coral/Ladbrokes - ფრის კოეფიციენტი",
    "CLA": "Coral/Ladbrokes - სტუმრის კოეფიციენტი",
    "LBH": "Ladbrokes - მასპინძლის კოეფიციენტი",
    "LBD": "Ladbrokes - ფრის კოეფიციენტი",
    "LBA": "Ladbrokes - სტუმრის კოეფიციენტი",
    "PSH": "Pinnacle - მასპინძლის კოეფიციენტი",
    "PSD": "Pinnacle - ფრის კოეფიციენტი",
    "PSA": "Pinnacle - სტუმრის კოეფიციენტი",
    "MaxH": "მაქსიმალური კოეფიციენტი - მასპინძელი",
    "MaxD": "მაქსიმალური კოეფიციენტი - ფრე",
    "MaxA": "მაქსიმალური კოეფიციენტი - სტუმარი",
    "AvgH": "საშუალო კოეფიციენტი - მასპინძელი",
    "AvgD": "საშუალო კოეფიციენტი - ფრე",
    "AvgA": "საშუალო კოეფიციენტი - სტუმარი",
    "BFEH": "Betfair Exchange - მასპინძლის კოეფიციენტი",
    "BFED": "Betfair Exchange - ფრის კოეფიციენტი",
    "BFEA": "Betfair Exchange - სტუმრის კოეფიციენტი",
    
    # Over/Under 2.5 გოლი
    "B365>2.5": "Bet365 - 2.5 გოლზე მეტი",
    "B365<2.5": "Bet365 - 2.5 გოლზე ნაკლები",
    "P>2.5": "Pinnacle - 2.5 გოლზე მეტი",
    "P<2.5": "Pinnacle - 2.5 გოლზე ნაკლები",
    "Max>2.5": "მაქსიმალური - 2.5 გოლზე მეტი",
    "Max<2.5": "მაქსიმალური - 2.5 გოლზე ნაკლები",
    "Avg>2.5": "საშუალო - 2.5 გოლზე მეტი",
    "Avg<2.5": "საშუალო - 2.5 გოლზე ნაკლები",
    "BFE>2.5": "Betfair Exchange - 2.5 გოლზე მეტი",
    "BFE<2.5": "Betfair Exchange - 2.5 გოლზე ნაკლები",
    
    # Asian Handicap (ფორა)
    "AHh": "Asian Handicap - ფორის ზომა (მაგ: -1.5)",
    "B365AHH": "Bet365 - ფორა მასპინძელზე",
    "B365AHA": "Bet365 - ფორა სტუმარზე",
    "PAHH": "Pinnacle - ფორა მასპინძელზე",
    "PAHA": "Pinnacle - ფორა სტუმარზე",
    "MaxAHH": "მაქსიმალური - ფორა მასპინძელზე",
    "MaxAHA": "მაქსიმალური - ფორა სტუმარზე",
    "AvgAHH": "საშუალო - ფორა მასპინძელზე",
    "AvgAHA": "საშუალო - ფორა სტუმარზე",
    "BFEAHH": "Betfair Exchange - ფორა მასპინძელზე",
    "BFEAHA": "Betfair Exchange - ფორა სტუმარზე",
    
    # დახურვის კოეფიციენტები (Closing Odds)
    "B365CH": "Bet365 - დახურვის მასპინძელი",
    "B365CD": "Bet365 - დახურვის ფრე",
    "B365CA": "Bet365 - დახურვის სტუმარი",
    "BFDCH": "Betfred - დახურვის მასპინძელი",
    "BFDCD": "Betfred - დახურვის ფრე",
    "BFDCA": "Betfred - დახურვის სტუმარი",
    "BMGMCH": "BetMGM - დახურვის მასპინძელი",
    "BMGMCD": "BetMGM - დახურვის ფრე",
    "BMGMCA": "BetMGM - დახურვის სტუმარი",
    "BVCH": "Betvictor - დახურვის მასპინძელი",
    "BVCD": "Betvictor - დახურვის ფრე",
    "BVCA": "Betvictor - დახურვის სტუმარი",
    "BWCH": "Betway - დახურვის მასპინძელი",
    "BWCD": "Betway - დახურვის ფრე",
    "BWCA": "Betway - დახურვის სტუმარი",
    "CLCH": "Coral/Ladbrokes - დახურვის მასპინძელი",
    "CLCD": "Coral/Ladbrokes - დახურვის ფრე",
    "CLCA": "Coral/Ladbrokes - დახურვის სტუმარი",
    "LBCH": "Ladbrokes - დახურვის მასპინძელი",
    "LBCD": "Ladbrokes - დახურვის ფრე",
    "LBCA": "Ladbrokes - დახურვის სტუმარი",
    "PSCH": "Pinnacle - დახურვის მასპინძელი",
    "PSCD": "Pinnacle - დახურვის ფრე",
    "PSCA": "Pinnacle - დახურვის სტუმარი",
    "MaxCH": "მაქსიმალური დახურვის - მასპინძელი",
    "MaxCD": "მაქსიმალური დახურვის - ფრე",
    "MaxCA": "მაქსიმალური დახურვის - სტუმარი",
    "AvgCH": "საშუალო დახურვის - მასპინძელი",
    "AvgCD": "საშუალო დახურვის - ფრე",
    "AvgCA": "საშუალო დახურვის - სტუმარი",
    "BFECH": "Betfair Exchange - დახურვის მასპინძელი",
    "BFECD": "Betfair Exchange - დახურვის ფრე",
    "BFECA": "Betfair Exchange - დახურვის სტუმარი",
    
    # დახურვის Over/Under
    "B365C>2.5": "Bet365 - დახურვის 2.5 გოლზე მეტი",
    "B365C<2.5": "Bet365 - დახურვის 2.5 გოლზე ნაკლები",
    "PC>2.5": "Pinnacle - დახურვის 2.5 გოლზე მეტი",
    "PC<2.5": "Pinnacle - დახურვის 2.5 გოლზე ნაკლები",
    "MaxC>2.5": "მაქსიმალური დახურვის - 2.5 გოლზე მეტი",
    "MaxC<2.5": "მაქსიმალური დახურვის - 2.5 გოლზე ნაკლები",
    "AvgC>2.5": "საშუალო დახურვის - 2.5 გოლზე მეტი",
    "AvgC<2.5": "საშუალო დახურვის - 2.5 გოლზე ნაკლები",
    "BFEC>2.5": "Betfair Exchange - დახურვის 2.5 გოლზე მეტი",
    "BFEC<2.5": "Betfair Exchange - დახურვის 2.5 გოლზე ნაკლები",
    
    # დახურვის Asian Handicap
    "AHCh": "Asian Handicap - დახურვის ფორა",
    "B365CAHH": "Bet365 - დახურვის ფორა მასპინძელზე",
    "B365CAHA": "Bet365 - დახურვის ფორა სტუმარზე",
    "PCAHH": "Pinnacle - დახურვის ფორა მასპინძელზე",
    "PCAHA": "Pinnacle - დახურვის ფორა სტუმარზე",
    "MaxCAHH": "მაქსიმალური დახურვის - ფორა მასპინძელზე",
    "MaxCAHA": "მაქსიმალური დახურვის - ფორა სტუმარზე",
    "AvgCAHH": "საშუალო დახურვის - ფორა მასპინძელზე",
    "AvgCAHA": "საშუალო დახურვის - ფორა სტუმარზე",
    "BFECAHH": "Betfair Exchange - დახურვის ფორა მასპინძელზე",
    "BFECAHA": "Betfair Exchange - დახურვის ფორა სტუმარზე"
}

# ==========================================
# CSV Parser - სრული მონაცემების ამოღება
# ==========================================
def parse_csv_complete(csv_text: str) -> Tuple[List[str], List[Dict]]:
    """ამოიღებს ყველა სვეტს და სტრიქონს CSV ფაილიდან"""
    try:
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        headers = csv_reader.fieldnames or []
        rows = []
        for row in csv_reader:
            if any(row.values()):
                rows.append(row)
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
    return {"message": "FootStats Dashboard v5.0 - Full 132 Columns"}

@app.post("/api/import/csv")
async def import_csv(request: dict):
    """იმპორტავს CSV-ს და ინახავს მეხსიერებაში"""
    global matches_storage, headers_storage
    
    csv_data = request.get("csv_data", "")
    if not csv_data.strip():
        return {"success": False, "error": "CSV ცარიელია"}
    
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
        "data": matches_storage,
        "column_dictionary": COLUMN_DICTIONARY
    }

@app.get("/api/columns/dictionary")
async def get_column_dictionary():
    """აბრუნებს სვეტების გაშიფვრას"""
    return {
        "success": True,
        "dictionary": COLUMN_DICTIONARY,
        "total_columns": len(COLUMN_DICTIONARY)
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
            
            /* ცხრილის სტილები */
            .data-table {
                width: 100%;
                border-collapse: collapse;
                font-size: 0.7rem;
            }
            .data-table thead {
                position: sticky;
                top: 0;
                background-color: #0F172A;
                z-index: 10;
            }
            .data-table th {
                padding: 0.5rem 0.5rem;
                text-align: left;
                font-weight: 600;
                color: #9CA3AF;
                border-bottom: 2px solid #374151;
                white-space: nowrap;
                cursor: help;
                position: relative;
            }
            .data-table th:hover {
                background-color: #1E293B;
            }
            .data-table td {
                padding: 0.4rem 0.5rem;
                border-bottom: 1px solid #374151;
                white-space: nowrap;
                color: #E2E8F0;
            }
            .data-table tr:hover {
                background-color: rgba(16, 185, 129, 0.1);
            }
            
            /* Tooltip */
            .tooltip {
                position: absolute;
                background: #1F2937;
                color: #F3F4F6;
                padding: 0.5rem 0.75rem;
                border-radius: 0.375rem;
                font-size: 0.75rem;
                white-space: nowrap;
                z-index: 100;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
                pointer-events: none;
                opacity: 0;
                transition: opacity 0.2s;
            }
            .data-table th:hover .tooltip {
                opacity: 1;
            }
            
            /* Scrollable container */
            .table-container {
                overflow: auto;
                max-height: 600px;
                border: 1px solid #374151;
                border-radius: 0.5rem;
            }
            
            /* Column categories */
            .cat-main { color: #10b981; }
            .cat-score { color: #3b82f6; }
            .cat-stats { color: #8b5cf6; }
            .cat-odds { color: #f59e0b; }
            .cat-ou { color: #ef4444; }
            .cat-ah { color: #ec4899; }
        </style>
    </head>
    <body class="bg-gradient-to-br from-[#0B0F19] to-[#1a1f2e] text-[#E2E8F0] font-sans min-h-screen">
        <div class="max-w-full mx-auto p-6">
            <!-- Header -->
            <div class="text-center mb-8">
                <h1 class="text-4xl font-bold text-white mb-2">📊 FootStats Dashboard v5.0</h1>
                <p class="text-gray-400">სრული 132 სვეტიანი მონაცემთა ბაზა - ყველა ინფორმაცია ერთ ადგილას</p>
            </div>

            <!-- Stats Cards -->
            <div class="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
                <div class="glass-panel rounded-xl p-5">
                    <p class="text-gray-400 text-sm">სულ მატჩი</p>
                    <p class="text-3xl font-bold text-white mt-1" id="stat-matches">0</p>
                </div>
                <div class="glass-panel rounded-xl p-5">
                    <p class="text-gray-400 text-sm">სვეტები</p>
                    <p class="text-3xl font-bold text-emerald-400 mt-1" id="stat-columns">0</p>
                </div>
                <div class="glass-panel rounded-xl p-5">
                    <p class="text-gray-400 text-sm">სულ გოლი</p>
                    <p class="text-3xl font-bold text-blue-400 mt-1" id="stat-goals">0</p>
                </div>
                <div class="glass-panel rounded-xl p-5">
                    <p class="text-gray-400 text-sm">საშუალო გოლი</p>
                    <p class="text-3xl font-bold text-purple-400 mt-1" id="stat-avg">0</p>
                </div>
                <div class="glass-panel rounded-xl p-5">
                    <p class="text-gray-400 text-sm">ექსპორტი</p>
                    <button onclick="exportJSON()" class="mt-1 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-semibold">💾 JSON</button>
                </div>
            </div>

            <!-- Tabs -->
            <div class="flex gap-2 mb-6">
                <button onclick="switchTab('import')" id="tab-import" class="tab-active px-6 py-3 rounded-lg font-semibold">📥 იმპორტი</button>
                <button onclick="switchTab('data')" id="tab-data" class="tab-inactive px-6 py-3 rounded-lg font-semibold">📊 მონაცემები</button>
                <button onclick="switchTab('dictionary')" id="tab-dictionary" class="tab-inactive px-6 py-3 rounded-lg font-semibold">📖 სვეტების გაშიფვრა</button>
            </div>

            <!-- Import Tab -->
            <div id="section-import" class="glass-panel rounded-xl p-6 mb-8">
                <h2 class="text-2xl font-bold text-white mb-4">📥 CSV ფაილის იმპორტი</h2>
                <p class="text-gray-400 mb-4">ჩასვით football-data.co.uk ფორმატის CSV ფაილი. სისტემა ამოიღებს ყველა 132 სვეტს.</p>
                <textarea id="csvInput" rows="12" placeholder="Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR..." class="w-full bg-[#0B0F19] border border-gray-700 rounded-lg p-4 text-emerald-400 font-mono text-xs resize-none focus:outline-none focus:border-emerald-500"></textarea>
                <div class="flex gap-3 mt-4">
                    <button onclick="importCSV()" id="importBtn" class="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-3 rounded-lg">🚀 იმპორტი</button>
                    <button onclick="document.getElementById('csvInput').value=''" class="px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg">🗑️ გასუფთავება</button>
                </div>
            </div>

            <!-- Data Tab -->
            <div id="section-data" class="hidden glass-panel rounded-xl p-6 mb-8">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-2xl font-bold text-white">📊 სრული მონაცემთა ცხრილი</h2>
                    <span class="px-3 py-1 bg-gray-800 rounded text-sm text-gray-400" id="tableInfo">0 მატჩი × 0 სვეტი</span>
                </div>
                <div class="table-container" id="tableContainer">
                    <table class="data-table">
                        <thead id="tableHeader">
                            <tr>
                                <th>მონაცემები ჯერ არ არის იმპორტირებული</th>
                            </tr>
                        </thead>
                        <tbody id="tableBody">
                            <tr>
                                <td>ჩასვით CSV და დააჭირეთ "იმპორტი"-ს</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Dictionary Tab -->
            <div id="section-dictionary" class="hidden glass-panel rounded-xl p-6 mb-8">
                <h2 class="text-2xl font-bold text-white mb-4">📖 სვეტების გაშიფვრა (132 სვეტი)</h2>
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3" id="dictionaryContainer">
                    <div class="text-gray-500">იტვირთება...</div>
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
            let allMatchesData = [];
            let allHeaders = [];
            let columnDictionary = {};

            function switchTab(tab) {
                ['import', 'data', 'dictionary'].forEach(t => {
                    document.getElementById('tab-' + t).className = tab === t ? 'tab-active px-6 py-3 rounded-lg font-semibold' : 'tab-inactive px-6 py-3 rounded-lg font-semibold';
                    document.getElementById('section-' + t).classList.toggle('hidden', tab !== t);
                });
            }

            async function importCSV() {
                const csvData = document.getElementById('csvInput').value;
                const btn = document.getElementById('importBtn');
                
                if (!csvData.trim()) {
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
                        body: JSON.stringify({ csv_data: csvData })
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        addLog(`✅ ${result.message}`, 'success');
                        addLog(`📊 სვეტები: ${result.columns_count}`, 'info');
                        
                        document.getElementById('stat-matches').textContent = result.matches_count;
                        document.getElementById('stat-columns').textContent = result.columns_count;
                        
                        await loadData();
                        switchTab('data');
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

            async function loadData() {
                try {
                    const response = await fetch('/api/matches/all');
                    const result = await response.json();
                    
                    if (result.success) {
                        allMatchesData = result.data;
                        allHeaders = result.headers;
                        columnDictionary = result.column_dictionary || {};
                        
                        addLog(`✅ ჩაიტვირთა ${allMatchesData.length} მატჩი`, 'success');
                        
                        renderTable();
                        calculateStats();
                    }
                } catch (error) {
                    addLog(`❌ ${error.message}`, 'error');
                }
            }

            function calculateStats() {
                let totalGoals = 0;
                allMatchesData.forEach(m => {
                    const hg = parseInt(m.FTHG) || 0;
                    const ag = parseInt(m.FTAG) || 0;
                    totalGoals += hg + ag;
                });
                
                const avgGoals = allMatchesData.length > 0 ? (totalGoals / allMatchesData.length).toFixed(2) : 0;
                
                document.getElementById('stat-goals').textContent = totalGoals;
                document.getElementById('stat-avg').textContent = avgGoals;
            }

            function getCategoryClass(col) {
                if (['Div','Date','Time','HomeTeam','AwayTeam','Referee'].includes(col)) return 'cat-main';
                if (['FTHG','FTAG','FTR','HTHG','HTAG','HTR'].includes(col)) return 'cat-score';
                if (['HS','AS','HST','AST','HF','AF','HC','AC','HY','AY','HR','AR'].includes(col)) return 'cat-stats';
                if (col.includes('>2.5') || col.includes('<2.5')) return 'cat-ou';
                if (col.includes('AH')) return 'cat-ah';
                return 'cat-odds';
            }

            function renderTable() {
                if (allMatchesData.length === 0 || allHeaders.length === 0) return;
                
                const header = document.getElementById('tableHeader');
                const tbody = document.getElementById('tableBody');
                
                // სათაური
                header.innerHTML = '<tr>' + allHeaders.map(col => {
                    const catClass = getCategoryClass(col);
                    const tooltip = columnDictionary[col] || col;
                    return `<th class="${catClass}" title="${tooltip}">${col}<span class="tooltip">${tooltip}</span></th>`;
                }).join('') + '</tr>';
                
                // სხეული
                tbody.innerHTML = allMatchesData.map(row => 
                    '<tr>' + allHeaders.map(col => {
                        const value = row[col] || '-';
                        const catClass = getCategoryClass(col);
                        return `<td class="${catClass}">${value}</td>`;
                    }).join('') + '</tr>'
                ).join('');
                
                document.getElementById('tableInfo').textContent = `${allMatchesData.length} მატჩი × ${allHeaders.length} სვეტი`;
                addLog(`📊 ცხრილი აგებულია: ${allMatchesData.length} × ${allHeaders.length}`, 'success');
            }

            async function loadDictionary() {
                try {
                    const response = await fetch('/api/columns/dictionary');
                    const result = await response.json();
                    
                    if (result.success) {
                        const container = document.getElementById('dictionaryContainer');
                        const dict = result.dictionary;
                        
                        container.innerHTML = Object.entries(dict).map(([col, desc]) => {
                            const catClass = getCategoryClass(col);
                            return `
                                <div class="bg-[#0B0F19] border border-gray-700 rounded-lg p-3 hover:border-emerald-500 transition">
                                    <div class="font-mono font-bold ${catClass} text-sm mb-1">${col}</div>
                                    <div class="text-xs text-gray-400">${desc}</div>
                                </div>
                            `;
                        }).join('');
                        
                        addLog(`📖 ჩაიტვირთა ${result.total_columns} სვეტის გაშიფვრა`, 'success');
                    }
                } catch (error) {
                    addLog(`❌ ${error.message}`, 'error');
                }
            }

            function exportJSON() {
                if (allMatchesData.length === 0) {
                    alert('ჯერ იმპორტირეთ მონაცემები');
                    return;
                }
                
                const data = {
                    headers: allHeaders,
                    matches: allMatchesData,
                    column_dictionary: columnDictionary,
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
            loadDictionary();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)