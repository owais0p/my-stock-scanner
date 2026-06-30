# AAPNATRADER | Application Knowledge Base

This document serves as a persistent context reference for AI agents working on the AAPNATRADER Terminal Deck.

## 🚀 Overview
AAPNATRADER is a high-performance, institutional-grade stock scanning dashboard designed for the National Stock Exchange (NSE) and Bombay Stock Exchange (BSE). It focuses on identifying high-alpha momentum breakouts using parallelized market data processing.

## 🛠 Tech Stack
- **Backend**: FastAPI (Python)
- **Frontend**: Single-Page Application (HTML5, Vanilla JS, Tailwind CSS via CDN)
- **Market Data**: `yfinance` (NSE & BSE integration via `.NS` and `.BO` suffix resolution)
- **Deployment**: Dockerized (optimized for Hugging Face Spaces port 7860)

## 📊 Core Metrics & Logic
### Volume Multiple (`vol_multiple`)
- **Definition**: The ratio of the current day's trading volume to the 20-day average volume.
- **Significance**: Indicators institutional activity. Multiples ≥ 2.0 trigger a **Neon Green Glow** on the UI to signify a volume breakout.
- **Backend Logic**: `avg_vol_20 = volume.iloc[-20:].mean()`; `vol_multiple = current_vol / avg_vol_20`.

### Scanning Strategies
1. **MOMENTUM VELOCITY (Institutional Grade)**:
   - Price > ₹50
   - 20-day Average Volume > 100,000
   - Price > 9 EMA AND Price > 20 EMA
2. **MOMENTUM OPEN 2.0 (Alpha Early-Breakout)**:
   - Price > ₹30
   - No liquidity constraints (Early volatility focus)
   - Price > 9 EMA AND Price > 20 EMA

### IPO Base Bypassing Guard Gate
- **Logic**: For stocks with limited history (`30 <= len(df) < 150`), standard minimum length limits and long-term EMA checks are bypassed to prevent rejection.
- **VCP/Consolidation**: Consolidation and Volatility Contraction Pattern (VCP) analysis is executed strictly on the available lifecycle data since Listing Day High.

### 2nd Last Pullback Zone & Auto Pullback
- **Manual 2nd Pullback**: Measures distance from the previous-to-previous swing low $L_2$ (shifted by a user-configured day offset):
  $$L_2 = \text{Lowest}(Low, 20)[\text{Offset}]$$
  Condition: $\text{Price} \ge L_2 \times (1 + \text{Swing Gate Value})$.
