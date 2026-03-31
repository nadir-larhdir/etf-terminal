from dataclasses import dataclass
from models.security import Security


@dataclass
class ETF(Security):
    flow_usd_mm: float = 0.0
    premium_discount_pct: float = 0.0
    desk_note: str = ""
