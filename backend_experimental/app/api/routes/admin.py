"""管理者パネル用APIルート — メトリクス設定の取得・更新"""

import logging
from fastapi import APIRouter, HTTPException

from app.schemas.admin import MetricsConfigUpdate
from app.services.metrics.metrics_config import MetricsConfigManager

logger = logging.getLogger(__name__)
router = APIRouter()

config_manager = MetricsConfigManager()


@router.get("/config/metrics")
async def get_metrics_config():
    """現在のメトリクス設定を取得"""
    return config_manager.get_config()


@router.put("/config/metrics")
async def update_metrics_config(body: MetricsConfigUpdate):
    """メトリクス設定を部分更新"""
    partial = body.model_dump(exclude_none=True)
    if not partial:
        raise HTTPException(status_code=400, detail="更新するフィールドが指定されていません")

    # ネストされたOptionalモデルからNoneを除去
    cleaned = {}
    for section_key, section_val in partial.items():
        if isinstance(section_val, dict):
            cleaned_section = {k: v for k, v in section_val.items() if v is not None}
            if cleaned_section:
                cleaned[section_key] = cleaned_section
        else:
            cleaned[section_key] = section_val

    if not cleaned:
        raise HTTPException(status_code=400, detail="更新するフィールドが指定されていません")

    try:
        updated = config_manager.update_config(cleaned)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/config/metrics/reset")
async def reset_metrics_config():
    """デフォルト値にリセット"""
    return config_manager.reset_to_defaults()


@router.get("/config/metrics/defaults")
async def get_metrics_defaults():
    """デフォルト値を取得（比較用）"""
    return config_manager.get_defaults()
