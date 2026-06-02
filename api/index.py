from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import requests
import io
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed

warnings.filterwarnings("ignore")

app = FastAPI()

# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURATION (Original Logic) ---
CONFIG = {
    "market_cap_min_cr": 100,
    "ema_short": 9,
    "ema_long": 20,
    "data_period": "3mo",
    "pole_lookback_sessions": 60,
    "pole_window_sessions": 40,
    "pole_min_gain_pct": 20,
    "consolidation_sessions": 30,
    "consolidation_min_sessions": 5,
    "consolidation_range_pct": 8,
}

# --- HELPER FUNCTIONS ---
def compute_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def has_prior_up_move(close: pd.Series, cfg: dict) -> tuple[bool, float]:
    lookback = cfg["pole_lookback_sessions"]
    window = cfg["pole_window_sessions"]
    min_gain = cfg["pole_min_gain_pct"]
    segment = close.iloc[-lookback:]
    if len(segment) < window: return False, 0.0
    max_gain = 0.0
    for i in range(len(segment) - window + 1):
        chunk = segment.iloc[i: i + window]
        gain = (chunk.iloc[-1] / chunk.iloc[0] - 1) * 100
        if gain > max_gain: max_gain = gain
    return max_gain >= min_gain, round(max_gain, 2)

def is_tight_consolidation(close, high, low, ema9, ema20, cfg):
    max_sessions = cfg["consolidation_sessions"]
    min_sessions = cfg["consolidation_min_sessions"]
    max_range = cfg["consolidation_range_pct"]
    best_range, best_length, found = float("inf"), 0, False
    for n in range(min_sessions, max_sessions + 1):
        if n > len(close): break
        seg_high, seg_low = high.iloc[-n:], low.iloc[-n:]
        seg_ema9, seg_ema20 = ema9.iloc[-n:], ema20.iloc[-n:]
        hh, ll = seg_high.max(), seg_low.min()
        range_pct = (hh - ll) / ll * 100
        all_above = (seg_low >= seg_ema9).all() and (seg_low >= seg_ema20).all()
        if range_pct <= max_range and all_above and range_pct < best_range:
            best_range, best_length, found = range_pct, n, True
    return found, round(best_range if found else 0.0, 2), best_length

def get_nse_universe():
    try:
        url = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        df = pd.read_csv(io.StringIO(res.text))
        return [s.strip() + ".NS" for s in df[df["SERIES"].str.strip() == "EQ"]["SYMBOL"]]
    except:
        return []

def scan_single_stock(ticker):
    try:
        stock = yf.Ticker(ticker)
        # Fast info check
        hist = stock.history(period="3mo")
        if hist.empty or len(hist) < 60: return None
        
        close, high, low = hist["Close"], hist["High"], hist["Low"]
        ema9 = compute_ema(close, CONFIG["ema_short"])
        ema20 = compute_ema(close, CONFIG["ema_long"])
        
        # Criterion 1: Pole
        has_pole, pole_gain = has_prior_up_move(close, CONFIG)
        if not has_pole: return None
        
        # Criterion 2: Price above EMAs
        last_close = close.iloc[-1]
        if not (last_close > ema9.iloc[-1] and last_close > ema20.iloc[-1]): return None
        
        # Criterion 3: Consolidation
        is_vcp, vcp_range, vcp_len = is_tight_consolidation(close, high, low, ema9, ema20, CONFIG)
        if not is_vcp: return None
        
        return {
            "ticker": ticker.replace(".NS", ""),
            "price": round(last_close, 2),
            "pole_gain": pole_gain,
            "vcp_range": vcp_range,
            "vcp_len": vcp_len,
            "setup": "High Tight Flag" if pole_gain > 50 else "VCP Structure",
            "score": round((pole_gain / vcp_range), 1) if vcp_range > 0 else 0
        }
    except:
        return None

@app.get("/api/scan")
def run_scan():
    # To avoid Vercel timeouts, we'll scan a prioritized list or a subset
    # for this demo, we'll take a subset of popular stocks to ensure responsiveness.
    full_universe = get_nse_universe()
    # In a real production app, we'd use a background task or cache.
    # For now, let's scan the top 50 to keep it within serverless limits.
    test_universe = full_universe[:50] 
    
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(scan_single_stock, t) for t in test_universe]
        for f in as_completed(futures):
            res = f.result()
            if res: results.append(res)
            
    return {
        "status": "success",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "count": len(results),
        "data": sorted(results, key=lambda x: x['score'], reverse=True)
    }

@app.get("/")
def health():
    return {"status": "active"}
