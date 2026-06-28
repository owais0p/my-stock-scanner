from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import yfinance as yf
import pandas as pd
import requests
import io
import json
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Real-Time Telegram Webhook Configuration ---
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"

class ReportPayload(BaseModel):
    category: str
    description: str
    device_info: str = "Unknown"

class FeedbackPayload(BaseModel):
    rating: int
    improvement: str
    device_info: str = "Unknown"

def append_to_submissions_log(entry: dict):
    log_file = "submissions_log.json"
    try:
        # Open/Create submissions_log.json in append mode (a+)
        with open(log_file, "a+") as f:
            # Safely write the JSON dictionary sequence
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        print(f"Error logging to submissions_log.json: {e}")

def send_telegram_alert(message: str):
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN" or TELEGRAM_CHAT_ID == "YOUR_CHAT_ID":
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        # Lightweight synchronous requests POST call with 5 seconds timeout
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Telegram Webhook Alert failed: {e}")

@app.post("/api/report")
async def report_problem(payload: ReportPayload):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {
        "timestamp": timestamp,
        "type": "report",
        "category": payload.category,
        "description": payload.description,
        "device_info": payload.device_info
    }
    
    # 1. Console print
    print(f"[{timestamp}] [USER REPORT] Category: {payload.category} | Device: {payload.device_info} | Description: {payload.description}")
    
    # 2. Append directly to local submissions_log.json
    append_to_submissions_log(log_entry)
    
    # 3. Dispatch real-time Telegram alert
    alert_text = (
        f"*🚨 AAPNATRADER - NEW PROBLEM REPORT*\n"
        f"*Category:* {payload.category}\n"
        f"*Time:* {timestamp}\n"
        f"*Device:* `{payload.device_info}`\n\n"
        f"*Description:*\n{payload.description}"
    )
    send_telegram_alert(alert_text)
    
    return {"status": "success", "message": "Report Submitted! Thanks."}

@app.post("/api/feedback")
async def give_feedback(payload: FeedbackPayload):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {
        "timestamp": timestamp,
        "type": "feedback",
        "rating": payload.rating,
        "improvement": payload.improvement,
        "device_info": payload.device_info
    }
    
    # 1. Console print
    print(f"[{timestamp}] [USER FEEDBACK] Rating: {payload.rating}/5 | Device: {payload.device_info} | Improvement: {payload.improvement}")
    
    # 2. Append directly to local submissions_log.json
    append_to_submissions_log(log_entry)
    
    # 3. Dispatch real-time Telegram alert
    alert_text = (
        f"*💬 AAPNATRADER - NEW FEEDBACK RECEIVED*\n"
        f"*Rating:* {payload.rating}/5\n"
        f"*Time:* {timestamp}\n"
        f"*Device:* `{payload.device_info}`\n\n"
        f"*Improvement:* {payload.improvement}"
    )
    send_telegram_alert(alert_text)
    
    return {"status": "success", "message": "Feedback Submitted! Thanks."}


