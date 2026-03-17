#!/usr/bin/env python3
"""
Test script to verify the Multi-Agent Trading System setup.

Usage:
    uv run scripts/test_setup.py
"""
import asyncio
import sys


async def test_database():
    """Test database connection."""
    print("Testing database connection...")
    try:
        from tortoise import Tortoise
        from app.config import settings
        
        await Tortoise.init(
            db_url=settings.DATABASE_URL,
            modules={"models": ["app.models"]}
        )
        await Tortoise.generate_schemas(safe=True)
        
        # Test query
        from app.models import TradeSignal
        count = await TradeSignal.all().count()
        print(f"✓ Database connected. Signals in DB: {count}")
        
        await Tortoise.close_connections()
        return True
    except Exception as e:
        print(f"✗ Database error: {e}")
        return False


async def test_chromadb():
    """Test ChromaDB initialization."""
    print("\nTesting ChromaDB...")
    try:
        from app.memory import get_chroma_memory
        
        memory = await get_chroma_memory()
        stats = await memory.get_stats()
        
        print(f"✓ ChromaDB initialized. Total memories: {stats['total_memories']}")
        return True
    except Exception as e:
        print(f"✗ ChromaDB error: {e}")
        return False


async def test_langgraph():
    """Test LangGraph initialization."""
    print("\nTesting LangGraph...")
    try:
        from app.graph import get_trading_graph
        
        graph = get_trading_graph()
        print(f"✓ LangGraph initialized. Nodes: {list(graph.nodes.keys())}")
        return True
    except Exception as e:
        print(f"✗ LangGraph error: {e}")
        return False


async def test_llm():
    """Test LLM configuration."""
    print("\nTesting LLM configuration...")
    try:
        from app.config import settings
        from app.nodes import get_llm
        
        if not settings.OPENAI_API_KEY and settings.LLM_PROVIDER == "openai":
            print("⚠ OpenAI API key not set (skipping LLM test)")
            return True
        
        llm = get_llm()
        print(f"✓ LLM configured: {settings.LLM_PROVIDER}/{settings.LLM_MODEL}")
        return True
    except Exception as e:
        print(f"✗ LLM error: {e}")
        return False


async def main():
    """Run all tests."""
    print("=" * 50)
    print("Multi-Agent Trading System - Setup Verification")
    print("=" * 50)
    
    results = []
    
    results.append(await test_database())
    results.append(await test_chromadb())
    results.append(await test_langgraph())
    results.append(await test_llm())
    
    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)
    
    if all(results):
        print(f"✓ All tests passed ({passed}/{total})")
        print("\nSystem is ready to start:")
        print("  uv run uvicorn app.main:app --reload")
        return 0
    else:
        print(f"✗ Some tests failed ({passed}/{total})")
        print("\nPlease fix the errors above before starting.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