- **Auto 2nd Pullback**: Automatically detects $L_1$ closest to the 20 EMA in the last 25 days, scans for the most recent structural pivot low $L_2$ before $L_1$ (minimum in a 5-day window), and checks if the price has broken out above the swing gate threshold (where the threshold is the user's Swing Gate Value, defaulting to 15% if 0):
  $$\text{Price} > L_2 \times \text{upper\_multiplier}$$

### Chartink Style Weekly Close Gate
- **Logic**: Validates structural close strength over weeks: $\text{Weekly Close} > \text{Weekly Close}[N]$ (where $N$ is user-configurable "Weeks Number"). It resamples historical daily data to weekly candles and checks the $N$-week lag.

### 19-Sector Custom Allocation Schema & Real-Time Local Market Cap Calculations
- **Sector Mapping**: Groups all resolved tickers into 19 custom allocation keys. Sub-sectors like `IT - Software`, `IT - Services`, and `IT - Hardware` are merged under the parent `IT` sector, Commercial Vehicles/Ancillaries under `AUTO`, and Pharmaceuticals/Healthcare under `PHARMA & HEALTH`.
- **Local Outstanding Shares Database**: Rather than making individual queries to yfinance, the backend downloads the BSE capital list (`scrip.zip` containing `CI.txt`) at startup and maps the outstanding shares in lakhs to tickers. This yields a 99.3%+ matching rate (5,168 mapped tickers).
- **Fast Local Calculations**: Market capitalization is calculated locally inside the scan loop to eliminate API overhead:
  $$\text{Market Cap (Cr)} = \frac{\text{Shares in Lakhs} \times \text{Last Close}}{100}$$
- **Parallel Chunked Downloader**: Standard scans are divided into batches of 150 to query yfinance concurrently, avoiding URL length and rate limit restrictions.
- **URL Parameter Encoding**: JavaScript fetch URLs wrap the sector name in `encodeURIComponent(sector)` to ensure sectors containing special characters like `&` are query-parsed as a single parameter by the FastAPI backend.

## 🎨 Design System (Cyber-Terminal)
- **Theme**: Pure Deep Obsidian (`#060810`) background, Bloomberg Amber/Yellow (`#FFC400`) accents, slate-200 text.
- **Interactive Signature**: High-intensity amber (`#FFC400`) glow on hover for premium elements. Volume breakouts (multiplier >= 2.0) are highlighted with green (`#10B981`), and percentage changes use dynamic green/red.
- **Typography**: Inter (UI), JetBrains Mono (Data), Iceland (Brand).
- **Transitions**: Hardware-accelerated `.theme-transition` class; NO universal wildcard transitions for performance.

## 📱 Key UI Components
- **Follow Us Hub**: Header-pinned social links (Telegram/Instagram) with neon hover effects and mobile adaptive layout (icons-only on mobile).
- **BSE Universe Toggle**: Header-pinned checkbox switch ("Scan Combined Market (NSE + BSE Exclusives)") to dynamically switch the target market universe scan to a union of the active NSE segment and BSE-exclusive stocks.
- **Bloomberg Terminal Summary Console**: Header panel showing market segment, active strategy engine mode with a blinking cursor, and real-time session clock (IST).
- **Dynamic Infinite Loop Ticker Tape**: Marquee scrolling tape below the header showing live indexes (Nifty 50, Sensex, Bank Nifty, Nifty IT, Nifty 500, India VIX, USD/INR) synced via background polling to the FastAPI backend `/api/live_indices` route.
- **Tactical Sort**: Pill-shaped sorting button for dynamic, client-side re-rendering of results by % change.
- **Sentinel Monitor**: A pulsing status indicator signifying the active data link.

## ⚙️ Development Commands
- **Local Run**: `py -m uvicorn api.index:app --reload --port 7860`
- **Data Export**: Client-side CSV generation using Browser Blobs.
- Charts: Embedded interactive ApexCharts candlestick + volume charts inside cards, supporting TradingView-style vertical scaling, right Y-axis scale price badges, and timeframe switcher (1D/1W/1M) with server-side dynamic fetching and resampling. Candles display traditional green (bullish) and red (bearish) colors.
- Card Metadata badges: Card headers display `1D` and dynamic `NSE` or `BSE` monospace metadata badges (`text-slate-400 bg-slate-800/50 px-1.5 py-0.5 rounded text-[10px]`) inline next to the ticker name.

## 📈 Chart Annotation & Layout System
- **Dashed Horizontal CMP Line**: Drawn using a line-only Y-axis annotation at `annotations.yaxis[0]` with `label.show: false` to force the dashed line to stretch 100% across the plotting area up to the right axis border. Color is dynamic green (`#10B981`) or red (`#ef5350`) matching price movement.
- **Y-Axis Price Badge**: Drawn using a secondary transparent-border annotation at `annotations.yaxis[1]` with `label.position: 'right'`, `label.textAnchor: 'start'`, and `label.offsetX: 62` to overlay a solid text price badge exactly on the numeric scale. The badge background is dynamically colored green (`#10B981`) or red (`#ef5350`) matching price movement.
- **Timeframe Selector (1D / 1W / 1M)**: Executes an asynchronous backend fetch to query resampled historical OHLCV data. The backend retrieves the appropriate yfinance period (`6mo` for `1D`, `3y` for `1W`, `10y` for `1M`), processes Monday-aligned weekly and Month Start-aligned monthly grouping in Python, and returns exactly 120 candles. Clicks trigger dynamic series updates with `animate: false`.
- **9 EMA & 20 EMA Line Overlays**: Plotted directly over the candlestick series. The 9 EMA uses color `#3b82f6` (Premium Light Blue) and the 20 EMA uses color `#f59e0b` (Amber Orange) with a stroke width of `1.5px` for both wicks/borders and line indicators. The chart series array accepts 4 inputs in sequence: `Price` (candlestick), `9 EMA` (line), `20 EMA` (line), and `Volume` (bar).
- **Y-Axis Price Axis Sync Gating**: All chart interaction events (zoomed, scrolled, scaled, dragged, timeframe-switched, double-clicked) must specify a 4-item `yaxis` configuration array: the first three configurations match `seriesName: 'Price'` (with the second and third configurations hidden via `show: false`) to force the EMA lines to scale symmetrically with the candlesticks, and the fourth matches `seriesName: 'Volume'`.
- **Y-Axis Volume Scale Lock**: Explicitly locks Volume Y-axis bounds (`min: 0, max: function(max) { return max * 1.35; }`) to scale volume bars dynamically to occupy a full 20-25% height ratio of the active viewport.
- **Floating Legend & Grid Padding**: The legend floats on the top-left (`position: 'top', horizontalAlign: 'left', floating: true, offsetY: -5, offsetX: 10`) inline with controls. Grid bottom padding is set to `15` to stretch active bounds and give the expanded bars immediate room to breathe.

---
*Last Updated: June 30, 2026*
