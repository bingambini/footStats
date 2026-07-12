import re
from typing import Dict, List, Tuple
from supabase import create_client, Client
import os

class ControllerBot:
    """მაკონტროლებელი აგენტი - ამოწმებს მონაცემების ვალიდურობას"""
    
    def __init__(self):
        self.supabase_url = os.environ.get("SUPABASE_URL")
        self.supabase_key = os.environ.get("SUPABASE_KEY")
        
        if self.supabase_url and self.supabase_key:
            self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        else:
            self.supabase = None
        
        # Validation rules
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
            },
            "logo_url": {
                "required": False,
                "pattern": r"^https?://.+\.(png|jpg|jpeg|svg|webp)$",
                "error_message": "logo_url უნდა იყოს ვალიდური URL"
            },
            "city": {
                "required": False,
                "min_length": 2
            },
            "country": {
                "required": False,
                "min_length": 2
            }
        }
    
    def validate_field(self, field: str, value: any) -> Tuple[bool, str]:
        """ამოწმებს ერთ ველს"""
        rules = self.VALIDATION_RULES.get(field, {})
        
        # Required check
        if rules.get("required") and (value is None or value == ""):
            return False, f"{field} აუცილებელია"
        
        # ცარიელი ველი თუ არ არის required - ვამოწმებთ დანარჩენს მხოლოდ თუ არის მნიშვნელობა
        if not value:
            return True, ""
        
        # Length check
        if "min_length" in rules:
            if len(str(value)) < rules["min_length"]:
                return False, f"{field} ძალიან მოკლეა (მინიმუმ {rules['min_length']} სიმბოლო)"
        
        if "max_length" in rules:
            if len(str(value)) > rules["max_length"]:
                return False, f"{field} ძალიან გრძელია (მაქსიმუმ {rules['max_length']} სიმბოლო)"
        
        # Pattern check
        if "pattern" in rules:
            if not re.match(rules["pattern"], str(value)):
                return False, rules.get("error_message", f"{field} არასწორი ფორმატია")
        
        return True, ""
    
    def validate_team(self, team_data: Dict) -> Tuple[bool, List[str]]:
        """ამოწმებს გუნდის მონაცემებს"""
        errors = []
        
        for field, value in team_data.items():
            is_valid, error_msg = self.validate_field(field, value)
            if not is_valid:
                errors.append(error_msg)
        
        return len(errors) == 0, errors
    
    async def check_duplicate(self, team_data: Dict) -> Tuple[bool, str]:
        """ამოწმებს თუ გუნდი უკვე არის ბაზაში"""
        if not self.supabase:
            return False, "Supabase არ არის დაკონფიგურირებული"
        
        try:
            # ვეძებთ გუნდს სახელით
            response = self.supabase.table("teams").select("id").eq("name", team_data["name"]).execute()
            
            if response.data and len(response.data) > 0:
                return True, f"გუნდი '{team_data['name']}' უკვე არსებობს ბაზაში"
            
            return False, ""
        except Exception as e:
            return False, f"შეცდომა duplicate check-ისას: {str(e)}"
    
    async def save_team(self, team_data: Dict) -> Tuple[bool, str]:
        """ინახავს გუნდს Supabase-ში"""
        if not self.supabase:
            return False, "Supabase არ არის დაკონფიგურირებული"
        
        try:
            # ვამზადებთ მონაცემებს ჩასაწერად
            team_record = {
                "name": team_data["name"],
                "short_code": team_data["short_code"],
                "city": team_data["city"] or None,
                "country": team_data["country"] or None,
                "stadium": team_data["stadium"] or None,
                "coach": team_data["coach"] or None,
                "logo_url": team_data["logo_url"] or None
            }
            
            response = self.supabase.table("teams").insert(team_record).execute()
            
            if response.data:
                return True, f"გუნდი '{team_data['name']}' წარმატებით ჩაიწერა ბაზაში (ID: {response.data[0]['id']})"
            else:
                return False, "ვერ მოხერხდა ბაზაში ჩაწერა"
                
        except Exception as e:
            return False, f"შეცდომა ჩაწერისას: {str(e)}"
    
    async def process_team(self, team_data: Dict) -> Tuple[bool, List[str], str]:
        """მთავარი ფუნქცია - ამოწმებს და ინახავს გუნდს"""
        # Step 1: Validation
        is_valid, validation_errors = self.validate_team(team_data)
        
        if not is_valid:
            return False, validation_errors, "ვალიდაცია ვერ გაიარა"
        
        # Step 2: Duplicate check
        is_duplicate, duplicate_msg = await self.check_duplicate(team_data)
        
        if is_duplicate:
            return False, [duplicate_msg], "გუნდი უკვე არსებობს"
        
        # Step 3: Save to database
        save_success, save_msg = await self.save_team(team_data)
        
        if not save_success:
            return False, [save_msg], "შეცდომა ჩაწერისას"
        
        return True, [], save_msg