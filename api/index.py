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
# API Vault - გასაღებების მენეჯერი
# ============================================
class APIVault:
    """API გასაღებების საცავი და მენეჯერი"""
    
    def __init__(self):
        self.providers = {
            "google": {
                "name": "Google Gemini",
                "api_key": None,
                "base_url": "https://generativelanguage.googleapis.com/v1beta",
                "available_models": [],
                "selected_model": None
            },
            "groq": {
                "name": "Groq",
                "api_key": None,
                "base_url": "https://api.groq.com/openai/v1",
                "available_models": [],
                "selected_model": None
            }
        }
    
    def set_api_key(self, provider: str, api_key: str):
        """აყენებს API გასაღებს"""
        if provider in self.providers:
            self.providers[provider]["api_key"] = api_key
            print(f"[API Vault] {provider} გასაღები დაყენებულია")
    
    async def fetch_available_models(self, provider: str) -> List[str]:
        """გამოითხოვს ხელმისაწვდომ მოდელებს"""
        if provider not in self.providers:
            return []
        
        config = self.providers[provider]
        api_key = config["api_key"]
        
        if not api_key:
            print(f"[API Vault] {provider} გასაღები არ არის დაყენებული")
            return []
        
        try:
            if provider == "google":
                # Google Gemini - list models
                url = f"{config['base_url']}/models?key={api_key}"
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, timeout=10.0)
                    if response.status_code == 200:
                        data = response.json()
                        models = []
                        for model in data.get("models", []):
                            name = model.get("name", "")
                            # ვიღებთ მხოლოდ უფასო მოდელებს (flash variants)
                            if "flash" in name.lower() or "pro" in name.lower():
                                models.append(name.replace("models/", ""))
                        config["available_models"] = models
                        print(f"[API Vault] Google {len(models)} მოდელი ხელმისაწვდომია: {models}")
                        return models
            
            elif provider == "groq":
                # Groq - list models
                url = f"{config['base_url']}/models"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, headers=headers, timeout=10.0)
                    if response.status_code == 200:
                        data = response.json()
                        models = [m["id"] for m in data.get("data", [])]
                        config["available_models"] = models
                        print(f"[API Vault] Groq {len(models)} მოდელი ხელმისაწვდომია: {models}")
                        return models
        
        except Exception as e:
            print(f"[API Vault] {provider} მოდელების გამოთხოვის შეცდომა: {e}")
        
        return []
    
    def select_best_model(self, provider: str) -> Optional[str]:
        """ირჩევს საუკეთესო მოდელს"""
        config = self.providers[provider]
        models = config["available_models"]
        
        if not models:
            return None
        
        # ვირჩევთ უფასო/სწრაფ მოდელებს პრიორიტეტით
        if provider == "google":
            # ვეძებთ flash მოდელებს (უფასო)
            for model in models:
                if "flash" in model.lower():
                    config["selected_model"] = model
                    print(f"[API Vault] Google არჩეული მოდელი: {model}")
                    return model
            # თუ flash არ არის, ვირჩევთ პირველს
            config["selected_model"] = models[0]
            return models[0]
        
        elif provider == "groq":
            # Groq-ზე ვირჩევთ llama-3.3-70b ან მსგავსს
            for model in models:
                if "llama-3.3" in model.lower() or "llama-3" in model.lower():
                    config["selected_model"] = model
                    print(f"[API Vault] Groq არჩეული მოდელი: {model}")
                    return model
            config["selected_model"] = models[0]
            return models[0]
        
        return None
    
    async def initialize_provider(self, provider: str) -> Tuple[bool, str]:
        """ინიციალიზაცია პროვაიდერს - ამოწმებს გასაღებს და ირჩევს მოდელს"""
        if provider not in self.providers:
            return False, "პროვაიდერი არ არსებობს"
        
        config = self.providers[provider]
        
        if not config["api_key"]:
            return False, f"{config['name']} API გასაღები არ არის დაყენებული"
        
        # ვითხოვთ მოდელებს
        models = await self.fetch_available_models(provider)
        
        if not models:
            return False, f"{config['name']} მოდელები ვერ მოიძებნა"
        
        # ვირჩევთ საუკეთესო მოდელს
        selected = self.select_best_model(provider)
        
        if not selected:
            return False, f"{config['name']} ვერ აირჩია მოდელი"
        
        return True, f"{config['name']} მზად არის. მოდელი: {selected}"

