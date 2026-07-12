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
            "Cache-Control": "max-age=0"
        }
    
    def normalize_url(self, url: str) -> str:
        """ნორმალიზაცია URL-ს - მოაშორებს /players/ თუ არის"""
        print(f"[DEBUG] normalize_url - ორიგინალი: {url}")
        
        # მოვაშოროთ /players/ ბოლოდან
        if url.endswith('/players/'):
            url = url[:-len('/players/')]
        elif url.endswith('/players'):
            url = url[:-len('/players')]
        
        # დავრწმუნდეთ რომ ბოლოში / არის
        if not url.endswith('/'):
            url += '/'
        
        print(f"[DEBUG] normalize_url - ნორმალიზებული: {url}")
        return url
    
    async def fetch_page(self, url: str) -> Optional[str]:
        """გადმოწერს HTML გვერდს გაუმჯობესებული headers-ით"""
        try:
            print(f"[DEBUG] ვცდილობ გადმოწერას: {url}")
            
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=30.0,
                verify=False
            ) as client:
                response = await client.get(url, headers=self.headers)
                print(f"[DEBUG] Response status: {response.status_code}")
                print(f"[DEBUG] Response headers: {dict(response.headers)}")
                response.raise_for_status()
                print(f"[DEBUG] HTML სიგრძე: {len(response.text)} bytes")
                return response.text
        except httpx.HTTPStatusError as e:
            print(f"[ERROR] HTTP შეცდომა: {e.response.status_code}")
            print(f"[ERROR] Response text: {e.response.text[:500]}")
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
        
        # გუნდის სახელი - ვეძებთ h1-ს რომელიც შეიცავს გუნდის სახელს
        h1_tags = soup.find_all('h1')
        print(f"[DEBUG] ვიპოვე {len(h1_tags)} h1 tag")
        
        for h1 in h1_tags:
            text = h1.get_text(strip=True)
            print(f"[DEBUG] h1 ტექსტი: {text}")
            
            # ვეძებთ გუნდის სახელს რომელიც არ არის title
            if 'состав' not in text.lower() and 'состав команды' not in text.lower():
                # ვცადოთ ამოვიღოთ გუნდის სახელი
                if '(' in text and ')' in text:
                    # ფორმატი: "გუნდი (ქალაქი, ქვეყანა)"
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
        
        # თუ ვერ ვიპოვეთ h1-ში, ვცადოთ meta tags
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
        
        # ლოგო - ვეძებთ og:image meta tag
        og_image = soup.find('meta', property='og:image')
        if og_image:
            team_data["logo_url"] = og_image.get('content', '')
            print(f"[DEBUG] ლოგო (og:image): {team_data['logo_url']}")
        else:
            # fallback - ვეძებთ img თაგს
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
        
        # ვეძებთ გუნდის დეტალებს - სპეციფიკური კლასებით
        info_elements = soup.find_all(['dl', 'table', 'div'], class_=re.compile(r'team-info|info|details', re.I))
        print(f"[DEBUG] ვიპოვე {len(info_elements)} info element")
        
        for element in info_elements:
            text = element.get_text()
            
            # სტადიონი
            stadium_match = re.search(r'(?:стадион|stadium)[:\s]+([^\n\r]+)', text, re.I)
            if stadium_match:
                team_data["stadium"] = stadium_match.group(1).strip()
                print(f"[DEBUG] სტადიონი: {team_data['stadium']}")
            
            # ქალაქი
            city_match = re.search(r'(?:город|city)[:\s]+([^\n\r]+)', text, re.I)
            if city_match:
                team_data["city"] = city_match.group(1).strip()
                print(f"[DEBUG] ქალაქი: {team_data['city']}")
            
            # ქვეყანა
            country_match = re.search(r'(?:страна|country)[:\s]+([^\n\r]+)', text, re.I)
            if country_match:
                team_data["country"] = country_match.group(1).strip()
                print(f"[DEBUG] ქვეყანა: {team_data['country']}")
            
            # მწვრთნელი
            coach_match = re.search(r'(?:тренер|coach|главный тренер)[:\s]+([^\n\r]+)', text, re.I)
            if coach_match:
                team_data["coach"] = coach_match.group(1).strip()
                print(f"[DEBUG] მწვრთნელი: {team_data['coach']}")
        
        # Short code - პირველი 3 ასო სახელიდან
        if team_data["name"]:
            # ვცადოთ ინგლისური ასოები
            english_name = re.sub(r'[^a-zA-Z\s]', '', team_data["name"])
            if english_name:
                words = english_name.split()
                if words:
                    team_data["short_code"] = words[0][:3].upper()
            else:
                # თუ არა ინგლისური, ვიღებთ პირველ 3 ასოს
                team_data["short_code"] = team_data["name"][:3].upper()
            print(f"[DEBUG] Short code: {team_data['short_code']}")
        
        print(f"[DEBUG] Parsing დასრულდა. მონაცემები: {team_data}")
        return team_data
    
    async def scout_team(self, url: str) -> Dict:
        """მთავარი ფუნქცია - აგროვებს გუნდის ინფორმაციას"""
        print(f"[DEBUG] scout_team - ორიგინალი URL: {url}")
        
        # ნორმალიზაცია URL
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
        </style>
    </head>
    <body class="bg-gradient-to-br from-[#0B0F19] to-[#1a1f2e] text-[#E2E8F0] font-sans min-h-screen p-6">
        <div class="max-w-6xl mx-auto">
            <div class="text-center mb-8">
                <h1 class="text-4xl font-bold text-white mb-2">🤖 FootStats Agent Dashboard</h1>
                <p class="text-gray-400">ავტომატიზებული საფეხბურთო სტატისტიკის სისტემა</p>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
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
                        <div class="flex justify-between">
                            <span class="text-gray-500">ბოლო მოპოვება:</span>
                            <span id="scout-last" class="text-gray-400">არ არის</span>
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
                            <span class="text-gray-500">სტატუსი:</span>
                            <span id="controller-task" class="text-blue-400">მოლოდინში</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-500">შემოწმებული:</span>
                            <span id="controller-checked" class="text-gray-400">0 გუნდი</span>
                        </div>
                    </div>
                </div>
            </div>

            <div class="bg-[#0E1424] border border-gray-800 rounded-xl p-6 mb-8">
                <h3 class="text-lg font-bold text-white mb-4">🎯 გუნდის URL</h3>
                <div class="flex gap-3">
                    <input 
                        id="targetUrl" 
                        type="text" 
                        value="https://www.championat.com/football/_england/tournament/6592/teams/268572/players/"
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

            <div class="bg-[#0E1424] border border-gray-800 rounded-xl p-6 mb-8">
                <h3 class="text-lg font-bold text-white mb-4">📋 პროცესის ნაბიჯები</h3>
                <div class="space-y-3">
                    <div id="step-1" class="step-pending bg-[#070A13] rounded-lg p-4 transition-all">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 bg-gray-700 rounded-full flex items-center justify-center text-sm font-bold">1</div>
                            <div class="flex-1">
                                <div class="font-semibold text-white">მონაცემების მოპოვება</div>
                                <div class="text-xs text-gray-400">TeamScout აგროვებს ინფორმაციას საიტიდან</div>
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

            <!-- ახალი: მოპოვებული მონაცემების სექცია -->
            <div id="data-display" class="hidden bg-[#0E1424] border border-gray-800 rounded-xl p-6 mb-8">
                <h3 class="text-lg font-bold text-white mb-4">📊 მოპოვებული მონაცემები</h3>
                <div id="team-data" class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <!-- მონაცემები აქ გამოჩნდება -->
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
                        
                        // თუ მონაცემები მოვიპოვეთ, ვაჩვენოთ
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
            }

            function confirmData() {
                // ვიღებთ რედაქტირებულ მონაცემებს
                const inputs = document.querySelectorAll('#team-data input');
                const updatedData = {};
                inputs.forEach(input => {
                    updatedData[input.dataset.key] = input.value;
                });
                
                addLog('system', '✅ მონაცემები დადასტურდა. ბაზაში ჩაწერა იწყება...', 'success');
                
                // აქ დავამატებთ ბაზაში ჩაწერის ლოგიკას მოგვიანებით
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
                document.getElementById('controller-card').classList.remove('agent-active');
                document.getElementById('scout-status').innerHTML = '⏸️ მზად';
                document.getElementById('scout-status').className = 'px-3 py-1 bg-gray-700 rounded-full text-xs font-semibold';
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
                    
                    if (team_name) {
                        document.getElementById('scout-last').textContent = team_name;
                    }
                } else if (agent === 'Controller') {
                    document.getElementById('controller-card').classList.add('agent-active');
                    document.getElementById('controller-status').innerHTML = '🔄 მუშაობს';
                    document.getElementById('controller-status').className = 'px-3 py-1 bg-blue-600 rounded-full text-xs font-semibold animate-pulse';
                    document.getElementById('controller-task').textContent = message.substring(0, 30) + '...';
                }

                if (step) {
                    updateStep(step, status);
                }

                if (data.done) {
                    document.getElementById('scout-card').classList.remove('agent-active');
                    document.getElementById('controller-card').classList.remove('agent-active');
                    document.getElementById('scout-status').innerHTML = '✅ დასრულდა';
                    document.getElementById('scout-status').className = 'px-3 py-1 bg-emerald-600 rounded-full text-xs font-semibold';
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

@app.get("/api/agent/stream-scout")
async def stream_scout(url: str):
    scout = TeamScout()
    controller = ControllerBot()
    
    async def agent_runner():
        # STEP 1: TeamScout მუშაობს
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
        
        # STEP 2: Controller Bot მუშაობს
        yield "data: " + json.dumps({
            "agent": "Controller", 
            "message": "🔍 ვიწყებ მონაცემების შემოწმებას...",
            "step": 2,
            "status": "active"
        }) + "\n\n"
        await asyncio.sleep(1)
        
        # Validation
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
        
        # STEP 3: ვიზუალიზაცია
        yield "data: " + json.dumps({
            "agent": "Controller", 
            "message": f"📊 მონაცემები მზად არის შესამოწმებლად",
            "step": 3,
            "status": "completed",
            "done": True,
            "team_data": team_data
        }) + "\n\n"
    
    return StreamingResponse(agent_runner(), media_type="text/event-stream")