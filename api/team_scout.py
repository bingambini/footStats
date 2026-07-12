import httpx
from bs4 import BeautifulSoup
from typing import Dict, Optional
import re

class TeamScout:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8"
        }
    
    async def fetch_page(self, url: str) -> Optional[str]:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers, timeout=30.0, follow_redirects=True)
                response.raise_for_status()
                return response.text
        except Exception as e:
            return None
    
    def parse_team_info(self, html: str, url: str) -> Dict:
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
        
        title = soup.find('h1')
        if title:
            team_data["name"] = title.get_text(strip=True)
        
        if team_data["name"]:
            words = team_data["name"].split()
            if words:
                team_data["short_code"] = words[0][:3].upper()
        
        return team_data
    
    async def scout_team(self, url: str) -> Dict:
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