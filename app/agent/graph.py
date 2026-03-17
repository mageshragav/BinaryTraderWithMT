"""
LangGraph StateGraph for the Multi-Agent Trading System.
Defines the orchestration flow between specialist agents.
"""
import logging
from typing import Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from .state import GraphState, initialize_state
from .nodes import (
    trend_specialist_node,
    momentum_specialist_node,
    volatility_specialist_node,
    volume_specialist_node,
    memory_node,
    decision_node,
    error_recovery_node
)

logger = logging.getLogger(__name__)


def create_trading_graph() -> StateGraph:
    """
    Create and configure the LangGraph StateGraph for trading decisions.
    
    Graph Flow:
    1. START -> Memory Node (query historical patterns)
    2. Memory Node -> Specialist Nodes (parallel execution)
    3. Specialist Nodes -> Decision Node
    4. Decision Node -> END
    
    Returns:
        Compiled StateGraph
    """
    
    # Initialize the graph with our state schema
    workflow = StateGraph(GraphState)
    
    # Add all nodes
    workflow.add_node("memory", memory_node)
    workflow.add_node("trend_specialist", trend_specialist_node)
    workflow.add_node("momentum_specialist", momentum_specialist_node)
    workflow.add_node("volatility_specialist", volatility_specialist_node)
    workflow.add_node("volume_specialist", volume_specialist_node)
    workflow.add_node("decision", decision_node)
    workflow.add_node("error_recovery", error_recovery_node)
    
    # Define edges
    # Start -> Memory Node
    workflow.set_entry_point("memory")
    
    # Memory Node -> All Specialist Nodes (parallel)
    workflow.add_edge("memory", "trend_specialist")
    workflow.add_edge("memory", "momentum_specialist")
    workflow.add_edge("memory", "volatility_specialist")
    workflow.add_edge("memory", "volume_specialist")
    
    # Specialist Nodes -> Decision Node
    # LangGraph will wait for all parallel branches to complete
    workflow.add_edge("trend_specialist", "decision")
    workflow.add_edge("momentum_specialist", "decision")
    workflow.add_edge("volatility_specialist", "decision")
    workflow.add_edge("volume_specialist", "decision")
    
    # Decision Node -> End
    workflow.add_edge("decision", END)
    
    # Compile the graph
    app = workflow.compile()
    
    logger.info("Trading graph compiled successfully")
    return app


def should_continue(state: GraphState) -> str:
    """
    Conditional edge function to determine next step.
    Currently unused but available for complex routing logic.
    """
    if state.get("errors"):
        return "error_recovery"
    return "decision"


# Global graph instance
_trading_graph: StateGraph = None


def get_trading_graph() -> StateGraph:
    """Get or create the trading graph instance."""
    global _trading_graph
    if _trading_graph is None:
        _trading_graph = create_trading_graph()
    return _trading_graph
