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



def get_bse_universe():
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        n500_url = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"
        n500_res = requests.get(n500_url, headers=headers, timeout=10)
        n500_df = pd.read_csv(io.StringIO(n500_res.text))
        return [s.strip() + ".BO" for s in n500_df["Symbol"].str.strip().tolist()]
    except Exception as e:
        print(f"BSE Universe Error: {e}")
        return ["RELIANCE.BO", "TCS.BO", "INFY.BO", "HDFCBANK.BO", "ICICIBANK.BO"]

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
    
    # Toggle Switches (1 = ON, 0 = OFF)
    use_ema_filter: int = Query(1),
    use_vol_filter: int = Query(1),
    use_consolidation: int = Query(1),
    use_swing_run: int = Query(1),
    use_base_pullback: int = Query(1),
    scan_bse: int = Query(0)
):
    if ticker:
        return await get_historical_ticker_route(ticker, timeframe)

    if timeframe == "1W":
        period = "3y"
    elif timeframe == "1M":
        period = "10y"
    else:
        period = "6mo"

    if scan_bse == 1:
        tickers = get_bse_universe()
    else:
        tickers = get_nse_universe(universe)
    data = yf.download(tickers, period=period, group_by="ticker", threads=True, progress=False)
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
            
            # --- CRITICAL: Slicing for scan calculations ---
            # If the stock has limited history (Recent IPO tracking window)
            is_ipo = 30 <= len(df) < 150
            if is_ipo:
                df_calc = df.copy()
            else:
                df_calc = df.iloc[-120:]
                
            # Validation guard gate
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
                if len(df_calc) >= (consolidation_days + 1):
                    consol_patch = close.iloc[-(consolidation_days + 1) : -1]
                    highest_high = consol_patch.max()
                    lowest_low = consol_patch.min()
                    actual_range_pct = ((highest_high - lowest_low) / lowest_low) * 100
                    if actual_range_pct > consolidation_range: continue

            # 4. MODULAR SWING RUN FILTER LOGIC
            if use_swing_run == 1:
                lowest_swing_low = df_calc["Low"].iloc[-20:].min()
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