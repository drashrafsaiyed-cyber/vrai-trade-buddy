# VRAI Trade Buddy 🤖📈

AI-powered F&O trading companion for Indian markets.
Built by Ashraf | VRAI AI Automations

## Features
- 🌅 **Morning Brief** — 8:30 AM daily market overview
- ⚡ **Gamma Blast Scanner** — Real-time OI wall break detection
- 🎯 **BTST Scanner** — 2 PM daily best setup finder
- 💬 **2-Way Chat** — Talk to buddy anytime
- 📊 **Live OI Walls** — Nifty, BankNifty, Sensex
- 💰 **FII/DII Tracking** — Daily flow monitoring
- 🔔 **Telegram Alerts** — (Add tomorrow after ban lifted)

## Setup

### 1. Clone & Install
```bash
git clone https://github.com/YOUR_USERNAME/vrai-trade-buddy
cd vrai-trade-buddy
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env and add your NVIDIA API key
```

### 3. Run Locally
```bash
python main.py
# Open http://localhost:8000
```

### 4. Deploy on Render
1. Push to GitHub
2. Connect repo on render.com
3. Add NVIDIA_API_KEY in environment variables
4. Deploy!

## Adding Telegram (Tomorrow)
1. Create bot via @BotFather
2. Add token to .env: `TELEGRAM_BOT_TOKEN=your_token`
3. Add chat ID: `TELEGRAM_CHAT_ID=your_chat_id`
4. Redeploy on Render

## Project Structure
```
trade_buddy/
├── main.py              # FastAPI app + scheduler
├── core/
│   └── brain.py         # AI brain (NVIDIA NIM)
├── data/
│   └── market_data.py   # NSE data fetcher
├── scanners/
│   ├── morning_brief.py # 8:30 AM brief
│   ├── btst_scanner.py  # 2 PM BTST scan
│   └── gamma_blast.py   # OI wall scanner
├── notifications/
│   └── notifier.py      # Telegram + web alerts
├── static/
│   └── index.html       # Chat UI
└── render.yaml          # Render deployment
```

## API Endpoints
- `GET /` — Chat UI
- `POST /chat` — Send message to buddy
- `GET /scan/morning` — Trigger morning brief
- `GET /scan/btst` — Trigger BTST scan
- `GET /scan/gamma` — Trigger gamma blast check
- `GET /market/walls?symbol=NIFTY` — Get OI walls
- `GET /market/fii-dii` — Get FII/DII data
- `GET /notifications` — Get alerts log
- `GET /health` — Health check

## Tech Stack
- **AI**: NVIDIA NIM (llama-3.3-70b) → Claude API (later)
- **Backend**: FastAPI + APScheduler
- **Data**: NSE public APIs + Yahoo Finance
- **Notifications**: Telegram Bot API
- **Deploy**: Render.com
- **UI**: Vanilla HTML/CSS/JS
