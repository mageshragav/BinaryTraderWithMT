"""
LangGraph Nodes for the Multi-Agent Trading System.
Each node represents a specialist agent or processing step.
"""
import json
import logging
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from .state import GraphState, SpecialistReport
from .config import settings
from .memory import query_chroma_memory

logger = logging.getLogger(__name__)


def get_llm():
    """Get the configured LLM instance."""
    if settings.LLM_PROVIDER == "anthropic":
        return ChatAnthropic(
            model=settings.LLM_MODEL or "claude-3-5-sonnet-20241022",
            temperature=0.1,
        )
    else:
        return ChatOpenAI(
            model=settings.LLM_MODEL or "gpt-4o-mini",
            temperature=0.1,
        )


def extract_indicator_predictions(indicator_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract CALL/PUT/WAIT predictions from indicator data.
    Each indicator from MT4 has: {"value": float, "prediction": "CALL|PUT|WAIT"}
    
    Args:
        indicator_data: Dictionary of indicator data from MT4
        
    Returns:
        Dictionary mapping indicator name to its prediction
    """
    predictions = {}
    for name, data in indicator_data.items():
        if isinstance(data, dict):
            if "prediction" in data:
                predictions[name] = data["prediction"]
            # Recursively check nested dicts
            else:
                nested = extract_indicator_predictions(data)
                predictions.update(nested)
    return predictions


def aggregate_predictions(predictions: Dict[str, str]) -> Dict[str, Any]:
    """
    Aggregate individual predictions into category-level signals.
    
    Args:
        predictions: Dict of indicator -> prediction
        
    Returns:
        Aggregated signal with counts
    """
    call_count = sum(1 for p in predictions.values() if p == "CALL")
    put_count = sum(1 for p in predictions.values() if p == "PUT")
    wait_count = sum(1 for p in predictions.values() if p == "WAIT")
    
    total = call_count + put_count + wait_count
    if total == 0:
        return {"signal": "NEUTRAL", "call": 0, "put": 0, "wait": 0, "predictions": predictions}
    
    # Determine dominant signal
    if call_count > put_count and call_count > wait_count:
        signal = "BULLISH"
    elif put_count > call_count and put_count > wait_count:
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"
    
    return {
        "signal": signal,
        "call": call_count,
        "put": put_count,
        "wait": wait_count,
        "predictions": predictions
    }


# ============================================================================
# SPECIALIST NODES
# ============================================================================

async def trend_specialist_node(state: GraphState) -> Dict[str, Any]:
    """
    Analyzes trend indicators (MA, EMA, ADX, etc.).
    Extracts predictions from MT4 payload and aggregates them.
    """
    try:
        trend_data = state["raw_data"].get("trend", {})
        
        # Extract predictions from MT4 data
        predictions = extract_indicator_predictions(trend_data)
        aggregated = aggregate_predictions(predictions)
        
        # Build report with MT4 predictions
        report = {
            "trend": {
                "agent_name": "Trend Specialist",
                "category": "trend",
                "analysis": f"Trend indicators show {aggregated['signal']} signal. CALL: {aggregated['call']}, PUT: {aggregated['put']}, WAIT: {aggregated['wait']}",
                "signal": aggregated["signal"],
                "confidence": aggregated['call'] / (aggregated['call'] + aggregated['put'] + aggregated['wait']) if (aggregated['call'] + aggregated['put']) > 0 else 0.5,
                "key_indicators": trend_data,
                "indicator_predictions": predictions
            }
        }
        
        logger.info(f"Trend Specialist: {aggregated['signal']} (CALL:{aggregated['call']}, PUT:{aggregated['put']}, WAIT:{aggregated['wait']})")
        return {"specialist_reports": report, "indicator_predictions": {"trend": predictions}}
        
    except Exception as e:
        logger.error(f"Trend specialist error: {e}")
        return {"errors": [f"Trend specialist: {str(e)}"]}


async def momentum_specialist_node(state: GraphState) -> Dict[str, Any]:
    """
    Analyzes momentum indicators (RSI, Stochastic, MACD, etc.).
    Extracts predictions from MT4 payload and aggregates them.
    """
    try:
        momentum_data = state["raw_data"].get("momentum", {})
        
        # Extract predictions from MT4 data
        predictions = extract_indicator_predictions(momentum_data)
        aggregated = aggregate_predictions(predictions)
        
        # Build report with MT4 predictions
        report = {
            "momentum": {
                "agent_name": "Momentum Specialist",
                "category": "momentum",
                "analysis": f"Momentum indicators show {aggregated['signal']} signal. CALL: {aggregated['call']}, PUT: {aggregated['put']}, WAIT: {aggregated['wait']}",
                "signal": aggregated["signal"],
                "confidence": aggregated['call'] / (aggregated['call'] + aggregated['put'] + aggregated['wait']) if (aggregated['call'] + aggregated['put']) > 0 else 0.5,
                "key_indicators": momentum_data,
                "indicator_predictions": predictions
            }
        }
        
        logger.info(f"Momentum Specialist: {aggregated['signal']} (CALL:{aggregated['call']}, PUT:{aggregated['put']}, WAIT:{aggregated['wait']})")
        return {"specialist_reports": report, "indicator_predictions": {"momentum": predictions}}
        
    except Exception as e:
        logger.error(f"Momentum specialist error: {e}")
        return {"errors": [f"Momentum specialist: {str(e)}"]}


async def volatility_specialist_node(state: GraphState) -> Dict[str, Any]:
    """
    Analyzes volatility indicators (Bollinger Bands, ATR, etc.).
    Extracts predictions from MT4 payload and aggregates them.
    """
    try:
        volatility_data = state["raw_data"].get("volatility", {})
        
        # Extract predictions from MT4 data
        predictions = extract_indicator_predictions(volatility_data)
        aggregated = aggregate_predictions(predictions)
        
        # Build report with MT4 predictions
        report = {
            "volatility": {
                "agent_name": "Volatility Specialist",
                "category": "volatility",
                "analysis": f"Volatility indicators show {aggregated['signal']} signal. CALL: {aggregated['call']}, PUT: {aggregated['put']}, WAIT: {aggregated['wait']}",
                "signal": aggregated["signal"],
                "confidence": 0.5,  # Volatility doesn't directly predict direction
                "key_indicators": volatility_data,
                "indicator_predictions": predictions
            }
        }
        
        logger.info(f"Volatility Specialist: {aggregated['signal']} (CALL:{aggregated['call']}, PUT:{aggregated['put']}, WAIT:{aggregated['wait']})")
        return {"specialist_reports": report, "indicator_predictions": {"volatility": predictions}}
        
    except Exception as e:
        logger.error(f"Volatility specialist error: {e}")
        return {"errors": [f"Volatility specialist: {str(e)}"]}


async def volume_specialist_node(state: GraphState) -> Dict[str, Any]:
    """
    Analyzes volume indicators (OBV, MFI, etc.).
    Extracts predictions from MT4 payload and aggregates them.
    """
    try:
        volume_data = state["raw_data"].get("volume", {})
        
        # Extract predictions from MT4 data
        predictions = extract_indicator_predictions(volume_data)
        aggregated = aggregate_predictions(predictions)
        
        # Build report with MT4 predictions
        report = {
            "volume": {
                "agent_name": "Volume Specialist",
                "category": "volume",
                "analysis": f"Volume indicators show {aggregated['signal']} signal. CALL: {aggregated['call']}, PUT: {aggregated['put']}, WAIT: {aggregated['wait']}",
                "signal": aggregated["signal"],
                "confidence": aggregated['call'] / (aggregated['call'] + aggregated['put'] + aggregated['wait']) if (aggregated['call'] + aggregated['put']) > 0 else 0.5,
                "key_indicators": volume_data,
                "indicator_predictions": predictions
            }
        }
        
        logger.info(f"Volume Specialist: {aggregated['signal']} (CALL:{aggregated['call']}, PUT:{aggregated['put']}, WAIT:{aggregated['wait']})")
        return {"specialist_reports": report, "indicator_predictions": {"volume": predictions}}
        
    except Exception as e:
        logger.error(f"Volume specialist error: {e}")
        return {"errors": [f"Volume specialist: {str(e)}"]}


# ============================================================================
# MEMORY NODE
# ============================================================================

async def memory_node(state: GraphState) -> Dict[str, Any]:
    """
    Queries ChromaDB for similar historical patterns.
    """
    try:
        # Extract indicator state for embedding
        indicator_state = {
            "symbol": state["symbol"],
            "timeframe": state["timeframe"],
            **state["raw_data"]
        }
        
        # Query vector memory for similar patterns
        historical_context = await query_chroma_memory(indicator_state, top_k=5)
        
        logger.info(f"Memory Node: Found {len(historical_context)} similar patterns")
        return {"historical_context": historical_context}
        
    except Exception as e:
        logger.error(f"Memory node error: {e}")
        return {"historical_context": "", "errors": [f"Memory node: {str(e)}"]}


# ============================================================================
# DECISION NODE
# ============================================================================

async def decision_node(state: GraphState) -> Dict[str, Any]:
    """
    Synthesizes all specialist reports and MT4 predictions to produce final decision.
    Uses weighted voting based on MT4 indicator predictions + LLM reasoning.
    """
    try:
        # Collect all indicator predictions from specialists
        all_predictions = {}
        specialist_summary = {}
        
        for category, report in state.get("specialist_reports", {}).items():
            if isinstance(report, dict):
                # Get indicator-level predictions
                if "indicator_predictions" in report:
                    all_predictions[category] = report["indicator_predictions"]
                # Get category signal
                specialist_summary[category] = {
                    "signal": report.get("signal", "NEUTRAL"),
                    "confidence": report.get("confidence", 0.5)
                }
        
        # Also get predictions from state (aggregated by specialists)
        for category, predictions in state.get("indicator_predictions", {}).items():
            if category not in all_predictions:
                all_predictions[category] = predictions
        
        # Count all CALL/PUT/WAIT predictions
        call_count = 0
        put_count = 0
        wait_count = 0
        
        for category, predictions in all_predictions.items():
            for indicator, prediction in predictions.items():
                if prediction == "CALL":
                    call_count += 1
                elif prediction == "PUT":
                    put_count += 1
                elif prediction == "WAIT" or prediction == "NEUTRAL":
                    wait_count += 1
        
        total = call_count + put_count + wait_count
        
        # Calculate weighted vote
        if total > 0:
            call_ratio = call_count / total
            put_ratio = put_count / total
            
            # Use LLM for final synthesis when signals are mixed
            if abs(call_ratio - put_ratio) < 0.2:  # Close call, need LLM
                llm = get_llm()
                prompt = ChatPromptTemplate.from_messages([
                    ("system", """You are the Chief Trading Decision Officer. 
                    Signals are mixed. Synthesize all specialist reports and make a final decision.
                    
                    Your decision must be one of: CALL, PUT, or WAIT."""),
                    ("human", """
                    Symbol: {symbol}
                    Timeframe: {timeframe}
                    
                    Specialist Reports:
                    {specialist_reports}
                    
                    MT4 Indicator Predictions:
                    CALL: {call_count}, PUT: {put_count}, WAIT: {wait_count}
                    
                    Historical Context (similar past patterns):
                    {historical_context}
                    
                    Provide your decision in this JSON format:
                    {{
                        "decision": "CALL|PUT|WAIT",
                        "reasoning": "Detailed explanation"
                    }}
                    """)
                ])
                
                chain = prompt | llm | StrOutputParser()
                result = await chain.ainvoke({
                    "symbol": state["symbol"],
                    "timeframe": state["timeframe"],
                    "specialist_reports": json.dumps(specialist_summary),
                    "call_count": call_count,
                    "put_count": put_count,
                    "wait_count": wait_count,
                    "historical_context": state["historical_context"]
                })
                
                # Parse decision
                decision = "WAIT"
                if "CALL" in result.upper():
                    decision = "CALL"
                elif "PUT" in result.upper():
                    decision = "PUT"
                
                reasoning = result
                
            else:
                # Clear signal, use voting
                if call_ratio > put_ratio:
                    decision = "CALL"
                elif put_ratio > call_ratio:
                    decision = "PUT"
                else:
                    decision = "WAIT"
                
                reasoning = (
                    f"Decision based on MT4 indicator voting:\n"
                    f"CALL: {call_count} ({call_ratio:.1%}), PUT: {put_count} ({put_ratio:.1%}), WAIT: {wait_count}\n"
                    f"Specialist signals: {json.dumps(specialist_summary, indent=2)}"
                )
        else:
            decision = "WAIT"
            reasoning = "No indicator predictions available"
        
        logger.info(f"Decision Node: {decision} (CALL:{call_count}, PUT:{put_count}, WAIT:{wait_count})")
        return {
            "final_decision": decision,
            "reasoning": reasoning,
            "indicator_predictions": all_predictions
        }
        
    except Exception as e:
        logger.error(f"Decision node error: {e}", exc_info=True)
        return {"final_decision": "WAIT", "reasoning": f"Error: {str(e)}", "errors": [f"Decision node: {str(e)}"]}


# ============================================================================
# ERROR HANDLING NODE
# ============================================================================

async def error_recovery_node(state: GraphState) -> Dict[str, Any]:
    """
    Handles errors and provides fallback behavior.
    """
    if state.get("errors"):
        logger.warning(f"Recovering from errors: {state['errors']}")
        # Clear errors after handling
        return {"errors": []}
    return {}
