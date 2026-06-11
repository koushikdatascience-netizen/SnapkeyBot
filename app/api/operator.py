import secrets
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.services.telegram import accept_operator_update

router = APIRouter(prefix="/operator", tags=["operator"])


@router.post("/telegram", include_in_schema=False)
async def telegram_webhook(
    update: dict[str, Any],
    db: Annotated[AsyncSession, Depends(get_db)],
    secret: Annotated[str | None, Header(alias="X-Telegram-Bot-Api-Secret-Token")] = None,
) -> dict[str, bool]:
    settings = get_settings()
    if not settings.concierge_mode or not settings.telegram_webhook_secret:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if not secret or not secrets.compare_digest(secret, settings.telegram_webhook_secret):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook secret")
    return {"accepted": await accept_operator_update(db, update)}
