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
    strategy: str = Query("current", description="Strategy: current, vcp, momentum_2, or vcp_2"),
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
            
            # Anti-trash penny floor & Volume safety barrier
            if last_close < 50: 
                continue 
            
            avg_vol_20d = volume.iloc[-20:].mean()
            if avg_vol_20d < 100000: 
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
                ema9 = close.ewm(span=9, adjust=False).mean()
                ema20 = close.ewm(span=20, adjust=False).mean()
                
                l_ema9 = ema9.iloc[-1]
                l_ema20 = ema20.iloc[-1]
                
                if last_close > l_ema9 and last_close > l_ema20:
                    pct_diff = ((last_close - l_ema20) / l_ema20) * 100
                    score = round(100 - pct_diff, 2)

                    match_found = True
                    metadata = {
                        "ticker": ticker.replace(".NS", ""),
                        "price": round(last_close, 2),
                        "change": change,
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
                sma20 = close.rolling(window=20).mean()
                if last_close < sma20.iloc[-1]: 
                    continue
                
                range_t1 = (close.iloc[-24:-16].max() - close.iloc[-24:-16].min()) / close.iloc[-24:-16].mean()
                range_t2 = (close.iloc[-16:-8].max() - close.iloc[-16:-8].min()) / close.iloc[-16:-8].mean()
                range_t3 = (close.iloc[-8:].max() - close.iloc[-8:].min()) / close.iloc[-8:].mean()
                
                if range_t1 > range_t2 and range_t2 > range_t3:
                    compression_ratio = round(range_t3 * 100, 2)
                    vcp_score = round(100 - compression_ratio, 2)
                    
                    if volume.iloc[-8:].mean() < volume.iloc[-16:-8].mean():
                        match_found = True
                        metadata = {
                            "ticker": ticker.replace(".NS", ""),
                            "price": round(last_close, 2),
                            "change": change,
                            "Volume": val,
                            "ema9": round(range_t2 * 100, 1), 
                            "ema20": round(range_t3 * 100, 1), 
                            "score": vcp_score,
                            "setup": f"VCP Tightening ({compression_ratio}%)"
                        }

            # ====================================================
            # 🚀 MOMENTUM 2 ENGINE (TIGHT CONSOLIDATION & DRY VOL)
            # ====================================================
            elif strategy == "momentum_2":
                monthly_low = df["Low"].iloc[-20:].min()
                if last_close >= (monthly_low * 1.15):
                    ema9 = close.ewm(span=9, adjust=False).mean()
                    ema20 = close.ewm(span=20, adjust=False).mean()
                    
                    lows_above_emas = True
                    for idx in [-1, -2, -3]:
                        if not (df["Low"].iloc[idx] >= ema9.iloc[idx] and df["Low"].iloc[idx] >= ema20.iloc[idx]):
                            lows_above_emas = False
                            break
                    
                    if lows_above_emas:
                        high_3d = df["High"].iloc[-3:].max()
                        low_3d = df["Low"].iloc[-3:].min()
                        mean_close_3d = df["Close"].iloc[-3:].mean()
                        spread_pct = ((high_3d - low_3d) / mean_close_3d) * 100
                        
                        if spread_pct <= 7.0:
                            current_vol_3d_avg = volume.iloc[-3:].mean()
                            volume_20d_avg = volume.iloc[-20:].mean()
                            
                            if current_vol_3d_avg < volume_20d_avg * 0.85:
                                vol_ratio = (current_vol_3d_avg / volume_20d_avg)
                                breakout_score = round(100 - (spread_pct / 7.0) * 50 - (vol_ratio / 0.85) * 50, 2)
                                
                                match_found = True
                                metadata = {
                                    "ticker": ticker.replace(".NS", ""),
                                    "price": round(last_close, 2),
                                    "change": change,
                                    "Volume": val,
                                    "ema9": round(ema9.iloc[-1], 2),
                                    "ema20": round(ema20.iloc[-1], 2),
                                    "score": breakout_score,
                                    "setup": f"Momentum 2 (Spread: {spread_pct:.2f}%)"
                                }

            # ====================================================
            # 📈 MOMENTUM VELOCITY 2.0 (THE ULTIMATE ENGINE)
            # ====================================================
            elif strategy == "vcp_2":
                if len(df) < 30: continue
                
                # Condition 1: Monthly Pullback Guard (15% Above 20-Day Low)
                monthly_low = df["Low"].iloc[-20:].min()
                if last_close >= (monthly_low * 1.15):
                    
                    # Condition 2: Short-Term Trend (CMP > Daily 9 EMA & 20 EMA)
                    ema9 = close.ewm(span=9, adjust=False).mean()
                    ema20 = close.ewm(span=20, adjust=False).mean()
                    
                    l_ema9 = ema9.iloc[-1]
                    l_ema20 = ema20.iloc[-1]
                    
                    if last_close > l_ema9 and last_close > l_ema20:
                        # Condition 3: Relaxed 5-Day Squeeze Range (<= 15.0%)
                        high_5d = df["High"].iloc[-5:].max()
                        low_5d = df["Low"].iloc[-5:].min()
                        mean_close_5d = df["Close"].iloc[-5:].mean()
                        
                        if mean_close_5d > 0:
                            squeeze_range = round(((high_5d - low_5d) / mean_close_5d) * 100, 2)
                            
                            if squeeze_range <= 15.0:
                                # Strategic fallback for short historical depth 50 EMA
                                ema50 = close.ewm(span=50, adjust=False).mean()
                                l_ema50 = ema50.iloc[-1] if not np.isnan(ema50.iloc[-1]) else l_ema20
                                
                                # Balance score scaling
                                breakout_score = round(100 - (squeeze_range / 15.0) * 50, 2)
                                        
                                match_found = True
                                metadata = {
                                    "ticker": ticker.replace(".NS", ""),
                                    "price": round(last_close, 2),
                                    "change": change,
                                    "Volume": val,
                                    "ema9": squeeze_range, # 5D Squeeze mapped to frontend EMA9 slot
                                    "ema20": round(l_ema50, 2), # 50 EMA mapped to frontend EMA20 slot
                                    "score": breakout_score,
                                    "setup": f"MV 2.0 (5D: {squeeze_range:.2f}%)"
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

app.mount("/", StaticFiles(directory="public", html=True), name="public")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)