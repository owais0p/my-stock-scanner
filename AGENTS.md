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

## 🎨 Design System (Cyber-Terminal)
- **Theme**: Pure Deep Obsidian (`#060810`) background, Emerald (`#10B981`) accents.
- **Interactive Signature**: High-intensity neon green (`#00ff9d`) glow on hover for premium elements.
- **Typography**: Inter (UI), JetBrains Mono (Data), Iceland (Brand).
- **Transitions**: Hardware-accelerated `.theme-transition` class; NO universal wildcard transitions for performance.

## 📱 Key UI Components
- **Follow Us Hub**: Header-pinned social links (Telegram/Instagram) with neon hover effects and mobile adaptive layout (icons-only on mobile).
- **BSE Universe Toggle**: Header-pinned checkbox switch ("Scan Combined Market (NSE + BSE Exclusives)") to dynamically switch the target market universe scan to a union of the active NSE segment and BSE-exclusive stocks.
- **Tactical Sort**: Pill-shaped sorting button for dynamic, client-side re-rendering of results by % change.
- **Sentinel Monitor**: A pulsing status indicator signifying the active data link.

## ⚙️ Development Commands
- **Local Run**: `py -m uvicorn api.index:app --reload --port 7860`
- **Data Export**: Client-side CSV generation using Browser Blobs.
- Charts: Embedded interactive ApexCharts candlestick + volume charts inside cards, supporting TradingView-style vertical scaling, right Y-axis scale price badges, and timeframe switcher (1D/1W/1M) with server-side dynamic fetching and resampling.
- Card Metadata badges: Card headers display `1D` and dynamic `NSE` or `BSE` monospace metadata badges (`text-slate-400 bg-slate-800/50 px-1.5 py-0.5 rounded text-[10px]`) inline next to the ticker name.

## 📈 Chart Annotation & Layout System
- **Dashed Horizontal CMP Line**: Drawn using a line-only Y-axis annotation at `annotations.yaxis[0]` with `label.show: false` to force the dashed line to stretch 100% across the plotting area up to the right axis border.
- **Y-Axis Price Badge**: Drawn using a secondary transparent-border annotation at `annotations.yaxis[1]` with `label.position: 'right'`, `label.textAnchor: 'start'`, and `label.offsetX: 52` to overlay a solid emerald green (`#10B981`) text badge exactly on the numeric scale without cluttering the candlestick canvas.
- **Timeframe Selector (1D / 1W / 1M)**: Executes an asynchronous backend fetch to query resampled historical OHLCV data. The backend retrieves the appropriate yfinance period (`6mo` for `1D`, `3y` for `1W`, `10y` for `1M`), processes Monday-aligned weekly and Month Start-aligned monthly grouping in Python, and returns exactly 120 candles. Clicks trigger dynamic series updates with `animate: false`.
- **Y-Axis Volume Scale Lock**: Explicitly locks Volume Y-axis bounds (`min: 0, max: function(max) { return max * 3.0; }`) to constrain volume bars to the bottom 33% floor height, keeping them fully visible.
- **Floating Legend & Grid Padding**: The legend floats on the top-right (`position: 'top', horizontalAlign: 'right', floating: true, offsetY: -10, offsetX: -10`) inline with controls. Grid bottom padding is set to `25` to stretch active bounds. Chart container wrappers are expanded to `h-[400px]` in list view and `h-[360px]` in grid view.

---
*Last Updated: June 25, 2026*
