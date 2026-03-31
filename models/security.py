from dataclasses import dataclass


@dataclass
class Security:
    ticker: str
    name: str
    asset_class: str
