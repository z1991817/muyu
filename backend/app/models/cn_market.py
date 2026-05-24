from __future__ import annotations

from app.models.common import APIModel


class CnMarketIndex(APIModel):
    symbol: str
    name: str
    price: float
    change: float
    change_pct: float
    url: str
    updated_at: str
    disclaimer: str


class CnMarketStock(APIModel):
    symbol: str
    name: str
    price: float
    change: float
    change_pct: float
    volume: str
    turnover: str
    url: str
    updated_at: str
    disclaimer: str


class CnFundFlow(APIModel):
    name: str
    value: str
    change_pct: float
    direction: str


class CnLimitStock(APIModel):
    symbol: str
    name: str
    price: float
    change_pct: float
    reason: str
    url: str


class CnMarketAnalysis(APIModel):
    fund_flows: list[CnFundFlow]
    limit_up: list[CnLimitStock]
    limit_down: list[CnLimitStock]


class CnMarketResponse(APIModel):
    indices: list[CnMarketIndex]
    stocks: list[CnMarketStock]
    analysis: CnMarketAnalysis
    stale: bool = False
    updated_at: str
