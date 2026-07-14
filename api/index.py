import asyncio
import json
import os
import csv
import io
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from loguru import logger

try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False

app = FastAPI(title="FootStats API - Full 132 Columns")

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
# სვეტების გაშიფვრა (132 სვეტი)
# ==========================================
COLUMN_DICTIONARY = {
    # ძირითადი ინფორმაცია (1-12)
    "Div": "🏆 დივიზიონი/ლიგა (E0 = ინგლისის პრემიერლიგა)",
    "Date": "📅 მატჩის თარიღი (DD/MM/YYYY)",
    "Time": "⏰ მატჩის დაწყების დრო (HH:MM)",
    "HomeTeam": "🏠 მასპინძელი გუნდის სახელი",
    "AwayTeam": "✈️ სტუმარი გუნდის სახელი",
    "FTHG": "⚽ მატჩის ბოლოს მასპინძლის გოლები (Full Time Home Goals)",
    "FTAG": "⚽ მატჩის ბოლოს სტუმრის გოლები (Full Time Away Goals)",
    "FTR": "🏁 მატჩის შედეგი (H=მასპინძელი, D=ფრე, A=სტუმარი)",
    "HTHG": "⚽ პირველი ტაიმის მასპინძლის გოლები (Half Time Home Goals)",
    "HTAG": "⚽ პირველი ტაიმის სტუმრის გოლები (Half Time Away Goals)",
    "HTR": "🏁 პირველი ტაიმის შედეგი (H/D/A)",
    "Referee": "👨‍⚖️ მატჩის მსაჯის სახელი",
    
    # სტატისტიკა (13-24)
    "HS": "🥅 მასპინძლის დარტყმები სულ (Home Shots)",
    "AS": "🥅 სტუმრის დარტყმები სულ (Away Shots)",
    "HST": "🎯 მასპინძლის დარტყმები კარში (Home Shots on Target)",
    "AST": "🎯 სტუმრის დარტყმები კარში (Away Shots on Target)",
    "HF": "⚠️ მასპინძლის ჯარიმები (Home Fouls)",
    "AF": "⚠️ სტუმრის ჯარიმები (Away Fouls)",
    "HC": "🚩 მასპინძლის კუთხურები (Home Corners)",
    "AC": "🚩 სტუმრის კუთხურები (Away Corners)",
    "HY": "🟨 მასპინძლის ყვითელი ბარათები (Home Yellow Cards)",
    "AY": "🟨 სტუმრის ყვითელი ბარათები (Away Yellow Cards)",
    "HR": "🟥 მასპინძლის წითელი ბარათები (Home Red Cards)",
    "AR": "🟥 სტუმრის წითელი ბარათები (Away Red Cards)",
    
    # საბუკმეკერო კოეფიციენტები - შესავლის (25-57)
    "B365H": "💰 Bet365 - მასპინძლის კოეფიციენტი",
    "B365D": "💰 Bet365 - ფრის კოეფიციენტი",
    "B365A": "💰 Bet365 - სტუმრის კოეფიციენტი",
    "BFDH": "💰 Betfred - მასპინძლის კოეფიციენტი",
    "BFDD": "💰 Betfred - ფრის კოეფიციენტი",
    "BFDA": "💰 Betfred - სტუმრის კოეფიციენტი",
    "BMGMH": "💰 BetMGM - მასპინძლის კოეფიციენტი",
    "BMGMD": "💰 BetMGM - ფრის კოეფიციენტი",
    "BMGMA": "💰 BetMGM - სტუმრის კოეფიციენტი",
    "BVH": "💰 Betvictor - მასპინძლის კოეფიციენტი",
    "BVD": "💰 Betvictor - ფრის კოეფიციენტი",
    "BVA": "💰 Betvictor - სტუმრის კოეფიციენტი",
    "BWH": "💰 Betway - მასპინძლის კოეფიციენტი",
    "BWD": "💰 Betway - ფრის კოეფიციენტი",
    "BWA": "💰 Betway - სტუმრის კოეფიციენტი",
    "CLH": "💰 Coral/Ladbrokes - მასპინძლის კოეფიციენტი",
    "CLD": "💰 Coral/Ladbrokes - ფრის კოეფიციენტი",
    "CLA": "💰 Coral/Ladbrokes - სტუმრის კოეფიციენტი",
    "LBH": "💰 Ladbrokes - მასპინძლის კოეფიციენტი",
    "LBD": "💰 Ladbrokes - ფრის კოეფიციენტი",
    "LBA": "💰 Ladbrokes - სტუმრის კოეფიციენტი",
    "PSH": "💰 Pinnacle - მასპინძლის კოეფიციენტი",
    "PSD": "💰 Pinnacle - ფრის კოეფიციენტი",
    "PSA": "💰 Pinnacle - სტუმრის კოეფიციენტი",
    "MaxH": "📈 მაქსიმალური კოეფიციენტი - მასპინძელი",
    "MaxD": "📈 მაქსიმალური კოეფიციენტი - ფრე",
    "MaxA": "📈 მაქსიმალური კოეფიციენტი - სტუმარი",
    "AvgH": "📊 საშუალო კოეფიციენტი - მასპინძელი",
    "AvgD": "📊 საშუალო კოეფიციენტი - ფრე",
    "AvgA": "📊 საშუალო კოეფიციენტი - სტუმარი",
    "BFEH": "💰 Betfair Exchange - მასპინძლის კოეფიციენტი",
    "BFED": "💰 Betfair Exchange - ფრის კოეფიციენტი",
    "BFEA": "💰 Betfair Exchange - სტუმრის კოეფიციენტი",
    
    # Over/Under 2.5 გოლი - შესავლის (58-67)
    "B365>2.5": "📊 Bet365 - 2.5 გოლზე მეტი",
    "B365<2.5": "📊 Bet365 - 2.5 გოლზე ნაკლები",
    "P>2.5": "📊 Pinnacle - 2.5 გოლზე მეტი",
    "P<2.5": "📊 Pinnacle - 2.5 გოლზე ნაკლები",
    "Max>2.5": "📈 მაქსიმალური - 2.5 გოლზე მეტი",
    "Max<2.5": "📈 მაქსიმალური - 2.5 გოლზე ნაკლები",
    "Avg>2.5": "📊 საშუალო - 2.5 გოლზე მეტი",
    "Avg<2.5": "📊 საშუალო - 2.5 გოლზე ნაკლები",
    "BFE>2.5": "📊 Betfair Exchange - 2.5 გოლზე მეტი",
    "BFE<2.5": "📊 Betfair Exchange - 2.5 გოლზე ნაკლები",
    
    # Asian Handicap (ფორა) - შესავლის (68-77)
    "AHh": "🎯 Asian Handicap - ფორის ზომა (მაგ: -1.5)",
    "B365AHH": "💰 Bet365 - ფორა მასპინძელზე",
    "B365AHA": "💰 Bet365 - ფორა სტუმარზე",
    "PAHH": "💰 Pinnacle - ფორა მასპინძელზე",
    "PAHA": "💰 Pinnacle - ფორა სტუმარზე",
    "MaxAHH": "📈 მაქსიმალური - ფორა მასპინძელზე",
    "MaxAHA": "📈 მაქსიმალური - ფორა სტუმარზე",
    "AvgAHH": "📊 საშუალო - ფორა მასპინძელზე",
    "AvgAHA": "📊 საშუალო - ფორა სტუმარზე",
    "BFEAHH": "💰 Betfair Exchange - ფორა მასპინძელზე",
    "BFEAHA": "💰 Betfair Exchange - ფორა სტუმარზე",
    
    # დახურვის კოეფიციენტები (78-109)
    "B365CH": "🔒 Bet365 - დახურვის მასპინძელი",
    "B365CD": "🔒 Bet365 - დახურვის ფრე",
    "B365CA": "🔒 Bet365 - დახურვის სტუმარი",
    "BFDCH": "🔒 Betfred - დახურვის მასპინძელი",
    "BFDCD": "🔒 Betfred - დახურვის ფრე",
    "BFDCA": "🔒 Betfred - დახურვის სტუმარი",
    "BMGMCH": "🔒 BetMGM - დახურვის მასპინძელი",
    "BMGMCD": "🔒 BetMGM - დახურვის ფრე",
    "BMGMCA": "🔒 BetMGM - დახურვის სტუმარი",
    "BVCH": "🔒 Betvictor - დახურვის მასპინძელი",
    "BVCD": "🔒 Betvictor - დახურვის ფრე",
    "BVCA": "🔒 Betvictor - დახურვის სტუმარი",
    "BWCH": "🔒 Betway - დახურვის მასპინძელი",
    "BWCD": "🔒 Betway - დახურვის ფრე",
    "BWCA": "🔒 Betway - დახურვის სტუმარი",
    "CLCH": "🔒 Coral/Ladbrokes - დახურვის მასპინძელი",
    "CLCD": "🔒 Coral/Ladbrokes - დახურვის ფრე",
    "CLCA": "🔒 Coral/Ladbrokes - დახურვის სტუმარი",
    "LBCH": "🔒 Ladbrokes - დახურვის მასპინძელი",
    "LBCD": "🔒 Ladbrokes - დახურვის ფრე",
    "LBCA": "🔒 Ladbrokes - დახურვის სტუმარი",
    "PSCH": "🔒 Pinnacle - დახურვის მასპინძელი",
    "PSCD": "🔒 Pinnacle - დახურვის ფრე",
    "PSCA": "🔒 Pinnacle - დახურვის სტუმარი",
    "MaxCH": "📈 მაქსიმალური დახურვის - მასპინძელი",
    "MaxCD": "📈 მაქსიმალური დახურვის - ფრე",
    "MaxCA": "📈 მაქსიმალური დახურვის - სტუმარი",
    "AvgCH": "📊 საშუალო დახურვის - მასპინძელი",
    "AvgCD": "📊 საშუალო დახურვის - ფრე",
    "AvgCA": "📊 საშუალო დახურვის - სტუმარი",
    "BFECH": "🔒 Betfair Exchange - დახურვის მასპინძელი",
    "BFECD": "🔒 Betfair Exchange - დახურვის ფრე",
    "BFECA": "🔒 Betfair Exchange - დახურვის სტუმარი",
    
    # დახურვის Over/Under (110-119)
    "B365C>2.5": "🔒 Bet365 - დახურვის 2.5 გოლზე მეტი",
    "B365C<2.5": "🔒 Bet365 - დახურვის 2.5 გოლზე ნაკლები",
    "PC>2.5": "🔒 Pinnacle - დახურვის 2.5 გოლზე მეტი",
    "PC<2.5": "🔒 Pinnacle - დახურვის 2.5 გოლზე ნაკლები",
    "MaxC>2.5": "📈 მაქსიმალური დახურვის - 2.5 გოლზე მეტი",
    "MaxC<2.5": "📈 მაქსიმალური დახურვის - 2.5 გოლზე ნაკლები",
    "AvgC>2.5": "📊 საშუალო დახურვის - 2.5 გოლზე მეტი",
    "AvgC<2.5": "📊 საშუალო დახურვის - 2.5 გოლზე ნაკლები",
    "BFEC>2.5": "🔒 Betfair Exchange - დახურვის 2.5 გოლზე მეტი",
    "BFEC<2.5": "🔒 Betfair Exchange - დახურვის 2.5 გოლზე ნაკლები",
    
    # დახურვის Asian Handicap (120-132)
    "AHCh": "🎯 Asian Handicap - დახურვის ფორა",
    "B365CAHH": "🔒 Bet365 - დახურვის ფორა მასპინძელზე",
    "B365CAHA": "🔒 Bet365 - დახურვის ფორა სტუმარზე",
    "PCAHH": "🔒 Pinnacle - დახურვის ფორა მასპინძელზე",
    "PCAHA": "🔒 Pinnacle - დახურვის ფორა სტუმარზე",
    "MaxCAHH": "📈 მაქსიმალური დახურვის - ფორა მასპინძელზე",
    "MaxCAHA": "📈 მაქსიმალური დახურვის - ფორა სტუმარზე",
    "AvgCAHH": "📊 საშუალო დახურვის - ფორა მასპინძელზე",
    "AvgCAHA": "📊 საშუალო დახურვის - ფორა სტუმარზე",
    "BFECAHH": "🔒 Betfair Exchange - დახურვის ფორა მასპინძელზე",
    "BFECAHA": "🔒 Betfair Exchange - დახურვის ფორა სტუმარზე"
}

