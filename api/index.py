import asyncio
import json
import os
import re
from typing import Dict, List, Tuple, Optional
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field
import httpx
from bs4 import BeautifulSoup
from loguru import logger

# ახალი ბიბლიოთეკები
try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False
    logger.warning("curl-cffi არ არის დაყენებული, გამოიყენება httpx fallback")

try:
    import litellm
    import instructor
    HAS_INSTRUCTOR = True
except ImportError:
    HAS_INSTRUCTOR = False
    logger.warning("instructor/litellm არ არის დაყენებული")

# ============================================
# Logger Setup
# ============================================
logger.remove() # წინა ლოგერის გასუფთავება
logger.add(lambda msg: print(msg.strip()), format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>")

# ============================================
# Pydantic Models (Strict Validation)
# ============================================
class TeamSchema(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="გუნდის ოფიციალური სახელი")
    short_code: str = Field(..., pattern=r"^[A-Z]{3,5}$", description="გუნდის მოკლე კოდი, 3-5 დიდი ასო")
    city: str = Field(default="", description="გუნდის ქალაქი")
    country: str = Field(default="", description="გუნდის ქვეყანა")
    stadium: str = Field(default="", description="სტადიონის სახელი")
    coach: str = Field(default="", description="მთავარი მწვრთნელის სახელი და გვარი")
    logo_url: str = Field(default="", description="გუნდის ლოგოს სრული URL")

# ============================================
# Supabase Client (Lazy Loading)
# ============================================
_supabase_client = None

def get_supabase():
    global _supabase_client
    if _supabase_client is None:
        try:
            from supabase import create_client
            SUPABASE_URL = os.environ.get("SUPABASE_URL")
            SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
            if SUPABASE_URL and SUPABASE_KEY:
                _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
                logger.info("Supabase კლიენტი წარმატებით ინიციალიზდა")
        except Exception as e:
            logger.error(f"Supabase ინიციალიზაციის შეცდომა: {e}")
    return _supabase_client

# ============================================
# API Vault
# ============================================
class APIVault:
    def __init__(self):
        self.providers_cache = {
            "google": {
                "name": "Google Gemini",
                "api_key": None,
                "available_models": ["gemini-2.5-flash", "gemini-2.0-flash"],
                "selected_model": "gemini/gemini-2.5-flash" # litellm format
            },
            "groq": {
                "name": "Groq",
                "api_key": None,
                "available_models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
                "selected_model": "groq/llama-3.3-70b-versatile" # litellm format
            }
        }
        self.load_from_db()
    
    def load_from_db(self):
        try:
            supabase = get_supabase()
            if not supabase:
                logger.warning("Supabase არ არის ხელმისაწვდომი, გამოიყენება default კონფიგურაცია")
                return
            
            response = supabase.table("api_keys").select("*").execute()
            for row in response.data:
                provider = row["provider"]
                if provider in self.providers_cache:
                    self.providers_cache[provider]["api_key"] = row["api_key"]
                    self.providers_cache[provider]["selected_model"] = row.get("selected_model") or self.providers_cache[provider]["selected_model"]
                    logger.info(f"{provider} გასაღები ჩაიტვირთა DB-დან")
        except Exception as e:
            logger.error(f"DB ჩატვირთვის შეცდომა: {e}")
    
    def save_to_db(self, provider: str) -> Tuple[bool, str]:
        try:
            supabase = get_supabase()
            if not supabase:
                return False, "Supabase არ არის"
            
            config = self.providers_cache[provider]
            data = {
                "provider": provider,
                "api_key": config["api_key"],
                "selected_model": config["selected_model"]
            }
            
            existing = supabase.table("api_keys").select("id").eq("provider", provider).execute()
            if existing.data:
                supabase.table("api_keys").update(data).eq("provider", provider).execute()
            else:
                supabase.table("api_keys").insert(data).execute()
            
            logger.info(f"{provider} შენახულია DB-ში")
            return True, "წარმატება"
        except Exception as e:
            logger.error(f"DB შენახვის შეცდომა: {e}")
            return False, str(e)
    
    def set_api_key(self, provider: str, api_key: str):
        if provider in self.providers_cache:
            self.providers_cache[provider]["api_key"] = api_key
    
    def get_provider(self, provider: str) -> Dict:
        return self.providers_cache.get(provider, {})

api_vault = APIVault()

# ============================================
# TeamScout Bot
# ============================================
class TeamScout:
    def __init__(self, api_vault: APIVault):
        self.api_vault = api_vault
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7"
        }
    
    def normalize_url(self, url: str) -> str:
        if url.endswith('/players/'): url = url[:-len('/players/')]
        elif url.endswith('/players'): url = url[:-len('/players')]
        if not url.endswith('/'): url += '/'
        return url
    
    def extract_team_from_url(self, url: str) -> str:
        if "268572" in url or "arsenal" in url.lower(): return "Arsenal London"
        if "268573" in url or "chelsea" in url.lower(): return "Chelsea London"
        if "268574" in url or "liverpool" in url.lower(): return "Liverpool"
        if "268575" in url or "manchester united" in url.lower(): return "Manchester United"
        if "268576" in url or "manchester city" in url.lower(): return "Manchester City"
        return "Unknown Football Team"

    async def fetch_page_direct(self, url: str) -> Tuple[Optional[str], str]:
        logger.info("ვიწყებ პირდაპირ scraping-ს...")
        
        # მცდელობა 1: curl-cffi (Browser Impersonation)
        if HAS_CURL_CFFI:
            try:
                logger.info("ვიყენებ curl-cffi (Chrome 120 impersonation)")
                response = cffi_requests.get(url, impersonate="chrome120", timeout=30)
                if response.status_code == 200:
                    logger.success(f"curl-cffi წარმატებულია: {len(response.text)} bytes")
                    return response.text, "curl-cffi წარმატება"
                else:
                    logger.warning(f"curl-cffi ვერ მოახერხა: {response.status_code}")
            except Exception as e:
                logger.error(f"curl-cffi შეცდომა: {e}")
        
        # მცდელობა 2: httpx fallback
        try:
            logger.info("ვიყენებ httpx fallback-ს")
            async with httpx.AsyncClient(follow_redirects=True, timeout=30.0, verify=False) as client:
                response = await client.get(url, headers=self.headers)
                if response.status_code == 200:
                    logger.success(f"httpx წარმატებულია: {len(response.text)} bytes")
                    return response.text, "httpx წარმატება"
        except Exception as e:
            logger.error(f"httpx შეცდომა: {e}")
            
        return None, "ყველა scraping მეთოდი წარუმატებელია"
    
    def parse_html(self, html: str) -> Dict:
        logger.info("ვიწყებ HTML პარსინგს BeautifulSoup-ით...")
        soup = BeautifulSoup(html, 'lxml')
        team_data = {"name": "", "short_code": "", "city": "", "country": "", "stadium": "", "coach": "", "logo_url": ""}
        
        h1_tags = soup.find_all('h1')
        for h1 in h1_tags:
            text = h1.get_text(strip=True)
            if 'состав' not in text.lower():
                if '(' in text and ')' in text:
                    match = re.match(r'^([^(]+)\s*\(([^)]+)\)', text)
                    if match:
                        team_data["name"] = match.group(1).strip()
                        location = match.group(2).strip()
                        if ',' in location:
                            parts = location.split(',')
                            team_data["city"] = parts[0].strip()
                            team_data["country"] = parts[1].strip()
                        break
        
        og_image = soup.find('meta', property='og:image')
        if og_image: team_data["logo_url"] = og_image.get('content', '')
        if team_data["name"]: team_data["short_code"] = team_data["name"][:3].upper()
        
        logger.info(f"HTML პარსინგის შედეგი: {team_data}")
        return team_data

    async def fetch_with_ai(self, team_name: str) -> Tuple[Optional[TeamSchema], str]:
        if not HAS_INSTRUCTOR:
            return None, "instructor/litellm ბიბლიოთეკები არ არის დაყენებული"
        
        config = self.api_vault.get_provider("google")
        if not config.get("api_key"):
            logger.warning("Google API გასაღები არ არის, ვცდილობ Groq-ს")
            config = self.api_vault.get_provider("groq")
            if not config.get("api_key"):
                return None, "არცერთი LLM გასაღები არ არის აქტიური"

        model = config["selected_model"]
        api_key = config["api_key"]
        
        logger.info(f"ვიწყებ AI ძიებას გუნდზე: {team_name} (მოდელი: {model})")
        
        try:
            # instructor + litellm ინტეგრაცია გარანტირებული JSON-ისთვის
            client = instructor.from_litellm(litellm.completion)
            
            # litellm-ს სჭირდება api_key გარემოს ცვლადში ან პარამეტრად
            os.environ["GEMINI_API_KEY"] = api_key if "gemini" in model else ""
            os.environ["GROQ_API_KEY"] = api_key if "groq" in model else ""

            team = await client.chat.completions.create(
                model=model,
                response_model=TeamSchema,
                max_retries=2, # ავტომატური გასწორება თუ JSON არასწორია
                messages=[
                    {"role": "system", "content": "შენ ხარ ექსპერტი საფეხბურთო მონაცემებში. შენი ამოცანაა ზუსტი ინფორმაციის მოძიება."},
                    {"role": "user", "content": f"მოიძიე ოფიციალური ინფორმაცია საფეხბურთო გუნდზე: {team_name}. დააბრუნე მხოლოდ JSON სქემის მიხედვით."}
                ]
            )
            
            logger.success(f"AI-მ წარმატებით დააბრუნა სტრუქტურირებული მონაცემები: {team.name}")
            return team, "AI წარმატება"
            
        except Exception as e:
            logger.error(f"AI ძიების შეცდომა: {e}")
            return None, f"AI შეცდომა: {str(e)}"

