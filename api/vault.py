"""
API გასაღებების მენეჯერი - DEBUG ვერსია
"""
import os
from typing import Dict, Optional
from loguru import logger

# Supabase კლიენტი
_supabase = None

def get_supabase():
    global _supabase
    if _supabase is None:
        try:
            from supabase import create_client
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_KEY")
            
            logger.info(f"🔍 SUPABASE_URL: {url[:20] if url else 'NOT SET'}...")
            logger.info(f"🔍 SUPABASE_KEY: {'SET' if key else 'NOT SET'}")
            
            if url and key:
                _supabase = create_client(url, key)
                logger.info("✅ Supabase კლიენტი ინიციალიზდა")
            else:
                logger.error("❌ SUPABASE_URL ან SUPABASE_KEY არ არის დაყენებული!")
        except Exception as e:
            logger.error(f"❌ Supabase ინიციალიზაციის შეცდომა: {e}")
    return _supabase

# Cache
_cache: Dict[str, Dict] = {}
_loaded = False

def _load_from_db():
    """ჩატვირთავს გასაღებებს Supabase-დან"""
    global _loaded
    
    logger.info("🔄 ვცდილობ გასაღებების ჩატვირთვას DB-დან...")
    
    supabase = get_supabase()
    if not supabase:
        logger.error("❌ Supabase არ არის ხელმისაწვდომი")
        _loaded = True  # ვაყენებთ True-ს რომ ხელახლა არ სცადოს
        return False
    
    try:
        logger.info("📡 ვაგზავნი SELECT request-ს api_keys ცხრილზე...")
        response = supabase.table("api_keys").select("*").execute()
        
        logger.info(f"📥 მიღებულია {len(response.data) if response.data else 0} ჩანაწერი")
        
        if not response.data:
            logger.warning("⚠️ api_keys ცხრილი ცარიელია!")
            _loaded = True
            return False
        
        for row in response.data:
            provider = row["provider"]
            _cache[provider] = {
                "api_key": row["api_key"],
                "selected_model": row.get("selected_model", ""),
                "name": "Google Gemini" if provider == "google" else "Groq"
            }
            logger.info(f"✅ ჩაიტვირთა {provider}: {row['api_key'][:10]}...")
        
        _loaded = True
        logger.info(f"✅ წარმატებით ჩაიტვირთა {len(response.data)} გასაღები")
        return True
        
    except Exception as e:
        logger.error(f"❌ DB ჩატვირთვის შეცდომა: {type(e).__name__} - {str(e)}")
        _loaded = True
        return False

def ensure_loaded():
    """გარანტირებულად ტვირთავს გასაღებებს"""
    global _loaded
    if not _loaded:
        logger.info("🔄 პირველი ჩატვირთვა DB-დან...")
        _load_from_db()
    return _loaded

def get_key(provider: str) -> Optional[str]:
    """იღებს API გასაღებს"""
    ensure_loaded()
    
    if provider in _cache:
        return _cache[provider]["api_key"]
    
    logger.warning(f"⚠️ {provider} გასაღები ვერ მოიძებნა cache-ში")
    return None

def get_model(provider: str) -> Optional[str]:
    """იღებს არჩეულ მოდელს"""
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
    """ინახავს გასაღებს Supabase-ში"""
    supabase = get_supabase()
    if not supabase:
        logger.error("❌ Supabase არ არის ხელმისაწვდომი")
        return False
    
    try:
        existing = supabase.table("api_keys").select("id").eq("provider", provider).execute()
        
        data = {
            "provider": provider,
            "api_key": api_key,
            "selected_model": selected_model
        }
        
        if existing.data:
            supabase.table("api_keys").update(data).eq("provider", provider).execute()
            logger.info(f"✅ განახლდა {provider} გასაღები DB-ში")
        else:
            supabase.table("api_keys").insert(data).execute()
            logger.info(f"✅ შეიქმნა {provider} გასაღები DB-ში")
        
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