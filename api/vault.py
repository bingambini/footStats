"""
API გასაღებების მენეჯერი
გარანტირებული ჩატვირთვა Supabase-დან ყოველი მოთხოვნისას
"""
import os
from typing import Dict, Optional
from loguru import logger

# Supabase კლიენტი (ერთხელ ინიციალიზდება)
_supabase = None

def get_supabase():
    global _supabase
    if _supabase is None:
        try:
            from supabase import create_client
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_KEY")
            if url and key:
                _supabase = create_client(url, key)
                logger.info("✅ Supabase კლიენტი ინიციალიზდა")
            else:
                logger.error("❌ SUPABASE_URL ან SUPABASE_KEY არ არის დაყენებული")
        except Exception as e:
            logger.error(f"❌ Supabase ინიციალიზაციის შეცდომა: {e}")
    return _supabase

# Cache - ინახავს გასაღებებს memory-ში
_cache: Dict[str, Dict] = {}
_loaded = False

def _load_from_db():
    """ჩატვირთავს ყველა გასაღებს Supabase-დან"""
    global _loaded
    
    supabase = get_supabase()
    if not supabase:
        logger.warning("⚠️ Supabase არ არის ხელმისაწვდომი")
        return False
    
    try:
        response = supabase.table("api_keys").select("*").execute()
        
        if not response.data:
            logger.warning("⚠️ api_keys ცხრილი ცარიელია")
            _loaded = True
            return False
        
        for row in response.data:
            provider = row["provider"]
            _cache[provider] = {
                "api_key": row["api_key"],
                "selected_model": row.get("selected_model", ""),
                "name": "Google Gemini" if provider == "google" else "Groq"
            }
            logger.info(f"✅ ჩაიტვირთა {provider} გასაღები")
        
        _loaded = True
        logger.info(f"✅ წარმატებით ჩაიტვირთა {len(response.data)} გასაღები")
        return True
        
    except Exception as e:
        logger.error(f"❌ DB ჩატვირთვის შეცდომა: {e}")
        return False

def ensure_loaded():
    """გარანტირებულად ტვირთავს გასაღებებს (თუ ჯერ არ ჩატვირთულა)"""
    global _loaded
    if not _loaded:
        logger.info("🔄 პირველი ჩატვირთვა DB-დან...")
        _load_from_db()
    return _loaded

def get_key(provider: str) -> Optional[str]:
    """იღებს API გასაღებს provider-ის მიხედვით"""
    ensure_loaded()
    
    if provider in _cache:
        return _cache[provider]["api_key"]
    
    logger.warning(f"⚠️ {provider} გასაღები ვერ მოიძებნა")
    return None

def get_model(provider: str) -> Optional[str]:
    """იღებს არჩეულ მოდელს provider-ის მიხედვით"""
    ensure_loaded()
    
    if provider in _cache:
        return _cache[provider]["selected_model"]
    
    return None

def get_provider_info(provider: str) -> Dict:
    """იღებს სრულ ინფორმაციას provider-ზე"""
    ensure_loaded()
    
    if provider in _cache:
        return {
            "has_key": True,
            "selected_model": _cache[provider]["selected_model"],
            "name": _cache[provider]["name"]
        }
    
    return {"has_key": False, "selected_model": None, "name": provider}

def save_key(provider: str, api_key: str, selected_model: str = "") -> bool:
    """ინახავს გასაღებს Supabase-ში და ახდენს cache-ის განახლებას"""
    supabase = get_supabase()
    if not supabase:
        logger.error("❌ Supabase არ არის ხელმისაწვდომი")
        return False
    
    try:
        # ვამოწმებთ არსებობს თუ არა
        existing = supabase.table("api_keys").select("id").eq("provider", provider).execute()
        
        data = {
            "provider": provider,
            "api_key": api_key,
            "selected_model": selected_model
        }
        
        if existing.data:
            # განვაახლებთ
            supabase.table("api_keys").update(data).eq("provider", provider).execute()
            logger.info(f"✅ განახლდა {provider} გასაღები DB-ში")
        else:
            # ვქმნით ახალს
            supabase.table("api_keys").insert(data).execute()
            logger.info(f"✅ შეიქმნა {provider} გასაღები DB-ში")
        
        # ვახდენთ cache-ის განახლებას
        _cache[provider] = {
            "api_key": api_key,
            "selected_model": selected_model,
            "name": "Google Gemini" if provider == "google" else "Groq"
        }
        
        return True
        
    except Exception as e:
        logger.error(f"❌ გასაღების შენახვის შეცდომა: {e}")
        return False

def get_all_status() -> Dict:
    """იღებს ყველა provider-ის სტატუსს"""
    ensure_loaded()
    
    result = {}
    for provider in ["google", "groq"]:
        result[provider] = get_provider_info(provider)
    
    return result