from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..dependencies import get_db

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/", response_model=List[schemas.CustomerRead])
def list_customers(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> List[schemas.CustomerRead]:
    return crud.list_customers(db, skip=skip, limit=limit)


@router.post("/", response_model=schemas.CustomerRead, status_code=201)
def create_customer(
    customer: schemas.CustomerCreate,
    db: Session = Depends(get_db),
) -> schemas.CustomerRead:
    return crud.create_customer(db, customer)


@router.get("/{customer_id}", response_model=schemas.CustomerRead)
def get_customer(customer_id: int, db: Session = Depends(get_db)) -> schemas.CustomerRead:
    db_customer = crud.get_customer(db, customer_id)
    if not db_customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return db_customer


@router.put("/{customer_id}", response_model=schemas.CustomerRead)
def update_customer(
    customer_id: int,
    customer_update: schemas.CustomerUpdate,
    db: Session = Depends(get_db),
) -> schemas.CustomerRead:
    db_customer = crud.get_customer(db, customer_id)
    if not db_customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return crud.update_customer(db, db_customer, customer_update)
