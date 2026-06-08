from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import yfinance as yf
import pandas as pd
import numpy as np
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
        others_symbols = [s for s in all_symbols if s in all_symbols and s not in premium_set]
        
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
    strategy: str = Query("current", description="Strategy: current or vcp"),
    universe: str = Query("chunk1", description="Target Matrix Chunk: chunk1-chunk5")
):
    # 1. DATA UPLINK & UNIVERSE TARGETING
    tickers = get_nse_universe(universe)
    
    # Batch download optimization (High-speed multi-threading enabled)
    data = yf.download(tickers, period="4mo", group_by="ticker", threads=True, progress=False)
    
    results = []
    
    # 2. STRATEGY EXECUTION ENGINE
    for ticker in tickers:
        try:
            # Check for multi-index integrity or single ticker data consistency
            if ticker not in data.columns.levels[0] if isinstance(data.columns, pd.MultiIndex) else [ticker]:
                continue
                
            df = data[ticker].dropna()
            if len(df) < 30: continue # Minimum historical candle depth
            
            close = df["Close"]
            volume = df["Volume"]
            last_close = close.iloc[-1]
            
            # ====================================================
            # 🛡️ INSTITUTIONAL FILTERS (PENNY & LIQUIDITY BARRIERS)
            # ====================================================
            if last_close < 50: continue # Anti-trash penny floor
            
            avg_vol_20d = volume.iloc[-20:].mean()
            if avg_vol_20d < 100000: continue # Volume safety barrier
            
            match_found = False
            metadata = {}

            # ====================================================
            # 📈 CURRENT BREAKOUT ENGINE (9/20 EMA MOMENTUM)
            # ====================================================
            if strategy == "current":
                ema9 = close.ewm(span=9, adjust=False).mean()
                ema20 = close.ewm(span=20, adjust=False).mean()
                
                l_ema9 = ema9.iloc[-1]
                l_ema20 = ema20.iloc[-1]
                
                if last_close > l_ema9 and last_close > l_ema20:
                    pct_diff = ((last_close - l_ema20) / l_ema20) * 100
                    score = round(100 - pct_diff, 2)
                    
                    # Robust Volume Fallback (Safe for late-night data gaps)
                    try:
                        val = next((int(v) for v in reversed(volume.dropna().values) if v > 0), 0)
                    except Exception:
                        val = 0
                    
                    if not val:
                        try:
                            # Secondary fallback to 5-day history for delisted/stale data
                            v_hist = yf.Ticker(ticker).history(period="5d")["Volume"].dropna()
                            val = next((int(v) for v in reversed(v_hist.values) if v > 0), 0)
                        except Exception:
                            val = 0

                    match_found = True
                    metadata = {
                        "ticker": ticker.replace(".NS", ""),
                        "price": round(last_close, 2),
                        "Volume": val,
                        "ema9": round(l_ema9, 2),
                        "ema20": round(l_ema20, 2),
                        "score": score,
                        "setup": "Momentum Breakout" if last_close > close.iloc[-20:].max() * 0.98 else "EMA Support"
                    }
            
            # ====================================================
            # ⚡ VCP MATRIX ENGINE (MARK MINERVINI COMPRESSION)
            # ====================================================
            elif strategy == "vcp":
                sma50 = close.rolling(window=20).mean() # Scaled trend filter
                if last_close < sma50.iloc[-1]: continue
                
                # Dynamic Volatility Blocks (T1->T2->T3 Compression)
                range_t1 = (close.iloc[-24:-16].max() - close.iloc[-24:-16].min()) / close.iloc[-24:-16].mean()
                range_t2 = (close.iloc[-16:-8].max() - close.iloc[-16:-8].min()) / close.iloc[-16:-8].mean()
                range_t3 = (close.iloc[-8:].max() - close.iloc[-8:].min()) / close.iloc[-8:].mean()
                
                # Sequential tightening verification
                if range_t1 > range_t2 and range_t2 > range_t3:
                    compression_ratio = round(range_t3 * 100, 2)
                    vcp_score = round(100 - compression_ratio, 2)
                    
                    # Volume Contraction Check (Supply absorption)
                    if volume.iloc[-8:].mean() < volume.iloc[-16:-8].mean():
                        # Robust Volume Fallback (Safe for late-night data gaps)
                        try:
                            val = next((int(v) for v in reversed(volume.dropna().values) if v > 0), 0)
                        except Exception:
                            val = 0
                        
                        if not val:
                            try:
                                # Secondary fallback to 5-day history for delisted/stale data
                                v_hist = yf.Ticker(ticker).history(period="5d")["Volume"].dropna()
                                val = next((int(v) for v in reversed(v_hist.values) if v > 0), 0)
                            except Exception:
                                val = 0

                        match_found = True
                        metadata = {
                            "ticker": ticker.replace(".NS", ""),
                            "price": round(last_close, 2),
                            "Volume": val,
                            "ema9": round(range_t2 * 100, 1), # Reusing schema for T2 comp
                            "ema20": round(range_t3 * 100, 1), # Reusing schema for T3 comp
                            "score": vcp_score,
                            "setup": f"VCP Tightening ({compression_ratio}%)"
                        }

            if match_found:
                results.append(metadata)
                
        except Exception:
            continue

    # 3. PAYBOARD OUTPUT GENERATION
    sorted_results = sorted(results, key=lambda x: x['score'], reverse=True)
    
    return {
        "status": "success",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "count": len(sorted_results),
        "data": sorted_results
    }

# MOUNT FRONTEND TERMINAL
app.mount("/", StaticFiles(directory="public", html=True), name="public")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
