from db.connection import get_engine
from repositories.macro import MacroFeatureRepository, MacroRepository
from services.macro import MacroFeatureService


if __name__ == "__main__":
    engine = get_engine()
    macro_repo = MacroRepository(engine)
    feature_repo = MacroFeatureRepository(engine)
    service = MacroFeatureService(macro_repo, feature_repo)

    rows = service.persist_features()
    if rows.empty:
        print("No macro features were generated.")
    else:
        counts = rows.groupby("feature_name").size().sort_index()
        print("Macro feature build complete:")
        for feature_name, row_count in counts.items():
            print(f" - {feature_name}: {row_count}")
