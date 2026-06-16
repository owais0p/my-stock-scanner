from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import yfinance as yf
import pandas as pd
import requests
import io
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get("/api/scan")
async def run_scan(
    strategy: str = Query("current"),
    universe: str = Query("chunk1"),
    ema_fast: int = Query(9),
    ema_slow: int = Query(20),
    min_volume: int = Query(20000),
    consolidation_days: int = Query(15),       
    consolidation_range: float = Query(10.0),   
    swing_run_pct: float = Query(15.0),         
    base_pullback_pct: float = Query(15.0),     
    
    # Toggle Switches (1 = ON, 0 = OFF)
    use_ema_filter: int = Query(1),
    use_vol_filter: int = Query(1),
    use_consolidation: int = Query(1),
    use_swing_run: int = Query(1),
    use_base_pullback: int = Query(1)
):
    tickers = get_nse_universe(universe)
    data = yf.download(tickers, period="6mo", group_by="ticker", threads=True, progress=False)
    results = []
    
    for ticker in tickers:
        try:
            if isinstance(data.columns, pd.MultiIndex):
                if ticker not in data.columns.get_level_values(0): continue
                df = data[ticker].copy()
            else:
                if data.empty: continue
                df = data.copy()
            
            df = df.dropna(subset=["Close", "Volume"])
            if len(df) < max(60, ema_slow, consolidation_days): continue 
            
            close = df["Close"]
            volume = df["Volume"]
            last_close = close.iloc[-1]
            prev_close = close.iloc[-2]
            change = round(((last_close - prev_close) / prev_close) * 100, 2)
            
            # Baseline Global Strategy Guards (Price Floor)
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
            if use_ema_filter == 1:
                # Custom Active UI EMAs
                ema_f_series = close.ewm(span=ema_fast, adjust=False).mean()
                ema_s_series = close.ewm(span=ema_slow, adjust=False).mean()
            else:
                # Fallback to Base Strategy Default 9/20 EMAs
                ema_f_series = close.ewm(span=9, adjust=False).mean()
                ema_s_series = close.ewm(span=20, adjust=False).mean()
            
            l_ema_f = ema_f_series.iloc[-1]
            l_ema_s = ema_s_series.iloc[-1]
            
            # Baseline EMA crossing condition is ALWAYS active as part of base structure
            if not (last_close > l_ema_f and last_close > l_ema_s):
                continue

            # 3. MODULAR CONSOLIDATION FILTER LOGIC
            if use_consolidation == 1:
                if len(df) >= (consolidation_days + 1):
                    consol_patch = close.iloc[-(consolidation_days + 1) : -1]
                    highest_high = consol_patch.max()
                    lowest_low = consol_patch.min()
                    actual_range_pct = ((highest_high - lowest_low) / lowest_low) * 100
                    if actual_range_pct > consolidation_range: continue

            # 4. MODULAR SWING RUN FILTER LOGIC
            if use_swing_run == 1:
                lowest_swing_low = df["Low"].iloc[-20:].min()
                current_run_pct = ((last_close - lowest_swing_low) / lowest_swing_low) * 100
                if current_run_pct < swing_run_pct: continue

            # 5. MODULAR BASE PULLBACK FILTER LOGIC
            if use_base_pullback == 1:
                recent_base_level = ema_s_series.iloc[-10]
                distance_from_base_pct = ((last_close - recent_base_level) / recent_base_level) * 100
                if distance_from_base_pct > base_pullback_pct: continue

            # ----------------------------------------------------
            # PAYLOAD COMPILING
            # ----------------------------------------------------
            vol_multiple = round(val / avg_vol_20d, 2) if avg_vol_20d > 0 else 1.0
            
            # Determine dynamic tag for dashboard feedback
            active_custom_filters = []
            if use_ema_filter == 1: active_custom_filters.append(f"EMA({ema_fast}/{ema_slow})")
            if use_vol_filter == 1: active_custom_filters.append(f"Vol(>{min_volume})")
            if use_consolidation == 1: active_custom_filters.append("Consol")
            if use_swing_run == 1: active_custom_filters.append("Swing")
            if use_base_pullback == 1: active_custom_filters.append("Base")
            
            setup_label = " | ".join(active_custom_filters) if active_custom_filters else "Pure Base Strategy"

            metadata = {
                "ticker": ticker.replace(".NS", ""),
                "price": round(last_close, 2),
                "change": change,
                "Volume": val,
                "ema9": round(l_ema_f, 2),
                "ema20": round(l_ema_s, 2),
                "vol_multiple": vol_multiple,
                "setup": setup_label
            }
            results.append(metadata)
                
        except Exception:
            continue

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