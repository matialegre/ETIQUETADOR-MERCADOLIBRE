from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/status")
def integrations_status() -> dict[str, list[dict[str, str]]]:
    return {
        "pos": [
            {"provider": "POS Central", "status": "connected", "last_sync": "2024-09-15T09:00:00Z"}
        ],
        "ecommerce": [
            {"provider": "Shopify", "status": "connected", "last_sync": "2024-09-15T08:45:00Z"}
        ],
        "reports": [
            {"name": "Ventas Mensuales", "status": "scheduled", "frequency": "daily"}
        ],
    }
