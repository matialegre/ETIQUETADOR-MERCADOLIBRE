from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..dependencies import get_db

router = APIRouter(prefix="/segments", tags=["segments"])


@router.get("/", response_model=List[schemas.SegmentRead])
def list_segments(db: Session = Depends(get_db)) -> List[schemas.SegmentRead]:
    return crud.list_segments(db)


@router.post("/", response_model=schemas.SegmentRead, status_code=201)
def create_segment(
    segment: schemas.SegmentCreate,
    db: Session = Depends(get_db),
) -> schemas.SegmentRead:
    return crud.create_segment(db, segment)
