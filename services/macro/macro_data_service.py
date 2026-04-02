class MacroDataService:
    """Provide grouped macro datasets used by the terminal's market-context layer."""

    def __init__(self, fred_client):
        self.fred = fred_client

    def get_treasury_curve(self):
        return {
            "2Y": self.fred.get_series("DGS2"),
            "5Y": self.fred.get_series("DGS5"),
            "10Y": self.fred.get_series("DGS10"),
            "30Y": self.fred.get_series("DGS30"),
        }

    def get_inflation(self):
        return self.fred.get_series("CPIAUCSL")
