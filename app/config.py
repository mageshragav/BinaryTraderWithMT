"""
Configuration settings for the Multi-Agent Trading System.
Load from environment variables with sensible defaults.
"""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgres://user:password@localhost:5432/trading_db"
    )
    
    # ZeroMQ
    ZMQ_HOST: str = os.getenv("ZMQ_HOST", "tcp://127.0.0.1")
    ZMQ_PORT: int = int(os.getenv("ZMQ_PORT", "5555"))
    ZMQ_SUBSCRIBE_TOPIC: str = os.getenv("ZMQ_SUBSCRIBE_TOPIC", "mt4_signal")
    
    # LLM
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")  # openai or anthropic
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    
    # ChromaDB
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
    CHROMA_COLLECTION_NAME: str = os.getenv("CHROMA_COLLECTION_NAME", "trading_memory")
    
    # Trading
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    TRADE_TIMEOUT_SECONDS: int = int(os.getenv("TRADE_TIMEOUT_SECONDS", "300"))
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
