# AAPNATRADER: Architectural & Technical Overview

This document provides a comprehensive breakdown of the engineering decisions, tech stack, and logic behind the AAPNATRADER institutional momentum deck.

## 1. Core Infrastructure & Hosting
- **Platform**: Hugging Face Spaces (Docker SDK).
- **Rationale**: Persistent, long-running processes allow for multi-threaded scanning of large market slices without serverless timeout constraints.
- **Environment**: Python 3.12 (configured for local consistency) in a Docker container.

## 2. Backend Engine (FastAPI & Python)
- **Framework**: FastAPI (Asynchronous high-performance engine).
- **Data Sourcing**: `yfinance` for multi-threaded market data retrieval.
- **Scanning Matrix (Universe Segmentation)**:
    - **Chunk 1 & 2 (Premium)**: Derived from the **Nifty 500** list. Segmented into two 250-symbol blocks for high-liquidity institutional focus.
    - **Chunk 3, 4 & 5 (Alpha Pools)**: Derived from the broader NSE equity market (excluding Nifty 500). Split evenly into three segments to surface under-the-radar micro-cap and nano-cap opportunities.
- **Logic Parameters**:
    - `strategy`: Supports `current` (MOMENTUM VELOCITY: 9/20 EMA Breakouts) and `vcp` (VCP MATRIX: Minervini Compression).
    - `universe`: Targets specific market slices from `chunk1` to `chunk5`.
- **Performance Optimizations**:
    - **Fast Price Lookup**: Implements `fast_info` metadata retrieval with a strict **0.5s thread-based timeout** to eliminate network-loop lag.
    - **Historical Volume Fallback**: Intelligent lookback logic that scans for the last non-zero trading session's volume, ensuring data consistency during off-market hours.
- **Institutional Guardrails**:
    - **Price Floor**: Strict `if last_close < 50` rule to eliminate high-risk penny stocks.
    - **Liquidity Barrier**: Enforces a minimum **100k average daily volume** (20-day baseline) to ensure tradeability.
- **Momentum Engines**:
    - **Momentum Velocity**: Scores based on 9/20 EMA support and proximity to recent highs.
    - **VCP Matrix**: Implements Mark Minervini's Volatility Contraction Pattern. Tracks structural tightening across three blocks (T1 > T2 > T3) with supply-absorption volume verification.

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
    - **Background Layering**: 3x dense technical textures (Cyber-Grid for Dark, Dot-Matrix for Light) isolated on a fixed pseudo-element to prevent overlapping with content.
    - **Tactile Interactions**: Cubic-bezier transitions, hover-lift effects, and mechanical click feedback on all buttons and cards.
- **UX Features**:
    - **Advanced Signal Cards**: 4px left-accent strips, floating shadow profiles, and sleek HUD-style tactical badges.
    - **Section Masking**: Section headers use opaque background shielding to ensure 100% legibility above dense textures.
    - **Native Tab Redirection**: Global click interceptor launches TradingView charts directly in new tabs for zero-latency analysis.
    - **Client-Side Export**: Browser-side CSV generation (including Volume data) using Blobs.

## 4. Deployment Strategy
- **Automation**: GitHub integration with Hugging Face for automated Docker builds.
- **Continuity**: Local environment configured with custom Python library paths to match production requirements (Port 7860).