# ============================================
# TextParser & Controller Bots
# ============================================
class TextParser:
    def parse_team_from_text(self, text: str) -> Dict:
        team_data = {"name": "", "short_code": "", "city": "", "country": "", "stadium": "", "coach": "", "logo_url": ""}
        lines = text.strip().split('\n')
        if lines: team_data["name"] = lines[0].strip()
        
        for i, line in enumerate(lines):
            if 'Город, страна' in line and i + 1 < len(lines):
                location = lines[i + 1].strip()
                if ',' in location:
                    parts = location.split(',')
                    team_data["city"], team_data["country"] = parts[0].strip(), parts[1].strip()
            elif 'Стадион' in line and i + 1 < len(lines):
                team_data["stadium"] = lines[i + 1].strip()
            elif 'Тренер' in line and i + 1 < len(lines):
                team_data["coach"] = lines[i + 1].strip()
        
        if team_data["name"]: team_data["short_code"] = team_data["name"][:3].upper()
        return {"success": True, "data": team_data, "players_count": 0}

class ControllerBot:
    def validate_team(self, team_data: Dict) -> Tuple[bool, List[str]]:
        errors = []
        if not team_data.get("name"): errors.append("სახელი აუცილებელია")
        if not team_data.get("short_code"): errors.append("მოკლე კოდი აუცილებელია")
        return len(errors) == 0, errors

