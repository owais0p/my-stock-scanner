from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import yfinance as yf
import pandas as pd
import requests
import io
from datetime import datetime

app = FastAPI()

# Enable CORS for institutional terminal access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_nse_universe(universe_mode: str):
    """
    SEGMENTATION MATRIX:
    - Chunk 1 & 2: Premium Nifty 500 (Institutional Grade)
    - Chunk 3, 4 & 5: Standard Broader Market (Alpha Micro-cap Pools)
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        # 1. FETCH PREMIUM POOL (Nifty 500)
        n500_url = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"
        n500_res = requests.get(n500_url, headers=headers, timeout=10)
        n500_df = pd.read_csv(io.StringIO(n500_res.text))
        premium_symbols = [s.strip() + ".NS" for s in n500_df["Symbol"].str.strip().tolist()]
        
        # 2. FETCH BROAD POOL (All Equities)
        full_url = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
        full_res = requests.get(full_url, headers=headers, timeout=10)
        full_df = pd.read_csv(io.StringIO(full_res.text))
        all_symbols = [s.strip() + ".NS" for s in full_df["SYMBOL"].str.strip().tolist()]
        
        # 3. SEGMENT OTHERS (Standard Equities not in Nifty 500)
        premium_set = set(premium_symbols)
        others_symbols = [s for s in all_symbols if s not in premium_set]
        
        if universe_mode == "chunk1":
            return premium_symbols[:250]
        elif universe_mode == "chunk2":
            return premium_symbols[250:]
        elif universe_mode == "chunk3":
            split_size = len(others_symbols) // 3
            return others_symbols[:split_size]
        elif universe_mode == "chunk4":
            split_size = len(others_symbols) // 3
            return others_symbols[split_size : 2 * split_size]
        elif universe_mode == "chunk5":
            split_size = len(others_symbols) // 3
            return others_symbols[2 * split_size :]
        else:
            return premium_symbols[:100] # Default fallback
            
    except Exception as e:
        print(f"Universe Fetch Critical Error: {e}")
        return ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "BHARTIARTL.NS"]

@app.get("/api/scan")
async def run_scan(
    strategy: str = Query("current", description="Strategy: current or momentum_open_30"),
    universe: str = Query("chunk1", description="Target Matrix Chunk: chunk1-chunk5")
):
    # 1. DATA UPLINK & UNIVERSE TARGETING
    tickers = get_nse_universe(universe)
    period_days = "4mo"
    
    # Batch download optimization
    data = yf.download(tickers, period=period_days, group_by="ticker", threads=True, progress=False)
    results = []
    
    # 2. STRATEGY EXECUTION ENGINE
    for ticker in tickers:
        try:
            # FIX: Robust MultiIndex check avoiding drops on stale rows
            if isinstance(data.columns, pd.MultiIndex):
                if ticker not in data.columns.get_level_values(0):
                    continue
                df = data[ticker].copy()
            else:
                if data.empty:
                    continue
                df = data.copy()
            
            # Filter rows containing valid sequential data
            df = df.dropna(subset=["Close", "Volume"])
            if len(df) < 30: 
                continue 
            
            close = df["Close"]
            volume = df["Volume"]
            last_close = close.iloc[-1]
            prev_close = close.iloc[-2]
            change = round(((last_close - prev_close) / prev_close) * 100, 2)
            
            # Anti-trash penny floor & Volume safety barrier for global loops
            if last_close < 30: 
                continue 
            
            match_found = False
            metadata = {}

            # Fallback helper for volume fetch
            valid_vols = volume.dropna().values
            val = int(valid_vols[-1]) if len(valid_vols) > 0 and valid_vols[-1] > 0 else 0
            if not val:
                for v in reversed(valid_vols):
                    if v > 0:
                        val = int(v)
                        break

            # ====================================================
            # 📈 CURRENT BREAKOUT ENGINE (9/20 EMA MOMENTUM)
            # ====================================================
            if strategy == "current":
                # Original Baseline Strategy Guards (As-Is Safe! No changes here)
                if last_close < 50: 
                    continue 
                
                avg_vol_20d = volume.iloc[-20:].mean()
                if avg_vol_20d < 100000: 
                    continue 

                ema9 = close.ewm(span=9, adjust=False).mean()
                ema20 = close.ewm(span=20, adjust=False).mean()
                
                l_ema9 = ema9.iloc[-1]
                l_ema20 = ema20.iloc[-1]
                
                if last_close > l_ema9 and last_close > l_ema20:
                    vol_multiple = round(val / avg_vol_20d, 2) if avg_vol_20d > 0 else 1.0

                    match_found = True
                    metadata = {
                        "ticker": ticker.replace(".NS", ""),
                        "price": round(last_close, 2),
                        "change": change,
                        "Volume": val,
                        "ema9": round(l_ema9, 2),
                        "ema20": round(l_ema20, 2),
                        "vol_multiple": vol_multiple,
                        "setup": "Momentum Breakout" if last_close > close.iloc[-20:].max() * 0.98 else "EMA Support"
                    }

            # ====================================================
            # 🚀 RAYYAN OVERRIDE: OPEN MOMENTUM 2.0 (NEW ALAG BUTTON)
            # ====================================================
            elif strategy == "momentum_open_30":
                # Strict Live Daily Volume Gate: Must cross 20,000 shares today
                current_day_vol = volume.iloc[-1]
                if current_day_vol < 20000:
                    continue

                avg_vol_20d = volume.iloc[-20:].mean()
                ema9 = close.ewm(span=9, adjust=False).mean()
                ema20 = close.ewm(span=20, adjust=False).mean()
                
                l_ema9 = ema9.iloc[-1]
                l_ema20 = ema20.iloc[-1]
                
                if last_close > l_ema9 and last_close > l_ema20:
                    vol_multiple = round(val / avg_vol_20d, 2) if avg_vol_20d > 0 else 1.0

                    match_found = True
                    metadata = {
                        "ticker": ticker.replace(".NS", ""),
                        "price": round(last_close, 2),
                        "change": change,
                        "Volume": val,
                        "ema9": round(l_ema9, 2),
                        "ema20": round(l_ema20, 2),
                        "vol_multiple": vol_multiple,
                        "setup": "Open Breakout (Floor ₹30)"
                    }
            
            if match_found:
                results.append(metadata)
                
        except Exception:
            continue

    # 3. PAYBOARD OUTPUT GENERATION
    sorted_results = sorted(results, key=lambda x: x['vol_multiple'], reverse=True)
    
    return {
        "status": "success",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "count": len(sorted_results),
        "data": sorted_results
    }

app.mount("/", StaticFiles(directory="public", html=True), name="public")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)