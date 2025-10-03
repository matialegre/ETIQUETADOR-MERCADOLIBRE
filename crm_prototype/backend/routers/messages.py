from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..dependencies import get_db

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/templates", response_model=List[schemas.MessageTemplateRead])
def list_templates(db: Session = Depends(get_db)) -> List[schemas.MessageTemplateRead]:
    return crud.list_templates(db)


@router.post(
    "/templates",
    response_model=schemas.MessageTemplateRead,
    status_code=201,
)
def create_template(
    template: schemas.MessageTemplateCreate,
    db: Session = Depends(get_db),
) -> schemas.MessageTemplateRead:
    return crud.create_template(db, template)


@router.get("/interactions", response_model=List[schemas.InteractionLogRead])
def list_interactions(
    customer_id: int | None = None,
    db: Session = Depends(get_db),
) -> List[schemas.InteractionLogRead]:
    return crud.list_interactions(db, customer_id)


@router.post(
    "/interactions",
    response_model=schemas.InteractionLogRead,
    status_code=201,
)
def log_interaction(
    interaction: schemas.InteractionLogCreate,
    db: Session = Depends(get_db),
) -> schemas.InteractionLogRead:
    return crud.log_interaction(db, interaction)