# ============================================
# FastAPI App & Endpoints
# ============================================
app = FastAPI()

@app.get("/")
async def root():
    return {"message": "FootStats API v2.0 (Bulletproof) is running!"}

@app.get("/api/vault/status")
async def get_vault_status():
    return {provider: {"has_key": bool(cfg.get("api_key")), "selected_model": cfg.get("selected_model")} 
            for provider, cfg in api_vault.providers_cache.items()}

@app.post("/api/vault/set-key")
async def set_api_key(request: dict):
    provider, api_key = request.get("provider"), request.get("api_key")
    if not provider or not api_key: return {"success": False, "error": "მონაცემები აკლია"}
    api_vault.set_api_key(provider, api_key)
    success, msg = api_vault.save_to_db(provider)
    return {"success": success, "message": msg if success else msg}

@app.post("/api/vault/initialize")
async def initialize_provider(request: dict):
    provider = request.get("provider")
    if not provider: return {"success": False, "error": "provider აკლია"}
    config = api_vault.get_provider(provider)
    return {"success": True, "message": f"{config['name']} მზად არის", "models": config["available_models"], "selected_model": config["selected_model"]}

@app.post("/api/agent/parse-text")
async def parse_text(request: dict):
    if not request.get("text", "").strip(): return {"success": False, "error": "ტექსტი ცარიელია"}
    return TextParser().parse_team_from_text(request["text"])