TICKER_SECTOR_MAP = {
    # NIFTY AUTO (OEMs & Auto Ancillaries)
    "MARUTI": "NIFTY_AUTO",
    "TATAMOTORS": "NIFTY_AUTO",
    "M&M": "NIFTY_AUTO",
    "BAJAJ-AUTO": "NIFTY_AUTO",
    "HEROMOTOCO": "NIFTY_AUTO",
    "TIINDIA": "NIFTY_AUTO",
    "EICHERMOT": "NIFTY_AUTO",
    "TVSMOTOR": "NIFTY_AUTO",
    "ASHOKLEY": "NIFTY_AUTO",
    "BALKRISIND": "NIFTY_AUTO",
    "MRF": "NIFTY_AUTO",
    "BHARATFORG": "NIFTY_AUTO",
    "BOSCHLTD": "NIFTY_AUTO",
    "SONACOMS": "NIFTY_AUTO",
    "TUBEINVEST": "NIFTY_AUTO",
    "EXIDEIND": "NIFTY_AUTO",
    "AMARAJABAT": "NIFTY_AUTO",
    "ARE&M": "NIFTY_AUTO",
    "APOLLOTYRE": "NIFTY_AUTO",
    "CEATLTD": "NIFTY_AUTO",
    "JKTYRE": "NIFTY_AUTO",
    "CIEINDIA": "NIFTY_AUTO",
    "ENDURANCE": "NIFTY_AUTO",
    "UNOMINDA": "NIFTY_AUTO",
    "SANSERA": "NIFTY_AUTO",
    "ROLEXRINGS": "NIFTY_AUTO",
    "GRAVITA": "NIFTY_AUTO",
    "MOTHERSON": "NIFTY_AUTO",
    "MSUMI": "NIFTY_AUTO",
    "JAMNAAUTO": "NIFTY_AUTO",
    "LUMAXIND": "NIFTY_AUTO",
    "PRICOL": "NIFTY_AUTO",
    "TALBROSAUTO": "NIFTY_AUTO",
    "RAMKRISHN": "NIFTY_AUTO",
    "MINDACORP": "NIFTY_AUTO",
    "SUPRAJIT": "NIFTY_AUTO",
    "GABRIEL": "NIFTY_AUTO",
    "FIEMIND": "NIFTY_AUTO",
    "SANDHAR": "NIFTY_AUTO",
    "SUBROS": "NIFTY_AUTO",
    "AUTOAXLES": "NIFTY_AUTO",
    
    # NIFTY ENERGY (Utilities, Power generation, Oil & Gas, Coal, Renewables)
    "RELIANCE": "NIFTY_ENERGY",
    "ONGC": "NIFTY_ENERGY",
    "POWERGRID": "NIFTY_ENERGY",
    "NTPC": "NIFTY_ENERGY",
    "IOC": "NIFTY_ENERGY",
    "BPCL": "NIFTY_ENERGY",
    "COALINDIA": "NIFTY_ENERGY",
    "GAIL": "NIFTY_ENERGY",
    "ADANIGREEN": "NIFTY_ENERGY",
    "ADANIENSOL": "NIFTY_ENERGY",
    "ADANIPOWER": "NIFTY_ENERGY",
    "TATAPOWER": "NIFTY_ENERGY",
    "JSWENERGY": "NIFTY_ENERGY",
    "NHPC": "NIFTY_ENERGY",
    "SJVN": "NIFTY_ENERGY",
    "ACMESOLAR": "NIFTY_ENERGY",
    "IREDA": "NIFTY_ENERGY",
    "SUZLON": "NIFTY_ENERGY",
    "OIL": "NIFTY_ENERGY",
    "HPCL": "NIFTY_ENERGY",
    "MRPL": "NIFTY_ENERGY",
    "CHENNPETRO": "NIFTY_ENERGY",
    "MGL": "NIFTY_ENERGY",
    "IGL": "NIFTY_ENERGY",
    "GUJGASLTD": "NIFTY_ENERGY",
    "GSPL": "NIFTY_ENERGY",
    "PETRONET": "NIFTY_ENERGY",
    "RECLTD": "NIFTY_ENERGY",
    "PFC": "NIFTY_ENERGY",
    "CESC": "NIFTY_ENERGY",
    "TORNTPOWER": "NIFTY_ENERGY",
    "KPIGREEN": "NIFTY_ENERGY",
    "GENUSPOWER": "NIFTY_ENERGY",
    "JPPOWER": "NIFTY_ENERGY",
    "SWSOLAR": "NIFTY_ENERGY",
    "GIPCL": "NIFTY_ENERGY",
    
    # NIFTY IT (Software services, Consulting, Hardware, and SaaS)
    "TCS": "NIFTY_IT",
    "INFY": "NIFTY_IT",
    "WIPRO": "NIFTY_IT",
    "HCLTECH": "NIFTY_IT",
    "TECHM": "NIFTY_IT",
    "LTIM": "NIFTY_IT",
    "COFORGE": "NIFTY_IT",
    "PERSISTENT": "NIFTY_IT",
    "MPHASIS": "NIFTY_IT",
    "KPITTECH": "NIFTY_IT",
    "LTTS": "NIFTY_IT",
    "TATAELXSI": "NIFTY_IT",
    "CYIENT": "NIFTY_IT",
    "SONATAW": "NIFTY_IT",
    "BIRLASOFT": "NIFTY_IT",
    "ZENSARTECH": "NIFTY_IT",
    "INTELLECT": "NIFTY_IT",
    "HAPPSTMNDS": "NIFTY_IT",
    "NEWGEN": "NIFTY_IT",
    "MASTEK": "NIFTY_IT",
    "BBOX": "NIFTY_IT",
    "FSL": "NIFTY_IT",
    "ECLERX": "NIFTY_IT",
    "CEINFO": "NIFTY_IT",
    "QUESS": "NIFTY_IT",
    "AFFLE": "NIFTY_IT",
    "LATENTVIEW": "NIFTY_IT",
    "TEJASNET": "NIFTY_IT",
    "AURUM": "NIFTY_IT",
    
    # NIFTY METAL (Steel, Copper, Aluminium, Zinc, Alloys, Mining)
    "JSWSTEEL": "NIFTY_METAL",
    "TATASTEEL": "NIFTY_METAL",
    "HINDALCO": "NIFTY_METAL",
    "VEDL": "NIFTY_METAL",
    "SAIL": "NIFTY_METAL",
    "NMDC": "NIFTY_METAL",
    "JINDALSTEL": "NIFTY_METAL",
    "HINDZINC": "NIFTY_METAL",
    "NATIONALUM": "NIFTY_METAL",
    "HNDFDS": "NIFTY_METAL",
    "JSL": "NIFTY_METAL",
    "APLAPOLLO": "NIFTY_METAL",
    "WELCORP": "NIFTY_METAL",
    "HINDCOPPER": "NIFTY_METAL",
    "MAITHANALL": "NIFTY_METAL",
    "MOIL": "NIFTY_METAL",
    "GPIL": "NIFTY_METAL",
    "SHYAMMETL": "NIFTY_METAL",
    "ISMTLTD": "NIFTY_METAL",
    "ELECTCAST": "NIFTY_METAL",
    "RAMASTEEL": "NIFTY_METAL",
    "MUKANDLTD": "NIFTY_METAL",
    "KALYANIFRG": "NIFTY_METAL",
    
    # NIFTY PHARMA (Pharmaceuticals, Biotech, Hospitals, Diagnostics)
    "SUNPHARMA": "NIFTY_PHARMA",
    "CIPLA": "NIFTY_PHARMA",
    "DRREDDY": "NIFTY_PHARMA",
    "APLLTD": "NIFTY_PHARMA",
    "DIVISLAB": "NIFTY_PHARMA",
    "LALPATH": "NIFTY_PHARMA",
    "TORNTPHARM": "NIFTY_PHARMA",
    "MANKIND": "NIFTY_PHARMA",
    "LUPIN": "NIFTY_PHARMA",
    "AUROPHARMA": "NIFTY_PHARMA",
    "ALKEM": "NIFTY_PHARMA",
    "IPCALAB": "NIFTY_PHARMA",
    "GLAND": "NIFTY_PHARMA",
    "BIOCON": "NIFTY_PHARMA",
    "ZYDUSLIFE": "NIFTY_PHARMA",
    "LAURUSLABS": "NIFTY_PHARMA",
    "METROPOLIS": "NIFTY_PHARMA",
    "SYNGENE": "NIFTY_PHARMA",
    "GRANULES": "NIFTY_PHARMA",
    "MARKSANS": "NIFTY_PHARMA",
    "FDC": "NIFTY_PHARMA",
    "JAGSNPHARM": "NIFTY_PHARMA",
    "HIKAL": "NIFTY_PHARMA",
    "ERIS": "NIFTY_PHARMA",
    "AARTIDRUGS": "NIFTY_PHARMA",
    "CONCORDBIO": "NIFTY_PHARMA",
    "BLUEJET": "NIFTY_PHARMA",
    "SUPRIYA": "NIFTY_PHARMA",
    "NEULANDDR": "NIFTY_PHARMA",
    "SOLARA": "NIFTY_PHARMA",
    "NATCOPHARM": "NIFTY_PHARMA",
    "JBCHEPHARM": "NIFTY_PHARMA",
    "GLAXO": "NIFTY_PHARMA",
    "SANOFI": "NIFTY_PHARMA",
    "ABBOTINDIA": "NIFTY_PHARMA",
    "KIMS": "NIFTY_PHARMA",
    "ASTERDM": "NIFTY_PHARMA",
    "NARAYANA": "NIFTY_PHARMA",
    "RAINBOW": "NIFTY_PHARMA",
    
    # NIFTY INFRA (Infrastructure, EPC, Construction, Cement, Telecom hardware)
    "L&T": "NIFTY_INFRA",
    "LT": "NIFTY_INFRA",
    "ULTRACEMCO": "NIFTY_INFRA",
    "GRASIM": "NIFTY_INFRA",
    "ADANIPORTS": "NIFTY_INFRA",
    "GMRINFRA": "NIFTY_INFRA",
    "IRB": "NIFTY_INFRA",
    "NCC": "NIFTY_INFRA",
    "KEC": "NIFTY_INFRA",
    "TATACHEM": "NIFTY_INFRA",
    "AMBUJACEM": "NIFTY_INFRA",
    "ACC": "NIFTY_INFRA",
    "SHREECEM": "NIFTY_INFRA",
    "ENGINERSIN": "NIFTY_INFRA",
    "DILIPBUILD": "NIFTY_INFRA",
    "PNCINFRA": "NIFTY_INFRA",
    "KNRLR": "NIFTY_INFRA",
    "HGINFRA": "NIFTY_INFRA",
    "ITDCEM": "NIFTY_INFRA",
    "AHLUCONT": "NIFTY_INFRA",
    "PSPPROJECT": "NIFTY_INFRA",
    "MANINFRA": "NIFTY_INFRA",
    "PATELENG": "NIFTY_INFRA",
    "RAILTEL": "NIFTY_INFRA",
    "RVNL": "NIFTY_INFRA",
    "IRCON": "NIFTY_INFRA",
    "RITES": "NIFTY_INFRA",
    "TATACOMM": "NIFTY_INFRA",
    "HFCL": "NIFTY_INFRA",
    "JKCEMENT": "NIFTY_INFRA",
    "RAMCOCEM": "NIFTY_INFRA",
    "NUVOWOCO": "NIFTY_INFRA",
    "PRSMJOHNSN": "NIFTY_INFRA",
    "HEIDELBERG": "NIFTY_INFRA",
    "JKIL": "NIFTY_INFRA",
    "EPIGRAL": "NIFTY_INFRA",
    "HEG": "NIFTY_INFRA",
    "GRAPHITE": "NIFTY_INFRA",
    "POWERMECH": "NIFTY_INFRA",
    "TECHNOE": "NIFTY_INFRA",
    "DREDGECORP": "NIFTY_INFRA",
    
    # NIFTY REALTY (Developers & Allied Real Estate Services)
    "DLF": "NIFTY_REALTY",
    "LODHA": "NIFTY_REALTY",
    "MACROTECH": "NIFTY_REALTY",
    "GODREJPROP": "NIFTY_REALTY",
    "OBEROIRLTY": "NIFTY_REALTY",
    "PRESTIGE": "NIFTY_REALTY",
    "PHOENIXLTD": "NIFTY_REALTY",
    "SOBHA": "NIFTY_REALTY",
    "BRIGADE": "NIFTY_REALTY",
    "SIGNATURE": "NIFTY_REALTY",
    "SIGNATUREGLOBAL": "NIFTY_REALTY",
    "KOLTEPATIL": "NIFTY_REALTY",
    "PURVA": "NIFTY_REALTY",
    "SUNTECK": "NIFTY_REALTY",
    "AJMERA": "NIFTY_REALTY",
    "ASHIANA": "NIFTY_REALTY",
    "MAHLIFE": "NIFTY_REALTY",
    "ELDECO": "NIFTY_REALTY",
    "IBREALEST": "NIFTY_REALTY",
    
    # NIFTY FMCG (Consumer Goods, Food, Beverages, Agri & Sugars)
    "ITC": "NIFTY_FMCG",
    "HINDUNILVR": "NIFTY_FMCG",
    "NESTLEIND": "NIFTY_FMCG",
    "BRITANNIA": "NIFTY_FMCG",
    "GODREJCP": "NIFTY_FMCG",
    "TATACONSUM": "NIFTY_FMCG",
    "DABUR": "NIFTY_FMCG",
    "MARICO": "NIFTY_FMCG",
    "VBL": "NIFTY_FMCG",
    "COLPAL": "NIFTY_FMCG",
    "BALRAMCHIN": "NIFTY_FMCG",
    "RENUKA": "NIFTY_FMCG",
    "EIDPARRY": "NIFTY_FMCG",
    "DALMIASUG": "NIFTY_FMCG",
    "TRIVENI": "NIFTY_FMCG",
    "DWARKESH": "NIFTY_FMCG",
    "AVANTIFEED": "NIFTY_FMCG",
    "KRBL": "NIFTY_FMCG",
    "LTFOODS": "NIFTY_FMCG",
    "ZYDUSWELL": "NIFTY_FMCG",
    "EMAMILTD": "NIFTY_FMCG",
    "BAJAJCON": "NIFTY_FMCG",
    "JYOTHYLAB": "NIFTY_FMCG",
    "GODREJAGRO": "NIFTY_FMCG",
    "HATSUN": "NIFTY_FMCG",
    "HERITGFOOD": "NIFTY_FMCG",
    "BIKAJI": "NIFTY_FMCG",
    "CAMPUS": "NIFTY_FMCG",
    "METROBRAND": "NIFTY_FMCG",
    "BECTORFOOD": "NIFTY_FMCG",
    "HONASA": "NIFTY_FMCG",
    "PRATAAP": "NIFTY_FMCG",
    "TASTYBITE": "NIFTY_FMCG",
    
    # NIFTY MEDIA ( multiplex, print, cable, television, and tip-selling/music services)
    "ZEEL": "NIFTY_MEDIA",
    "SAREGAMA": "NIFTY_MEDIA",
    "SUNTV": "NIFTY_MEDIA",
    "PVRINOX": "NIFTY_MEDIA",
    "TV18BRDCST": "NIFTY_MEDIA",
    "NETWORK18": "NIFTY_MEDIA",
    "DISHTV": "NIFTY_MEDIA",
    "HATHWAY": "NIFTY_MEDIA",
    "DEN": "NIFTY_MEDIA",
    "DBCORP": "NIFTY_MEDIA",
    "JAGRAN": "NIFTY_MEDIA",
    "ENIL": "NIFTY_MEDIA",
    "TIPSINDLTD": "NIFTY_MEDIA",
    "SHEMAROO": "NIFTY_MEDIA",
    "NDTV": "NIFTY_MEDIA",
    "PVR": "NIFTY_MEDIA",
    
    # NIFTY DEFENCE (Defense, Shipbuilders, Aerospace component makers)
    "HAL": "NIFTY_DEFENCE",
    "BEL": "NIFTY_DEFENCE",
    "MAZDOCK": "NIFTY_DEFENCE",
    "PREMIEREXPLO": "NIFTY_DEFENCE",
    "PREMIEREXP": "NIFTY_DEFENCE",
    "COCHINSHIP": "NIFTY_DEFENCE",
    "GRSE": "NIFTY_DEFENCE",
    "BDL": "NIFTY_DEFENCE",
    "PATELENG": "NIFTY_DEFENCE",
    "ASTRAZEN": "NIFTY_DEFENCE",
    "CENTUM": "NIFTY_DEFENCE",
    "ASTRAMIC": "NIFTY_DEFENCE",
    "DATAPATTERNS": "NIFTY_DEFENCE",
    "PARAS": "NIFTY_DEFENCE",
    "MTARTECH": "NIFTY_DEFENCE",
    "DCXINDIA": "NIFTY_DEFENCE",
    "IDEAFORGE": "NIFTY_DEFENCE",
    "ZENTECH": "NIFTY_DEFENCE",
    "BEML": "NIFTY_DEFENCE",
    "TITAGARH": "NIFTY_DEFENCE",
    "DYNAMATECH": "NIFTY_DEFENCE",
    "SOLARINDS": "NIFTY_DEFENCE"
}

