from __future__ import annotations

from enum import Enum


class ListedExchange(str, Enum):
    NYSE = "NYSE"
    NASDAQ = "NASDAQ"
    NYSE_ARCA = "NYSE_ARCA"
    AMEX = "AMEX"


class MarketDataSource(str, Enum):
    POLYGON = "POLYGON"


class UniverseRefreshSession(str, Enum):
    PREMARKET = "PREMARKET"
    POSTMARKET = "POSTMARKET"
    INTRADAY = "INTRADAY"


class UniverseTier(str, Enum):
    TIER_1 = "TIER_1"
    TIER_2 = "TIER_2"
    TIER_3 = "TIER_3"


class Timeframe(str, Enum):
    MIN_5 = "5M"
    MIN_15 = "15M"
    HOUR_1 = "1H"
    HOUR_4 = "4H"
    DAY_1 = "1D"


class HTFBias(str, Enum):
    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    BEARISH = "BEARISH"


class SignalValue(str, Enum):
    LONG = "LONG"
    NONE = "NONE"


class SignalGrade(str, Enum):
    A_PLUS = "A+"
    A = "A"
    B = "B"
    IGNORE = "IGNORE"


class EntryType(str, Enum):
    AGGRESSIVE = "AGGRESSIVE"
    BASE = "BASE"
    CONFIRMATION = "CONFIRMATION"


class TrailMode(str, Enum):
    STRUCTURAL = "STRUCTURAL"
    NONE = "NONE"


class EvaluationStatus(str, Enum):
    PENDING = "PENDING"
    EVALUATING = "EVALUATING"
    FINALIZED = "FINALIZED"
    ERROR = "ERROR"