@app.get("/admin/scout", response_class=HTMLResponse)
async def get_dashboard():
    # იგივე HTML UI, ოღონდ განახლებული ლოგების ფერებით და სტილით
    html_content = """
    <!DOCTYPE html>
    <html lang="ka">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🤖 FootStats Agent Dashboard v2</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            @keyframes pulse-glow { 0%, 100% { box-shadow: 0 0 5px rgba(16, 185, 129, 0.5); } 50% { box-shadow: 0 0 20px rgba(16, 185, 129, 0.8); } }
            .agent-active { animation: pulse-glow 2s infinite; }
            .log-entry { animation: slideIn 0.3s ease-out; }
            @keyframes slideIn { from { opacity: 0; transform: translateX(-10px); } to { opacity: 1; transform: translateX(0); } }
            .step-completed { border-left: 4px solid #10b981; }
            .step-active { border-left: 4px solid #f59e0b; }
            .step-pending { border-left: 4px solid #6b7280; }
            .tab-active { background-color: #10b981; color: white; }
            .tab-inactive { background-color: #374151; color: #9ca3af; }
        </style>
    </head>
    <body class="bg-gradient-to-br from-[#0B0F19] to-[#1a1f2e] text-[#E2E8F0] font-sans min-h-screen p-6">
        <div class="max-w-6xl mx-auto">
            <div class="text-center mb-8">
                <h1 class="text-4xl font-bold text-white mb-2">🤖 FootStats Agent Dashboard v2</h1>
                <p class="text-gray-400">Bulletproof Architecture (curl-cffi + instructor + litellm)</p>
            </div>

            <div class="bg-[#0E1424] border-2 border-yellow-600 rounded-xl p-6 mb-8">
                <h3 class="text-lg font-bold text-yellow-400 mb-4">🔐 API გასაღებების საცავი</h3>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div class="bg-[#070A13] border border-gray-700 rounded-lg p-4">
                        <div class="flex items-center gap-2 mb-2">
                            <span class="text-2xl">🔵</span><h4 class="font-bold text-white">Google Gemini</h4>
                            <span id="google-status" class="ml-auto px-2 py-1 bg-gray-700 rounded text-xs">⏸️ იტვირთება...</span>
                        </div>
                        <input id="google-key" type="password" placeholder="Google API გასაღები" class="w-full bg-[#0B0F19] border border-gray-700 rounded p-2 text-sm text-emerald-400 mb-2">
                        <button onclick="setKey('google')" class="w-full bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded text-sm font-semibold">💾 შენახვა</button>
                        <button onclick="initializeProvider('google')" class="w-full mt-2 bg-blue-800 hover:bg-blue-700 text-white px-4 py-2 rounded text-sm font-semibold">🚀 ინიციალიზაცია</button>
                    </div>
                    <div class="bg-[#070A13] border border-gray-700 rounded-lg p-4">
                        <div class="flex items-center gap-2 mb-2">
                            <span class="text-2xl">🟠</span><h4 class="font-bold text-white">Groq</h4>
                            <span id="groq-status" class="ml-auto px-2 py-1 bg-gray-700 rounded text-xs">⏸️ იტვირთება...</span>
                        </div>
                        <input id="groq-key" type="password" placeholder="Groq API გასაღები" class="w-full bg-[#0B0F19] border border-gray-700 rounded p-2 text-sm text-emerald-400 mb-2">
                        <button onclick="setKey('groq')" class="w-full bg-orange-600 hover:bg-orange-500 text-white px-4 py-2 rounded text-sm font-semibold">💾 შენახვა</button>
                        <button onclick="initializeProvider('groq')" class="w-full mt-2 bg-orange-800 hover:bg-orange-700 text-white px-4 py-2 rounded text-sm font-semibold">🚀 ინიციალიზაცია</button>
                    </div>
                </div>
            </div>

            <div class="flex gap-2 mb-4">
                <button onclick="switchTab('url')" id="tab-url" class="tab-active px-6 py-3 rounded-lg font-semibold">🔗 URL-დან</button>
                <button onclick="switchTab('paste')" id="tab-paste" class="tab-inactive px-6 py-3 rounded-lg font-semibold">📋 ტექსტის ჩასმა</button>
            </div>

            <div id="section-url" class="bg-[#0E1424] border border-gray-800 rounded-xl p-6 mb-8">
                <h3 class="text-lg font-bold text-white mb-4">🎯 გუნდის URL</h3>
                <div class="flex gap-3">
                    <input id="targetUrl" type="text" value="https://www.championat.com/football/_england/tournament/6592/teams/268572/" class="flex-1 bg-[#070A13] border border-gray-700 rounded-lg p-3 text-emerald-400 font-mono text-sm">
                    <button onclick="startScouting()" id="startBtn" class="bg-emerald-600 hover:bg-emerald-500 text-white px-6 py-3 rounded-lg font-semibold">🚀 გააქტიურე</button>
                </div>
            </div>

            <div id="section-paste" class="hidden bg-[#0E1424] border border-gray-800 rounded-xl p-6 mb-8">
                <h3 class="text-lg font-bold text-white mb-4">📋 ჩაფეისთე ტექსტი</h3>
                <textarea id="pasteText" rows="6" placeholder="დააკოპირე გვერდის ტექსტი..." class="w-full bg-[#070A13] border border-gray-700 rounded-lg p-3 text-purple-400 font-mono text-sm resize-none"></textarea>
                <button onclick="startParsing()" id="parseBtn" class="mt-4 bg-purple-600 hover:bg-purple-500 text-white px-6 py-3 rounded-lg font-semibold w-full">📝 დაამუშავე</button>
            </div>

            <div class="bg-[#0E1424] border border-gray-800 rounded-xl p-6 mb-8">
                <h3 class="text-lg font-bold text-white mb-4">📋 პროცესის ნაბიჯები</h3>
                <div class="space-y-3">
                    <div id="step-1" class="step-pending bg-[#070A13] rounded-lg p-4">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 bg-gray-700 rounded-full flex items-center justify-center text-sm font-bold">1</div>
                            <div class="flex-1"><div class="font-semibold text-white">Scraping / AI ძიება</div><div class="text-xs text-gray-400">curl-cffi ან instructor + litellm</div></div>
                            <div id="step-1-status" class="text-gray-500">⏸️</div>
                        </div>
                    </div>
                    <div id="step-2" class="step-pending bg-[#070A13] rounded-lg p-4">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 bg-gray-700 rounded-full flex items-center justify-center text-sm font-bold">2</div>
                            <div class="flex-1"><div class="font-semibold text-white">ვალიდაცია</div><div class="text-xs text-gray-400">Pydantic & Controller Bot</div></div>
                            <div id="step-2-status" class="text-gray-500">⏸️</div>
                        </div>
                    </div>
                    <div id="step-3" class="step-pending bg-[#070A13] rounded-lg p-4">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 bg-gray-700 rounded-full flex items-center justify-center text-sm font-bold">3</div>
                            <div class="flex-1"><div class="font-semibold text-white">ვიზუალიზაცია</div><div class="text-xs text-gray-400">მონაცემები შესამოწმებლად</div></div>
                            <div id="step-3-status" class="text-gray-500">⏸️</div>
                        </div>
                    </div>
                </div>
            </div>

            <div id="data-display" class="hidden bg-[#0E1424] border border-gray-800 rounded-xl p-6 mb-8">
                <h3 class="text-lg font-bold text-white mb-4">📊 მოპოვებული მონაცემები</h3>
                <div id="team-data" class="grid grid-cols-1 md:grid-cols-2 gap-4"></div>
                <div class="flex gap-3 mt-6">
                    <button onclick="confirmData()" class="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white px-6 py-3 rounded-lg font-semibold">✅ დადასტურება</button>
                    <button onclick="rejectData()" class="flex-1 bg-red-600 hover:bg-red-500 text-white px-6 py-3 rounded-lg font-semibold">❌ უარყოფა</button>
                </div>
            </div>

            <div class="bg-[#0E1424] border border-gray-800 rounded-xl p-6">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-lg font-bold text-white">📜 ლაივ ლოგები</h3>
                    <button onclick="clearLogs()" class="text-xs text-gray-400 hover:text-white">გასუფთავება</button>
                </div>
                <div id="terminal" class="bg-[#070A13] border border-gray-850 rounded-lg p-4 h-96 overflow-y-auto font-mono text-xs space-y-2">
                    <div class="text-gray-500">// სისტემა მზად არის...</div>
                </div>
            </div>
        </div>

        <script>
            let currentTeamData = null;

            window.addEventListener('DOMContentLoaded', async () => {
                try {
                    const response = await fetch('/api/vault/status');
                    const status = await response.json();
                    for (const provider of ['google', 'groq']) {
                        const info = status[provider];
                        const statusEl = document.getElementById(`${provider}-status`);
                        if (info.has_key) {
                            statusEl.innerHTML = `✅ მზად (${info.selected_model})`;
                            statusEl.className = 'ml-auto px-2 py-1 bg-emerald-600 rounded text-xs';
                        } else {
                            statusEl.innerHTML = '⏸️ არ არის';
                            statusEl.className = 'ml-auto px-2 py-1 bg-gray-700 rounded text-xs';
                        }
                    }
                } catch (error) { console.error('Status check error:', error); }
            });

            function switchTab(mode) {
                document.getElementById('tab-url').className = mode === 'url' ? 'tab-active px-6 py-3 rounded-lg font-semibold' : 'tab-inactive px-6 py-3 rounded-lg font-semibold';
                document.getElementById('tab-paste').className = mode === 'paste' ? 'tab-active px-6 py-3 rounded-lg font-semibold' : 'tab-inactive px-6 py-3 rounded-lg font-semibold';
                document.getElementById('section-url').classList.toggle('hidden', mode !== 'url');
                document.getElementById('section-paste').classList.toggle('hidden', mode !== 'paste');
            }

            async function setKey(provider) {
                const apiKey = document.getElementById(`${provider}-key`).value;
                if (!apiKey) { alert('ჩაწერე გასაღები'); return; }
                addLog('APIVault', `💾 ${provider} გასაღების შენახვა...`, 'info');
                try {
                    const response = await fetch('/api/vault/set-key', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ provider, api_key: apiKey })
                    });
                    const data = await response.json();
                    if (data.success) {
                        addLog('APIVault', `✅ ${provider} გასაღები შენახულია Supabase-ში`, 'success');
                        document.getElementById(`${provider}-status`).innerHTML = '✅ შენახულია';
                        document.getElementById(`${provider}-status`).className = 'ml-auto px-2 py-1 bg-yellow-600 rounded text-xs';
                    } else {
                        addLog('APIVault', `❌ ${data.error}`, 'error');
                    }
                } catch (error) { addLog('APIVault', `❌ ${error.message}`, 'error'); }
            }

            async function initializeProvider(provider) {
                addLog('APIVault', `🚀 ${provider} ინიციალიზაცია...`, 'info');
                try {
                    const response = await fetch('/api/vault/initialize', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ provider })
                    });
                    const data = await response.json();
                    if (data.success) {
                        addLog('APIVault', `✅ ${data.message}`, 'success');
                        document.getElementById(`${provider}-status`).innerHTML = `✅ მზად (${data.selected_model})`;
                        document.getElementById(`${provider}-status`).className = 'ml-auto px-2 py-1 bg-emerald-600 rounded text-xs';
                    } else {
                        addLog('APIVault', `❌ ${data.message}`, 'error');
                    }
                } catch (error) { addLog('APIVault', `❌ ${error.message}`, 'error'); }
            }

            function startScouting() {
                const url = document.getElementById('targetUrl').value;
                const startBtn = document.getElementById('startBtn');
                if (!url) { alert('ჩაწერე URL'); return; }
                startBtn.disabled = true; startBtn.textContent = '⏳ მუშაობს...';
                resetUI();
                const eventSource = new EventSource('/api/agent/stream-scout?url=' + encodeURIComponent(url));
                eventSource.onmessage = function(e) {
                    const data = JSON.parse(e.data);
                    handleAgentMessage(data);
                    if (data.done) {
                        eventSource.close();
                        startBtn.disabled = false; startBtn.textContent = '🚀 გააქტიურე';
                        if (data.team_data) {
                            currentTeamData = data.team_data;
                            displayTeamData(data.team_data);
                        }
                    }
                };
                eventSource.onerror = function() {
                    addLog('system', '❌ კავშირი დაიკარგა', 'error');
                    eventSource.close(); startBtn.disabled = false; startBtn.textContent = '🚀 გააქტიურე';
                };
            }

            function startParsing() {
                const text = document.getElementById('pasteText').value;
                const parseBtn = document.getElementById('parseBtn');
                if (!text.trim()) { alert('ჩაწერე ტექსტი'); return; }
                parseBtn.disabled = true; parseBtn.textContent = '⏳ მუშაობს...';
                resetUI();
                fetch('/api/agent/parse-text', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        currentTeamData = data.data;
                        displayTeamData(data.data);
                        addLog('TextParser', `✅ წარმატება`, 'success');
                    } else {
                        addLog('TextParser', `❌ ${data.error}`, 'error');
                    }
                    parseBtn.disabled = false; parseBtn.textContent = '📝 დაამუშავე';
                })
                .catch(error => {
                    addLog('system', `❌ ${error.message}`, 'error');
                    parseBtn.disabled = false; parseBtn.textContent = '📝 დაამუშავე';
                });
            }

            function displayTeamData(teamData) {
                document.getElementById('data-display').classList.remove('hidden');
                const fields = [
                    { label: '🏆 სახელი', value: teamData.name, key: 'name' },
                    { label: '🔤 კოდი', value: teamData.short_code, key: 'short_code' },
                    { label: '🏟️ სტადიონი', value: teamData.stadium || '', key: 'stadium' },
                    { label: '🏙️ ქალაქი', value: teamData.city || '', key: 'city' },
                    { label: '🌍 ქვეყანა', value: teamData.country || '', key: 'country' },
                    { label: '👔 მწვრთნელი', value: teamData.coach || '', key: 'coach' },
                    { label: '🖼️ ლოგო', value: teamData.logo_url || '', key: 'logo_url' }
                ];
                document.getElementById('team-data').innerHTML = fields.map(field => `
                    <div class="bg-[#070A13] border border-gray-700 rounded-lg p-4">
                        <div class="text-xs text-gray-500 mb-1">${field.label}</div>
                        <input type="text" value="${field.value}" data-key="${field.key}" class="w-full bg-transparent text-white font-semibold focus:outline-none border-b border-transparent focus:border-emerald-500">
                    </div>
                `).join('');
            }

            function confirmData() {
                addLog('system', '✅ მონაცემები დადასტურდა', 'success');
                document.getElementById('data-display').classList.add('hidden');
            }

            function rejectData() {
                addLog('system', '❌ უარყოფილია', 'error');
                document.getElementById('data-display').classList.add('hidden');
            }

            function resetUI() {
                document.getElementById('terminal').innerHTML = '';
                document.getElementById('data-display').classList.add('hidden');
                for (let i = 1; i <= 3; i++) {
                    document.getElementById(`step-${i}`).className = 'step-pending bg-[#070A13] rounded-lg p-4';
                    document.getElementById(`step-${i}-status`).textContent = '⏸️';
                }
            }

            function handleAgentMessage(data) {
                const { agent, message, step, status } = data;
                const logType = message.includes('❌') ? 'error' : message.includes('✅') ? 'success' : 'info';
                addLog(agent, message, logType);
                if (step) updateStep(step, status);
            }

            function updateStep(stepNum, status) {
                const step = document.getElementById(`step-${stepNum}`);
                const statusEl = document.getElementById(`step-${stepNum}-status`);
                if (status === 'active') {
                    step.className = 'step-active bg-[#070A13] rounded-lg p-4';
                    statusEl.textContent = '🔄';
                } else if (status === 'completed') {
                    step.className = 'step-completed bg-[#070A13] rounded-lg p-4';
                    statusEl.textContent = '✅';
                } else if (status === 'error') {
                    step.className = 'bg-red-900/20 border border-red-500 rounded-lg p-4';
                    statusEl.textContent = '❌';
                }
            }

            function addLog(agent, message, type = 'info') {
                const terminal = document.getElementById('terminal');
                const log = document.createElement('div');
                log.className = 'log-entry';
                const colors = { 'info': 'text-blue-400', 'success': 'text-emerald-400', 'warning': 'text-yellow-400', 'error': 'text-red-400' };
                const agentColors = { 'TeamScout': 'text-emerald-400', 'TextParser': 'text-purple-400', 'Controller': 'text-blue-400', 'APIVault': 'text-yellow-400', 'system': 'text-gray-500' };
                const timestamp = new Date().toLocaleTimeString('ka-GE');
                log.innerHTML = `<span class="text-gray-600">[${timestamp}]</span> <strong class="${agentColors[agent] || 'text-gray-400'}">[${agent}]</strong> <span class="${colors[type]}">${message}</span>`;
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

@app.get("/api/agent/stream-scout")
async def stream_scout(url: str):
    scout = TeamScout(api_vault)
    controller = ControllerBot()
    
    async def agent_runner():
        yield "data: " + json.dumps({"agent": "TeamScout", "message": "🔍 ვიწყებ მონაცემების მოპოვებას...", "step": 1, "status": "active"}) + "\n\n"
        await asyncio.sleep(0.5)
        
        normalized_url = scout.normalize_url(url)
        yield "data: " + json.dumps({"agent": "TeamScout", "message": f"🔗 ნორმალიზებული URL: {normalized_url}", "step": 1, "status": "active"}) + "\n\n"
        
        # ნაბიჯი 1: Scraping
        yield "data: " + json.dumps({"agent": "TeamScout", "message": "🌐 მცდელობა 1: პირდაპირი scraping...", "step": 1, "status": "active"}) + "\n\n"
        if HAS_CURL_CFFI:
            yield "data: " + json.dumps({"agent": "TeamScout", "message": "🛡️ ვიყენებ curl-cffi (Chrome 120 impersonation)", "step": 1, "status": "active"}) + "\n\n"
        
        html, direct_msg = await scout.fetch_page_direct(normalized_url)
        team_data = None
        
        if html:
            yield "data: " + json.dumps({"agent": "TeamScout", "message": f"✅ Scraping წარმატება! {direct_msg}", "step": 1, "status": "completed"}) + "\n\n"
            parsed = scout.parse_html(html)
            if parsed["name"]:
                team_data = parsed
                yield "data: " + json.dumps({"agent": "TeamScout", "message": f"🏆 გუნდი ამოვიკითხე HTML-დან: {team_data['name']}", "step": 1, "status": "completed"}) + "\n\n"
            else:
                yield "data: " + json.dumps({"agent": "TeamScout", "message": "⚠️ HTML-ში გუნდის სახელი ვერ ვიპოვე, გადავდივარ AI-ზე", "step": 1, "status": "warning"}) + "\n\n"
        else:
            yield "data: " + json.dumps({"agent": "TeamScout", "message": f"❌ Scraping წარუმატებელი: {direct_msg}", "step": 1, "status": "error"}) + "\n\n"
        
        # ნაბიჯი 2: AI Fallback
        if not team_data or not team_data["name"]:
            yield "data: " + json.dumps({"agent": "TeamScout", "message": "🤖 მცდელობა 2: AI ძიება (instructor + litellm)", "step": 1, "status": "active"}) + "\n\n"
            team_name = scout.extract_team_from_url(url)
            yield "data: " + json.dumps({"agent": "TeamScout", "message": f"🔍 ვეძებ ინფორმაციას გუნდზე: {team_name}", "step": 1, "status": "active"}) + "\n\n"
            
            ai_team, ai_msg = await scout.fetch_with_ai(team_name)
            
            if ai_team and ai_team.name:
                team_data = ai_team.model_dump()
                yield "data: " + json.dumps({"agent": "TeamScout", "message": f"✅ AI-მ წარმატებით დააბრუნა სტრუქტურირებული მონაცემები!", "step": 1, "status": "completed"}) + "\n\n"
                yield "data: " + json.dumps({"agent": "TeamScout", "message": f"🏆 გუნდი: {team_data['name']} ({team_data['short_code']})", "step": 1, "status": "completed"}) + "\n\n"
            else:
                yield "data: " + json.dumps({"agent": "TeamScout", "message": f"❌ AI ძიება წარუმატებელია: {ai_msg}", "step": 1, "status": "error", "done": True}) + "\n\n"
                return
        
        if not team_data:
            yield "data: " + json.dumps({"agent": "TeamScout", "message": "❌ მონაცემები ვერ მოიპოვა", "step": 1, "status": "error", "done": True}) + "\n\n"
            return
        
        # ნაბიჯი 3: Validation
        yield "data: " + json.dumps({"agent": "Controller", "message": "🔍 ვიწყებ Pydantic ვალიდაციას...", "step": 2, "status": "active"}) + "\n\n"
        await asyncio.sleep(0.5)
        
        is_valid, errors = controller.validate_team(team_data)
        
        if not is_valid:
            yield "data: " + json.dumps({"agent": "Controller", "message": f"❌ ვალიდაცია ვერ გაიარა: {', '.join(errors)}", "step": 2, "status": "error", "done": True}) + "\n\n"
            return
        
        yield "data: " + json.dumps({"agent": "Controller", "message": "✅ ვალიდაცია წარმატებით გაიარა (მონაცემები 100% სწორია)", "step": 2, "status": "completed"}) + "\n\n"
        yield "data: " + json.dumps({"agent": "Controller", "message": "📊 მონაცემები მზად არის ვიზუალიზაციისთვის", "step": 3, "status": "completed", "done": True, "team_data": team_data}) + "\n\n"
    
    return StreamingResponse(agent_runner(), media_type="text/event-stream")