# ============================================
# TeamScout Bot - AI-გაუმჯობესებული ვერსია
# ============================================
class TeamScout:
    def __init__(self, api_vault: APIVault):
        self.api_vault = api_vault
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
    
    def normalize_url(self, url: str) -> str:
        """ნორმალიზაცია URL-ს"""
        if url.endswith('/players/'):
            url = url[:-len('/players/')]
        elif url.endswith('/players'):
            url = url[:-len('/players')]
        
        if not url.endswith('/'):
            url += '/'
        
        return url
    
    async def fetch_page_direct(self, url: str) -> Optional[str]:
        """პირდაპირ ცდილობს გვერდის გადმოწერას"""
        try:
            print(f"[TeamScout] ვცდილობ პირდაპირ გადმოწერას: {url}")
            
            for attempt in range(2):
                async with httpx.AsyncClient(
                    follow_redirects=True,
                    timeout=30.0,
                    verify=False
                ) as client:
                    response = await client.get(url, headers=self.headers)
                    print(f"[TeamScout] Response status: {response.status_code}")
                    
                    if response.status_code == 200:
                        print(f"[TeamScout] HTML სიგრძე: {len(response.text)} bytes")
                        return response.text
                    elif response.status_code in [403, 429]:
                        print(f"[TeamScout] {response.status_code} - ბლოკი, ვცდილობ თავიდან...")
                        await asyncio.sleep(1)
                        continue
                    else:
                        response.raise_for_status()
            
            return None
        except Exception as e:
            print(f"[TeamScout] პირდაპირი გადმოწერის შეცდომა: {e}")
            return None
    
    async def fetch_with_google(self, url: str) -> Tuple[Optional[str], str]:
        """იყენებს Google Gemini-ს გვერდის წასაკითხად"""
        config = self.api_vault.providers["google"]
        
        if not config["api_key"] or not config["selected_model"]:
            return None, "Google API არ არის ინიციალიზებული"
        
        try:
            model = config["selected_model"]
            api_url = f"{config['base_url']}/models/{model}:generateContent?key={config['api_key']}"
            
            prompt = f"""წაიკითხე ეს URL და ამოიღე გუნდის ინფორმაცია JSON ფორმატში:
URL: {url}

დაბრუნდი მხოლოდ JSON ამ სტრუქტურით:
{{
    "name": "გუნდის სახელი",
    "short_code": "3-5 ასო",
    "city": "ქალაქი",
    "country": "ქვეყანა",
    "stadium": "სტადიონი",
    "coach": "მწვრთნელი",
    "logo_url": "ლოგოს URL"
}}

თუ ვერ იპოვი რაიმე ველი, დატოვე ცარიელი."""

            payload = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "tools": [{
                    "google_search": {}
                }]
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(api_url, json=payload, timeout=60.0)
                
                if response.status_code == 200:
                    data = response.json()
                    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    print(f"[TeamScout] Google-მა დააბრუნა: {text[:200]}...")
                    return text, "წარმატება"
                else:
                    return None, f"Google API შეცდომა: {response.status_code}"
        
        except Exception as e:
            return None, f"Google შეცდომა: {str(e)}"
    
    async def fetch_with_groq(self, url: str) -> Tuple[Optional[str], str]:
        """იყენებს Groq-ს გვერდის წასაკითხად"""
        config = self.api_vault.providers["groq"]
        
        if not config["api_key"] or not config["selected_model"]:
            return None, "Groq API არ არის ინიციალიზებული"
        
        try:
            model = config["selected_model"]
            api_url = f"{config['base_url']}/chat/completions"
            
            headers = {
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json"
            }
            
            prompt = f"""წაიკითხე ეს URL და ამოიღე გუნდის ინფორმაცია JSON ფორმატში:
URL: {url}

დაბრუნდი მხოლოდ JSON ამ სტრუქტურით:
{{
    "name": "გუნდის სახელი",
    "short_code": "3-5 ასო",
    "city": "ქალაქი",
    "country": "ქვეყანა",
    "stadium": "სტადიონი",
    "coach": "მწვრთნელი",
    "logo_url": "ლოგოს URL"
}}

თუ ვერ იპოვი რაიმე ველი, დატოვე ცარიელი."""

            payload = {
                "model": model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(api_url, headers=headers, json=payload, timeout=60.0)
                
                if response.status_code == 200:
                    data = response.json()
                    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    print(f"[TeamScout] Groq-მა დააბრუნა: {text[:200]}...")
                    return text, "წარმატება"
                else:
                    return None, f"Groq API შეცდომა: {response.status_code}"
        
        except Exception as e:
            return None, f"Groq შეცდომა: {str(e)}"
    
    def parse_ai_response(self, ai_text: str) -> Dict:
        """პარსავს AI-ის პასუხს JSON-ად"""
        team_data = {
            "name": "",
            "short_code": "",
            "city": "",
            "country": "",
            "stadium": "",
            "coach": "",
            "logo_url": ""
        }
        
        try:
            # ვეძებთ JSON-ს ტექსტში
            json_match = re.search(r'\{[^{}]*\}', ai_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)
                
                team_data["name"] = data.get("name", "")
                team_data["short_code"] = data.get("short_code", "")
                team_data["city"] = data.get("city", "")
                team_data["country"] = data.get("country", "")
                team_data["stadium"] = data.get("stadium", "")
                team_data["coach"] = data.get("coach", "")
                team_data["logo_url"] = data.get("logo_url", "")
                
                print(f"[TeamScout] AI პასუხი წარმატებით დაპარსულია: {team_data}")
        except Exception as e:
            print(f"[TeamScout] AI პასუხის პარსინგის შეცდომა: {e}")
        
        return team_data
    
    async def scout_team(self, url: str) -> Dict:
        """მთავარი ფუნქცია - აგროვებს გუნდის ინფორმაციას"""
        normalized_url = self.normalize_url(url)
        print(f"[TeamScout] ნორმალიზებული URL: {normalized_url}")
        
        # STEP 1: ვცდილობთ პირდაპირ გადმოწერას
        print("[TeamScout] STEP 1: პირდაპირი გადმოწერა...")
        html = await self.fetch_page_direct(normalized_url)
        
        if html:
            print("[TeamScout] პირდაპირი გადმოწერა წარმატებით დასრულდა!")
            # TODO: დავამატოთ HTML parsing ლოგიკა
            return {
                "success": True,
                "data": self.parse_team_info(html, normalized_url),
                "method": "direct",
                "raw_html_length": len(html)
            }
        
        # STEP 2: ვცდილობთ Google Gemini-ს
        print("[TeamScout] STEP 2: Google Gemini...")
        ai_text, ai_msg = await self.fetch_with_google(normalized_url)
        
        if ai_text:
            print(f"[TeamScout] Google წარმატება: {ai_msg}")
            team_data = self.parse_ai_response(ai_text)
            return {
                "success": True,
                "data": team_data,
                "method": "google",
                "model": self.api_vault.providers["google"]["selected_model"]
            }
        
        print(f"[TeamScout] Google წარუმატებელი: {ai_msg}")
        
        # STEP 3: ვცდილობთ Groq-ს
        print("[TeamScout] STEP 3: Groq...")
        ai_text, ai_msg = await self.fetch_with_groq(normalized_url)
        
        if ai_text:
            print(f"[TeamScout] Groq წარმატება: {ai_msg}")
            team_data = self.parse_ai_response(ai_text)
            return {
                "success": True,
                "data": team_data,
                "method": "groq",
                "model": self.api_vault.providers["groq"]["selected_model"]
            }
        
        print(f"[TeamScout] Groq წარუმატებელი: {ai_msg}")
        
        # ყველა მეთოდი წარუმატებელია
        return {
            "success": False,
            "error": "ვერცერთმა მეთოდმა ვერ მოახერხა მონაცემების მოპოვება",
            "data": None
        }
    
    def parse_team_info(self, html: str, url: str) -> Dict:
        """პარსავს გუნდის ინფორმაციას HTML-დან"""
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
        
        # გუნდის სახელი
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
                else:
                    team_data["name"] = text
                break
        
        # ლოგო
        og_image = soup.find('meta', property='og:image')
        if og_image:
            team_data["logo_url"] = og_image.get('content', '')
        
        # Short code
        if team_data["name"]:
            team_data["short_code"] = team_data["name"][:3].upper()
        
        return team_data

# ============================================
# TextParser Bot
# ============================================
class TextParser:
    def parse_team_from_text(self, text: str) -> Dict:
        """პარსავს გუნდის ინფორმაციას ჩაფეისთებული ტექსტიდან"""
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
        
        if lines:
            team_data["name"] = lines[0].strip()
        
        for i, line in enumerate(lines):
            if 'Город, страна' in line:
                if i + 1 < len(lines):
                    location_line = lines[i + 1].strip()
                    if ',' in location_line:
                        parts = location_line.split(',')
                        team_data["city"] = parts[0].strip()
                        team_data["country"] = parts[1].strip()
                break
        
        for i, line in enumerate(lines):
            if 'Стадион' in line:
                if i + 1 < len(lines):
                    team_data["stadium"] = lines[i + 1].strip()
                break
        
        for i, line in enumerate(lines):
            if 'Тренер' in line:
                if i + 1 < len(lines):
                    team_data["coach"] = lines[i + 1].strip()
                break
        
        if team_data["name"]:
            team_data["short_code"] = team_data["name"][:3].upper()
        
        return {
            "success": True,
            "data": team_data,
            "players_count": len(team_data["players"])
        }

# ============================================
# Controller Bot
# ============================================
class ControllerBot:
    def __init__(self):
        self.supabase_url = os.environ.get("SUPABASE_URL")
        self.supabase_key = os.environ.get("SUPABASE_KEY")
        
        if self.supabase_url and self.supabase_key:
            self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        else:
            self.supabase = None
    
    def validate_team(self, team_data: Dict) -> Tuple[bool, List[str]]:
        errors = []
        
        if not team_data.get("name"):
            errors.append("სახელი აუცილებელია")
        
        if not team_data.get("short_code"):
            errors.append("მოკლე კოდი აუცილებელია")
        
        return len(errors) == 0, errors

# ============================================
# API Vault Instance
# ============================================
api_vault = APIVault()

# ============================================
# API Endpoints
# ============================================
@app.get("/")
async def root():
    return {"message": "FootStats API is running!"}

@app.post("/api/vault/set-key")
async def set_api_key(request: dict):
    """აყენებს API გასაღებს"""
    provider = request.get("provider")
    api_key = request.get("api_key")
    
    if not provider or not api_key:
        return {"success": False, "error": "provider და api_key აუცილებელია"}
    
    api_vault.set_api_key(provider, api_key)
    return {"success": True, "message": f"{provider} გასაღები დაყენებულია"}

@app.post("/api/vault/initialize")
async def initialize_provider(request: dict):
    """ინიციალიზაცია პროვაიდერს"""
    provider = request.get("provider")
    
    if not provider:
        return {"success": False, "error": "provider აუცილებელია"}
    
    success, message = await api_vault.initialize_provider(provider)
    
    return {
        "success": success,
        "message": message,
        "models": api_vault.providers[provider]["available_models"],
        "selected_model": api_vault.providers[provider]["selected_model"]
    }

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

            <!-- API Vault Section -->
            <div class="bg-[#0E1424] border-2 border-yellow-600 rounded-xl p-6 mb-8">
                <h3 class="text-lg font-bold text-yellow-400 mb-4">🔐 API გასაღებების საცავი</h3>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <!-- Google Gemini -->
                    <div class="bg-[#070A13] border border-gray-700 rounded-lg p-4">
                        <div class="flex items-center gap-2 mb-2">
                            <span class="text-2xl">🔵</span>
                            <h4 class="font-bold text-white">Google Gemini</h4>
                            <span id="google-status" class="ml-auto px-2 py-1 bg-gray-700 rounded text-xs">⏸️ არ არის დაყენებული</span>
                        </div>
                        <input 
                            id="google-key" 
                            type="password" 
                            placeholder="Google API გასაღები"
                            class="w-full bg-[#0B0F19] border border-gray-700 rounded p-2 text-sm text-emerald-400 mb-2"
                        >
                        <button 
                            onclick="setKey('google')" 
                            class="w-full bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded text-sm font-semibold"
                        >
                            💾 გასაღების შენახვა
                        </button>
                        <button 
                            onclick="initializeProvider('google')" 
                            class="w-full mt-2 bg-blue-800 hover:bg-blue-700 text-white px-4 py-2 rounded text-sm font-semibold"
                        >
                            🚀 ინიციალიზაცია და მოდელის არჩევა
                        </button>
                        <div id="google-models" class="mt-2 text-xs text-gray-400"></div>
                    </div>

                    <!-- Groq -->
                    <div class="bg-[#070A13] border border-gray-700 rounded-lg p-4">
                        <div class="flex items-center gap-2 mb-2">
                            <span class="text-2xl">🟠</span>
                            <h4 class="font-bold text-white">Groq</h4>
                            <span id="groq-status" class="ml-auto px-2 py-1 bg-gray-700 rounded text-xs">⏸️ არ არის დაყენებული</span>
                        </div>
                        <input 
                            id="groq-key" 
                            type="password" 
                            placeholder="Groq API გასაღები"
                            class="w-full bg-[#0B0F19] border border-gray-700 rounded p-2 text-sm text-emerald-400 mb-2"
                        >
                        <button 
                            onclick="setKey('groq')" 
                            class="w-full bg-orange-600 hover:bg-orange-500 text-white px-4 py-2 rounded text-sm font-semibold"
                        >
                            💾 გასაღების შენახვა
                        </button>
                        <button 
                            onclick="initializeProvider('groq')" 
                            class="w-full mt-2 bg-orange-800 hover:bg-orange-700 text-white px-4 py-2 rounded text-sm font-semibold"
                        >
                            🚀 ინიციალიზაცია და მოდელის არჩევა
                        </button>
                        <div id="groq-models" class="mt-2 text-xs text-gray-400"></div>
                    </div>
                </div>
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
                    <p class="text-sm text-gray-400 mb-3">აგროვებს გუნდის ინფორმაციას</p>
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
                    <p class="text-sm text-gray-400 mb-3">ამოწმებს მონაცემებს</p>
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
                        placeholder="ჩაწერე გუნდის URL" 
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
                                <div class="text-xs text-gray-400">TeamScout აგროვებს ინფორმაციას</div>
                            </div>
                            <div id="step-1-status" class="text-gray-500">⏸️</div>
                        </div>
                    </div>
                    <div id="step-2" class="step-pending bg-[#070A13] rounded-lg p-4 transition-all">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 bg-gray-700 rounded-full flex items-center justify-center text-sm font-bold">2</div>
                            <div class="flex-1">
                                <div class="font-semibold text-white">ვალიდაცია</div>
                                <div class="text-xs text-gray-400">Controller ამოწმებს მონაცემებს</div>
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
                <div class="flex gap-3 mt-6">
                    <button 
                        onclick="confirmData()" 
                        class="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white px-6 py-3 rounded-lg font-semibold transition-all"
                    >
                        ✅ დადასტურება
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
                <div id="terminal" class="bg-[#070A13] border border-gray-850 rounded-lg p-4 h-96 overflow-y-auto font-mono text-xs space-y-2">
                    <div class="text-gray-500">// სისტემა მზად არის...</div>
                </div>
            </div>
        </div>

        <script>
            let currentTeamData = null;
            let currentMode = 'url';

            function switchTab(mode) {
                currentMode = mode;
                document.getElementById('tab-url').className = mode === 'url' ? 'tab-active px-6 py-3 rounded-lg font-semibold transition-all' : 'tab-inactive px-6 py-3 rounded-lg font-semibold transition-all';
                document.getElementById('tab-paste').className = mode === 'paste' ? 'tab-active px-6 py-3 rounded-lg font-semibold transition-all' : 'tab-inactive px-6 py-3 rounded-lg font-semibold transition-all';
                document.getElementById('section-url').classList.toggle('hidden', mode !== 'url');
                document.getElementById('section-paste').classList.toggle('hidden', mode !== 'paste');
            }

            async function setKey(provider) {
                const keyInput = document.getElementById(`${provider}-key`);
                const apiKey = keyInput.value;
                
                if (!apiKey) {
                    alert('გთხოვთ ჩაწეროთ API გასაღები');
                    return;
                }

                addLog('APIVault', `💾 ${provider} გასაღების შენახვა...`, 'info');

                try {
                    const response = await fetch('/api/vault/set-key', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ provider, api_key: apiKey })
                    });

                    const data = await response.json();
                    
                    if (data.success) {
                        addLog('APIVault', `✅ ${provider} გასაღები შენახულია`, 'success');
                        document.getElementById(`${provider}-status`).innerHTML = '✅ გასაღები შენახულია';
                        document.getElementById(`${provider}-status`).className = 'ml-auto px-2 py-1 bg-emerald-600 rounded text-xs';
                    } else {
                        addLog('APIVault', `❌ ${data.error}`, 'error');
                    }
                } catch (error) {
                    addLog('APIVault', `❌ შეცდომა: ${error.message}`, 'error');
                }
            }

            async function initializeProvider(provider) {
                addLog('APIVault', `🚀 ${provider} ინიციალიზაცია იწყება...`, 'info');
                addLog('APIVault', `🔍 მოდელების სია გამოითხოვა...`, 'info');

                try {
                    const response = await fetch('/api/vault/initialize', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ provider })
                    });

                    const data = await response.json();
                    
                    if (data.success) {
                        addLog('APIVault', `✅ ${data.message}`, 'success');
                        addLog('APIVault', `📋 ხელმისაწვდომი მოდელები: ${data.models.join(', ')}`, 'info');
                        addLog('APIVault', `🎯 არჩეული მოდელი: ${data.selected_model}`, 'success');
                        
                        document.getElementById(`${provider}-status`).innerHTML = '✅ მზად';
                        document.getElementById(`${provider}-status`).className = 'ml-auto px-2 py-1 bg-emerald-600 rounded text-xs';
                        document.getElementById(`${provider}-models`).innerHTML = `
                            <div class="text-emerald-400">✓ ${data.models.length} მოდელი</div>
                            <div class="text-yellow-400">🎯 ${data.selected_model}</div>
                        `;
                    } else {
                        addLog('APIVault', `❌ ${data.message}`, 'error');
                        document.getElementById(`${provider}-status`).innerHTML = '❌ შეცდომა';
                        document.getElementById(`${provider}-status`).className = 'ml-auto px-2 py-1 bg-red-600 rounded text-xs';
                    }
                } catch (error) {
                    addLog('APIVault', `❌ შეცდომა: ${error.message}`, 'error');
                }
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
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: text })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        currentTeamData = data.data;
                        displayTeamData(data.data);
                        addLog('TextParser', `✅ წარმატებით დამუშავდა`, 'success');
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
                    { label: '🏟️ სტადიონი', value: teamData.stadium || '', key: 'stadium' },
                    { label: '🏙️ ქალაქი', value: teamData.city || '', key: 'city' },
                    { label: '🌍 ქვეყანა', value: teamData.country || '', key: 'country' },
                    { label: '👔 მწვრთნელი', value: teamData.coach || '', key: 'coach' }
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
                addLog('system', '✅ მონაცემები დადასტურდა', 'success');
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
            }

            function handleAgentMessage(data) {
                const { agent, message, step, status } = data;

                const logType = message.includes('❌') ? 'error' : 
                               message.includes('✅') ? 'success' : 
                               message.includes('⚠️') ? 'warning' : 'info';
                addLog(agent, message, logType);

                if (agent === 'TeamScout') {
                    document.getElementById('scout-card').classList.add('agent-active');
                } else if (agent === 'Controller') {
                    document.getElementById('controller-card').classList.add('agent-active');
                }

                if (step) {
                    updateStep(step, status);
                }

                if (data.done) {
                    document.getElementById('scout-card').classList.remove('agent-active');
                    document.getElementById('controller-card').classList.remove('agent-active');
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
                    'APIVault': 'text-yellow-400',
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
    text = request.get("text", "")
    
    if not text.strip():
        return {"success": False, "error": "ტექსტი ცარიელია"}
    
    parser = TextParser()
    result = parser.parse_team_from_text(text)
    
    return result

@app.get("/api/agent/stream-scout")
async def stream_scout(url: str):
    scout = TeamScout(api_vault)
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
            "message": f"📡 URL: {url}",
            "step": 1,
            "status": "active"
        }) + "\n\n"
        
        # STEP 1: პირდაპირი გადმოწერა
        yield "data: " + json.dumps({
            "agent": "TeamScout", 
            "message": "🌐 მცდელობა 1: პირდაპირი გადმოწერა...",
            "step": 1,
            "status": "active"
        }) + "\n\n"
        await asyncio.sleep(0.5)
        
        html = await scout.fetch_page_direct(scout.normalize_url(url))
        
        if html:
            yield "data: " + json.dumps({
                "agent": "TeamScout", 
                "message": f"✅ პირდაპირი გადმოწერა წარმატებით! ({len(html)} bytes)",
                "step": 1,
                "status": "completed"
            }) + "\n\n"
            
            team_data = scout.parse_team_info(html, url)
            
            yield "data: " + json.dumps({
                "agent": "TeamScout", 
                "message": f"🏆 გუნდი: {team_data['name'] or 'არ მოიძებნა'}",
                "step": 1,
                "status": "completed"
            }) + "\n\n"
        else:
            yield "data: " + json.dumps({
                "agent": "TeamScout", 
                "message": "❌ პირდაპირი გადმოწერა წარუმატებელია",
                "step": 1,
                "status": "error"
            }) + "\n\n"
            
            # STEP 2: Google Gemini
            yield "data: " + json.dumps({
                "agent": "TeamScout", 
                "message": "🔵 მცდელობა 2: Google Gemini...",
                "step": 1,
                "status": "active"
            }) + "\n\n"
            await asyncio.sleep(0.5)
            
            ai_text, ai_msg = await scout.fetch_with_google(url)
            
            if ai_text:
                yield "data: " + json.dumps({
                    "agent": "TeamScout", 
                    "message": f"✅ Google წარმატება! მოდელი: {api_vault.providers['google']['selected_model']}",
                    "step": 1,
                    "status": "completed"
                }) + "\n\n"
                
                team_data = scout.parse_ai_response(ai_text)
            else:
                yield "data: " + json.dumps({
                    "agent": "TeamScout", 
                    "message": f"❌ Google წარუმატებელი: {ai_msg}",
                    "step": 1,
                    "status": "error"
                }) + "\n\n"
                
                # STEP 3: Groq
                yield "data: " + json.dumps({
                    "agent": "TeamScout", 
                    "message": "🟠 მცდელობა 3: Groq...",
                    "step": 1,
                    "status": "active"
                }) + "\n\n"
                await asyncio.sleep(0.5)
                
                ai_text, ai_msg = await scout.fetch_with_groq(url)
                
                if ai_text:
                    yield "data: " + json.dumps({
                        "agent": "TeamScout", 
                        "message": f"✅ Groq წარმატება! მოდელი: {api_vault.providers['groq']['selected_model']}",
                        "step": 1,
                        "status": "completed"
                    }) + "\n\n"
                    
                    team_data = scout.parse_ai_response(ai_text)
                else:
                    yield "data: " + json.dumps({
                        "agent": "TeamScout", 
                        "message": f"❌ ყველა მეთოდი წარუმატებელია",
                        "step": 1,
                        "status": "error",
                        "done": True
                    }) + "\n\n"
                    return
        
        # STEP 2: Controller
        yield "data: " + json.dumps({
            "agent": "Controller", 
            "message": "🔍 ვიწყებ ვალიდაციას...",
            "step": 2,
            "status": "active"
        }) + "\n\n"
        await asyncio.sleep(1)
        
        is_valid, errors = controller.validate_team(team_data)
        
        if not is_valid:
            yield "data: " + json.dumps({
                "agent": "Controller", 
                "message": f"❌ ვალიდაცია ვერ გაიარა: {', '.join(errors)}",
                "step": 2,
                "status": "error",
                "done": True
            }) + "\n\n"
            return
        
        yield "data: " + json.dumps({
            "agent": "Controller", 
            "message": "✅ ვალიდაცია წარმატებით გაიარა",
            "step": 2,
            "status": "completed"
        }) + "\n\n"
        
        # STEP 3: ვიზუალიზაცია
        yield "data: " + json.dumps({
            "agent": "Controller", 
            "message": "📊 მონაცემები მზად არის",
            "step": 3,
            "status": "completed",
            "done": True,
            "team_data": team_data
        }) + "\n\n"
    
    return StreamingResponse(agent_runner(), media_type="text/event-stream")