def normalize_sector(sec: str) -> str:
    return sec.upper().strip().replace(" ", "_")


_all_base_symbols_cached = []

def get_all_base_symbols() -> list:
    global _all_base_symbols_cached
    if _all_base_symbols_cached:
        return _all_base_symbols_cached
    
    symbols = set()
    
    # 1. Add all symbols from TICKER_SECTOR_MAP
    for b in TICKER_SECTOR_MAP.keys():
        symbols.add(b.upper().strip())
        
    # 2. Try fetching the full NSE list
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        full_url = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
        res = requests.get(full_url, headers=headers, timeout=10)
        df = pd.read_csv(io.StringIO(res.text))
        for s in df["SYMBOL"].str.strip().tolist():
            if isinstance(s, str) and s and not pd.isna(s):
                symbols.add(s.upper())
    except Exception as e:
        print(f"Error fetching full NSE list: {e}")
        
    # 3. Try fetching Nifty 500 list
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        n500_url = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"
        n500_res = requests.get(n500_url, headers=headers, timeout=10)
        n500_df = pd.read_csv(io.StringIO(n500_res.text))
        for s in n500_df["Symbol"].str.strip().tolist():
            if isinstance(s, str) and s and not pd.isna(s):
                symbols.add(s.upper())
    except Exception as e:
        print(f"Error fetching Nifty 500 list: {e}")
        
    _all_base_symbols_cached = sorted(list(symbols))
    return _all_base_symbols_cached

