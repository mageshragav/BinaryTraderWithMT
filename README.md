# Multi-Agent Trading System

A production-grade, asynchronous multi-agent trading system powered by LangGraph orchestration, FastAPI, and PostgreSQL.

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              MT4 EA (MQL4)                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Each indicator sends: { "value": float, "prediction": CALL/PUT/WAIT } │
│  │  - Trend: SMA, EMA, ADX with predictions                             │
│  │  - Momentum: RSI, MACD, Stochastic with predictions                  │
│  │  - Volatility: BB, ATR with predictions                              │
│  │  - Volume: MFI, OBV with predictions                                 │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ PUB (tcp://5555)
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FastAPI + LangGraph                                 │
│                                                                             │
│  ┌──────────────┐    ┌─────────────────────────────────────────────────┐   │
│  │ ZMQ Listener │───▶│  Specialist Nodes (Extract MT4 predictions)     │   │
│  └──────────────┘    │  - Trend: Aggregates CALL/PUT/WAIT counts       │   │
│                      │  - Momentum: Aggregates CALL/PUT/WAIT counts    │   │
│                      │  - Volatility: Aggregates CALL/PUT/WAIT counts  │   │
│                      │  - Volume: Aggregates CALL/PUT/WAIT counts      │   │
│                      └─────────────────────────────────────────────────┘   │
│                                          │                                  │
│                                          ▼                                  │
│                      ┌─────────────────────────────────────────────────┐   │
│                      │  Decision Node                                  │   │
│                      │  - Votes all indicator predictions              │   │
│                      │  - LLM synthesizes if signals are mixed         │   │
│                      │  - Final CALL/PUT/WAIT decision                 │   │
│                      └─────────────────────────────────────────────────┘   │
│                                          │                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                ┌───────────────────┼───────────────────┐
                ▼                   ▼                   ▼
      ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
      │  PostgreSQL DB  │ │   ChromaDB      │ │  Response to    │
      │  (Signals &     │ │   (Vector       │ │  MT4 via ZMQ    │
      │   Results)      │ │    Memory)      │ │                 │
      └─────────────────┘ └─────────────────┘ └─────────────────┘
```

## 📁 Project Structure

```
TradingMultiAgent/
├── app/
│   ├── __init__.py
│   ├── config.py          # Configuration settings
│   ├── models.py          # Tortoise ORM database models
│   ├── state.py           # LangGraph state schema
│   ├── nodes.py           # LangGraph agent nodes
│   ├── graph.py           # LangGraph StateGraph definition
│   ├── memory.py          # ChromaDB vector memory
│   └── main.py            # FastAPI application
├── mt4/
│   ├── mt4_bridge.mq4     # MT4 Expert Advisor (ZeroMQ publisher)
│   └── ZeroMQ.mqh         # ZeroMQ library for MT4
├── scripts/
│   ├── zmq_router.py      # ZeroMQ message router
│   └── test_setup.py      # Setup verification script
├── requirements.txt       # pip/uv dependencies
├── pyproject.toml         # uv project configuration
├── .env.example
├── README.md
└── aerich.ini             # Migration configuration
```

## 🚀 Quick Start

### Option 1: Using uv (Recommended)

```bash
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone and setup
cd TradingMultiAgent
uv venv
source .venv/bin/activate

# 3. Install dependencies
uv pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 5. Setup database
createdb trading_db
uv run aerich init -t app.models.TortoiseORM
uv run aerich init-db

# 6. Run application
uv run uvicorn app.main:app --reload
```

### Option 2: Using Docker Compose

```bash
# Set your API key
export OPENAI_API_KEY=sk-...

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api
```

---

### 1. Prerequisites

- Python 3.10+
- PostgreSQL 14+
- MT4/MT5 (optional, for live signals)
- OpenAI or Anthropic API key

### 3. Database Setup

```bash
# Create PostgreSQL database
createdb trading_db

# Run migrations
aerich init -t app.models.TortoiseORM
aerich init-db
```

### 4. Run the Application

```bash
# With uv (recommended)
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or activate venv first
source .venv/bin/activate
uvicorn app.main:app --reload
```

### 5. MT4 Setup (Optional)

1. Install ZeroMQ library for MT4:
   - Download from: https://github.com/dingmaotu/mt4-zmq
   - Copy DLL files to MT4/terminal.exe folder

2. Compile the EA:
   - Open `mt4/mt4_bridge.mq4` in MetaEditor
   - Compile to generate `.ex4` file

3. Attach to chart:
   - Drag EA onto desired chart
   - Configure settings (symbol, timeframe, interval)

## 📊 API Endpoints

### Health Check
```bash
GET /api/v1/health
```

### Submit Signal
```bash
POST /api/v1/signals
Content-Type: application/json

{
  "symbol": "EURUSD",
  "timeframe": "M15",
  "indicators": {
    "trend": {
      "sma_20": {"value": 1.0865, "prediction": "CALL"},
      "sma_50": {"value": 1.0850, "prediction": "CALL"},
      "ema_12": {"value": 1.0870, "prediction": "CALL"},
      "adx_14": {"value": 28.5, "prediction": "CALL"}
    },
    "momentum": {
      "rsi_14": {"value": 58.2, "prediction": "WAIT"},
      "macd_main": {"value": 0.0012, "prediction": "CALL"},
      "stoch_k": {"value": 65.3, "prediction": "WAIT"}
    },
    "volatility": {
      "bb_signal": {"prediction": "CALL"},
      "atr_14": {"value": 0.0045}
    },
    "volume": {
      "mfi_14": {"value": 55.8, "prediction": "WAIT"}
    }
  }
}
```

**Note:** Each indicator from MT4 includes both `value` and `prediction` fields. The `prediction` field contains CALL/PUT/WAIT signals calculated by the MT4 EA based on indicator-specific logic.

### Get Signal
```bash
GET /api/v1/signals/{signal_id}
```

### List Signals
```bash
GET /api/v1/signals?limit=50&offset=0
```

### Update Trade Outcome
```bash
PUT /api/v1/results/{result_id}/outcome
Content-Type: application/json

{
  "outcome": "WIN"  // or "LOSS"
}
```

### Memory Stats
```bash
GET /api/v1/memory/stats
```

### Indicator Configs
```bash
GET /api/v1/indicators
POST /api/v1/indicators
```

## 🧠 LangGraph Flow

The trading decision process follows this flow:

1. **Memory Node**: Queries ChromaDB for similar historical patterns

2. **Specialist Nodes** (parallel execution - extract MT4 predictions):
   - **Trend Specialist**: Extracts CALL/PUT/WAIT from SMA, EMA, ADX indicators
   - **Momentum Specialist**: Extracts CALL/PUT/WAIT from RSI, MACD, Stochastic
   - **Volatility Specialist**: Extracts CALL/PUT/WAIT from Bollinger Bands, ATR
   - **Volume Specialist**: Extracts CALL/PUT/WAIT from MFI, OBV

3. **Decision Node**: 
   - Counts all indicator predictions (CALL vs PUT vs WAIT)
   - If clear majority (>20% difference): Uses voting result
   - If mixed signals: Invokes LLM for final synthesis
   - Produces final CALL/PUT/WAIT decision with reasoning

### Example Prediction Aggregation

```
Trend Indicators:    CALL: 4, PUT: 1, WAIT: 2  → BULLISH
Momentum Indicators: CALL: 2, PUT: 1, WAIT: 4  → NEUTRAL
Volatility:          CALL: 1, PUT: 0, WAIT: 1  → BULLISH
Volume:              CALL: 0, PUT: 0, WAIT: 2  → NEUTRAL

Total: CALL: 7 (46%), PUT: 2 (13%), WAIT: 6 (40%)
Decision: CALL (clear majority)
```

## 🔄 Feedback Loop

The system learns from trade outcomes:

1. Trade result is updated with WIN/LOSS outcome
2. Background task adds the trade to ChromaDB vector memory
3. Future similar patterns will retrieve this memory
4. Decision node considers historical success/failure

## ⚙️ Configuration

Edit `.env` file:

```bash
# Database
DATABASE_URL=postgres://user:password@localhost:5432/trading_db

# ZeroMQ
ZMQ_HOST=tcp://127.0.0.1
ZMQ_PORT=5555

# LLM
OPENAI_API_KEY=sk-...
LLM_PROVIDER=openai  # or anthropic
LLM_MODEL=gpt-4o-mini

# ChromaDB
CHROMA_PERSIST_DIR=./chroma_db
CHROMA_COLLECTION_NAME=trading_memory
```

## 🧪 Testing

```bash
# Run tests with uv
uv run pytest

# With coverage
uv run pytest --cov=app
```

## 📝 Database Migrations

```bash
# Initialize aerich (first time only)
uv run aerich init -t app.models.TortoiseORM

# Create migration
uv run aerich migrate --name initial

# Apply migration
uv run aerich upgrade
```

## 🔒 Security Notes

- Never commit `.env` file
- Use strong database passwords
- Restrict API access in production
- Enable CORS only for trusted origins
- Use HTTPS in production

## 📈 Monitoring

Key metrics to monitor:
- Signal processing latency
- Decision accuracy (win rate)
- Vector memory growth
- Database query performance
- ZeroMQ connection stability

## 🛠 Troubleshooting

### ZeroMQ Connection Issues
```bash
# Check if port is in use
netstat -an | grep 5555

# Test connection
telnet 127.0.0.1 5555
```

### Database Connection Errors
```bash
# Test PostgreSQL connection
psql -h localhost -U user -d trading_db
```

### LLM API Errors
- Verify API key in `.env`
- Check rate limits
- Ensure network connectivity

## 📄 License

MIT License

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Commit changes
4. Push to branch
5. Create Pull Request
