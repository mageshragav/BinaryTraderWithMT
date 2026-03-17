"""
ChromaDB Vector Memory for the Multi-Agent Trading System.
Stores and retrieves historical trading patterns for similarity-based learning.
"""
import json
import logging
from typing import Dict, List, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

from .config import settings

logger = logging.getLogger(__name__)


class ChromaMemory:
    """
    Manages ChromaDB vector store for trading memory.
    """
    
    def __init__(self):
        self._client: Optional[chromadb.Client] = None
        self._collection: Optional[chromadb.Collection] = None
        self._embeddings: Optional[OpenAIEmbeddings] = None
    
    async def initialize(self):
        """Initialize ChromaDB client and collection."""
        if self._client is None:
            # Initialize ChromaDB client with persistence
            self._client = chromadb.Client(
                ChromaSettings(
                    persist_directory=settings.CHROMA_PERSIST_DIR,
                    anonymized_telemetry=False
                )
            )
            
            # Get or create collection
            self._collection = self._client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )
            
            # Initialize embeddings
            self._embeddings = OpenAIEmbeddings(
                model="text-embedding-3-small"
            )
            
            logger.info(f"ChromaDB initialized: {settings.CHROMA_COLLECTION_NAME}")
    
    async def add_trade_memory(
        self,
        indicator_state: Dict[str, Any],
        decision: str,
        outcome: str,
        reasoning: str
    ) -> str:
        """
        Add a trade outcome to memory for future learning.
        
        Args:
            indicator_state: The indicator values at trade time
            decision: CALL/PUT/WAIT
            outcome: WIN/LOSS
            reasoning: The reasoning behind the decision
            
        Returns:
            Document ID
        """
        if not self._collection:
            await self.initialize()
        
        # Create document content
        content = json.dumps({
            "indicators": indicator_state,
            "decision": decision,
            "outcome": outcome,
            "reasoning": reasoning
        })
        
        # Generate metadata
        metadata = {
            "symbol": indicator_state.get("symbol", "UNKNOWN"),
            "timeframe": indicator_state.get("timeframe", "UNKNOWN"),
            "decision": decision,
            "outcome": outcome
        }
        
        # Add to collection
        doc_id = f"trade_{indicator_state.get('symbol', 'UNK')}_{len(self._collection)}"
        
        self._collection.add(
            documents=[content],
            metadatas=[metadata],
            ids=[doc_id]
        )
        
        logger.info(f"Added trade memory: {doc_id} ({outcome})")
        return doc_id
    
    async def query_similar_patterns(
        self,
        indicator_state: Dict[str, Any],
        top_k: int = 5,
        filter_outcome: Optional[str] = None
    ) -> str:
        """
        Query for similar historical patterns.
        
        Args:
            indicator_state: Current indicator values
            top_k: Number of results to return
            filter_outcome: Filter by outcome (WIN/LOSS) if specified
            
        Returns:
            Formatted string of similar patterns
        """
        if not self._collection:
            await self.initialize()
        
        # Prepare query
        query_text = json.dumps(indicator_state)
        
        # Build where filter
        where_filter = None
        if filter_outcome:
            where_filter = {"outcome": filter_outcome}
        
        # Query collection
        results = self._collection.query(
            query_texts=[query_text],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )
        
        # Format results
        if not results["documents"] or not results["documents"][0]:
            return "No similar historical patterns found."
        
        formatted_results = []
        for i, (doc, meta, distance) in enumerate(zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        )):
            try:
                data = json.loads(doc)
                formatted_results.append(
                    f"Pattern {i+1} (similarity: {1-distance:.2f}):\n"
                    f"  Decision: {data['decision']}, Outcome: {data['outcome']}\n"
                    f"  Reasoning: {data['reasoning'][:200]}..."
                )
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Error parsing memory document: {e}")
                continue
        
        return "\n\n".join(formatted_results) if formatted_results else "No valid patterns found."
    
    async def update_trade_outcome(
        self,
        trade_id: str,
        new_outcome: str
    ) -> bool:
        """
        Update the outcome of a stored trade.
        
        Args:
            trade_id: Document ID to update
            new_outcome: New outcome value (WIN/LOSS)
            
        Returns:
            True if successful
        """
        if not self._collection:
            await self.initialize()
        
        try:
            # Get existing document
            existing = self._collection.get(ids=[trade_id], include=["documents", "metadatas"])
            
            if not existing["documents"] or not existing["documents"][0]:
                logger.error(f"Trade {trade_id} not found in memory")
                return False
            
            # Update document
            data = json.loads(existing["documents"][0])
            data["outcome"] = new_outcome
            
            self._collection.update(
                ids=[trade_id],
                documents=[json.dumps(data)],
                metadatas=[{**existing["metadatas"][0], "outcome": new_outcome}]
            )
            
            logger.info(f"Updated trade {trade_id} outcome to {new_outcome}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating trade outcome: {e}")
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        if not self._collection:
            await self.initialize()
        
        count = self._collection.count()
        
        # Count by outcome
        wins = self._collection.get(where={"outcome": "WIN"})
        losses = self._collection.get(where={"outcome": "LOSS"})
        
        return {
            "total_memories": count,
            "wins": len(wins["ids"]) if wins["ids"] else 0,
            "losses": len(losses["ids"]) if losses["ids"] else 0,
            "win_rate": len(wins["ids"]) / (len(wins["ids"]) + len(losses["ids"])) 
                       if (len(wins["ids"]) + len(losses["ids"])) > 0 else 0
        }


# Global instance
_chroma_memory: Optional[ChromaMemory] = None


async def get_chroma_memory() -> ChromaMemory:
    """Get or create ChromaMemory instance."""
    global _chroma_memory
    if _chroma_memory is None:
        _chroma_memory = ChromaMemory()
        await _chroma_memory.initialize()
    return _chroma_memory


async def query_chroma_memory(
    indicator_state: Dict[str, Any],
    top_k: int = 5
) -> str:
    """
    Convenience function to query ChromaDB.
    
    Args:
        indicator_state: Current indicator values
        top_k: Number of results
        
    Returns:
        Formatted query results
    """
    memory = await get_chroma_memory()
    return await memory.query_similar_patterns(indicator_state, top_k)


async def add_to_memory(
    indicator_state: Dict[str, Any],
    decision: str,
    outcome: str,
    reasoning: str
) -> str:
    """
    Convenience function to add trade to memory.
    
    Args:
        indicator_state: Indicator values
        decision: CALL/PUT/WAIT
        outcome: WIN/LOSS
        reasoning: Decision reasoning
        
    Returns:
        Document ID
    """
    memory = await get_chroma_memory()
    return await memory.add_trade_memory(indicator_state, decision, outcome, reasoning)
