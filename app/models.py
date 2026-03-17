"""
Tortoise ORM Database Models for the Multi-Agent Trading System.
"""
from tortoise import fields, models
from tortoise.contrib.pydantic import pydantic_model_creator


class TradeSignal(models.Model):
    """
    Stores incoming trade signals from MT4.
    """
    id = fields.IntField(pk=True)
    symbol = fields.CharField(max_length=20, index=True)
    timeframe = fields.CharField(max_length=10)
    raw_json = fields.JSONField()
    created_at = fields.DatetimeField(auto_now_add=True, index=True)
    processed = fields.BooleanField(default=False)
    
    class Meta:
        table = "trade_signals"
        ordering = ["-created_at"]
    
    def __str__(self) -> str:
        return f"TradeSignal({self.symbol}, {self.timeframe}, {self.created_at})"


class TradeResult(models.Model):
    """
    Stores the outcome of the trade decision.
    """
    id = fields.IntField(pk=True)
    signal = fields.ForeignKeyField(
        "models.TradeSignal",
        related_name="results",
        on_delete=fields.CASCADE
    )
    decision = fields.CharField(max_length=10)  # CALL, PUT, WAIT
    reasoning = fields.TextField()
    outcome = fields.CharField(max_length=10, null=True)  # WIN, LOSS, PENDING
    executed_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    
    # Additional metadata
    confidence_score = fields.FloatField(null=True)
    specialist_reports = fields.JSONField(null=True)
    
    class Meta:
        table = "trade_results"
        ordering = ["-executed_at"]
    
    def __str__(self) -> str:
        return f"TradeResult({self.signal.symbol}, {self.decision}, {self.outcome or 'PENDING'})"


class IndicatorConfig(models.Model):
    """
    Stores active indicator configurations to sync with MT4.
    """
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100, unique=True)
    category = fields.CharField(max_length=50)  # trend, momentum, volatility, etc.
    parameters = fields.JSONField()
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    
    class Meta:
        table = "indicator_configs"
    
    def __str__(self) -> str:
        return f"IndicatorConfig({self.name}, {self.category})"


# Pydantic models for API validation
TradeSignal_Pydantic = pydantic_model_creator(TradeSignal, name="TradeSignal")
TradeSignalIn_Pydantic = pydantic_model_creator(TradeSignal, exclude=("id", "created_at", "processed"), name="TradeSignalIn")
TradeResult_Pydantic = pydantic_model_creator(TradeResult, name="TradeResult")
TradeResultIn_Pydantic = pydantic_model_creator(TradeResult, exclude=("id", "executed_at", "updated_at"), name="TradeResultIn")
IndicatorConfig_Pydantic = pydantic_model_creator(IndicatorConfig, name="IndicatorConfig")
IndicatorConfigIn_Pydantic = pydantic_model_creator(IndicatorConfig, exclude=("id", "created_at", "updated_at"), name="IndicatorConfigIn")


# TortoiseORM configuration for aerich
TortoiseORM = {
    "connections": {"default": "postgres://user:password@localhost:5432/trading_db"},
    "apps": {
        "models": {
            "models": ["app.models", "aerich.models"],
            "default_connection": "default",
        },
    },
}