# ==========================================
# CSV Parser - ყველა სვეტის ამოღება
# ==========================================
def parse_csv_complete(csv_text: str) -> Tuple[List[str], List[Dict]]:
    """ამოიღებს ყველა 132 სვეტს CSV ფაილიდან"""
    try:
        # BOM-ის მოცილება
        if csv_text.startswith('\ufeff'):
            csv_text = csv_text[1:]
        
        lines = csv_text.strip().split('\n')
        
        if len(lines) < 2:
            return [], []
        
        # სათაურების ამოღება
        header_line = lines[0]
        headers = [h.strip() for h in header_line.split(',')]
        
        logger.info(f"📊 ნაპოვნია {len(headers)} სვეტი")
        
        # მონაცემების პარსინგი
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
        
        logger.success(f"✅ წარმატებით დამუშავდა {len(matches)} მატჩი")
        return headers, matches
    
    except Exception as e:
        logger.error(f"❌ CSV პარსინგის შეცდომა: {e}")
        return [], []

# ==========================================
# API Endpoints
# ==========================================
@app.get("/")
async def root():
    return {
        "message": "FootStats API v7.0 - Full 132 Columns",
        "status": "running",
        "matches_loaded": len(matches_storage),
        "columns_count": len(headers_storage)
    }

@app.post("/api/import/csv")
async def import_csv(request: Request):
    """იმპორტავს CSV-ს ყველა 132 სვეტით"""
    global matches_storage, headers_storage
    
    try:
        body = await request.json()
        csv_data = body.get("csv_data", "")
        
        if not csv_data.strip():
            return {"success": False, "error": "CSV ცარიელია"}
        
        headers_storage, matches_storage = parse_csv_complete(csv_data)
        
        if not matches_storage:
            return {"success": False, "error": "მონაცემები ვერ მოიძებნა"}
        
        # სტატისტიკა
        total_matches = len(matches_storage)
        total_goals = sum(
            (m.get("FTHG", 0) or 0) + (m.get("FTAG", 0) or 0) 
            for m in matches_storage
        )
        home_wins = sum(1 for m in matches_storage if m.get("FTR") == "H")
        away_wins = sum(1 for m in matches_storage if m.get("FTR") == "A")
        draws = sum(1 for m in matches_storage if m.get("FTR") == "D")
        
        return {
            "success": True,
            "message": f"წარმატებით იმპორტირდა {total_matches} მატჩი",
            "matches_count": total_matches,
            "columns_count": len(headers_storage),
            "total_goals": total_goals,
            "home_wins": home_wins,
            "away_wins": away_wins,
            "draws": draws,
            "avg_goals": round(total_goals / total_matches, 2) if total_matches > 0 else 0
        }
    except Exception as e:
        logger.error(f"❌ იმპორტის შეცდომა: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/matches/all")
