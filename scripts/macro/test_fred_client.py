from config import FRED_API_KEY, FRED_BASE_URL
from services.macro import FredClient


if __name__ == "__main__":
    client = FredClient(api_key=FRED_API_KEY, base_url=FRED_BASE_URL)

    print("DGS10")
    print(client.get_series("DGS10").head())
    print()
    print("CPIAUCSL")
    print(client.get_series("CPIAUCSL").head())
