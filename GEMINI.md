# AAPNATRADER Project Instructions

## Architecture & Tech Stack
- **Backend**: FastAPI (Python) running in a Docker container.
- **Frontend**: Single-Page Application (SPA) using HTML5, Vanilla JavaScript, and Tailwind CSS.
- **Deployment**: Hugging Face Spaces (Docker SDK).
- **Market Data**: `yfinance` for free, parallelized NSE & BSE market data.

## Project Structure
- `api/index.py`: Core FastAPI backend. Handles the NSE/BSE universe fetching, parallel stock scanning, and momentum breakout logic.
- `public/index.html`: Unified frontend containing UI structure (HTML), styling (Tailwind CSS via CDN), interaction logic (JavaScript), and interactive TradingView charts. Includes the **Advanced Configuration Console**.
- `Dockerfile`: Production-ready container configuration for Hugging Face Spaces.
- `requirements.txt`: Python dependencies.
- `public/logo.svg`: Official vector logo (Ignored by Git, integrated via Data URI).

## Key Workflows
- **Scanning Logic**: Triggered via `/api/scan`. Downloads data for the targeted NSE/BSE universe segment in parallel.
- **BSE Universe Toggle**: Includes a "Scan Combined Market (NSE + BSE Exclusives)" checkbox in the header which targets the union of the active NSE segment and BSE-exclusive stock tickers (resolved using Yahoo Finance `.BO` suffix mappings and de-duplicated against full NSE listings).
- **IPO Base Bypassing Guard Gate**: Automatically catches recent IPOs with limited history (`30 <= len(df) < 150`) to bypass 60-day baseline limits and long-term EMA filters, running consolidation and VCP analysis on the available listing history.
- **Unified Live Filters Matrix**: The backend uses a centralized gate system to evaluate dynamic user inputs (`ema_fast`, `ema_slow`, `min_volume`, `consolidation`, `swing_run`, `base_pullback`, `pullback_offset`, `swing_gate_pct`, `weekly_close_n`, `use_pullback_zone`, `use_auto_pullback`, `use_weekly_close_gate`) BEFORE applying strategy-specific logic. Advanced filters are strictly disarmed (unchecked) by default on app boot.
- **2nd Last Pullback (Manual & Auto)**: Manual mode uses `pullback_offset` to check if `Price >= Lowest(Low, 20)[Offset] * (1 + Swing Gate)`. Auto mode programmatically resolves $L_1$ near the 20 EMA in the last 25 days, locates the previous structural pivot floor $L_2$ before $L_1$, and checks if the current close has broken out above $L_2 \times \text{upper\_multiplier}$ (where $\text{upper\_multiplier} = 1 + \text{Swing Gate Value}$ or 1.15 by default).
- **Weekly Close Gate**: Checks if the current weekly close is greater than $N$ weeks ago close. If active, it automatically resamples daily candles and extends the yfinance download period dynamically for large lookbacks.
- **19-Sector Custom Allocation Schema & Offline Market Cap Engine**: Maps sub-sectors like `IT - Software`/`IT - Services` to parent `IT` sector, auto-ancillaries/commercial vehicles to `AUTO`, and biotechnology/hospitals to `PHARMA & HEALTH`. Downloads BSE scrip capital data (`scrip.zip`) at startup to map outstanding shares locally with a 99.3%+ match rate (5,168 tickers), computing market caps inline inside the scan loop:
  $$\text{Market Cap (Cr)} = \frac{\text{Shares in Lakhs} \times \text{Last Close}}{100}$$
  Standard scans query yfinance using a parallel chunked downloader (batches of 150) to completely avoid rate limits. JavaScript calls use `encodeURIComponent(sector)` to encode ampersands (`&`) to prevent query parameter parsing bugs.
