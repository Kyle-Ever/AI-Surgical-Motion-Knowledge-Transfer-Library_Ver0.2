"""
メトリクス設定マネージャー
JSON設定ファイルからパラメータを読み書きするシングルトン
"""

import json
import copy
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

# デフォルト値（ハードコードされていた値をそのまま保持）
DEFAULTS: Dict[str, Any] = {
    "weights": {
        "a1": 0.40,
        "a2": 0.35,
        "a3": 0.25,
        "b1": 0.40,
        "b2": 0.30,
        "b3": 0.30,
        "group_a": 0.50,
        "group_b": 0.50,
    },
    "thresholds": {
        "idle_velocity_threshold": 0.005,
        "idle_velocity_threshold_pixel": 5.0,
        "micro_pause_max_sec": 1.0,
        "check_pause_max_sec": 3.0,
        "movement_velocity_threshold": 0.008,
        "movement_velocity_threshold_pixel": 8.0,
        "smoothing_window": 5,
        "hysteresis_ratio": 0.7,
        "adaptive_threshold": True,
        "idle_percentile": 15,
        "movement_percentile": 30,
    },
    "scoring": {
        "a1_max_path_pixel": 50000.0,
        "a1_max_path_normalized": 10.0,
        "a2_sparc_min": -7.0,
        "a2_sparc_max": -1.0,
        "a3_both_hands_min_ratio": 0.30,
        "a3_correlation_weight": 0.60,
        "a3_balance_weight": 0.40,
        "b1_max_idle_ratio": 0.30,
        "b2_max_movements_per_minute": 60.0,
        "b3_max_area_pixel": 500000.0,
        "b3_max_area_normalized": 0.10,
    },
    "sparc": {
        "freq_cutoff_hz": 20.0,
        "amplitude_threshold": 0.05,
    },
}

CONFIG_PATH = Path(__file__).resolve().parents[3] / "configs" / "metrics_config.json"


def _deep_merge(base: dict, override: dict) -> dict:
    """baseにoverrideをマージ（ネスト対応）"""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def validate_config(config: Dict[str, Any]) -> None:
    """設定値のバリデーション。不正な場合はValueErrorを送出"""
    w = config.get("weights", {})

    # 重み合計チェック
    group_a_sum = w.get("a1", 0) + w.get("a2", 0) + w.get("a3", 0)
    if abs(group_a_sum - 1.0) > 0.01:
        raise ValueError(f"Group A重みの合計が1.0ではありません: {group_a_sum:.3f}")

    group_b_sum = w.get("b1", 0) + w.get("b2", 0) + w.get("b3", 0)
    if abs(group_b_sum - 1.0) > 0.01:
        raise ValueError(f"Group B重みの合計が1.0ではありません: {group_b_sum:.3f}")

    overall_sum = w.get("group_a", 0) + w.get("group_b", 0)
    if abs(overall_sum - 1.0) > 0.01:
        raise ValueError(f"総合重みの合計が1.0ではありません: {overall_sum:.3f}")

    # 重みは正の値
    for key, val in w.items():
        if val < 0:
            raise ValueError(f"重み '{key}' は正の値でなければなりません: {val}")

    # 閾値チェック
    t = config.get("thresholds", {})
    for key in [
        "idle_velocity_threshold", "idle_velocity_threshold_pixel",
        "movement_velocity_threshold", "movement_velocity_threshold_pixel",
    ]:
        if key in t and t[key] <= 0:
            raise ValueError(f"閾値 '{key}' は正の値でなければなりません: {t[key]}")

    if "micro_pause_max_sec" in t and "check_pause_max_sec" in t:
        if t["micro_pause_max_sec"] >= t["check_pause_max_sec"]:
            raise ValueError(
                f"micro_pause_max_sec ({t['micro_pause_max_sec']}) は "
                f"check_pause_max_sec ({t['check_pause_max_sec']}) より小さくなければなりません"
            )

    if "smoothing_window" in t:
        sw = t["smoothing_window"]
        if not isinstance(sw, int) or sw < 3 or sw > 15 or sw % 2 == 0:
            raise ValueError(f"smoothing_window は3-15の奇数でなければなりません: {sw}")

    if "hysteresis_ratio" in t:
        hr = t["hysteresis_ratio"]
        if hr <= 0 or hr >= 1.0:
            raise ValueError(f"hysteresis_ratio は0-1の範囲でなければなりません: {hr}")

    for pct_key in ["idle_percentile", "movement_percentile"]:
        if pct_key in t:
            pct = t[pct_key]
            if pct < 1 or pct > 50:
                raise ValueError(f"{pct_key} は1-50の範囲でなければなりません: {pct}")

    # スコアリングチェック
    s = config.get("scoring", {})
    for key in [
        "a1_max_path_pixel", "a1_max_path_normalized",
        "a3_both_hands_min_ratio",
        "b1_max_idle_ratio",
        "b2_max_movements_per_minute",
        "b3_max_area_pixel", "b3_max_area_normalized",
    ]:
        if key in s and s[key] <= 0:
            raise ValueError(f"スコアリング '{key}' は正の値でなければなりません: {s[key]}")

    if "a2_sparc_min" in s and "a2_sparc_max" in s:
        if s["a2_sparc_min"] >= s["a2_sparc_max"]:
            raise ValueError("a2_sparc_min は a2_sparc_max より小さくなければなりません")

    if "a3_correlation_weight" in s and "a3_balance_weight" in s:
        cw_sum = s["a3_correlation_weight"] + s["a3_balance_weight"]
        if abs(cw_sum - 1.0) > 0.01:
            raise ValueError(f"A3協調重みの合計が1.0ではありません: {cw_sum:.3f}")

    # SPARCチェック
    sp = config.get("sparc", {})
    if "freq_cutoff_hz" in sp and sp["freq_cutoff_hz"] <= 0:
        raise ValueError(f"freq_cutoff_hz は正の値でなければなりません: {sp['freq_cutoff_hz']}")
    if "amplitude_threshold" in sp and sp["amplitude_threshold"] <= 0:
        raise ValueError(f"amplitude_threshold は正の値でなければなりません: {sp['amplitude_threshold']}")


class MetricsConfigManager:
    """メトリクス設定のシングルトンマネージャー"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self._load()

    def _load(self) -> None:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                file_config = json.load(f)
            self._config = _deep_merge(DEFAULTS, file_config)
        else:
            self._config = copy.deepcopy(DEFAULTS)
            self._save()
        self._loaded = True

    def _save(self) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)

    def get_config(self) -> Dict[str, Any]:
        self._ensure_loaded()
        return copy.deepcopy(self._config)

    def get_defaults(self) -> Dict[str, Any]:
        return copy.deepcopy(DEFAULTS)

    def update_config(self, partial: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_loaded()
        merged = _deep_merge(self._config, partial)
        validate_config(merged)
        self._config = merged
        self._save()
        logger.info("メトリクス設定を更新しました")
        return copy.deepcopy(self._config)

    def reset_to_defaults(self) -> Dict[str, Any]:
        self._config = copy.deepcopy(DEFAULTS)
        self._save()
        self._loaded = True
        logger.info("メトリクス設定をデフォルトにリセットしました")
        return copy.deepcopy(self._config)

    def reload(self) -> None:
        """ファイルから再読み込み"""
        self._loaded = False
        self._ensure_loaded()