def classify_symbol_to_sector(symbol: str) -> str:
    symbol_upper = symbol.strip().upper()
    
    # 1. NIFTY DEFENCE
    if any(k in symbol_upper for k in [
        "DEFENCE", "AERO", "SHIP", "NAVY", "ARMOUR", "MISSILE", "EXPLOSIVE", 
        "PREMIEREX", "ASTRAMIC", "PARAS", "MTAR", "ZENTEC", "BEML", "TITAGARH", 
        "DYNAMATECH", "SOLARINDS", "DCXINDIA", "IDEAFORGE", "COCHIN", "MAZDOCK"
    ]):
        return "NIFTY_DEFENCE"
        
    # 2. NIFTY IT
    if any(k in symbol_upper for k in [
        "TECH", "SOFT", "SYSTEM", "SYS", "INFO", "DATA", "MIND", "DIGI", "INTELLECT", 
        "CYIENT", "SONATA", "WIPRO", "TCS", "INFY", "LTIM", "HAPSTMNDS", "NEWGEN", 
        "MASTEK", "BBOX", "CEINFO", "AFFLE", "LATENTVIEW", "TEJASNET", "COFORGE", 
        "PERSISTENT", "MPHASIS", "KPIT", "TATAELXSI", "ZENSAR", "ECLERX", "QUESS", "FSL"
    ]):
        return "NIFTY_IT"
        
    # 3. NIFTY ENERGY
    if any(k in symbol_upper for k in [
        "POWER", "ENERGY", "SOLAR", "GREEN", "OIL", "GAS", "PETRO", "COAL", "NTPC", 
        "NHPC", "SJVN", "IREDA", "SUZLON", "REC", "PFC", "CESC", "KPIGREEN", "GENUS", 
        "HPCL", "BPCL", "IOC", "ONGC", "RELIANCE", "GAIL", "MRPL", "CHENNPETRO", "PETRONET", 
        "GSPL", "GUJGAS", "IGL", "MGL", "JSWENERGY", "TATAPOWER", "ADANIGREEN", "ADANIPOWER"
    ]):
        return "NIFTY_ENERGY"
        
    # 4. NIFTY AUTO
    if any(k in symbol_upper for k in [
        "MOTOR", "AUTO", "TYRE", "WHEEL", "FORG", "MINDA", "BATTERY", "CEAT", "MRF", 
        "APOLLO", "BALKRIS", "EICHER", "ASHOK", "TUBE", "AMARA", "EXIDE", "MARUTI", 
        "MAHINDRA", "TATAMOTORS", "BAJAJ", "HERO", "TVS", "BOSCH", "SONACOMS", "SUPRAJIT"
    ]):
        return "NIFTY_AUTO"
        
    # 5. NIFTY PHARMA
    if any(k in symbol_upper for k in [
        "PHARMA", "LAB", "HEALTH", "BIO", "MED", "CARE", "DRREDDY", "CIPLA", "LUPIN", 
        "ALKEM", "BIOCON", "GLAND", "LAURUS", "METROPOLIS", "SYNGENE", "GRANULES", 
        "MARKSANS", "NATCO", "GLAXO", "SANOFI", "ABBOT", "KIMS", "ASTER", "NARAYANA", 
        "RAINBOW", "HOSPITAL", "CLINIC", "AARTI", "FDC", "HIKAL", "ERIS", "BLUEJET"
    ]):
        return "NIFTY_PHARMA"
        
    # 6. NIFTY METAL
    if any(k in symbol_upper for k in [
        "STEEL", "METAL", "COPPER", "ALUM", "ZINC", "IRON", "MINING", "MOIL", "SAIL", 
        "TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "NMDC", "HINDZINC", "JSL", "APLAPOLLO", 
        "WELCORP", "HINDCOPPER", "MAITHAN", "GPIL", "SHYAM", "ISMT", "ELECTCAST"
    ]):
        return "NIFTY_METAL"
        
    # 7. NIFTY REALTY
    if any(k in symbol_upper for k in [
        "REAL", "PROP", "ESTATE", "LAND", "DEV", "LODHA", "DLF", "SOBHA", "BRIGADE", 
        "PRESTIGE", "OBEROI", "AJMERA", "ASHIANA", "MACROTECH", "KOLTE", "PURVA", "SUNTECK", 
        "MAHLIFE", "ELDECO", "IBREALEST", "SIGNATURE"
    ]):
        return "NIFTY_REALTY"
        
    # 8. NIFTY FMCG
    if any(k in symbol_upper for k in [
        "FOOD", "BEV", "SUGAR", "MILK", "AGRO", "DAIRY", "BREW", "DIST", "MILL", "ITC", 
        "HUL", "NESTLE", "BRITANNIA", "DABUR", "MARICO", "VBL", "COLPAL", "BALRAM", "RENUKA", 
        "EIDPARRY", "TRIVENI", "DWARKESH", "AVANTI", "KRBL", "LTFOODS", "ZYDUSWELL", "EMAMI", 
        "JYOTHY", "HATSUN", "BIKAJI", "CAMPUS", "METRO", "BECTOR", "HONASA"
    ]):
        return "NIFTY_FMCG"
        
    # 9. NIFTY MEDIA
    if any(k in symbol_upper for k in [
        "MEDIA", "TV", "FILM", "NEWS", "CINE", "PVR", "INOX", "ZEE", "SUNTV", "SAREGAMA", 
        "NETWORK18", "HATHWAY", "DISHTV", "DEN", "DBCORP", "JAGRAN", "ENIL", "TIPS", "SHEMAROO", "NDTV"
    ]):
        return "NIFTY_MEDIA"
        
    # 10. NIFTY INFRA
    if any(k in symbol_upper for k in [
        "INFRA", "BUILD", "CON", "ENG", "STRUCT", "PORT", "RAIL", "ROAD", "TELE", "COMM", 
        "CEMENT", "NCC", "KEC", "L&T", "LT", "RVNL", "IRCON", "RITES", "HFCL", "JKCEMENT", 
        "RAMCO", "NUVOWOCO", "PRISM", "HEIDELBERG", "JKIL", "EPIGRAL", "HEG", "GRAPHITE", 
        "POWERMECH", "TECHNO", "DREDGE", "AHLUWALIA", "PSP"
    ]):
        return "NIFTY_INFRA"
        
    return None


