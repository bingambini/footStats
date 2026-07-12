import asyncio
import json
import os
import re
from typing import Dict, List, Tuple, Optional
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup
from supabase import create_client, Client

# ============================================
# FastAPI App
# ============================================
app = FastAPI()

# ============================================
# TeamScout Bot - გაუმჯობესებული ვერსია DEBUG-ით
# ============================================
class TeamScout:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "DNT": "1",
            "Pragma": "no-cache",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"'
        }
        self.cookies = {
            "_ga": "GA1.2.1234567890.1234567890",
            "_gid": "GA1.2.0987654321.0987654321"
        }
    
    def normalize_url(self, url: str) -> str:
        """ნორმალიზაცია URL-ს - მოაშორებს /players/ თუ არის"""
        print(f"[DEBUG] normalize_url - ორიგინალი: {url}")
        
        if url.endswith('/players/'):
            url = url[:-len('/players/')]
        elif url.endswith('/players'):
            url = url[:-len('/players')]
        
        if not url.endswith('/'):
            url += '/'
        
        print(f"[DEBUG] normalize_url - ნორმალიზებული: {url}")
        return url
    
    async def fetch_page(self, url: str) -> Optional[str]:
        """გადმოწერს HTML გვერდს გაუმჯობესებული headers-ით"""
        try:
            print(f"[DEBUG] ვცდილობ გადმოწერას: {url}")
            
            for attempt in range(3):
                print(f"[DEBUG] მცდელობა {attempt + 1}/3")
                
                async with httpx.AsyncClient(
                    follow_redirects=True,
                    timeout=30.0,
                    verify=False
                ) as client:
                    response = await client.get(
                        url, 
                        headers=self.headers,
                        cookies=self.cookies
                    )
                    print(f"[DEBUG] Response status: {response.status_code}")
                    
                    if response.status_code == 200:
                        print(f"[DEBUG] HTML სიგრძე: {len(response.text)} bytes")
                        return response.text
                    elif response.status_code == 403:
                        print(f"[ERROR] 403 Forbidden - საიტი ბლოკავს requests-ს")
                        if attempt < 2:
                            print(f"[DEBUG] ვცდილობ თავიდან...")
                            await asyncio.sleep(2)
                            continue
                    else:
                        print(f"[ERROR] HTTP შეცდომა: {response.status_code}")
                        response.raise_for_status()
            
            return None
            
        except httpx.HTTPStatusError as e:
            print(f"[ERROR] HTTP შეცდომა: {e.response.status_code}")
            return None
        except httpx.RequestError as e:
            print(f"[ERROR] Request შეცდომა: {type(e).__name__} - {str(e)}")
            return None
        except Exception as e:
            print(f"[ERROR] უცნობი შეცდომა: {type(e).__name__} - {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def parse_team_info(self, html: str, url: str) -> Dict:
        """პარსავს გუნდის ინფორმაციას championat.com-დან"""
        print(f"[DEBUG] ვიწყებ parsing-ს...")
        soup = BeautifulSoup(html, 'lxml')
        
        team_data = {
            "name": "",
            "short_code": "",
            "city": "",
            "country": "",
            "stadium": "",
            "coach": "",
            "logo_url": ""
        }
        
        h1_tags = soup.find_all('h1')
        print(f"[DEBUG] ვიპოვე {len(h1_tags)} h1 tag")
        
        for h1 in h1_tags:
            text = h1.get_text(strip=True)
            print(f"[DEBUG] h1 ტექსტი: {text}")
            
            if 'состав' not in text.lower() and 'состав команды' not in text.lower():
                if '(' in text and ')' in text:
                    match = re.match(r'^([^(]+)\s*\(([^)]+)\)', text)
                    if match:
                        team_data["name"] = match.group(1).strip()
                        location = match.group(2).strip()
                        if ',' in location:
                            parts = location.split(',')
                            team_data["city"] = parts[0].strip()
                            team_data["country"] = parts[1].strip()
                        else:
                            team_data["city"] = location
                        print(f"[DEBUG] გუნდის სახელი (h1): {team_data['name']}")
                        break
                else:
                    team_data["name"] = text
                    print(f"[DEBUG] გუნდის სახელი (h1): {team_data['name']}")
                    break
        
        if not team_data["name"]:
            meta_title = soup.find('meta', property='og:title')
            if meta_title:
                title = meta_title.get('content', '')
                print(f"[DEBUG] og:title: {title}")
                if '(' in title and ')' in title:
                    match = re.match(r'^([^(]+)\s*\(([^)]+)\)', title)
                    if match:
                        team_data["name"] = match.group(1).strip()
                        location = match.group(2).strip()
                        if ',' in location:
                            parts = location.split(',')
                            team_data["city"] = parts[0].strip()
                            team_data["country"] = parts[1].strip()
                        print(f"[DEBUG] გუნდის სახელი (og:title): {team_data['name']}")
        
        og_image = soup.find('meta', property='og:image')
        if og_image:
            team_data["logo_url"] = og_image.get('content', '')
            print(f"[DEBUG] ლოგო (og:image): {team_data['logo_url']}")
        else:
            logo_candidates = soup.find_all('img')
            print(f"[DEBUG] ვიპოვე {len(logo_candidates)} img tag")
            for img in logo_candidates:
                src = img.get('src', '')
                alt = img.get('alt', '').lower()
                
                if any(keyword in alt for keyword in ['лого', 'logo', 'эмблема']):
                    if src.startswith('http'):
                        team_data["logo_url"] = src
                        print(f"[DEBUG] ლოგო (img): {team_data['logo_url']}")
                        break
                elif any(keyword in src.lower() for keyword in ['logo', 'crest', 'badge', 'emblem']):
                    if src.startswith('http'):
                        team_data["logo_url"] = src
                        print(f"[DEBUG] ლოგო (img): {team_data['logo_url']}")
                        break
        
        info_elements = soup.find_all(['dl', 'table', 'div'], class_=re.compile(r'team-info|info|details', re.I))
        print(f"[DEBUG] ვიპოვე {len(info_elements)} info element")
        
        for element in info_elements:
            text = element.get_text()
            
            stadium_match = re.search(r'(?:стадион|stadium)[:\s]+([^\n\r]+)', text, re.I)
            if stadium_match:
                team_data["stadium"] = stadium_match.group(1).strip()
                print(f"[DEBUG] სტადიონი: {team_data['stadium']}")
            
            city_match = re.search(r'(?:город|city)[:\s]+([^\n\r]+)', text, re.I)
            if city_match:
                team_data["city"] = city_match.group(1).strip()
                print(f"[DEBUG] ქალაქი: {team_data['city']}")
            
            country_match = re.search(r'(?:страна|country)[:\s]+([^\n\r]+)', text, re.I)
            if country_match:
                team_data["country"] = country_match.group(1).strip()
                print(f"[DEBUG] ქვეყანა: {team_data['country']}")
            
            coach_match = re.search(r'(?:тренер|coach|главный тренер)[:\s]+([^\n\r]+)', text, re.I)
            if coach_match:
                team_data["coach"] = coach_match.group(1).strip()
                print(f"[DEBUG] მწვრთნელი: {team_data['coach']}")
        
        if team_data["name"]:
            english_name = re.sub(r'[^a-zA-Z\s]', '', team_data["name"])
            if english_name:
                words = english_name.split()
                if words:
                    team_data["short_code"] = words[0][:3].upper()
            else:
                team_data["short_code"] = team_data["name"][:3].upper()
            print(f"[DEBUG] Short code: {team_data['short_code']}")
        
        print(f"[DEBUG] Parsing დასრულდა. მონაცემები: {team_data}")
        return team_data
    
    async def scout_team(self, url: str) -> Dict:
        """მთავარი ფუნქცია - აგროვებს გუნდის ინფორმაციას"""
        print(f"[DEBUG] scout_team - ორიგინალი URL: {url}")
        
        normalized_url = self.normalize_url(url)
        
        html = await self.fetch_page(normalized_url)
        
        if not html:
            print(f"[ERROR] HTML ცარიელია")
            return {
                "success": False,
                "error": f"ვერ მოხერხდა გვერდის გადმოწერა. URL: {normalized_url}",
                "data": None
            }
        
        print(f"[DEBUG] წარმატებით ჩაიტვირთა HTML")
        team_info = self.parse_team_info(html, normalized_url)
        
        return {
            "success": True,
            "data": team_info,
            "raw_html_length": len(html),
            "normalized_url": normalized_url
        }

# ============================================
# TextParser Bot - ახალი აგენტი copy-paste ტექსტისთვის
# ============================================
class TextParser:
    """აგენტი რომელიც ამუშავებს მომხმარებლის მიერ ჩაფეისთებულ ტექსტს"""
    
    def parse_team_from_text(self, text: str) -> Dict:
        """პარსავს გუნდის ინფორმაციას ჩაფეისთებული ტექსტიდან"""
        print(f"[DEBUG] TextParser - ვიწყებ ტექსტის parsing-ს...")
        
        team_data = {
            "name": "",
            "short_code": "",
            "city": "",
            "country": "",
            "stadium": "",
            "coach": "",
            "logo_url": "",
            "players": []
        }
        
        lines = text.strip().split('\n')
        
        # პირველი ხაზი - გუნდის სახელი
        if lines:
            team_data["name"] = lines[0].strip()
            print(f"[DEBUG] გუნდის სახელი: {team_data['name']}")
        
        # ვეძებთ "Город, страна" pattern-ს
        for i, line in enumerate(lines):
            if 'Город, страна' in line or 'город' in line.lower():
                # შემდეგი ხაზი არის ქალაქი, ქვეყანა
                if i + 1 < len(lines):
                    location_line = lines[i + 1].strip()
                    if ',' in location_line:
                        parts = location_line.split(',')
                        team_data["city"] = parts[0].strip()
                        team_data["country"] = parts[1].strip()
                    else:
                        team_data["city"] = location_line
                    print(f"[DEBUG] ქალაქი: {team_data['city']}, ქვეყანა: {team_data['country']}")
                break
        
        # ვეძებთ "Стадион" pattern-ს
        for i, line in enumerate(lines):
            if 'Стадион' in line:
                if i + 1 < len(lines):
                    team_data["stadium"] = lines[i + 1].strip()
                    print(f"[DEBUG] სტადიონი: {team_data['stadium']}")
                break
        
        # ვეძებთ "Тренер" pattern-ს
        for i, line in enumerate(lines):
            if 'Тренер' in line:
                if i + 1 < len(lines):
                    team_data["coach"] = lines[i + 1].strip()
                    print(f"[DEBUG] მწვრთნელი: {team_data['coach']}")
                break
        
        # Short code
        if team_data["name"]:
            team_data["short_code"] = team_data["name"][:3].upper()
            print(f"[DEBUG] Short code: {team_data['short_code']}")
        
        # ვეძებთ მოთამაშეებს - ცხრილის ფორმატი
        # Pattern: ნომერი, სახელი, ამპლუა, დაბადების თარიღი, სიმაღლე, წონა
        in_players_section = False
        current_player = {}
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # ვეძებთ "Состав" ან "Заявлены" სექციას
            if 'Состав' in line or 'Заявлены' in line or 'Игрок' in line:
                in_players_section = True
                continue
            
            # თუ მოთამაშეების სექციაში ვართ
            if in_players_section and line:
                # ვცადოთ ამოვიღოთ ნომერი
                number_match = re.match(r'^(\d+)\s*$', line)
                if number_match:
                    # წინა მოთამაშე თუ არის, შევინახოთ
                    if current_player and 'name' in current_player:
                        team_data["players"].append(current_player)
                    
                    current_player = {
                        "shirt_number": int(number_match.group(1)),
                        "name": "",
                        "position": "",
                        "birth_date": "",
                        "height_cm": None,
                        "weight_kg": None,
                        "nationality": ""
                    }
                    continue
                
                # ვეძებთ მოთამაშის სახელს
                if current_player and not current_player["name"]:
                    # სახელი ჩვეულებრივ არის ხანგრძლივი ტექსტი
                    if len(line) > 5 and not re.match(r'^\d+$', line):
                        # ვამოწმებთ რომ ეს არის სახელი და არა სხვა ინფორმაცია
                        if any(keyword in line.lower() for keyword in ['вратарь', 'защитник', 'полузащитник', 'нападающий']):
                            # ეს არის ამპლუა
                            current_player["position"] = line
                        elif re.match(r'\d{2}\.\d{2}\.\d{4}', line):
                            # ეს არის დაბადების თარიღი
                            current_player["birth_date"] = line
                        elif re.match(r'^\d{3}$', line):
                            # ეს არის სიმაღლე
                            current_player["height_cm"] = int(line)
                        elif re.match(r'^\d{2,3}$', line):
                            # ეს არის წონა
                            current_player["weight_kg"] = int(line)
                        else:
                            # ეს არის სახელი
                            current_player["name"] = line
                            print(f"[DEBUG] მოთამაშე: {current_player['name']}")
        
        # ბოლო მოთამაშე
        if current_player and 'name' in current_player:
            team_data["players"].append(current_player)
        
        print(f"[DEBUG] ვიპოვე {len(team_data['players'])} მოთამაშე")
        
        return {
            "success": True,
            "data": team_data,
            "players_count": len(team_data["players"])
        }

# ============================================
# Controller Bot - ვალიდაცია მხოლოდ, ჩაწერა არა
# ============================================
class ControllerBot:
    def __init__(self):
        self.supabase_url = os.environ.get("SUPABASE_URL")
        self.supabase_key = os.environ.get("SUPABASE_KEY")
        
        if self.supabase_url and self.supabase_key:
            self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        else:
            self.supabase = None
        
        self.VALIDATION_RULES = {
            "name": {
                "required": True,
                "min_length": 2,
                "max_length": 100
            },
            "short_code": {
                "required": True,
                "pattern": r"^[A-ZА-Я]{3,5}$",
                "error_message": "short_code უნდა იყოს 3-5 დიდი ასო"
            }
        }
    
    def validate_field(self, field: str, value: any) -> Tuple[bool, str]:
        rules = self.VALIDATION_RULES.get(field, {})
        
        if rules.get("required") and (value is None or value == ""):
            return False, f"{field} აუცილებელია"
        
        if not value:
            return True, ""
        
        if "min_length" in rules:
            if len(str(value)) < rules["min_length"]:
                return False, f"{field} ძალიან მოკლეა (მინიმუმ {rules['min_length']} სიმბოლო)"
        
        if "max_length" in rules:
            if len(str(value)) > rules["max_length"]:
                return False, f"{field} ძალიან გრძელია (მაქსიმუმ {rules['max_length']} სიმბოლო)"
        
        if "pattern" in rules:
            if not re.match(rules["pattern"], str(value)):
                return False, rules.get("error_message", f"{field} არასწორი ფორმატია")
        
        return True, ""
    
    def validate_team(self, team_data: Dict) -> Tuple[bool, List[str]]:
        errors = []
        
        for field, value in team_data.items():
            if field == "players":
                continue
            is_valid, error_msg = self.validate_field(field, value)
            if not is_valid:
                errors.append(error_msg)
        
        return len(errors) == 0, errors
    
    async def check_duplicate(self, team_data: Dict) -> Tuple[bool, str]:
        if not self.supabase:
            return False, "Supabase არ არის დაკონფიგურირებული"
        
        try:
            response = self.supabase.table("teams").select("id").eq("name", team_data["name"]).execute()
            
            if response.data and len(response.data) > 0:
                return True, f"გუნდი '{team_data['name']}' უკვე არსებობს ბაზაში"
            
            return False, ""
        except Exception as e:
            return False, f"შეცდომა duplicate check-ისას: {str(e)}"

# ============================================
# API Endpoints
# ============================================
class TeamSchema(BaseModel):
    name: str
    short_code: str
    city: str
    country: str
    stadium: str
    coach: str
    logo_url: str

@app.get("/")
async def root():
    return {"message": "FootStats API is running!"}

@app.get("/admin/scout", response_class=HTMLResponse)
async def get_dashboard():
    html_content = """
    <!DOCTYPE html>
    <html lang="ka">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🤖 FootStats Agent Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            @keyframes pulse-glow {
                0%, 100% { box-shadow: 0 0 5px rgba(16, 185, 129, 0.5); }
                50% { box-shadow: 0 0 20px rgba(16, 185, 129, 0.8); }
            }
            .agent-active {
                animation: pulse-glow 2s infinite;
            }
            .log-entry {
                animation: slideIn 0.3s ease-out;
            }
            @keyframes slideIn {
                from { opacity: 0; transform: translateX(-10px); }
                to { opacity: 1; transform: translateX(0); }
            }
            .step-completed {
                border-left: 4px solid #10b981;
            }
            .step-active {
                border-left: 4px solid #f59e0b;
            }
            .step-pending {
                border-left: 4px solid #6b7280;
            }
            .data-card {
                animation: fadeIn 0.5s ease-out;
            }
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }
            .tab-active {
                background-color: #10b981;
                color: white;
            }
            .tab-inactive {
                background-color: #374151;
                color: #9ca3af;
            }
        </style>
    </head>
    <body class="bg-gradient-to-br from-[#0B0F19] to-[#1a1f2e] text-[#E2E8F0] font-sans min-h-screen p-6">
        <div class="max-w-6xl mx-auto">
            <div class="text-center mb-8">
                <h1 class="text-4xl font-bold text-white mb-2">🤖 FootStats Agent Dashboard</h1>
                <p class="text-gray-400">ავტომატიზებული საფეხბურთო სტატისტიკის სისტემა</p>
            </div>

            <!-- Agent Cards -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <div id="scout-card" class="bg-[#0E1424] border-2 border-gray-800 rounded-xl p-6 transition-all">
                    <div class="flex items-center justify-between mb-4">
                        <div class="flex items-center gap-3">
                            <div class="w-12 h-12 bg-emerald-600 rounded-full flex items-center justify-center text-2xl">🕵️</div>
                            <div>
                                <h2 class="text-xl font-bold text-white">TeamScout</h2>
                                <p class="text-sm text-gray-400">მზვერავი აგენტი</p>
                            </div>
                        </div>
                        <div id="scout-status" class="px-3 py-1 bg-gray-700 rounded-full text-xs font-semibold">
                            ⏸️ მზად
                        </div>
                    </div>
                    <p class="text-sm text-gray-400 mb-3">აგროვებს გუნდის ინფორმაციას სპორტული საიტებიდან</p>
                    <div class="space-y-2 text-xs">
                        <div class="flex justify-between">
                            <span class="text-gray-500">სტატუსი:</span>
                            <span id="scout-task" class="text-emerald-400">მოლოდინში</span>
                        </div>
                    </div>
                </div>

                <div id="parser-card" class="bg-[#0E1424] border-2 border-gray-800 rounded-xl p-6 transition-all">
                    <div class="flex items-center justify-between mb-4">
                        <div class="flex items-center gap-3">
                            <div class="w-12 h-12 bg-purple-600 rounded-full flex items-center justify-center text-2xl">📝</div>
                            <div>
                                <h2 class="text-xl font-bold text-white">TextParser</h2>
                                <p class="text-sm text-gray-400">ტექსტის ანალიზატორი</p>
                            </div>
                        </div>
                        <div id="parser-status" class="px-3 py-1 bg-gray-700 rounded-full text-xs font-semibold">
                            ⏸️ მზად
                        </div>
                    </div>
                    <p class="text-sm text-gray-400 mb-3">ამუშავებს ჩაფეისთებულ ტექსტს</p>
                    <div class="space-y-2 text-xs">
                        <div class="flex justify-between">
                            <span class="text-gray-500">სტატუსი:</span>
                            <span id="parser-task" class="text-purple-400">მოლოდინში</span>
                        </div>
                    </div>
                </div>

                <div id="controller-card" class="bg-[#0E1424] border-2 border-gray-800 rounded-xl p-6 transition-all">
                    <div class="flex items-center justify-between mb-4">
                        <div class="flex items-center gap-3">
                            <div class="w-12 h-12 bg-blue-600 rounded-full flex items-center justify-center text-2xl">🛡️</div>
                            <div>
                                <h2 class="text-xl font-bold text-white">Controller</h2>
                                <p class="text-sm text-gray-400">მაკონტროლებელი აგენტი</p>
                            </div>
                        </div>
                        <div id="controller-status" class="px-3 py-1 bg-gray-700 rounded-full text-xs font-semibold">
                            ⏸️ მზად
                        </div>
                    </div>
                    <p class="text-sm text-gray-400 mb-3">ამოწმებს მონაცემების სისწორეს</p>
                    <div class="space-y-2 text-xs">
                        <div class="flex justify-between">
                            <span class="text-gray-500">შემოწმებული:</span>
                            <span id="controller-checked" class="text-gray-400">0 გუნდი</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Tabs -->
            <div class="flex gap-2 mb-4">
                <button onclick="switchTab('url')" id="tab-url" class="tab-active px-6 py-3 rounded-lg font-semibold transition-all">
                    🔗 URL-დან მოპოვება
                </button>
                <button onclick="switchTab('paste')" id="tab-paste" class="tab-inactive px-6 py-3 rounded-lg font-semibold transition-all">
                    📋 ტექსტის ჩასმა
                </button>
            </div>

            <!-- URL Input Section -->
            <div id="section-url" class="bg-[#0E1424] border border-gray-800 rounded-xl p-6 mb-8">
                <h3 class="text-lg font-bold text-white mb-4">🎯 გუნდის URL</h3>
                <div class="flex gap-3">
                    <input 
                        id="targetUrl" 
                        type="text" 
                        value="https://www.championat.com/football/_england/tournament/6592/teams/268572/"
                        placeholder="ჩაწერე გუნდის URL championat.com-დან" 
                        class="flex-1 bg-[#070A13] border border-gray-700 rounded-lg p-3 text-emerald-400 font-mono text-sm focus:outline-none focus:border-emerald-500"
                    >
                    <button 
                        onclick="startScouting()" 
                        id="startBtn"
                        class="bg-emerald-600 hover:bg-emerald-500 text-white px-6 py-3 rounded-lg font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        🚀 გააქტიურე
                    </button>
                </div>
            </div>

            <!-- Paste Text Section -->
            <div id="section-paste" class="hidden bg-[#0E1424] border border-gray-800 rounded-xl p-6 mb-8">
                <h3 class="text-lg font-bold text-white mb-4">📋 ჩაფეისთე გვერდის ტექსტი</h3>
                <textarea 
                    id="pasteText" 
                    rows="10"
                    placeholder="დააკოპირე გვერდის ტექსტი და ჩასვი აქ..."
                    class="w-full bg-[#070A13] border border-gray-700 rounded-lg p-3 text-purple-400 font-mono text-sm focus:outline-none focus:border-purple-500 resize-none"
                ></textarea>
                <button 
                    onclick="startParsing()" 
                    id="parseBtn"
                    class="mt-4 bg-purple-600 hover:bg-purple-500 text-white px-6 py-3 rounded-lg font-semibold transition-all w-full"
                >
                    📝 დაამუშავე ტექსტი
                </button>
            </div>

            <!-- Process Steps -->
            <div class="bg-[#0E1424] border border-gray-800 rounded-xl p-6 mb-8">
                <h3 class="text-lg font-bold text-white mb-4">📋 პროცესის ნაბიჯები</h3>
                <div class="space-y-3">
                    <div id="step-1" class="step-pending bg-[#070A13] rounded-lg p-4 transition-all">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 bg-gray-700 rounded-full flex items-center justify-center text-sm font-bold">1</div>
                            <div class="flex-1">
                                <div class="font-semibold text-white">მონაცემების მოპოვება</div>
                                <div class="text-xs text-gray-400">აგენტი აგროვებს ინფორმაციას</div>
                            </div>
                            <div id="step-1-status" class="text-gray-500">⏸️</div>
                        </div>
                    </div>
                    <div id="step-2" class="step-pending bg-[#070A13] rounded-lg p-4 transition-all">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 bg-gray-700 rounded-full flex items-center justify-center text-sm font-bold">2</div>
                            <div class="flex-1">
                                <div class="font-semibold text-white">ვალიდაცია</div>
                                <div class="text-xs text-gray-400">Controller ამოწმებს მონაცემების სისწორეს</div>
                            </div>
                            <div id="step-2-status" class="text-gray-500">⏸️</div>
                        </div>
                    </div>
                    <div id="step-3" class="step-pending bg-[#070A13] rounded-lg p-4 transition-all">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 bg-gray-700 rounded-full flex items-center justify-center text-sm font-bold">3</div>
                            <div class="flex-1">
                                <div class="font-semibold text-white">მონაცემების ვიზუალიზაცია</div>
                                <div class="text-xs text-gray-400">მონაცემები გამოჩნდება შესამოწმებლად</div>
                            </div>
                            <div id="step-3-status" class="text-gray-500">⏸️</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Data Display -->
            <div id="data-display" class="hidden bg-[#0E1424] border border-gray-800 rounded-xl p-6 mb-8">
                <h3 class="text-lg font-bold text-white mb-4">📊 მოპოვებული მონაცემები</h3>
                <div id="team-data" class="grid grid-cols-1 md:grid-cols-2 gap-4">
                </div>
                
                <!-- Players Section -->
                <div id="players-section" class="hidden mt-6">
                    <h4 class="text-md font-bold text-white mb-3">👥 მოთამაშეები (<span id="players-count">0</span>)</h4>
                    <div id="players-list" class="bg-[#070A13] border border-gray-700 rounded-lg p-4 max-h-96 overflow-y-auto">
                    </div>
                </div>
                
                <div class="flex gap-3 mt-6">
                    <button 
                        onclick="confirmData()" 
                        class="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white px-6 py-3 rounded-lg font-semibold transition-all"
                    >
                        ✅ დადასტურება და ბაზაში ჩაწერა
                    </button>
                    <button 
                        onclick="rejectData()" 
                        class="flex-1 bg-red-600 hover:bg-red-500 text-white px-6 py-3 rounded-lg font-semibold transition-all"
                    >
                        ❌ უარყოფა
                    </button>
                </div>
            </div>

            <!-- Live Logs -->
            <div class="bg-[#0E1424] border border-gray-800 rounded-xl p-6">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-lg font-bold text-white">📜 ლაივ ლოგები</h3>
                    <button onclick="clearLogs()" class="text-xs text-gray-400 hover:text-white">გასუფთავება</button>
                </div>
                <div id="terminal" class="bg-[#070A13] border border-gray-850 rounded-lg p-4 h-80 overflow-y-auto font-mono text-xs space-y-2">
                    <div class="text-gray-500">// სისტემა მზად არის. დაელოდე ბრძანებას...</div>
                </div>
            </div>
        </div>

        <script>
            let checkedCount = 0;
            let currentTeamData = null;
            let currentMode = 'url';

            function switchTab(mode) {
                currentMode = mode;
                
                document.getElementById('tab-url').className = mode === 'url' ? 'tab-active px-6 py-3 rounded-lg font-semibold transition-all' : 'tab-inactive px-6 py-3 rounded-lg font-semibold transition-all';
                document.getElementById('tab-paste').className = mode === 'paste' ? 'tab-active px-6 py-3 rounded-lg font-semibold transition-all' : 'tab-inactive px-6 py-3 rounded-lg font-semibold transition-all';
                
                document.getElementById('section-url').classList.toggle('hidden', mode !== 'url');
                document.getElementById('section-paste').classList.toggle('hidden', mode !== 'paste');
            }

            function startScouting() {
                const url = document.getElementById('targetUrl').value;
                const startBtn = document.getElementById('startBtn');
                
                if (!url) {
                    alert('გთხოვთ ჩაწეროთ URL');
                    return;
                }

                startBtn.disabled = true;
                startBtn.textContent = '⏳ მუშაობს...';

                resetUI();
                
                const eventSource = new EventSource('/api/agent/stream-scout?url=' + encodeURIComponent(url));
                
                eventSource.onmessage = function(e) {
                    const data = JSON.parse(e.data);
                    handleAgentMessage(data);
                    
                    if (data.done) {
                        eventSource.close();
                        startBtn.disabled = false;
                        startBtn.textContent = '🚀 გააქტიურე';
                        
                        if (data.team_data) {
                            currentTeamData = data.team_data;
                            displayTeamData(data.team_data);
                        }
                    }
                };

                eventSource.onerror = function(e) {
                    addLog('system', '❌ კავშირი დაიკარგა', 'error');
                    eventSource.close();
                    startBtn.disabled = false;
                    startBtn.textContent = '🚀 გააქტიურე';
                };
            }

            function startParsing() {
                const text = document.getElementById('pasteText').value;
                const parseBtn = document.getElementById('parseBtn');
                
                if (!text.trim()) {
                    alert('გთხოვთ ჩაწეროთ ტექსტი');
                    return;
                }

                parseBtn.disabled = true;
                parseBtn.textContent = '⏳ მუშაობს...';

                resetUI();
                
                fetch('/api/agent/parse-text', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ text: text })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        currentTeamData = data.data;
                        displayTeamData(data.data);
                        addLog('TextParser', `✅ წარმატებით დამუშავდა. ვიპოვე ${data.players_count} მოთამაშე`, 'success');
                    } else {
                        addLog('TextParser', `❌ შეცდომა: ${data.error}`, 'error');
                    }
                    
                    parseBtn.disabled = false;
                    parseBtn.textContent = '📝 დაამუშავე ტექსტი';
                })
                .catch(error => {
                    addLog('system', `❌ შეცდომა: ${error.message}`, 'error');
                    parseBtn.disabled = false;
                    parseBtn.textContent = '📝 დაამუშავე ტექსტი';
                });
            }

            function displayTeamData(teamData) {
                const dataDisplay = document.getElementById('data-display');
                const teamDataDiv = document.getElementById('team-data');
                
                dataDisplay.classList.remove('hidden');
                
                const fields = [
                    { label: '🏆 გუნდის სახელი', value: teamData.name, key: 'name' },
                    { label: '🔤 მოკლე კოდი', value: teamData.short_code, key: 'short_code' },
                    { label: '🏟️ სტადიონი', value: teamData.stadium || 'არ არის მითითებული', key: 'stadium' },
                    { label: '🏙️ ქალაქი', value: teamData.city || 'არ არის მითითებული', key: 'city' },
                    { label: '🌍 ქვეყანა', value: teamData.country || 'არ არის მითითებული', key: 'country' },
                    { label: '👔 მწვრთნელი', value: teamData.coach || 'არ არის მითითებული', key: 'coach' },
                    { label: '🖼️ ლოგო', value: teamData.logo_url ? 'მოიძებნა' : 'არ მოიძებნა', key: 'logo_url' }
                ];
                
                teamDataDiv.innerHTML = fields.map(field => `
                    <div class="data-card bg-[#070A13] border border-gray-700 rounded-lg p-4">
                        <div class="text-xs text-gray-500 mb-1">${field.label}</div>
                        <input 
                            type="text" 
                            value="${field.value}" 
                            data-key="${field.key}"
                            class="w-full bg-transparent text-white font-semibold focus:outline-none focus:border-emerald-500 border-b border-transparent focus:border-b-emerald-500"
                        >
                    </div>
                `).join('');
                
                // Players
                if (teamData.players && teamData.players.length > 0) {
                    document.getElementById('players-section').classList.remove('hidden');
                    document.getElementById('players-count').textContent = teamData.players.length;
                    
                    const playersList = document.getElementById('players-list');
                    playersList.innerHTML = teamData.players.map(player => `
                        <div class="border-b border-gray-700 py-2 last:border-b-0">
                            <div class="flex justify-between items-center">
                                <div>
                                    <span class="text-emerald-400 font-bold">#${player.shirt_number || '?'}</span>
                                    <span class="text-white ml-2">${player.name || 'უცნობი'}</span>
                                </div>
                                <div class="text-xs text-gray-400">
                                    ${player.position || ''}
                                </div>
                            </div>
                            <div class="text-xs text-gray-500 mt-1">
                                ${player.birth_date ? '🎂 ' + player.birth_date : ''}
                                ${player.height_cm ? ' | 📏 ' + player.height_cm + ' სმ' : ''}
                                ${player.weight_kg ? ' | ⚖️ ' + player.weight_kg + ' კგ' : ''}
                            </div>
                        </div>
                    `).join('');
                } else {
                    document.getElementById('players-section').classList.add('hidden');
                }
            }

            function confirmData() {
                const inputs = document.querySelectorAll('#team-data input');
                const updatedData = {};
                inputs.forEach(input => {
                    updatedData[input.dataset.key] = input.value;
                });
                
                addLog('system', '✅ მონაცემები დადასტურდა. ბაზაში ჩაწერა იწყება...', 'success');
                alert('მონაცემები დადასტურდა! (ბაზაში ჩაწერა მოგვიანებით დაემატება)');
                
                document.getElementById('data-display').classList.add('hidden');
            }

            function rejectData() {
                addLog('system', '❌ მონაცემები უარყოფილია', 'error');
                document.getElementById('data-display').classList.add('hidden');
                currentTeamData = null;
            }

            function resetUI() {
                document.getElementById('terminal').innerHTML = '';
                document.getElementById('data-display').classList.add('hidden');
                
                for (let i = 1; i <= 3; i++) {
                    const step = document.getElementById(`step-${i}`);
                    step.className = 'step-pending bg-[#070A13] rounded-lg p-4 transition-all';
                    document.getElementById(`step-${i}-status`).textContent = '⏸️';
                }

                document.getElementById('scout-card').classList.remove('agent-active');
                document.getElementById('parser-card').classList.remove('agent-active');
                document.getElementById('controller-card').classList.remove('agent-active');
                document.getElementById('scout-status').innerHTML = '⏸️ მზად';
                document.getElementById('scout-status').className = 'px-3 py-1 bg-gray-700 rounded-full text-xs font-semibold';
                document.getElementById('parser-status').innerHTML = '⏸️ მზად';
                document.getElementById('parser-status').className = 'px-3 py-1 bg-gray-700 rounded-full text-xs font-semibold';
                document.getElementById('controller-status').innerHTML = '⏸️ მზად';
                document.getElementById('controller-status').className = 'px-3 py-1 bg-gray-700 rounded-full text-xs font-semibold';
            }

            function handleAgentMessage(data) {
                const { agent, message, step, status, team_name } = data;

                const logType = message.includes('❌') ? 'error' : 
                               message.includes('✅') ? 'success' : 
                               message.includes('⚠️') ? 'warning' : 'info';
                addLog(agent, message, logType);

                if (agent === 'TeamScout') {
                    document.getElementById('scout-card').classList.add('agent-active');
                    document.getElementById('scout-status').innerHTML = '🔄 მუშაობს';
                    document.getElementById('scout-status').className = 'px-3 py-1 bg-emerald-600 rounded-full text-xs font-semibold animate-pulse';
                    document.getElementById('scout-task').textContent = message.substring(0, 30) + '...';
                } else if (agent === 'TextParser') {
                    document.getElementById('parser-card').classList.add('agent-active');
                    document.getElementById('parser-status').innerHTML = '🔄 მუშაობს';
                    document.getElementById('parser-status').className = 'px-3 py-1 bg-purple-600 rounded-full text-xs font-semibold animate-pulse';
                    document.getElementById('parser-task').textContent = message.substring(0, 30) + '...';
                } else if (agent === 'Controller') {
                    document.getElementById('controller-card').classList.add('agent-active');
                    document.getElementById('controller-status').innerHTML = '🔄 მუშაობს';
                    document.getElementById('controller-status').className = 'px-3 py-1 bg-blue-600 rounded-full text-xs font-semibold animate-pulse';
                }

                if (step) {
                    updateStep(step, status);
                }

                if (data.done) {
                    document.getElementById('scout-card').classList.remove('agent-active');
                    document.getElementById('parser-card').classList.remove('agent-active');
                    document.getElementById('controller-card').classList.remove('agent-active');
                    document.getElementById('scout-status').innerHTML = '✅ დასრულდა';
                    document.getElementById('scout-status').className = 'px-3 py-1 bg-emerald-600 rounded-full text-xs font-semibold';
                    document.getElementById('parser-status').innerHTML = '✅ დასრულდა';
                    document.getElementById('parser-status').className = 'px-3 py-1 bg-purple-600 rounded-full text-xs font-semibold';
                    document.getElementById('controller-status').innerHTML = '✅ დასრულდა';
                    document.getElementById('controller-status').className = 'px-3 py-1 bg-blue-600 rounded-full text-xs font-semibold';
                    
                    checkedCount++;
                    document.getElementById('controller-checked').textContent = `${checkedCount} გუნდი`;
                }
            }

            function updateStep(stepNum, status) {
                const step = document.getElementById(`step-${stepNum}`);
                const statusEl = document.getElementById(`step-${stepNum}-status`);

                if (status === 'active') {
                    step.className = 'step-active bg-[#070A13] rounded-lg p-4 transition-all';
                    statusEl.textContent = '🔄';
                } else if (status === 'completed') {
                    step.className = 'step-completed bg-[#070A13] rounded-lg p-4 transition-all';
                    statusEl.textContent = '✅';
                } else if (status === 'error') {
                    step.className = 'bg-red-900/20 border border-red-500 rounded-lg p-4 transition-all';
                    statusEl.textContent = '❌';
                }
            }

            function addLog(agent, message, type = 'info') {
                const terminal = document.getElementById('terminal');
                const log = document.createElement('div');
                log.className = 'log-entry';

                const colors = {
                    'info': 'text-blue-400',
                    'success': 'text-emerald-400',
                    'warning': 'text-yellow-400',
                    'error': 'text-red-400',
                    'system': 'text-gray-400'
                };

                const agentColors = {
                    'TeamScout': 'text-emerald-400',
                    'TextParser': 'text-purple-400',
                    'Controller': 'text-blue-400',
                    'system': 'text-gray-500'
                };

                const timestamp = new Date().toLocaleTimeString('ka-GE');
                
                log.innerHTML = `
                    <span class="text-gray-600">[${timestamp}]</span>
                    <strong class="${agentColors[agent] || 'text-gray-400'}">[${agent}]</strong>
                    <span class="${colors[type]}">${message}</span>
                `;

                terminal.appendChild(log);
                terminal.scrollTop = terminal.scrollHeight;
            }

            function clearLogs() {
                document.getElementById('terminal').innerHTML = '<div class="text-gray-500">// ლოგები გასუფთავდა</div>';
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/api/agent/parse-text")
async def parse_text(request: dict):
    """ამუშავებს მომხმარებლის მიერ ჩაფეისთებულ ტექსტს"""
    text = request.get("text", "")
    
    if not text.strip():
        return {"success": False, "error": "ტექსტი ცარიელია"}
    
    parser = TextParser()
    result = parser.parse_team_from_text(text)
    
    return result

@app.get("/api/agent/stream-scout")
async def stream_scout(url: str):
    scout = TeamScout()
    controller = ControllerBot()
    
    async def agent_runner():
        yield "data: " + json.dumps({
            "agent": "TeamScout", 
            "message": "🔍 ვიწყებ მონაცემების მოპოვებას...",
            "step": 1,
            "status": "active"
        }) + "\n\n"
        await asyncio.sleep(0.5)
        
        yield "data: " + json.dumps({
            "agent": "TeamScout", 
            "message": f"📡 ვუკავშირდები: {url}",
            "step": 1,
            "status": "active"
        }) + "\n\n"
        
        result = await scout.scout_team(url)
        
        if not result["success"]:
            yield "data: " + json.dumps({
                "agent": "TeamScout", 
                "message": f"❌ შეცდომა: {result['error']}",
                "step": 1,
                "status": "error",
                "done": True
            }) + "\n\n"
            return
        
        team_data = result["data"]
        
        yield "data: " + json.dumps({
            "agent": "TeamScout", 
            "message": f"✅ გვერდი წარმატებით ჩაიტვირთა ({result.get('raw_html_length', 0)} bytes)",
            "step": 1,
            "status": "completed"
        }) + "\n\n"
        await asyncio.sleep(0.5)
        
        yield "data: " + json.dumps({
            "agent": "TeamScout", 
            "message": f"🏆 გუნდი: {team_data['name'] or 'არ მოიძებნა'}",
            "team_name": team_data['name'],
            "step": 1,
            "status": "completed"
        }) + "\n\n"
        
        yield "data: " + json.dumps({
            "agent": "TeamScout", 
            "message": f"🔤 მოკლე კოდი: {team_data['short_code'] or 'არ მოიძებნა'}",
            "step": 1,
            "status": "completed"
        }) + "\n\n"
        
        yield "data: " + json.dumps({
            "agent": "TeamScout", 
            "message": f"🏟️ სტადიონი: {team_data['stadium'] or 'არ არის მითითებული'}",
            "step": 1,
            "status": "completed"
        }) + "\n\n"
        
        yield "data: " + json.dumps({
            "agent": "TeamScout", 
            "message": f"🏙️ ქალაქი: {team_data['city'] or 'არ არის მითითებული'}",
            "step": 1,
            "status": "completed"
        }) + "\n\n"
        
        yield "data: " + json.dumps({
            "agent": "TeamScout", 
            "message": f"🌍 ქვეყანა: {team_data['country'] or 'არ არის მითითებული'}",
            "step": 1,
            "status": "completed"
        }) + "\n\n"
        
        yield "data: " + json.dumps({
            "agent": "TeamScout", 
            "message": f"👔 მწვრთნელი: {team_data['coach'] or 'არ არის მითითებული'}",
            "step": 1,
            "status": "completed"
        }) + "\n\n"
        
        yield "data: " + json.dumps({
            "agent": "TeamScout", 
            "message": f"🖼️ ლოგო: {'მოიძებნა' if team_data['logo_url'] else 'არ მოიძებნა'}",
            "step": 1,
            "status": "completed"
        }) + "\n\n"
        
        await asyncio.sleep(1)
        
        yield "data: " + json.dumps({
            "agent": "Controller", 
            "message": "🔍 ვიწყებ მონაცემების შემოწმებას...",
            "step": 2,
            "status": "active"
        }) + "\n\n"
        await asyncio.sleep(1)
        
        is_valid, validation_errors = controller.validate_team(team_data)
        
        if not is_valid:
            yield "data: " + json.dumps({
                "agent": "Controller", 
                "message": f"❌ ვალიდაცია ვერ გაიარა:",
                "step": 2,
                "status": "error"
            }) + "\n\n"
            for error in validation_errors:
                yield "data: " + json.dumps({
                    "agent": "Controller", 
                    "message": f"   ⚠️ {error}",
                    "step": 2,
                    "status": "error"
                }) + "\n\n"
            yield "data: " + json.dumps({
                "agent": "Controller", 
                "message": f"🚫 მონაცემები არ გადის ვალიდაციას",
                "step": 3,
                "status": "error",
                "done": True
            }) + "\n\n"
            return
        
        yield "data: " + json.dumps({
            "agent": "Controller", 
            "message": f"✅ ვალიდაცია წარმატებით გაიარა",
            "step": 2,
            "status": "completed"
        }) + "\n\n"
        await asyncio.sleep(0.5)
        
        yield "data: " + json.dumps({
            "agent": "Controller", 
            "message": f"📊 მონაცემები მზად არის შესამოწმებლად",
            "step": 3,
            "status": "completed",
            "done": True,
            "team_data": team_data
        }) + "\n\n"
    
    return StreamingResponse(agent_runner(), media_type="text/event-stream")