"""应用状态持久化 API 路由 — 统一管理所有浏览器状态到服务端。"""

import json
import logging
import os

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/state", tags=["状态持久化"])

_STATE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")
_STATE_FILE = os.path.join(_STATE_DIR, "app_state.json")


@router.post("/save")
async def state_save(data: dict):
    """保存全部应用状态到服务端，每次覆盖之前的。"""
    try:
        os.makedirs(_STATE_DIR, exist_ok=True)
        with open(_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return {"success": True}
    except Exception as exc:
        logger.exception("应用状态保存失败")
        raise HTTPException(status_code=500, detail=f"保存失败: {exc}") from exc


@router.get("/load")
async def state_load():
    """从服务端加载全部应用状态。"""
    try:
        if not os.path.exists(_STATE_FILE):
            return {}
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.exception("应用状态加载失败")
        raise HTTPException(status_code=500, detail=f"加载失败: {exc}") from exc
