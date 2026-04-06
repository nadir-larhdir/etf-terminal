import logging

from db.connection import get_engine
from stores.macro import MacroFeatureStore, MacroStore
from scripts.logging_utils import configure_logging
from services.macro import MacroFeatureService


logger = logging.getLogger(__name__)


def main() -> None:
    configure_logging()
    engine = get_engine()
    macro_store = MacroStore(engine)
    feature_store = MacroFeatureStore(engine)
    service = MacroFeatureService(macro_store, feature_store)

    rows = service.persist_features()
    if rows.empty:
        logger.info("No macro features were generated.")
    else:
        counts = rows.groupby("feature_name").size().sort_index()
        logger.info("Macro feature build complete:")
        for feature_name, row_count in counts.items():
            logger.info(" - %s: %s", feature_name, row_count)


if __name__ == "__main__":
    main()
