import csv
import os
from datetime import datetime
from supabase import create_client, Client

# Supabase-ის ინიციალიზაცია
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# CSV ფაილის წაკითხვა
csv_file = "data/premier_league_2025_2026.csv"

# სვეტების მაპინგი CSV სათაურიდან DB სვეტებზე
COLUMN_MAPPING = {
    "Div": "division",
    "Date": "match_date",
    "Time": "match_time",
    "HomeTeam": "home_team",
    "AwayTeam": "away_team",
    "FTHG": "full_time_home_goals",
    "FTAG": "full_time_away_goals",
    "FTR": "full_time_result",
    "HTHG": "half_time_home_goals",
    "HTAG": "half_time_away_goals",
    "HTR": "half_time_result",
    "Referee": "referee",
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
    "AR": "away_red_cards",
    "B365H": "bet365_home",
    "B365D": "bet365_draw",
    "B365A": "bet365_away",
    "BFDH": "betfred_home",
    "BFDD": "betfred_draw",
    "BFDA": "betfred_away",
    "BMGMH": "betmgm_home",
    "BMGMD": "betmgm_draw",
    "BMGMA": "betmgm_away",
    "BVH": "betvictor_home",
    "BVD": "betvictor_draw",
    "BVA": "betvictor_away",
    "BWH": "betway_home",
    "BWD": "betway_draw",
    "BWA": "betway_away",
    "CLH": "coral_home",
    "CLD": "coral_draw",
    "CLA": "coral_away",
    "LBH": "ladbrokes_home",
    "LBD": "ladbrokes_draw",
    "LBA": "ladbrokes_away",
    "PSH": "pinnacle_home",
    "PSD": "pinnacle_draw",
    "PSA": "pinnacle_away",
    "MaxH": "max_home",
    "MaxD": "max_draw",
    "MaxA": "max_away",
    "AvgH": "avg_home",
    "AvgD": "avg_draw",
    "AvgA": "avg_away",
    "BFEH": "betfair_home",
    "BFED": "betfair_draw",
    "BFEA": "betfair_away",
    "B365>2.5": "bet365_over_2_5",
    "B365<2.5": "bet365_under_2_5",
    "P>2.5": "pinnacle_over_2_5",
    "P<2.5": "pinnacle_under_2_5",
    "Max>2.5": "max_over_2_5",
    "Max<2.5": "max_under_2_5",
    "Avg>2.5": "avg_over_2_5",
    "Avg<2.5": "avg_under_2_5",
    "BFE>2.5": "betfair_over_2_5",
    "BFE<2.5": "betfair_under_2_5",
    "AHh": "asian_handicap_home",
    "B365AHH": "bet365_ah_home",
    "B365AHA": "bet365_ah_away",
    "PAHH": "pinnacle_ah_home",
    "PAHA": "pinnacle_ah_away",
    "MaxAHH": "max_ah_home",
    "MaxAHA": "max_ah_away",
    "AvgAHH": "avg_ah_home",
    "AvgAHA": "avg_ah_away",
    "BFEAHH": "betfair_ah_home",
    "BFEAHA": "betfair_ah_away",
    "B365CH": "bet365_closing_home",
    "B365CD": "bet365_closing_draw",
    "B365CA": "bet365_closing_away",
    "BFDCH": "betfred_closing_home",
    "BFDCD": "betfred_closing_draw",
    "BFDCA": "betfred_closing_away",
    "BMGMCH": "betmgm_closing_home",
    "BMGMCD": "betmgm_closing_draw",
    "BMGMCA": "betmgm_closing_away",
    "BVCH": "betvictor_closing_home",
    "BVCD": "betvictor_closing_draw",
    "BVCA": "betvictor_closing_away",
    "BWCH": "betway_closing_home",
    "BWCD": "betway_closing_draw",
    "BWCA": "betway_closing_away",
    "CLCH": "coral_closing_home",
    "CLCD": "coral_closing_draw",
    "CLCA": "coral_closing_away",
    "LBCH": "ladbrokes_closing_home",
    "LBCD": "ladbrokes_closing_draw",
    "LBCA": "ladbrokes_closing_away",
    "PSCH": "pinnacle_closing_home",
    "PSCD": "pinnacle_closing_draw",
    "PSCA": "pinnacle_closing_away",
    "MaxCH": "max_closing_home",
    "MaxCD": "max_closing_draw",
    "MaxCA": "max_closing_away",
    "AvgCH": "avg_closing_home",
    "AvgCD": "avg_closing_draw",
    "AvgCA": "avg_closing_away",
    "BFECH": "betfair_closing_home",
    "BFECD": "betfair_closing_draw",
    "BFECA": "betfair_closing_away",
    "B365C>2.5": "bet365_closing_over_2_5",
    "B365C<2.5": "bet365_closing_under_2_5",
    "PC>2.5": "pinnacle_closing_over_2_5",
    "PC<2.5": "pinnacle_closing_under_2_5",
    "MaxC>2.5": "max_closing_over_2_5",
    "MaxC<2.5": "max_closing_under_2_5",
    "AvgC>2.5": "avg_closing_over_2_5",
    "AvgC<2.5": "avg_closing_under_2_5",
    "BFEC>2.5": "betfair_closing_over_2_5",
    "BFEC<2.5": "betfair_closing_under_2_5",
    "AHCh": "asian_handicap_closing_home",
    "B365CAHH": "bet365_closing_ah_home",
    "B365CAHA": "bet365_closing_ah_away",
    "PCAHH": "pinnacle_closing_ah_home",
    "PCAHA": "pinnacle_closing_ah_away",
    "MaxCAHH": "max_closing_ah_home",
    "MaxCAHA": "max_closing_ah_away",
    "AvgCAHH": "avg_closing_ah_home",
    "AvgCAHA": "avg_closing_ah_away",
    "BFECAHH": "betfair_closing_ah_home",
    "BFECAHA": "betfair_closing_ah_away"
}

