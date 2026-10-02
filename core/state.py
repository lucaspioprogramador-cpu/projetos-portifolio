"""
Estruturas de estado de portfÃ³lio/posiÃ§Ãµes.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class Position:
    symbol: str
    amount: float
    entry_price: float
    side: str
    stop: Optional[float] = None
    take: Optional[float] = None


@dataclass
class PortfolioState:
    balance: float = 0.0
    positions: List[Position] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


