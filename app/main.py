"""
FastAPI Application for the Multi-Agent Trading System.
Handles ZeroMQ communication, database operations, and LangGraph orchestration.
"""
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any
from datetime import datetime

import zmq
import zmq.asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from tortoise import Tortoise
from tortoise.exceptions import DoesNotExist

from .config import settings
from .models import TradeSignal, TradeResult, IndicatorConfig
from .graph import get_trading_graph
from .state import initialize_state
from .memory import add_to_memory, get_chroma_memory

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================================
# GLOBAL STATE
# ============================================================================

zmq_context: Optional[zmq.asyncio.Context] = None
zmq_socket: Optional[zmq.asyncio.Socket] = None
zmq_running: bool = False
trading_graph = None


# ============================================================================
# LIFESPAN EVENTS
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handle application startup and shutdown.
    """
    # Startup
    logger.info("Starting Multi-Agent Trading System...")
    
    # Initialize database
    await Tortoise.init(
        db_url=settings.DATABASE_URL,
        modules={"models": ["app.models"]}
    )
    await Tortoise.generate_schemas(safe=True)
    logger.info("Database initialized")
    
    # Initialize ZeroMQ
    global zmq_context, zmq_socket, zmq_running, trading_graph
    zmq_context = zmq.asyncio.Context()
    zmq_socket = zmq_context.socket(zmq.SUB)
    zmq_socket.connect(f"{settings.ZMQ_HOST}:{settings.ZMQ_PORT}")
    zmq_socket.setsockopt_string(zmq.SUBSCRIBE, settings.ZMQ_SUBSCRIBE_TOPIC)
    zmq_running = True
    logger.info(f"ZeroMQ connected to {settings.ZMQ_HOST}:{settings.ZMQ_PORT}")
    
    # Initialize LangGraph
    trading_graph = get_trading_graph()
    logger.info("LangGraph initialized")
    
    # Initialize ChromaDB
    await get_chroma_memory()
    logger.info("ChromaDB initialized")
    
    # Start ZeroMQ listener task
    asyncio.create_task(zmq_listener_task())
    logger.info("ZeroMQ listener started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    zmq_running = False
    if zmq_socket:
        zmq_socket.close()
    if zmq_context:
        zmq_context.term()
    await Tortoise.close_connections()
    logger.info("Shutdown complete")


# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Multi-Agent Trading System",
    description="Production-grade trading system with LangGraph orchestration",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# ZERO MQ LISTENER
# ============================================================================

async def zmq_listener_task():
    """
    Background task that continuously listens for MT4 signals via ZeroMQ.
    """
    global zmq_running
    
    while zmq_running:
        try:
            # Receive message with timeout
            message = await asyncio.wait_for(
                zmq_socket.recv_multipart(),
                timeout=1.0
            )
            
            if len(message) >= 2:
                topic = message[0].decode()
                data = message[1].decode()
                
                logger.info(f"Received ZMQ message on topic: {topic}")
                
                # Process the signal
                await process_mt4_signal(data)
                
        except asyncio.TimeoutError:
            # Expected timeout, continue loop
            pass
        except Exception as e:
            logger.error(f"ZeroMQ listener error: {e}")
            await asyncio.sleep(1)  # Back off on error


async def process_mt4_signal(raw_data: str):
    """
    Process an incoming MT4 signal.
    
    Args:
        raw_data: JSON string from MT4
    """
    try:
        data = json.loads(raw_data)
        
        # Validate required fields
        if "symbol" not in data or "timeframe" not in data:
            logger.error(f"Invalid signal data: missing symbol or timeframe")
            return
        
        # Save raw signal to database
        signal = await TradeSignal.create(
            symbol=data["symbol"],
            timeframe=data["timeframe"],
            raw_json=data
        )
        
        logger.info(f"Saved signal: {signal.id} ({data['symbol']})")
        
        # Run through LangGraph
        state = initialize_state(data, signal.id)
        result = await trading_graph.ainvoke(state)
        
        # Save decision to database
        trade_result = await TradeResult.create(
            signal_id=signal.id,
            decision=result["final_decision"],
            reasoning=result["reasoning"],
            specialist_reports=result.get("specialist_reports", {})
        )
        
        # Mark signal as processed
        signal.processed = True
        await signal.save()
        
        logger.info(f"Decision: {result['final_decision']} for {data['symbol']}")
        
        # Send response back to MT4 (optional)
        await send_response_to_mt4({
            "signal_id": signal.id,
            "decision": result["final_decision"],
            "reasoning": result["reasoning"][:200]  # Truncate for brevity
        })
        
    except Exception as e:
        logger.error(f"Error processing MT4 signal: {e}", exc_info=True)


async def send_response_to_mt4(response: Dict[str, Any]):
    """
    Send decision response back to MT4 via ZeroMQ.
    """
    try:
        # Use PUB socket for responses
        pub_socket = zmq_context.socket(zmq.PUB)
        pub_socket.connect(f"{settings.ZMQ_HOST}:{settings.ZMQ_PORT + 1}")
        pub_socket.send_multipart([
            b"decision",
            json.dumps(response).encode()
        ])
        pub_socket.close()
        logger.debug(f"Sent response to MT4: {response['decision']}")
    except Exception as e:
        logger.error(f"Error sending response to MT4: {e}")


# ============================================================================
# API ENDPOINTS
# ============================================================================

class ManualSignalInput(BaseModel):
    """Schema for manual signal submission."""
    symbol: str = Field(..., description="Trading symbol (e.g., EURUSD)")
    timeframe: str = Field(..., description="Chart timeframe (e.g., M15, H1)")
    indicators: Dict[str, Any] = Field(..., description="Indicator data")


@app.post("/api/v1/signals", response_model=Dict[str, Any])
async def submit_signal(signal: ManualSignalInput):
    """
    Manually submit a trading signal for processing.
    """
    try:
        data = {
            "symbol": signal.symbol,
            "timeframe": signal.timeframe,
            **signal.indicators
        }
        
        # Save raw signal
        sig = await TradeSignal.create(
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            raw_json=data
        )
        
        # Run through graph
        state = initialize_state(data, sig.id)
        result = await trading_graph.ainvoke(state)
        
        # Save result
        await TradeResult.create(
            signal_id=sig.id,
            decision=result["final_decision"],
            reasoning=result["reasoning"],
            specialist_reports=result.get("specialist_reports", {})
        )
        
        sig.processed = True
        await sig.save()
        
        return {
            "signal_id": sig.id,
            "decision": result["final_decision"],
            "reasoning": result["reasoning"]
        }
        
    except Exception as e:
        logger.error(f"Error submitting signal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/signals/{signal_id}")
async def get_signal(signal_id: int):
    """
    Get a specific signal and its results.
    """
    try:
        signal = await TradeSignal.get(id=signal_id).prefetch_related("results")
        return {
            "signal": signal,
            "results": signal.results
        }
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Signal not found")


@app.get("/api/v1/signals")
async def list_signals(limit: int = 50, offset: int = 0):
    """
    List recent signals.
    """
    signals = await TradeSignal.all().limit(limit).offset(offset)
    return {
        "signals": signals,
        "total": await TradeSignal.all().count()
    }


class TradeOutcomeUpdate(BaseModel):
    """Schema for updating trade outcome."""
    outcome: str = Field(..., description="WIN or LOSS")


@app.put("/api/v1/results/{result_id}/outcome")
async def update_trade_outcome(result_id: int, update: TradeOutcomeUpdate, background_tasks: BackgroundTasks):
    """
    Update the outcome of a trade and add to vector memory.
    """
    try:
        result = await TradeResult.get(id=result_id)
        result.outcome = update.outcome
        await result.save()
        
        # Add to vector memory in background
        background_tasks.add_task(
            add_trade_to_memory,
            result
        )
        
        return {"status": "success", "result_id": result_id, "outcome": update.outcome}
        
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Result not found")


async def add_trade_to_memory(result: TradeResult):
    """
    Add a completed trade to vector memory for learning.
    """
    try:
        signal = await TradeSignal.get(id=result.signal_id)
        
        await add_to_memory(
            indicator_state=signal.raw_json,
            decision=result.decision,
            outcome=result.outcome,
            reasoning=result.reasoning
        )
        
        logger.info(f"Added trade {result.id} to memory ({result.outcome})")
    except Exception as e:
        logger.error(f"Error adding trade to memory: {e}")


@app.get("/api/v1/memory/stats")
async def get_memory_stats():
    """
    Get vector memory statistics.
    """
    try:
        memory = await get_chroma_memory()
        stats = await memory.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting memory stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/health")
async def health_check():
    """
    Health check endpoint.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "zmq_connected": zmq_running,
        "graph_initialized": trading_graph is not None
    }


# ============================================================================
# INDICATOR CONFIG ENDPOINTS
# ============================================================================

@app.get("/api/v1/indicators")
async def list_indicators(active_only: bool = True):
    """
    List indicator configurations.
    """
    query = IndicatorConfig.all()
    if active_only:
        query = query.filter(is_active=True)
    
    indicators = await query
    return {"indicators": indicators}


@app.post("/api/v1/indicators")
async def create_indicator(indicator: IndicatorConfig):
    """
    Create a new indicator configuration.
    """
    try:
        config = await IndicatorConfig.create(
            name=indicator.name,
            category=indicator.category,
            parameters=indicator.parameters,
            is_active=indicator.is_active
        )
        return {"id": config.id, "name": config.name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
