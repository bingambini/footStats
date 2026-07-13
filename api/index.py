import asyncio
import json
import os
import re
import csv
import io
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field
from loguru import logger

try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False

app = FastAPI()

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
matches_storage: List[Dict] = []
headers_storage: List[str] = []

# ==========================================
# Column Dictionary - 132 სვეტის გაშიფვრა
# ==========================================
COLUMN_DICTIONARY = {
    # ძირითადი ინფორმაცია (1-12)
    "Div": "დივიზიონი/ლიგა (E0 = ინგლისის პრემიერლიგა)",
    "Date": "მატჩის თარიღი (DD/MM/YYYY)",
    "Time": "მატჩის დაწყების დრო (HH:MM)",
    "HomeTeam": "მასპინძელი გუნდის სახელი",
    "AwayTeam": "სტუმარი გუნდის სახელი",
    "Referee": "მატჩის მსაჯის სახელი",
    
    # ანგარიში (5-11)
    "FTHG": "Full Time Home Goals - მატჩის ბოლოს მასპინძლის გოლები",
    "FTAG": "Full Time Away Goals - მატჩის ბოლოს სტუმრის გოლები",
    "FTR": "Full Time Result - შედეგი (H=მასპინძელი, D=ფრე, A=სტუმარი)",
    "HTHG": "Half Time Home Goals - პირველი ტაიმის მასპინძლის გოლები",
    "HTAG": "Half Time Away Goals - პირველი ტაიმის სტუმრის გოლები",
    "HTR": "Half Time Result - პირველი ტაიმის შედეგი",
    
    # სტატისტიკა (12-24)
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
    
    # საბუკმეკერო კოეფიციენტები - შესავლის (25-57)
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
    
    # Over/Under 2.5 გოლი (58-67)
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
    
    # Asian Handicap (68-77)
    "AHh": "Asian Handicap - ფორის ზომა",
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
    
    # დახურვის კოეფიციენტები (78-109)
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
    
    # დახურვის Over/Under (110-119)
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
    
    # დახურვის Asian Handicap (120-132)
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
# CSV Parser - სრული 132 სვეტი
# ==========================================
def parse_csv_complete(csv_text: str) -> Tuple[List[str], List[Dict]]:
    """ამოიღებს ყველა სვეტს CSV ფაილიდან"""
    try:
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        headers = csv_reader.fieldnames or []
        
        rows = []
        for row in csv_reader:
            # გამოტოვეთ ცარიელი სტრიქონები
            if not any(row.values()):
                continue
            
            # კონვერტაცია რიცხვით მნიშვნელობებად
            parsed_row = {}
            for key, value in row.items():
                if value and value.strip():
                    try:
                        # სცადეთ float კონვერტაცია
                        if '.' in value:
                            parsed_row[key] = float(value)
                        else:
                            parsed_row[key] = int(value)
                    except ValueError:
                        # თუ ვერ ხერხდება, დატოვეთ როგორც სტრიქონი
                        parsed_row[key] = value
                else:
                    parsed_row[key] = None
            
            rows.append(parsed_row)
        
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
    return {"message": "FootStats API v6.0 - Full 132 Columns Parser"}

@app.post("/api/import/csv")
async def import_csv(request: Request):
    """იმპორტავს CSV-ს და ინახავს მეხსიერებაში"""
    try:
        body = await request.json()
        csv_data = body.get("csv_data", "")
        
        if not csv_data.strip():
            return {"success": False, "error": "CSV ცარიელია"}
        
        global matches_storage, headers_storage
        headers_storage, matches_storage = parse_csv_complete(csv_data)
        
        # სტატისტიკის გამოთვლა
        total_matches = len(matches_storage)
        total_goals = sum(m.get("FTHG", 0) + m.get("FTAG", 0) for m in matches_storage if m.get("FTHG") and m.get("FTAG"))
        avg_goals = round(total_goals / total_matches, 2) if total_matches > 0 else 0
        
        return {
            "success": True,
            "message": f"წარმატებით იმპორტირდა {total_matches} მატჩი",
            "matches_count": total_matches,
            "columns_count": len(headers_storage),
            "total_goals": total_goals,
            "avg_goals": avg_goals
        }
    except Exception as e:
        logger.error(f"❌ იმპორტის შეცდომა: {e}")
        return {"success": False, "error": str(e)}

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

@app.post("/api/save/to-database")
async def save_to_database():
    """ინახავს მონაცემებს Supabase-ში"""
    if not HAS_SUPABASE:
        return {"success": False, "error": "Supabase არ არის დაყენებული"}
    
    supabase = get_supabase()
    if not supabase:
        return {"success": False, "error": "Supabase კლიენტი არ არის ინიციალიზებული"}
    
    if not matches_storage:
        return {"success": False, "error": "მონაცემები ჯერ არ არის იმპორტირებული"}
    
    try:
        # ბატჩური ჩაწერა (50 მატჩი ერთდროულად)
        batch_size = 50
        total_inserted = 0
        
        for i in range(0, len(matches_storage), batch_size):
            batch = matches_storage[i:i + batch_size]
            
            # Supabase-ში ჩაწერა
            response = supabase.table("premier_league_2025_2026").insert(batch).execute()
            total_inserted += len(batch)
            
            logger.info(f"📝 ჩაიწერა {total_inserted}/{len(matches_storage)} მატჩი")
        
        return {
            "success": True,
            "message": f"წარმატებით ჩაიწერა {total_inserted} მატჩი",
            "inserted": total_inserted
        }
    except Exception as e:
        logger.error(f"❌ ბაზაში ჩაწერის შეცდომა: {e}")
        return {"success": False, "error": str(e)}

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
            .glass-panel { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); }
            .tab-active { background-color: #10b981; color: white; }
            .tab-inactive { background-color: #374151; color: #9ca3af; }
            .tooltip { position: relative; }
            .tooltip:hover::after {
                content: attr(data-tooltip);
                position: absolute;
                bottom: 100%;
                left: 50%;
                transform: translateX(-50%);
                background: #1F2937;
                color: white;
                padding: 0.5rem;
                border-radius: 0.25rem;
                white-space: nowrap;
                z-index: 100;
                font-size: 0.75rem;
            }
        </style>
    </head>
    <body class="bg-gradient-to-br from-[#0B0F19] to-[#1a1f2e] text-[#E2E8F0] font-sans min-h-screen">
        <div class="max-w-full mx-auto p-6">
            <!-- Header -->
            <div class="text-center mb-8">
                <h1 class="text-4xl font-bold text-white mb-2">📊 FootStats Dashboard v6.0</h1>
                <p class="text-gray-400">სრული 132 სვეტიანი მონაცემთა პარსერი - Premier League 2025/2026</p>
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
                    <p class="text-gray-400 text-sm">მოქმედება</p>
                    <button onclick="saveToDatabase()" id="saveBtn" class="mt-1 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-semibold">💾 ბაზაში ჩაწერა</button>
                </div>
            </div>

            <!-- Tabs -->
            <div class="flex gap-2 mb-6">
                <button onclick="switchTab('import')" id="tab-import" class="tab-active px-6 py-3 rounded-lg font-semibold">📥 იმპორტი</button>
                <button onclick="switchTab('data')" id="tab-data" class="tab-inactive px-6 py-3 rounded-lg font-semibold">📊 მონაცემები</button>
                <button onclick="switchTab('columns')" id="tab-columns" class="tab-inactive px-6 py-3 rounded-lg font-semibold">📖 სვეტები (132)</button>
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
                    <h2 class="text-2xl font-bold text-white">📊 მატჩების ცხრილი (ყველა 132 სვეტი)</h2>
                    <span class="px-3 py-1 bg-gray-800 rounded text-sm text-gray-400" id="tableInfo">0 მატჩი × 0 სვეტი</span>
                </div>
                <div class="overflow-x-auto max-h-[600px] border border-gray-700 rounded-lg">
                    <table class="w-full text-xs text-left">
                        <thead class="text-xs text-gray-400 uppercase bg-[#0F172A] sticky top-0">
                            <tr id="tableHeader">
                                <th class="px-2 py-2">იტვირთება...</th>
                            </tr>
                        </thead>
                        <tbody id="tableBody">
                            <tr>
                                <td colspan="10" class="px-4 py-8 text-center text-gray-500">ჯერ არ არის მონაცემები</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Columns Tab -->
            <div id="section-columns" class="hidden glass-panel rounded-xl p-6 mb-8">
                <h2 class="text-2xl font-bold text-white mb-4">📖 სვეტების გაშიფვრა (132 სვეტი)</h2>
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3" id="columnsList">
                    <div class="text-gray-500">იტვირთება...</div>
                </div>
            </div>

            <!-- Logs -->
            <div class="glass-panel rounded-xl p-6">
                <div class="flex justify-between items-center mb-4">
                    <h3 class="text-lg font-bold text-white">📜 ლაივ ლოგები</h3>
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
                ['import', 'data', 'columns'].forEach(t => {
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
                        document.getElementById('stat-goals').textContent = result.total_goals;
                        document.getElementById('stat-avg').textContent = result.avg_goals;
                        
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
                        columnDictionary = result.column_dictionary;
                        
                        addLog(`✅ ჩაიტვირთა ${allMatchesData.length} მატჩი`, 'success');
                        renderTable();
                        loadColumns();
                    }
                } catch (error) {
                    addLog(`❌ ${error.message}`, 'error');
                }
            }

            function renderTable() {
                if (allMatchesData.length === 0 || allHeaders.length === 0) return;
                
                const header = document.getElementById('tableHeader');
                const tbody = document.getElementById('tableBody');
                
                // სათაური
                header.innerHTML = '<tr>' + allHeaders.map(h => {
                    const tooltip = columnDictionary[h] || h;
                    return `<th class="px-2 py-2 tooltip" data-tooltip="${tooltip}">${h}</th>`;
                }).join('') + '</tr>';
                
                // სხეული - ყველა სტრიქონი
                tbody.innerHTML = allMatchesData.map(row => 
                    '<tr class="hover:bg-[#1E293B]">' + allHeaders.map(h => {
                        const value = row[h] !== null && row[h] !== undefined ? row[h] : '-';
                        return `<td class="px-2 py-2 whitespace-nowrap">${value}</td>`;
                    }).join('') + '</tr>'
                ).join('');
                
                document.getElementById('tableInfo').textContent = `${allMatchesData.length} მატჩი × ${allHeaders.length} სვეტი`;
                addLog(`📊 ცხრილი აგებულია: ${allMatchesData.length} × ${allHeaders.length}`, 'success');
            }

            function loadColumns() {
                const columnsList = document.getElementById('columnsList');
                columnsList.innerHTML = Object.entries(columnDictionary).map(([col, desc]) => {
                    return `
                        <div class="bg-[#0B0F19] border border-gray-700 rounded-lg p-3 hover:border-emerald-500 transition">
                            <div class="font-mono font-bold text-emerald-400 text-sm mb-1">${col}</div>
                            <div class="text-xs text-gray-400">${desc}</div>
                        </div>
                    `;
                }).join('');
                
                addLog(`📖 ჩაიტვირთა ${Object.keys(columnDictionary).length} სვეტის გაშიფვრა`, 'success');
            }

            async function saveToDatabase() {
                const btn = document.getElementById('saveBtn');
                
                if (allMatchesData.length === 0) {
                    alert('ჯერ იმპორტირეთ მონაცემები');
                    return;
                }
                
                btn.disabled = true;
                btn.textContent = '⏳ ჩაწერა...';
                addLog('💾 ვიწყებ ბაზაში ჩაწერას...', 'info');
                
                try {
                    const response = await fetch('/api/save/to-database', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        addLog(`✅ ${result.message}`, 'success');
                        alert(result.message);
                    } else {
                        addLog(`❌ ${result.error}`, 'error');
                        alert('შეცდომა: ' + result.error);
                    }
                } catch (error) {
                    addLog(`❌ ${error.message}`, 'error');
                    alert('შეცდომა: ' + error.message);
                } finally {
                    btn.disabled = false;
                    btn.textContent = '💾 ბაზაში ჩაწერა';
                }
            }

            function addLog(message, type = 'info') {
                const terminal = document.getElementById('terminal');
                const log = document.createElement('div');
                log.className = 'log-entry';
                
                const colors = { 'info': 'text-blue-400', 'success': 'text-emerald-400', 'error': 'text-red-400' };
                const timestamp = new Date().toLocaleTimeString('ka-GE');
                
                log.innerHTML = `<span class="text-gray-600">[${timestamp}]</span> <span class="${colors[type]}">${message}</span>`;
                terminal.appendChild(log);
                terminal.scrollTop = terminal.scrollHeight;
            }

            function clearLogs() {
                document.getElementById('terminal').innerHTML = '<div class="text-gray-500">// გასუფთავდა</div>';
            }

            // ჩატვირთვისას
            loadColumns();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)