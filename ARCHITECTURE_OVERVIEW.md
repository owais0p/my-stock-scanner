# AAPNATRADER: Architectural & Technical Overview

This document provides a comprehensive breakdown of the engineering decisions, tech stack, and logic behind the AAPNATRADER institutional momentum deck.

## 1. Core Infrastructure & Hosting
- **Platform**: Hugging Face Spaces (Docker SDK).
- **Rationale**: Persistent, long-running processes allow for multi-threaded scanning of large market slices without serverless timeout constraints.
- **Environment**: Python 3.12 (configured for local consistency) in a Docker container.

## 2. Backend Engine (FastAPI & Python)
- **Framework**: FastAPI (Asynchronous high-performance engine).
- **Data Sourcing**: `yfinance` for multi-threaded market data retrieval supporting National Stock Exchange (NSE) and Bombay Stock Exchange (BSE) via `.NS`/`.BO` ticker suffix routing.
- **Scanning Matrix (Universe Segmentation)**:
    - **Chunk 1 & 2 (Premium)**: Derived from the **Nifty 500** list. Segmented into two 250-symbol blocks for high-liquidity institutional focus.
    - **Chunk 3, 4 & 5 (Alpha Pools)**: Derived from the broader NSE equity market (excluding Nifty 500). Split evenly into three segments to surface under-the-radar micro-cap and nano-cap opportunities.
    - **Combined Market Universe**: When the "Scan Combined Market (NSE + BSE Exclusives)" toggle is active, uvicorn fetches a union of the active NSE segment and BSE-exclusive stock tickers.
- **Logic Parameters**:
    - `strategy`: Supports `current` (MOMENTUM VELOCITY), `vcp` (VCP MATRIX), `momentum_2` (MOMENTUM 2), and `vcp_2` (MOMENTUM VELOCITY 2.0).
    - `universe`: Targets specific market slices from `chunk1` to `chunk5`.
    - `scan_combined`: Switch flag triggering uvicorn scan of the combined market (NSE segment + BSE-exclusive stocks).
    - `pullback_offset`, `swing_gate_pct`, `use_pullback_zone`: Configure the manual 2nd swing low pullback zone floor check.
    - `use_auto_pullback`: Toggles programmatic $L_1$ proximity EMA pivot resolving and $L_2$ structural support search.
    - `weekly_close_n`, `use_weekly_close_gate`: Toggles dynamic weekly resampling and lagging close strength validation.
- **Performance Optimizations**:
    - **Fast Price Lookup**: Implements `fast_info` metadata retrieval with a strict **0.5s thread-based timeout** to eliminate network-loop lag.
    - **Historical Volume Fallback**: Intelligent lookback logic that scans for the last non-zero trading session's volume, ensuring data consistency during off-market hours.
    - **Uniform Batch Loading**: Standardized all engines to use the high-efficiency `4mo` historical data baseline to maximize execution speed and ensure glitch-free pipeline results.
- **Institutional Guardrails**:
    - **Price Floor**: Strict `if last_close < 50` rule (fallback to 30 for Momentum Open 2.0) to eliminate high-risk penny stocks.
    - **Liquidity Barrier**: Enforces a minimum **100k average daily volume** (20-day baseline) to ensure tradeability.
    - **IPO Base Bypassing Guard Gate**: Automatically identifies recent IPOs with limited data history (`30 <= len(df) < 150`) to bypass 60-bar constraints and long-term EMA filters, running consolidation/VCP checks strictly on listing day history to capture new market breakouts instantly.
- **Momentum Engines**:
- **Momentum Velocity**: Scores based on 9/20 EMA support and proximity to recent highs.
- **Momentum Open 2.0**: A specialized high-alpha engine with a relaxed ₹30 price floor and no liquidity constraints, designed for early-session volatility capture.
- **VCP Matrix**: Implements Mark Minervini's Volatility Contraction Pattern. Tracks structural tightening across three blocks (T1 > T2 > T3) with supply-absorption volume verification.
    - **Momentum 2**: Enforces tight consolidations above 9 & 20 EMA (3-day spread <= 7.0%) combined with volume dryup (< 85% of 20-day average).
    - **Momentum Velocity 2.0 (vcp_2)**: A wide-funnel ruleset enforcing short-term trend (Close strictly above daily 9 and 20 EMA) and relaxed squeeze limit (5-day high-to-low spread <= 15.0%) with all volume contraction filters deactivated.

