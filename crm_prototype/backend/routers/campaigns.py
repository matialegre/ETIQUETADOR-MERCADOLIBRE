from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..dependencies import get_db

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("/", response_model=List[schemas.CampaignRead])
def list_campaigns(db: Session = Depends(get_db)) -> List[schemas.CampaignRead]:
    return crud.list_campaigns(db)


@router.post("/", response_model=schemas.CampaignRead, status_code=201)
def create_campaign(
    campaign: schemas.CampaignCreate,
    db: Session = Depends(get_db),
) -> schemas.CampaignRead:
    return crud.create_campaign(db, campaign)