def parse_date(date_str):
    """თარიღის პარსინგი DD/MM/YYYY ფორმატიდან"""
    try:
        return datetime.strptime(date_str, "%d/%m/%Y").date()
    except:
        return None

def parse_time(time_str):
    """დროის პარსინგი HH:MM ფორმატიდან"""
    try:
        return datetime.strptime(time_str, "%H:%M").time()
    except:
        return None

def parse_int(value):
    """მთელი რიცხვის პარსინგი"""
    try:
        return int(value) if value else None
    except:
        return None

def parse_float(value):
    """ათწილადის პარსინგი"""
    try:
        return float(value) if value else None
    except:
        return None

def import_csv():
    """CSV ფაილის იმპორტი Supabase-ში"""
    print("🚀 ვიწყებ CSV იმპორტს...")
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        matches = []
        for row_num, row in enumerate(reader, start=1):
            match_data = {}
            
            for csv_col, db_col in COLUMN_MAPPING.items():
                value = row.get(csv_col, "")
                
                # ტიპის მიხედვით კონვერტაცია
                if db_col == "match_date":
                    match_data[db_col] = parse_date(value)
                elif db_col == "match_time":
                    match_data[db_col] = parse_time(value)
                elif "goals" in db_col or "shots" in db_col or "fouls" in db_col or "corners" in db_col or "cards" in db_col:
                    match_data[db_col] = parse_int(value)
                elif "home" in db_col or "draw" in db_col or "away" in db_col or "over" in db_col or "under" in db_col or "handicap" in db_col:
                    match_data[db_col] = parse_float(value)
                else:
                    match_data[db_col] = value if value else None
            
            matches.append(match_data)
            
            # ყოველი 50 მატჩის შემდეგ ჩაწერა
            if len(matches) >= 50:
                print(f"📝 ვწერ {len(matches)} მატჩს...")
                supabase.table("premier_league_2025_2026").insert(matches).execute()
                matches = []
        
        # დარჩენილი მატჩების ჩაწერა
        if matches:
            print(f"📝 ვწერ ბოლო {len(matches)} მატჩს...")
            supabase.table("premier_league_2025_2026").insert(matches).execute()
    
    print(f"✅ იმპორტი დასრულდა! სულ {row_num} მატჩი ჩაიწერა.")

if __name__ == "__main__":
    import_csv()