def get_bse_universe():
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        n500_url = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"
        n500_res = requests.get(n500_url, headers=headers, timeout=10)
        n500_df = pd.read_csv(io.StringIO(n500_res.text))
        tickers = [s.strip() + ".BO" for s in n500_df["Symbol"].str.strip().tolist()]
        # Add popular BSE-exclusive scrip codes to enable de-duplication tests and exclusive scans
        bse_exclusive_candidates = [
            "500008.BO", "500012.BO", "500016.BO", "500020.BO", 
            "500023.BO", "500027.BO", "500031.BO", "500033.BO", 
            "500034.BO", "500038.BO", "500040.BO", "500041.BO", 
            "500042.BO", "500043.BO", "500048.BO", "500049.BO", 
            "500052.BO", "500055.BO", "500057.BO", "500059.BO"
        ]
        tickers.extend(bse_exclusive_candidates)
        return tickers
    except Exception as e:
        print(f"BSE Universe Error: {e}")
        return ["RELIANCE.BO", "TCS.BO", "INFY.BO", "HDFCBANK.BO", "ICICIBANK.BO", "500008.BO", "500012.BO"]

def get_nse_universe(universe_mode: str):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        n500_url = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"
        n500_res = requests.get(n500_url, headers=headers, timeout=10)
        n500_df = pd.read_csv(io.StringIO(n500_res.text))
        premium_symbols = [s.strip() + ".NS" for s in n500_df["Symbol"].str.strip().tolist()]
        
        full_url = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
        full_res = requests.get(full_url, headers=headers, timeout=10)
        full_df = pd.read_csv(io.StringIO(full_res.text))
        all_symbols = [s.strip() + ".NS" for s in full_df["SYMBOL"].str.strip().tolist()]
        
        others_symbols = [s for s in all_symbols if s not in set(premium_symbols)]
        
        if universe_mode == "chunk1": return premium_symbols[:250]
        elif universe_mode == "chunk2": return premium_symbols[250:]
        elif universe_mode == "chunk3": return others_symbols[:len(others_symbols)//3]
        elif universe_mode == "chunk4": return others_symbols[len(others_symbols)//3 : 2*(len(others_symbols)//3)]
        elif universe_mode == "chunk5": return others_symbols[2*(len(others_symbols)//3):]
        return premium_symbols[:100]
    except Exception as e:
        print(f"Universe Error: {e}")
        return ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS"]

def resample_to_weekly(df: pd.DataFrame) -> list:
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    df['monday'] = df.index.map(lambda d: d - pd.Timedelta(days=d.weekday()))
    grouped = df.groupby('monday').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).sort_index()
    
    ohlcv = []
    for date, row in grouped.iterrows():
        ohlcv.append({
            "time": date.strftime("%Y-%m-%d"),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"])
        })
    return ohlcv

def resample_to_monthly(df: pd.DataFrame) -> list:
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    df['month_start'] = df.index.map(lambda d: d.replace(day=1))
    grouped = df.groupby('month_start').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).sort_index()
    
    ohlcv = []
    for date, row in grouped.iterrows():
        ohlcv.append({
            "time": date.strftime("%Y-%m-%d"),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"])
        })
    return ohlcv

@app.get("/api/historical/{ticker}")
async def get_historical_ticker_route(ticker: str, timeframe: str = Query("1D")):
    if timeframe == "1W":
        period = "3y"
    elif timeframe == "1M":
        period = "10y"
    else:
        period = "6mo"
        
    if ticker.endswith(".NS") or ticker.endswith(".BO"):
        yf_ticker = ticker
    else:
        yf_ticker = f"{ticker}.NS"
    df = yf.download(yf_ticker, period=period, progress=False)
    
    if df.empty:
        return {"status": "error", "message": f"No data found for ticker {ticker}"}
        
    if isinstance(df.columns, pd.MultiIndex):
        if yf_ticker in df.columns.get_level_values(1):
            df = df.xs(yf_ticker, axis=1, level=1)
        elif ticker in df.columns.get_level_values(1):
            df = df.xs(ticker, axis=1, level=1)
        else:
            df.columns = df.columns.droplevel(1)
            
    df = df.dropna(subset=["Close", "Volume"])
            
    if timeframe == "1W":
        ohlcv_data = resample_to_weekly(df)[-120:]
    elif timeframe == "1M":
        ohlcv_data = resample_to_monthly(df)[-120:]
    else:
        ohlcv_data = [
            {
                "time": date.strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"])
            }
            for date, row in df.iloc[-120:].iterrows()
        ]
        
    return {
        "status": "success",
        "ticker": ticker.replace(".NS", "").replace(".BO", ""),
        "timeframe": timeframe,
        "data": ohlcv_data
    }

@app.get("/api/scan")
async def run_scan(
    strategy: str = Query("current"),
    universe: str = Query("chunk1"),
    ticker: str = Query(None),
    timeframe: str = Query("1D"),
    ema_fast: int = Query(9),
    ema_slow: int = Query(20),
    min_volume: int = Query(20000),
    consolidation_days: int = Query(15),       
    consolidation_range: float = Query(10.0),   
    swing_run_pct: float = Query(15.0),         
    base_pullback_pct: float = Query(15.0),     
    pullback_offset: int = Query(20),
    swing_gate_pct: float = Query(0.0),
    weekly_close_n: int = Query(2),
    
    # Sector Partition Module inputs
    sector: str = Query("ALL"),
    min_mcap: float = Query(100.0),
    apply_sector_filters: int = Query(0),
    
    # Toggle Switches (1 = ON, 0 = OFF)
    use_ema_filter: int = Query(1),
    use_vol_filter: int = Query(1),
    use_consolidation: int = Query(1),
    use_swing_run: int = Query(1),
    use_base_pullback: int = Query(1),
    use_pullback_zone: int = Query(0),
    use_weekly_close_gate: int = Query(0),
    use_auto_pullback: int = Query(0),
    scan_bse: int = Query(0),
    scan_combined: int = Query(0)
):
    if ticker:
        return await get_historical_ticker_route(ticker, timeframe)

    if timeframe == "1W":
        period = "3y"
    elif timeframe == "1M":
        period = "10y"
    else:
        if use_weekly_close_gate == 1 and weekly_close_n > 20:
            period = "2y"
        elif use_weekly_close_gate == 1 and weekly_close_n > 10:
            period = "1y"
        else:
            period = "6mo"

    if sector != "ALL":
        target_sector = normalize_sector(sector)
        all_bases = get_all_base_symbols()
        bases = []
        for b in all_bases:
            s_mapped = TICKER_SECTOR_MAP.get(b)
            if s_mapped:
                if normalize_sector(s_mapped) == target_sector:
                    bases.append(b)
            else:
                classified = classify_symbol_to_sector(b)
                if classified and normalize_sector(classified) == target_sector:
                    bases.append(b)
        sector_tickers = []
        for b in bases:
            sector_tickers.append(f"{b}.NS")
            sector_tickers.append(f"{b}.BO")
        tickers = list(set(sector_tickers))
    elif scan_combined == 1:
        nse_tickers = get_nse_universe(universe)
        bse_tickers = get_bse_universe()
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            full_url = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
            full_res = requests.get(full_url, headers=headers, timeout=10)
            full_df = pd.read_csv(io.StringIO(full_res.text))
            nse_all_clean = set(s.strip().upper() for s in full_df["SYMBOL"].str.strip().tolist())
        except Exception as e:
            print(f"Error fetching all NSE symbols: {e}")
            nse_all_clean = set(s.replace(".NS", "").upper() for s in nse_tickers)
            
        bse_exclusives = []
        for bse_ticker in bse_tickers:
            clean_symbol = bse_ticker.replace(".BO", "").upper()
            if clean_symbol not in nse_all_clean:
                bse_exclusives.append(bse_ticker)
        tickers = nse_tickers + bse_exclusives
    elif scan_bse == 1:
        tickers = get_bse_universe()
    else:
        tickers = get_nse_universe(universe)

    # Concurrently fetch market capitalization for the sector tickers if sector is chosen
    mcap_map = {}
    if sector != "ALL" and tickers:
        def get_mcap(t_sym):
            try:
                t = yf.Ticker(t_sym)
                mc = t.fast_info.get("marketCap")
                if mc is None:
                    mc = t.info.get("marketCap")
                return t_sym, mc
            except Exception:
                return t_sym, None
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            mcap_results = executor.map(get_mcap, tickers)
            for t_sym, mc in mcap_results:
                if mc is not None:
                    mcap_map[t_sym] = mc / 1e7

    data = yf.download(tickers, period=period, group_by="ticker", threads=True, progress=False)
    results = []
    
    for ticker in tickers:
        try:
            if sector != "ALL":
                mcap_crores = mcap_map.get(ticker)
                if mcap_crores is None or mcap_crores < min_mcap:
                    continue

            if isinstance(data.columns, pd.MultiIndex):
                if ticker not in data.columns.get_level_values(0): continue
                df = data[ticker].copy()
            else:
                if data.empty: continue
                df = data.copy()
            
            df = df.dropna(subset=["Close", "Volume"])
            
            # --- CRITICAL: Slicing for scan calculations ---
            # If the stock has limited history (Recent IPO tracking window)
            is_ipo = 30 <= len(df) < 150
            if is_ipo:
                df_calc = df.copy()
            else:
                df_calc = df.iloc[-120:]
                
            # Validation guard gate
            bypass_filters = (sector != "ALL" and apply_sector_filters == 0)
            
            if bypass_filters:
                if len(df_calc) < 2: continue
            else:
                if is_ipo:
                    # Bypass 150/200 EMA filters completely to prevent rejection
                    # Execute Consolidation / Volatility Contraction Pattern (VCP) analysis strictly on the available lifecycle data since Listing Day High.
                    if len(df_calc) < 30: continue
                else:
                    if len(df_calc) < max(60, ema_slow, consolidation_days): continue 
            
            close = df_calc["Close"]
            volume = df_calc["Volume"]
            last_close = close.iloc[-1]
            prev_close = close.iloc[-2]
            change = round(((last_close - prev_close) / prev_close) * 100, 2)
            
            # Baseline Global Strategy Guards (Price Floor)
            if not bypass_filters:
                strategy_floor = 50 if strategy == "current" else 30
                if last_close < strategy_floor: continue 
            
            # Live Day Volume Fetch
            valid_vols = volume.dropna().values
            val = int(valid_vols[-1]) if len(valid_vols) > 0 and valid_vols[-1] > 0 else 0
            
            avg_vol_20d = volume.iloc[-20:].mean()

            # ----------------------------------------------------
            # 📊 MODULAR HYBRID FILTERS STATE MACHINE
            # ----------------------------------------------------
            
            # 1. MODULAR VOLUME FILTER LOGIC
            if not bypass_filters:
                if use_vol_filter == 1:
                    # 🟩 ACTIVE CUSTOM UI FILTER MODE
                    if val < min_volume: 
                        continue
                else:
                    # ⬛ PURE BASELINE FALLBACK MODE (Panel Closed or Unchecked)
                    if strategy == "current":
                        if avg_vol_20d < 100000: 
                            continue
                    elif strategy == "momentum_open_30":
                        if val < 20000: 
                            continue

            # 2. MODULAR EMA FILTER LOGIC
            # Custom Active UI EMAs or Fallback Base Strategy Default 9/20 EMAs
            fast_span = ema_fast if use_ema_filter == 1 else 9
            slow_span = ema_slow if use_ema_filter == 1 else 20
            
            if len(close) >= slow_span:
                ema_f_series = close.ewm(span=fast_span, adjust=False).mean()
                ema_s_series = close.ewm(span=slow_span, adjust=False).mean()
                l_ema_f = ema_f_series.iloc[-1]
                l_ema_s = ema_s_series.iloc[-1]
            else:
                l_ema_f = last_close
                l_ema_s = last_close
            
            # Baseline EMA crossing condition is ALWAYS active as part of base structure
            if not bypass_filters:
                if not (last_close > l_ema_f and last_close > l_ema_s):
                    continue

            # 3. MODULAR CONSOLIDATION FILTER LOGIC
            if not bypass_filters and use_consolidation == 1:
                if len(df_calc) >= (consolidation_days + 1):
                    consol_patch = close.iloc[-(consolidation_days + 1) : -1]
                    highest_high = consol_patch.max()
                    lowest_low = consol_patch.min()
                    actual_range_pct = ((highest_high - lowest_low) / lowest_low) * 100
                    if actual_range_pct > consolidation_range: continue

            # 4. MODULAR SWING RUN FILTER LOGIC
            if not bypass_filters and use_swing_run == 1:
                lowest_swing_low = df_calc["Low"].iloc[-20:].min()
                current_run_pct = ((last_close - lowest_swing_low) / lowest_swing_low) * 100
                if current_run_pct < swing_run_pct: continue

            # 5. MODULAR BASE PULLBACK FILTER LOGIC
            if not bypass_filters and use_base_pullback == 1:
                if len(df_calc) >= 10:
                    recent_base_level = ema_s_series.iloc[-10] if len(close) >= slow_span else last_close
                    distance_from_base_pct = ((last_close - recent_base_level) / recent_base_level) * 100
                    if distance_from_base_pct > base_pullback_pct: continue

            # 6. MODULAR 2ND LAST PULLBACK ZONE FILTER LOGIC
            if not bypass_filters and use_pullback_zone == 1:
                if len(df_calc) >= 20 + pullback_offset:
                    L2 = df_calc["Low"].iloc[-20 - pullback_offset : -pullback_offset].min()
                    if not (last_close >= L2 * (1 + swing_gate_pct / 100)):
                        continue
                else:
                    continue

            # 6b. AUTOMATIC 2ND PULLBACK FILTER LOGIC
            if not bypass_filters and use_auto_pullback == 1:
                if len(df_calc) >= 30:
                    dist_to_ema = (df_calc["Low"] - ema_s_series).abs()
                    L1_date = dist_to_ema.iloc[-25:].idxmin()
                    L1_idx = df_calc.index.get_loc(L1_date)
                    df_prev = df_calc.iloc[:L1_idx]
                    
                    if len(df_prev) >= 5:
                        pivots = []
                        for i in range(2, len(df_prev) - 2):
                            window = df_prev["Low"].iloc[i-2 : i+3]
                            if df_prev["Low"].iloc[i] == window.min():
                                pivots.append(float(df_prev["Low"].iloc[i]))
                        
                        if pivots:
                            L2 = pivots[-1]
                        else:
                            L2 = float(df_prev["Low"].iloc[-30:].min())
                        
                        # --- DYNAMIC SWING GATE BUFFER CALCULATION ---
                        # If the user specifies a swing_gate_pct value > 0.0 (e.g., 6.0), use it as the upper boundary cushion.
                        # Otherwise, fall back to the default baseline baseline multiplier of 15% (1.15).
                        upper_multiplier = 1 + (swing_gate_pct / 100.0) if swing_gate_pct > 0.0 else 1.15

                        # SWING GATE LOGIC: Strict minimum floor pass. Skip anything below or equal to upper_multiplier
                        if last_close <= (L2 * upper_multiplier):
                            continue
                    else:
                        continue
                else:
                    continue

            # 7. WEEKLY CLOSE GATE FILTER LOGIC
            if not bypass_filters and use_weekly_close_gate == 1:
                df_w = df.copy()
                df_w.index = pd.to_datetime(df_w.index)
                df_w['monday'] = df_w.index.map(lambda d: d - pd.Timedelta(days=d.weekday()))
                grouped_w = df_w.groupby('monday').agg({'Close': 'last'}).sort_index()
                
                if len(grouped_w) > weekly_close_n:
                    current_w_close = float(grouped_w['Close'].iloc[-1])
                    n_weeks_ago_close = float(grouped_w['Close'].iloc[-1 - weekly_close_n])
                    if not (current_w_close > n_weeks_ago_close):
                        continue
                else:
                    continue

            # ----------------------------------------------------
            # PAYLOAD COMPILING
            # ----------------------------------------------------
            vol_multiple = round(val / avg_vol_20d, 2) if (avg_vol_20d > 0 and pd.notna(avg_vol_20d)) else 1.0
            
            # Determine dynamic tag for dashboard feedback
            active_custom_filters = []
            if use_ema_filter == 1: active_custom_filters.append(f"EMA({ema_fast}/{ema_slow})")
            if use_vol_filter == 1: active_custom_filters.append(f"Vol(>{min_volume})")
            if use_consolidation == 1: active_custom_filters.append("Consol")
            if use_swing_run == 1: active_custom_filters.append("Swing")
            if use_base_pullback == 1: active_custom_filters.append("Base")
            if use_pullback_zone == 1: active_custom_filters.append("Pullback")
            if use_auto_pullback == 1: active_custom_filters.append("AutoPB")
            if use_weekly_close_gate == 1: active_custom_filters.append(f"WGate({weekly_close_n})")
            
            setup_label = " | ".join(active_custom_filters) if active_custom_filters else "Pure Base Strategy"
            history_prices = [
                {"time": date.strftime("%Y-%m-%d"), "value": round(val, 2)}
                for date, val in close.iloc[-30:].items()
            ]
            
            if timeframe == "1W":
                ohlcv_data = resample_to_weekly(df)[-120:]
            elif timeframe == "1M":
                ohlcv_data = resample_to_monthly(df)[-120:]
            else:
                ohlcv_data = [
                    {
                        "time": date.strftime("%Y-%m-%d"),
                        "open": round(float(row["Open"]), 2),
                        "high": round(float(row["High"]), 2),
                        "low": round(float(row["Low"]), 2),
                        "close": round(float(row["Close"]), 2),
                        "volume": int(row["Volume"])
                    }
                    for date, row in df.iloc[-120:].iterrows()
                ]

            metadata = {
                "ticker": ticker.replace(".NS", "").replace(".BO", ""),
                "exchange": "BSE" if ticker.endswith(".BO") else "NSE",
                "price": round(last_close, 2),
                "change": change,
                "Volume": val,
                "ema9": round(l_ema_f, 2),
                "ema20": round(l_ema_s, 2),
                "vol_multiple": vol_multiple,
                "setup": setup_label,
                "history": history_prices,
                "ohlcv": ohlcv_data
            }
            results.append(metadata)
                
        except Exception:
            continue

    if sector != "ALL":
        seen_tickers = {}
        for r in results:
            base_sym = r["ticker"]
            exchange = r["exchange"]
            if base_sym not in seen_tickers:
                seen_tickers[base_sym] = r
            else:
                if exchange == "NSE" and seen_tickers[base_sym]["exchange"] == "BSE":
                    seen_tickers[base_sym] = r
        results = list(seen_tickers.values())

    sorted_results = sorted(results, key=lambda x: x['vol_multiple'], reverse=True)
    return {
        "status": "success",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "count": len(sorted_results),
        "data": sorted_results
    }

app.mount("/", StaticFiles(directory="public", html=True), name="public")

# ====================================================================
# 🚀 HUGGING FACE PRODUCTION SERVER STARTUP BLOCK
# ====================================================================
if __name__ == "__main__":
    import uvicorn
    import os
    # Hugging Face Spaces strictly injects a target PORT env variable, defaulting to 7860
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run("index:app", host="0.0.0.0", port=port, reload=False)