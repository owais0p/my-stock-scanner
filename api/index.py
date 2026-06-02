from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import io
import os
from datetime import datetime

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_nse_universe():
    try:
        url = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(url, headers=headers, timeout=15)
        df = pd.read_csv(io.StringIO(res.text))
        df.columns = df.columns.str.strip()
        # Filter for EQ series and take top 500
        symbols = df[df["SERIES"].str.strip() == "EQ"]["SYMBOL"].str.strip().head(500).tolist()
        return [s + ".NS" for s in symbols]
    except Exception as e:
        print(f"Error fetching universe: {e}")
        return ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS"]

@app.get("/api/scan")
async def run_scan():
    tickers = get_nse_universe()
    
    # Batch download using yfinance threads
    data = yf.download(tickers, period="3mo", group_by="ticker", threads=True, progress=False)
    
    results = []
    
    for ticker in tickers:
        try:
            # Handle yfinance multi-index or single index depending on download result
            if ticker not in data.columns.levels[0] if isinstance(data.columns, pd.MultiIndex) else [ticker]:
                continue
                
            df = data[ticker].dropna()
            if len(df) < 25: continue
            
            close = df["Close"]
            ema9 = close.ewm(span=9, adjust=False).mean()
            ema20 = close.ewm(span=20, adjust=False).mean()
            
            last_close = close.iloc[-1]
            l_ema9 = ema9.iloc[-1]
            l_ema20 = ema20.iloc[-1]
            
            # Optimized mathematical check
            if last_close > l_ema9 and last_close > l_ema20:
                # Score based on proximity to 20 EMA (lower pct difference = tighter = higher score for setup)
                # We use 100 - pct_diff to make higher values better
                pct_diff = ((last_close - l_ema20) / l_ema20) * 100
                score = round(100 - pct_diff, 2)
                
                results.append({
                    "ticker": ticker.replace(".NS", ""),
                    "price": round(last_close, 2),
                    "ema9": round(l_ema9, 2),
                    "ema20": round(l_ema20, 2),
                    "score": score,
                    "setup": "Momentum Breakout" if last_close > close.iloc[-20:].max() * 0.98 else "EMA Support"
                })
        except:
            continue
            
    # Sort results descending by score
    sorted_results = sorted(results, key=lambda x: x['score'], reverse=True)
    
    return {
        "status": "success",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "count": len(sorted_results),
        "data": sorted_results
    }

# Mount static files for the frontend
app.mount("/", StaticFiles(directory="public", html=True), name="public")

if __name__ == "__main__":
    import uvicorn
    # Hugging Face Spaces expects port 7860
    uvicorn.run(app, host="0.0.0.0", port=7860)