## 3. Frontend Design (Institutional Terminal UI)
- **Architecture**: Single-Page Application (SPA) using Vanilla JavaScript and Tailwind CSS.
- **Tactical Workspace**:
    - **Ticker Search**: High-contrast monospace field for instant client-side filtering of results without additional API overhead.
    - **Strategy Switcher**: High-response toggle for swapping between Momentum and VCP engines.
    - **Market Universe Selector**: Cyber-tactical dropdown for targeting specific market cap chunks.
    - **Dynamic Matrix Display**: Real-time UI label updates reflecting the active market segment.
    - **Theme System**: Premium Dark Obsidian / Slate Workstation toggle with `localStorage` persistence and high-contrast accessibility overrides.
    - **Performance Optimization (Theme)**: Implements a targeted, hardware-accelerated `.theme-transition` class with `will-change: background-color, border-color`. Universal wildcard transitions (`*`) are explicitly removed to ensure 0ms lag even with thousands of dynamic results populated in the DOM.
    - **Background Layering**: Optimized dual-layer background pseudo-elements (`::before` and `::after`) using opacity cross-fades for silky-smooth texture transitions.
    - **Terminology**: Swapped "Entry" for **"CMP"** (Current Market Price) for professional clarity.
    - **Volume Formatting**: Custom utility handles large values with suffixes (K, L, Cr) and provides a visual fallback (**<1K**) for sparse historical data.
    - **Typography**: 'Iceland' (Google Fonts) for branding; 'JetBrains Mono' for metrics; 'Inter' for UI.
    - **Branding Assets**:
        - **Official Logo**: High-fidelity custom SVG featuring a breakout-themed 'A' with Emerald-400 accents.
        - **Deployment**: Integrated via Base64 Data URIs in the header, hero section, and browser favicon to ensure zero-latency loading and cross-environment reliability.
    - **Background Layering**: 3x dense technical textures (Cyber-Grid for Dark, Dot-Matrix for Light) isolated on a fixed pseudo-element to prevent overlapping with content.
    - **Tactile Interactions**: Cubic-bezier transitions, hover-lift effects, and mechanical click feedback on all buttons and cards.
- **UX Features**:
    - **Advanced Signal Cards**: 4px left-accent strips, floating shadow profiles, and sleek HUD-style tactical badges.
    - **Section Masking**: Section headers use opaque background shielding to ensure 100% legibility above dense textures.
    - **Native Tab Redirection**: Global click interceptor launches TradingView charts directly in new tabs for zero-latency analysis.
    - **Client-Side Export**: Browser-side CSV generation (including Volume data) using Blobs.

## 4. Interactive Charting & Resampling Engine
- **Canvas Integration**: Embedded interactive ApexCharts candlestick + volume charts inside cards, supporting TradingView-style vertical scaling and right Y-axis scale price badges.
- **Server-Side Timeframe Selector**: Integrates server-side weekly and monthly candle resampling. When the user switches timeframes (1D / 1W / 1M), the frontend triggers an async fetch call back to the backend endpoint passing the respective timeframe flag. The backend downloads a larger historical matrix (`6mo` for `1D`, `3y` for `1W`, `10y` for `1M`), groups the daily rows (using Monday-aligned weeks and Month Start-aligned months), slices it to exactly 120 candles, and updates the series instantly using `chart.updateSeries` with `animate: false`.
- **Y-Axis Volume Scale Lock**: Automatically enforces a volume-constraining scale (`min: 0, max: function(max) { return max * 3.0; }`) when switching timeframes, keeping volume bars strictly bound to the bottom 33% height of the chart floor.
- **Layout & Padding Optimizations**:
  - **Repositioned Legend**: Legend container floats on the top-right (`position: 'top', horizontalAlign: 'right', floating: true, offsetY: -10, offsetX: -10`) to sit inline next to timeframe switchers without claiming a dedicated horizontal row block.
  - **Expanded Grid Padding**: Increased bottom grid padding (`grid.padding.bottom: 25`) to stretch the active layout bounds.
  - **Height Constraints**: Expanded card height containers to `h-[400px]` (List View inline charts) and `h-[360px]` (Grid/Maze View card charts) to ensure volume bars sit cleanly without vertical clipping.
  - **Event Shielding**: Dynamic buttons and toolbars catch and call `e.stopPropagation()` on mouse events to prevent interference with chart-dragging and scale-panning handlers.

## 5. Deployment Strategy
- **Automation**: GitHub integration with Hugging Face for automated Docker builds.
- **Continuity**: Local environment configured with custom Python library paths to match production requirements (Port 7860).
