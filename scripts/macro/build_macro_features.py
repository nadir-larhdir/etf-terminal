from db.connection import get_engine
from stores.macro import MacroFeatureStore, MacroStore
from services.macro import MacroFeatureService


def main() -> None:
    engine = get_engine()
    macro_store = MacroStore(engine)
    feature_store = MacroFeatureStore(engine)
    service = MacroFeatureService(macro_store, feature_store)

    rows = service.persist_features()
    if rows.empty:
        print("No macro features were generated.")
    else:
        counts = rows.groupby("feature_name").size().sort_index()
        print("Macro feature build complete:")
        for feature_name, row_count in counts.items():
            print(f" - {feature_name}: {row_count}")


if __name__ == "__main__":
    main()
