"""
Momentum Consolidation Scanner (High Tight Flag / VCP Style)
============================================================
Scans Indian stocks (NSE) for:
  1. Prior strong upward move (pole): >= 20% in last 40-60 sessions
  2. Price above 9 EMA and 20 EMA
  3. Tight consolidation (flag): range < 8% over last 5-30 sessions, above both EMAs
  4. Market cap filter: > 100 Crores (₹1,000,000,000)

Requirements:
    pip install yfinance pandas numpy requests beautifulsoup4 tqdm

Usage:
    python momentum_scanner.py

Results are saved to: momentum_results.csv
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
import time
from tqdm import tqdm

warnings.filterwarnings("ignore")

# ─── CONFIGURATION ────────────────────────────────────────────────────────────

CONFIG = {
    "market_cap_min_cr":  100,
    "ema_short":            9,
    "ema_long":            20,
    "data_period":       "3mo",
}
# ─── HELPER FUNCTIONS ─────────────────────────────────────────────────────────

def compute_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.rolling(period).mean()


def has_prior_up_move(close: pd.Series, cfg: dict) -> tuple[bool, float]:
    """
    Logic: Within the last `pole_lookback_sessions` bars, check if there was
    any rolling window of `pole_window_sessions` bars where price appreciated
    by at least `pole_min_gain_pct`%.
    
    Returns (True, max_gain_pct) if condition met.
    """
    lookback = cfg["pole_lookback_sessions"]
    window = cfg["pole_window_sessions"]
    min_gain = cfg["pole_min_gain_pct"]

    segment = close.iloc[-lookback:]
    if len(segment) < window:
        return False, 0.0

    max_gain = 0.0
    for i in range(len(segment) - window + 1):
        chunk = segment.iloc[i: i + window]
        gain = (chunk.iloc[-1] / chunk.iloc[0] - 1) * 100
        if gain > max_gain:
            max_gain = gain

    return max_gain >= min_gain, round(max_gain, 2)


def is_above_emas(close: pd.Series, ema9: pd.Series, ema20: pd.Series) -> bool:
    """
    Current price must be strictly above both 9 EMA and 20 EMA.
    """
    last_close = close.iloc[-1]
    return last_close > ema9.iloc[-1] and last_close > ema20.iloc[-1]


def is_tight_consolidation(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    ema9: pd.Series,
    ema20: pd.Series,
    cfg: dict
) -> tuple[bool, float, int]:

    max_sessions = cfg["consolidation_sessions"]
    min_sessions = cfg["consolidation_min_sessions"]
    max_range    = cfg["consolidation_range_pct"]

    best_range = float("inf")
    best_length = 0
    found = False

    for n in range(min_sessions, max_sessions + 1):
        if n > len(close):
            break

        seg_high  = high.iloc[-n:]
        seg_low   = low.iloc[-n:]
        seg_ema9  = ema9.iloc[-n:]
        seg_ema20 = ema20.iloc[-n:]

        hh        = seg_high.max()
        ll        = seg_low.min()
        range_pct = (hh - ll) / ll * 100

        # All lows must be above BOTH EMAs
        all_above = (seg_low >= seg_ema9).all() and (seg_low >= seg_ema20).all()

        if range_pct <= max_range and all_above and range_pct < best_range:
            best_range  = range_pct
            best_length = n
            found       = True

    return found, round(best_range if found else 0.0, 2), best_length


# ─── STOCK UNIVERSE ────────────────────────────────────────────────────────────

def get_nse_stock_list() -> list[str]:
    import requests, io
    
    url = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.nseindia.com",
    }
    
    session = requests.Session()
    session.get("https://www.nseindia.com", headers=headers, timeout=10)
    response = session.get(url, headers=headers, timeout=10)
    
    df = pd.read_csv(io.StringIO(response.text))
    df.columns = df.columns.str.strip()
    df = df[df["SERIES"].str.strip() == "EQ"]
    symbols = df["SYMBOL"].str.strip().tolist()
    
    print(f"Total NSE EQ stocks: {len(symbols)}")
    return [s + ".NS" for s in symbols]


# ─── MAIN SCANNER ─────────────────────────────────────────────────────────────

def scan_stock(ticker: str, cfg: dict) -> dict | None:
    """
    Run all screening criteria on a single stock.
    Returns a result dict if the stock passes, else None.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # ── Market Cap Filter ──────────────────────────────────────
        market_cap = info.get("marketCap", 0)
        min_cap = cfg["market_cap_min_cr"] * 1e7  # Crores to INR
        if not market_cap or market_cap < min_cap:
            return None

        market_cap_cr = round(market_cap / 1e7, 1)

        # ── Download OHLCV ─────────────────────────────────────────
        df = stock.history(period=cfg["data_period"])
        if df is None or len(df) < 60:
            return None

        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        # ── Compute EMAs ───────────────────────────────────────────
        ema9 = compute_ema(close, cfg["ema_short"])
        ema20 = compute_ema(close, cfg["ema_long"])

        # ── Criterion 1: Prior Up Move (The Pole) ─────────────────
        has_pole, pole_gain_pct = has_prior_up_move(close, cfg)
        if not has_pole:
            return None

        # ── Criterion 2: Above Both EMAs ──────────────────────────
        if not is_above_emas(close, ema9, ema20):
            return None

        # ── Criterion 3: Tight Consolidation (The Flag) ───────────
        consolidating, range_pct, consol_len = is_tight_consolidation(
            close, high, low, ema9, ema20, cfg
        )
        if not consolidating:
            return None

        # ── All criteria passed ────────────────────────────────────
        current_price = round(close.iloc[-1], 2)
        ema9_val = round(ema9.iloc[-1], 2)
        ema20_val = round(ema20.iloc[-1], 2)

        return {
            "Ticker": ticker.replace(".NS", ""),
            "Price (₹)": current_price,
            "Market Cap (Cr)": market_cap_cr,
            "Pole Gain (%)": pole_gain_pct,
            "Consol Range (%)": range_pct,
            "Consol Length (Days)": consol_len,
            "9 EMA": ema9_val,
            "20 EMA": ema20_val,
            "Above 9EMA": current_price > ema9_val,
            "Above 20EMA": current_price > ema20_val,
            "Scan Time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

    except Exception:
        return None


def run_scanner():
    print("=" * 60)
    print("  NSE Scanner — MarketCap > 100Cr | Above 9 & 20 EMA")
    print("=" * 60)

    universe = get_nse_stock_list()
    print(f"Scanning {len(universe)} stocks...\n")

    results = []

    for ticker in tqdm(universe, desc="Scanning"):
        try:
            stock = yf.Ticker(ticker)
            info  = stock.info

            market_cap = info.get("marketCap", 0)
            if not market_cap or market_cap < CONFIG["market_cap_min_cr"] * 1e7:
                continue

            df = stock.history(period=CONFIG["data_period"])
            if df is None or len(df) < 25:
                continue

            close = df["Close"]
            ema9  = compute_ema(close, CONFIG["ema_short"])
            ema20 = compute_ema(close, CONFIG["ema_long"])

            last_close = close.iloc[-1]
            if last_close > ema9.iloc[-1] and last_close > ema20.iloc[-1]:
                results.append({
                    "Ticker":           ticker.replace(".NS", ""),
                    "Price (₹)":       round(last_close, 2),
                    "Market Cap (Cr)": round(market_cap / 1e7, 1),
                    "9 EMA":           round(ema9.iloc[-1], 2),
                    "20 EMA":          round(ema20.iloc[-1], 2),
                    "Scan Time":       datetime.now().strftime("%Y-%m-%d %H:%M"),
                })

        except Exception:
            continue
        time.sleep(0.05)

    print(f"\n{'='*60}")
    if results:
        df_out = pd.DataFrame(results).sort_values("Market Cap (Cr)", ascending=False)
        print(f"✅  {len(results)} stocks above 9 & 20 EMA:\n")
        print(df_out.to_string(index=False))
        df_out.to_csv("ema_results.csv", index=False)
        print(f"\n📄  Saved to ema_results.csv")
    else:
        print("❌  No stocks matched.")
    print("=" * 60)

run_scanner()
