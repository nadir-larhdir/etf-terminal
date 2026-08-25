"""Cross-market risk regime signal derived from persisted macro z-score features."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from fixed_income.analytics.result_models import RegimeSnapshot

if TYPE_CHECKING:
    from stores.protocols import MacroFeatureReader


class RegimeAnalytics:
    """Derive a Risk On / Neutral / Risk Off regime from macro Z60 features."""

    # Z60 feature_name -> sign of its contribution to risk-on (+1) vs risk-off (-1).
    # These are the same 60D level z-scores MacroFeatureService already computes and
    # persists, so the regime signal stays consistent with the rest of the macro pipeline.
    FEATURES = {"HY_OAS_Z60": -1.0, "IG_OAS_Z60": -1.0, "UST_2S10S_Z60": 1.0}
    # Two trading weeks of smoothing: alpha is 2/(span+1) = 0.18, so a single day has to
    # print a ~2.75 sigma composite on its own to move the label. A sustained shift of
    # half that size still crosses within a few sessions.
    EWM_SPAN = 10
    RISK_ON_THRESHOLD = 0.5
    RISK_OFF_THRESHOLD = -0.5

    def __init__(self, macro_feature_store: MacroFeatureReader) -> None:
        self.macro_feature_store = macro_feature_store

    def current_regime(self) -> RegimeSnapshot:
        """Return the latest Risk On / Neutral / Risk Off regime snapshot."""
        matrix = self.macro_feature_store.get_feature_matrix(feature_names=list(self.FEATURES))
        composite = self.composite_zscore(matrix)
        latest_z = float(composite.iloc[-1]) if not composite.empty else 0.0
        return self._bucket(latest_z)

    def composite_zscore(self, matrix: pd.DataFrame) -> pd.Series:
        """Sign-weight and average the Z60 features into one EWM-smoothed composite series."""
        signed = [
            matrix[feature_name] * sign
            for feature_name, sign in self.FEATURES.items()
            if feature_name in matrix.columns
        ]
        if not signed:
            return pd.Series(dtype=float)
        composite = pd.concat(signed, axis=1).mean(axis=1).dropna()
        if composite.empty:
            return composite
        return composite.ewm(span=self.EWM_SPAN).mean()

    def _bucket(self, z: float) -> RegimeSnapshot:
        """Map a composite z-score to a regime label and a continuous 0-100 gauge position."""
        position = 50.0 + max(-2.0, min(2.0, z)) / 2.0 * 38.0
        if z <= self.RISK_OFF_THRESHOLD:
            label = "Risk Off"
        elif z >= self.RISK_ON_THRESHOLD:
            label = "Risk On"
        else:
            label = "Neutral"
        return RegimeSnapshot(label=label, composite_zscore=z, position=position)