async def get_all_matches():
    """აბრუნებს ყველა მატჩს ყველა 132 სვეტით"""
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
        # ბატჩური ჩაწერა (50 მატჩი)
        batch_size = 50
        total_inserted = 0
        
        for i in range(0, len(matches_storage), batch_size):
            batch = matches_storage[i:i + batch_size]
            supabase.table("premier_league_2025_2026").insert(batch).execute()
            total_inserted += len(batch)
            logger.info(f"📝 ჩაიწერა {total_inserted}/{len(matches_storage)} მატჩი")
        
        return {
            "success": True,
            "message": f"წარმატებით ჩაიწერა {total_inserted} მატჩი Supabase-ში",
            "inserted": total_inserted
        }
    except Exception as e:
        logger.error(f"❌ ბაზაში ჩაწერის შეცდომა: {e}")
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
        <title>FootStats Dashboard v7.0 - ყველა 132 სვეტი</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            @keyframes slideIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
            .log-entry { animation: slideIn 0.3s ease-out; }
            .glass { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); }
            .tab-active { background-color: #10b981; color: white; }
            .tab-inactive { background-color: #374151; color: #9ca3af; }
            
            .table-container {
                overflow-x: auto;
                overflow-y: auto;
                max-height: 600px;
                border: 1px solid #374151;
                border-radius: 0.5rem;
            }
            .data-table {
                border-collapse: collapse;
                font-size: 0.7rem;
                white-space: nowrap;
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
                border-right: 1px solid #1F2937;
                white-space: nowrap;
                cursor: help;
                position: relative;
            }
            .data-table th:hover {
                background-color: #1E293B;
            }
            .data-table th:hover::after {
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
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
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
            
            .column-filter {
                max-height: 400px;
                overflow-y: auto;
            }
            .column-checkbox {
                display: flex;
                align-items: center;
                padding: 0.5rem;
                cursor: pointer;
                border-radius: 0.25rem;
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
                <h1 class="text-4xl font-bold text-white mb-2">⚽ FootStats Dashboard v7.0</h1>
                <p class="text-gray-400">სრული 132 სვეტიანი მონაცემთა ბაზა - Premier League 2025/2026</p>
            </div>

            <!-- სტატისტიკის ბარათები -->
            <div class="grid grid-cols-1 md:grid-cols-6 gap-4 mb-8">
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
                    <p class="text-gray-400 text-sm">საშუალო გოლი</p>
                    <p class="text-3xl font-bold text-purple-400 mt-1" id="stat-avg">0</p>
                </div>
                <div class="glass rounded-xl p-5">
                    <p class="text-gray-400 text-sm">მასპ. მოგება</p>
                    <p class="text-3xl font-bold text-green-400 mt-1" id="stat-home">0</p>
                </div>
                <div class="glass rounded-xl p-5">
                    <p class="text-gray-400 text-sm">მოქმედება</p>
                    <button onclick="saveToDatabase()" class="w-full mt-1 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-semibold">💾 ბაზაში</button>
                </div>
            </div>

            <!-- ტაბები -->
            <div class="flex gap-2 mb-6">
                <button onclick="switchTab('import')" id="tab-import" class="tab-active px-6 py-3 rounded-lg font-semibold">📥 იმპორტი</button>
                <button onclick="switchTab('data')" id="tab-data" class="tab-inactive px-6 py-3 rounded-lg font-semibold">📊 მონაცემები (132 სვეტი)</button>
                <button onclick="switchTab('columns')" id="tab-columns" class="tab-inactive px-6 py-3 rounded-lg font-semibold">🎛️ სვეტების ფილტრი</button>
            </div>

            <!-- იმპორტის სექცია -->
            <div id="section-import" class="glass rounded-xl p-6 mb-8">
                <h2 class="text-2xl font-bold text-white mb-4">📥 CSV იმპორტი (ყველა 132 სვეტი)</h2>
                <p class="text-gray-400 mb-4">ჩასვი football-data.co.uk ფორმატის CSV ფაილი. სისტემა ავტომატურად ამოიღებს ყველა 132 სვეტს.</p>
                <textarea id="csvInput" rows="10" placeholder="ჩასვი CSV ფაილის შიგთავსი აქ..." class="w-full bg-[#0B0F19] border border-gray-700 rounded-lg p-4 text-emerald-400 font-mono text-xs resize-none focus:outline-none focus:border-emerald-500"></textarea>
                <div class="flex gap-3 mt-4">
                    <button onclick="importCSV()" id="importBtn" class="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-3 rounded-lg">🚀 იმპორტი</button>
                    <button onclick="document.getElementById('csvInput').value=''" class="px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg">🗑️</button>
                </div>
            </div>

            <!-- მონაცემების სექცია -->
            <div id="section-data" class="hidden glass rounded-xl p-6 mb-8">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-2xl font-bold text-white">📊 მონაცემთა ცხრილი (<span id="matchCount">0</span> მატჩი × <span id="colCount">0</span> სვეტი)</h2>
                    <div class="flex gap-2">
                        <button onclick="exportJSON()" class="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg text-sm font-semibold">💾 JSON</button>
                        <button onclick="exportCSV()" class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-semibold">📄 CSV</button>
                    </div>
                </div>
                <div class="table-container">
                    <table class="data-table w-full">
                        <thead>
                            <tr id="tableHeader">
                                <th>იტვირთება...</th>
                            </tr>
                        </thead>
                        <tbody id="tableBody">
                            <tr>
                                <td class="px-4 py-8 text-center text-gray-500">ჩასვი CSV და დააჭირე "იმპორტი"-ს</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- სვეტების ფილტრი -->
            <div id="section-columns" class="hidden glass rounded-xl p-6 mb-8">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-2xl font-bold text-white">🎛️ სვეტების ფილტრი (აირჩიე რომელი სვეტები გინდა)</h2>
                    <div class="flex gap-2">
                        <button onclick="selectAllColumns()" class="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-sm">✅ ყველა</button>
                        <button onclick="deselectAllColumns()" class="px-3 py-1 bg-red-600 hover:bg-red-500 text-white rounded text-sm">❌ არცერთი</button>
                        <button onclick="selectMainColumns()" class="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white rounded text-sm">⭐ მთავარი (24)</button>
                    </div>
                </div>
                <div class="column-filter grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2" id="columnFilter">
                    <div class="text-gray-500">ჯერ არ არის მონაცემები</div>
                </div>
            </div>

            <!-- ლოგები -->
            <div class="glass rounded-xl p-6">
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
            let visibleColumns = [];
            let columnDictionary = {};

            function switchTab(tab) {
                ['import', 'data', 'columns'].forEach(t => {
                    document.getElementById('tab-' + t).className = tab === t ? 'tab-active px-6 py-3 rounded-lg font-semibold' : 'tab-inactive px-6 py-3 rounded-lg font-semibold';
                    document.getElementById('section-' + t).classList.toggle('hidden', tab !== t);
                });
            }

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
                        addLog(`📈 საშუალო: ${result.avg_goals} გოლი/მატჩი`, 'info');
                        
                        document.getElementById('stat-matches').textContent = result.matches_count;
                        document.getElementById('stat-columns').textContent = result.columns_count;
                        document.getElementById('stat-goals').textContent = result.total_goals;
                        document.getElementById('stat-avg').textContent = result.avg_goals;
                        document.getElementById('stat-home').textContent = result.home_wins;
                        
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
                addLog('🔄 მონაცემების ჩატვირთვა...', 'info');
                
                try {
                    const response = await fetch('/api/matches/all');
                    const result = await response.json();
                    
                    if (result.success) {
                        allMatchesData = result.data;
                        allHeaders = result.headers;
                        columnDictionary = result.column_dictionary || {};
                        visibleColumns = [...allHeaders];
                        
                        document.getElementById('matchCount').textContent = result.count;
                        document.getElementById('colCount').textContent = allHeaders.length;
                        
                        renderTable();
                        renderColumnFilter();
                        addLog(`✅ ჩაიტვირთა ${result.count} მატჩი, ${allHeaders.length} სვეტი`, 'success');
                    }
                } catch (error) {
                    addLog(`❌ ${error.message}`, 'error');
                }
            }

            function renderTable() {
                const header = document.getElementById('tableHeader');
                const tbody = document.getElementById('tableBody');
                
                if (visibleColumns.length === 0) {
                    header.innerHTML = '<th>აირჩიე სვეტები ფილტრიდან</th>';
                    tbody.innerHTML = '<tr><td class="px-4 py-8 text-center text-gray-500">სვეტები არ არის არჩეული</td></tr>';
                    return;
                }
                
                // სათაური
                header.innerHTML = '<tr>' + visibleColumns.map(col => {
                    const tooltip = columnDictionary[col] || col;
                    return `<th data-tooltip="${tooltip}">${col}</th>`;
                }).join('') + '</tr>';
                
                // სხეული
                tbody.innerHTML = allMatchesData.map(row => {
                    return '<tr>' + visibleColumns.map(col => {
                        let value = row[col];
                        if (value === null || value === undefined || value === '') {
                            value = '-';
                        }
                        let cls = '';
                        if (col === 'FTR') {
                            if (value === 'H') cls = 'text-emerald-400 font-bold';
                            else if (value === 'A') cls = 'text-red-400 font-bold';
                            else if (value === 'D') cls = 'text-yellow-400 font-bold';
                        }
                        return `<td class="${cls}">${value}</td>`;
                    }).join('') + '</tr>';
                }).join('');
            }

            function renderColumnFilter() {
                const filter = document.getElementById('columnFilter');
                
                const categories = {
                    '📋 ძირითადი': ['Div', 'Date', 'Time', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR', 'HTHG', 'HTAG', 'HTR', 'Referee'],
                    '📊 სტატისტიკა': ['HS', 'AS', 'HST', 'AST', 'HF', 'AF', 'HC', 'AC', 'HY', 'AY', 'HR', 'AR'],
                    '💰 კოეფიციენტები (შესავლის)': ['B365H', 'B365D', 'B365A', 'BFDH', 'BFDD', 'BFDA', 'BMGMH', 'BMGMD', 'BMGMA', 'BVH', 'BVD', 'BVA', 'BWH', 'BWD', 'BWA', 'CLH', 'CLD', 'CLA', 'LBH', 'LBD', 'LBA', 'PSH', 'PSD', 'PSA', 'MaxH', 'MaxD', 'MaxA', 'AvgH', 'AvgD', 'AvgA', 'BFEH', 'BFED', 'BFEA'],
                    '📊 Over/Under 2.5': ['B365>2.5', 'B365<2.5', 'P>2.5', 'P<2.5', 'Max>2.5', 'Max<2.5', 'Avg>2.5', 'Avg<2.5', 'BFE>2.5', 'BFE<2.5'],
                    '🎯 Asian Handicap': ['AHh', 'B365AHH', 'B365AHA', 'PAHH', 'PAHA', 'MaxAHH', 'MaxAHA', 'AvgAHH', 'AvgAHA', 'BFEAHH', 'BFEAHA'],
                    '🔒 კოეფიციენტები (დახურვის)': ['B365CH', 'B365CD', 'B365CA', 'BFDCH', 'BFDCD', 'BFDCA', 'BMGMCH', 'BMGMCD', 'BMGMCA', 'BVCH', 'BVCD', 'BVCA', 'BWCH', 'BWCD', 'BWCA', 'CLCH', 'CLCD', 'CLCA', 'LBCH', 'LBCD', 'LBCA', 'PSCH', 'PSCD', 'PSCA', 'MaxCH', 'MaxCD', 'MaxCA', 'AvgCH', 'AvgCD', 'AvgCA', 'BFECH', 'BFECD', 'BFECA'],
                    '🔒 Over/Under (დახურვის)': ['B365C>2.5', 'B365C<2.5', 'PC>2.5', 'PC<2.5', 'MaxC>2.5', 'MaxC<2.5', 'AvgC>2.5', 'AvgC<2.5', 'BFEC>2.5', 'BFEC<2.5'],
                    '🔒 Asian Handicap (დახურვის)': ['AHCh', 'B365CAHH', 'B365CAHA', 'PCAHH', 'PCAHA', 'MaxCAHH', 'MaxCAHA', 'AvgCAHH', 'AvgCAHA', 'BFECAHH', 'BFECAHA']
                };
                
                let html = '';
                
                for (const [category, cols] of Object.entries(categories)) {
                    html += `<div class="col-span-full mt-4 mb-2">
                        <h3 class="text-sm font-bold text-emerald-400 border-b border-gray-700 pb-1">${category}</h3>
                    </div>`;
                    
                    for (const col of cols) {
                        if (allHeaders.includes(col)) {
                            const desc = columnDictionary[col] || col;
                            const isChecked = visibleColumns.includes(col) ? 'checked' : '';
                            html += `
                                <label class="column-checkbox bg-[#0B0F19] border border-gray-700 rounded p-2 cursor-pointer hover:border-emerald-500 transition">
                                    <input type="checkbox" ${isChecked} onchange="toggleColumn('${col}')" class="mr-2 accent-emerald-500">
                                    <div class="flex-1">
                                        <div class="text-xs font-mono text-emerald-400">${col}</div>
                                        <div class="text-[10px] text-gray-400">${desc}</div>
                                    </div>
                                </label>
                            `;
                        }
                    }
                }
                
                filter.innerHTML = html;
            }

            function toggleColumn(col) {
                if (visibleColumns.includes(col)) {
                    visibleColumns = visibleColumns.filter(c => c !== col);
                } else {
                    visibleColumns.push(col);
                }
                document.getElementById('colCount').textContent = visibleColumns.length;
                renderTable();
            }

            function selectAllColumns() {
                visibleColumns = [...allHeaders];
                document.getElementById('colCount').textContent = visibleColumns.length;
                renderColumnFilter();
                renderTable();
            }

            function deselectAllColumns() {
                visibleColumns = [];
                document.getElementById('colCount').textContent = 0;
                renderColumnFilter();
                renderTable();
            }

            function selectMainColumns() {
                const mainCols = ['Div', 'Date', 'Time', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR', 'HTHG', 'HTAG', 'HTR', 'Referee', 'HS', 'AS', 'HST', 'AST', 'HF', 'AF', 'HC', 'AC', 'HY', 'AY', 'HR', 'AR'];
                visibleColumns = allHeaders.filter(h => mainCols.includes(h));
                document.getElementById('colCount').textContent = visibleColumns.length;
                renderColumnFilter();
                renderTable();
            }

            async function saveToDatabase() {
                if (allMatchesData.length === 0) {
                    alert('ჯერ იმპორტირე მონაცემები');
                    return;
                }
                
                addLog('💾 ბაზაში ჩაწერა იწყება...', 'info');
                
                try {
                    const response = await fetch('/api/save/to-database', {
                        method: 'POST'
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
                }
            }

            function exportJSON() {
                if (allMatchesData.length === 0) {
                    alert('ჯერ იმპორტირე მონაცემები');
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
                a.download = `footstats_all_${new Date().toISOString().split('T')[0]}.json`;
                a.click();
                URL.revokeObjectURL(url);
                
                addLog('💾 JSON ექსპორტი წარმატებულია', 'success');
            }

            function exportCSV() {
                if (allMatchesData.length === 0 || visibleColumns.length === 0) {
                    alert('ჯერ იმპორტირე მონაცემები');
                    return;
                }
                
                let csvContent = visibleColumns.join(',') + '\\n';
                
                allMatchesData.forEach(row => {
                    const line = visibleColumns.map(col => {
                        const value = row[col] !== null && row[col] !== undefined ? row[col] : '';
                        return String(value).includes(',') ? `"${value}"` : value;
                    }).join(',');
                    csvContent += line + '\\n';
                });
                
                const blob = new Blob([csvContent], { type: 'text/csv' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `footstats_all_${new Date().toISOString().split('T')[0]}.csv`;
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