- **Filtering**:
  - *MOMENTUM VELOCITY* (Strategy: `current`): Inherits the global filter matrix and enforces a ?50 price floor.
  - *MOMENTUM OPEN 2.0* (Strategy: `momentum_open_30`): High-alpha engine that directly leverages the global dynamic alpha engine without hardcoded constraints.
  - *Base Strategy Fallback*: If the user toggles off ALL advanced filters, the engine falls back to a strict baseline: 100k average volume minimum and a hard 9/20 EMA crossing rule.
- **Indices API Endpoint (`/api/live_indices`)**: FastAPI backend route fetching Nifty 50, Sensex, Bank Nifty, Nifty IT, Nifty 500, India VIX, and USD/INR dynamically from Yahoo Finance with parallel workers.
- **Local Preview**: Use `py -m uvicorn api.index:app --reload --port 7860` for local development.
- **Performance**: Theme toggles are optimized via hardware-accelerated `.theme-transition` classes; avoid universal `*` transitions.
- **Data Export**: Client-side CSV generation using Browser Blobs for zero-cost data handling.
- **Chart Analysis**: Renders interactive ApexCharts candlestick + volume charts inline, supporting vertical scaling via Y-axis drag and right Y-axis scale price badges. Candles display standard green (bullish) and red (bearish) colors. Automatically calculates and displays the 9 EMA (Premium Light Blue `#3b82f6`) and 20 EMA (Amber Orange `#f59e0b`) overlay lines on the candlestick charts. Includes TradingView-style interactive timeframe selection options (1D, 1W, 1M) powered by server-side dynamic fetching and resampling (using `6mo`/`3y`/`10y` database periods to serve exactly 120 candles).
- **Y-Axis Volume & EMA Scale Lock**: When changing timeframes or interacting with the chart, the Volume Y-axis scale is explicitly locked (`min: 0, max: function(max) { return max * 1.35; }`) to keep the volume bars constrained to occupy a 20-25% height ratio of the viewport. All EMA lines are synced to the primary `Price` Y-axis scale via a 4-item `yaxis` configuration array to scale symmetrically with the candlesticks.

## Design Standards
- **Brand**: AAPNA (White/Slate) TRADER (Amber) two-tone identity.
- **Theme**: Pure Deep Obsidian (#060810) background, slate-200 text, Bloomberg Amber-400 (#FFC400) brand accent highlights. Volume breakouts (multiplier >= 2.0) are highlighted with green (`#10B981`), and percentage changes use dynamic green/red.
- **Branding**: Official logo is integrated as an inline SVG with `currentColor` support for theme-aware high contrast. Favicon updates dynamically via JS on theme toggle.
- **Typography**: Inter for UI headers/body, JetBrains Mono for financial data, metrics, and tickers.
- **Components**: Responsive dual-pane terminal grid (MD breakpoint) with a pinned command center and a results deck. Interactive UI elements use `cyber-checkbox` styling. Card headers contain `1D` and dynamic `NSE` or `BSE` monospace metadata badges next to the stock name headers.
- **Bloomberg Header Console**: Pinned console strip displaying system clock (IST) and engine state, combined with a dynamic infinite loop ticker tape marquee below the header showing live index quotes.
- **Chart Axis & Legend layout**: Uses a dual-annotation pattern on the Y-axis: index 0 renders the 100% width dashed CMP line with its label disabled, and index 1 renders the text price tag offset to overlay directly on the Y-axis scale (`offsetX: 62`). Both CMP line and price badge are dynamically colored green/red matching price direction. The legend is configured to float inline at the top-left corner (`position: 'top', horizontalAlign: 'left', floating: true, offsetY: -5, offsetX: 10`) with `grid.padding.bottom` set to `25` to prevent vertical compression or baseline volume bar clipping. Chart containers are set to `h-[400px]` in list view and `h-[360px]` in grid view.

## Deployment Notes
- Hugging Face Spaces expects the app to run on port `7860`.
- Docker configuration ensures all Python dependencies are isolated and consistent.
- Using `Symbol Overview` widget script strategy for charts to bypass Hugging Face domain constraints.

