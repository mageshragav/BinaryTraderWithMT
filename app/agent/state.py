"""
LangGraph State Schema for the Multi-Agent Trading System.
"""
from typing import TypedDict, Dict, List, Optional, Annotated
from typing_extensions import NotRequired
import operator


class GraphState(TypedDict):
    """
    State schema for the LangGraph StateGraph.
    
    Attributes:
        raw_data: JSON data received from MT4 containing indicators
        specialist_reports: Dictionary of outputs from specialist agents
        indicator_predictions: CALL/PUT/WAIT prediction for each indicator
        historical_context: Findings from vector DB similarity search
        final_decision: The final trade decision (CALL/PUT/WAIT)
        reasoning: Explanation for the decision
        signal_id: Database ID of the trade signal
        symbol: Trading symbol (e.g., EURUSD)
        timeframe: Chart timeframe (e.g., M15, H1)
        errors: List of errors
    """
    raw_data: Dict
    specialist_reports: Annotated[Dict, operator.add]
    indicator_predictions: Dict
    historical_context: str
    final_decision: str
    reasoning: str
    signal_id: int
    symbol: str
    timeframe: str
    errors: List[str]


class SpecialistReport(TypedDict):
    """
    Schema for individual specialist agent reports.
    """
    agent_name: str
    category: str  # trend, momentum, volatility, etc.
    analysis: str
    signal: str  # BULLISH, BEARISH, NEUTRAL
    confidence: float
    key_indicators: Dict
    indicator_predictions: Dict  # CALL/PUT/WAIT per indicator


def initialize_state(raw_data: Dict, signal_id: int) -> GraphState:
    """
    Initialize a new GraphState from raw MT4 data.
    
    Args:
        raw_data: JSON from MT4
        signal_id: Database ID of the trade signal
        
    Returns:
        Initialized GraphState
    """
    return GraphState(
        raw_data=raw_data,
        specialist_reports={},
        indicator_predictions={},
        historical_context="",
        final_decision="",
        reasoning="",
        signal_id=signal_id,
        symbol=raw_data.get("symbol", "UNKNOWN"),
        timeframe=raw_data.get("timeframe", "UNKNOWN"),
        errors=[]
    )
