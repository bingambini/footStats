import httpx
from bs4 import BeautifulSoup
from typing import Dict, Optional
import re

class TeamScout:
    """მზვერავი აგენტი - აგროვებს გუნდის ზოგად ინფორმაციას championat.com-დან"""
    
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8"
        }
    
    async def fetch_page(self, url: str) -> Optional[str]:
        """გადმოწერს HTML გვერდს"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers, timeout=30.0, follow_redirects=True)
                response.raise_for_status()
                return response.text
        except Exception as e:
            print(f"შეცდომა გვერდის გადმოწერისას: {e}")
            return None
    
    def parse_team_info(self, html: str, url: str) -> Dict:
        """პარსავს გუნდის ინფორმაციას championat.com-დან"""
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
        
        # გუნდის სახელი - ჩვეულებრივ h1 ან title-ში
        title = soup.find('h1')
        if title:
            team_data["name"] = title.get_text(strip=True)
        
        # ლოგო - ვეძებთ img თაგს რომელიც გუნდის ლოგოს შეიცავს
        logo_candidates = soup.find_all('img')
        for img in logo_candidates:
            src = img.get('src', '')
            alt = img.get('alt', '').lower()
            
            # ვეძებთ ლოგოს URL-ში ან alt text-ში
            if any(keyword in alt for keyword in ['лого', 'logo', 'эмблема']):
                if src.startswith('http'):
                    team_data["logo_url"] = src
                    break
            elif 'logo' in src.lower() or 'crest' in src.lower() or 'badge' in src.lower():
                if src.startswith('http'):
                    team_data["logo_url"] = src
                    break
        
        # ვეძებთ გუნდის დეტალებს (სტადიონი, ქალაქი, ქვეყანა, მწვრთნელი)
        info_blocks = soup.find_all('div', class_=re.compile(r'info|detail|team', re.I))
        
        for block in info_blocks:
            text = block.get_text()
            
            # სტადიონი
            if 'стадион' in text.lower() or 'stadium' in text.lower():
                match = re.search(r'[:\-]\s*([A-Za-zА-Яа-яЁё\s]+)', text)
                if match:
                    team_data["stadium"] = match.group(1).strip()
            
            # ქალაქი
            if 'город' in text.lower() or 'city' in text.lower():
                match = re.search(r'[:\-]\s*([A-Za-zА-Яа-яЁё\s]+)', text)
                if match:
                    team_data["city"] = match.group(1).strip()
            
            # ქვეყანა
            if 'страна' in text.lower() or 'country' in text.lower():
                match = re.search(r'[:\-]\s*([A-Za-zА-Яа-яЁё\s]+)', text)
                if match:
                    team_data["country"] = match.group(1).strip()
            
            # მწვრთნელი
            if 'тренер' in text.lower() or 'coach' in text.lower():
                match = re.search(r'[:\-]\s*([A-Za-zА-Яа-яЁё\s]+)', text)
                if match:
                    team_data["coach"] = match.group(1).strip()
        
        # Short code - ვცადოთ სახელიდან ამოღება (პირველი 3 ასო)
        if team_data["name"]:
            words = team_data["name"].split()
            if words:
                # ვიღებთ პირველი სიტყვის პირველ 3 ასოს
                team_data["short_code"] = words[0][:3].upper()
        
        return team_data
    
    async def scout_team(self, url: str) -> Dict:
        """მთავარი ფუნქცია - აგროვებს გუნდის ინფორმაციას"""
        html = await self.fetch_page(url)
        
        if not html:
            return {
                "success": False,
                "error": "ვერ მოხერხდა გვერდის გადმოწერა",
                "data": None
            }
        
        team_info = self.parse_team_info(html, url)
        
        return {
            "success": True,
            "data": team_info
        }