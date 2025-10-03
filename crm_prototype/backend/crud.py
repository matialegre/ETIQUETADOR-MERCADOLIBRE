from __future__ import annotations

from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from . import models, schemas


def list_customers(db: Session, skip: int = 0, limit: int = 100) -> List[models.Customer]:
    return (
        db.query(models.Customer)
        .order_by(models.Customer.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_customer(db: Session, customer_id: int) -> Optional[models.Customer]:
    return db.query(models.Customer).filter(models.Customer.id == customer_id).first()


def create_customer(db: Session, customer: schemas.CustomerCreate) -> models.Customer:
    db_customer = models.Customer(
        email=customer.email,
        full_name=customer.full_name,
        phone_number=customer.phone_number,
        source=customer.source,
        tags=customer.tags,
        preferences=customer.preferences,
        is_vip=customer.is_vip,
    )
    if customer.segment_ids:
        segments = (
            db.query(models.Segment)
            .filter(models.Segment.id.in_(customer.segment_ids))
            .all()
        )
        db_customer.segments.extend(segments)
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    return db_customer


def update_customer(
    db: Session, customer_db: models.Customer, customer_update: schemas.CustomerUpdate
) -> models.Customer:
    update_data = customer_update.dict(exclude_unset=True)
    segment_ids = update_data.pop("segment_ids", None)

    for field, value in update_data.items():
        setattr(customer_db, field, value)

    if segment_ids is not None:
        segments = (
            db.query(models.Segment)
            .filter(models.Segment.id.in_(segment_ids))
            .all()
        )
        customer_db.segments = segments

    db.add(customer_db)
    db.commit()
    db.refresh(customer_db)
    return customer_db


def list_segments(db: Session) -> List[models.Segment]:
    return db.query(models.Segment).order_by(models.Segment.name.asc()).all()


def create_segment(db: Session, segment: schemas.SegmentCreate) -> models.Segment:
    db_segment = models.Segment(**segment.dict())
    db.add(db_segment)
    db.commit()
    db.refresh(db_segment)
    return db_segment


def list_campaigns(db: Session) -> List[models.Campaign]:
    return (
        db.query(models.Campaign)
        .order_by(models.Campaign.created_at.desc())
        .all()
    )


def create_campaign(db: Session, campaign: schemas.CampaignCreate) -> models.Campaign:
    db_campaign = models.Campaign(**campaign.dict())
    db.add(db_campaign)
    db.commit()
    db.refresh(db_campaign)
    return db_campaign


def list_templates(db: Session) -> List[models.MessageTemplate]:
    return (
        db.query(models.MessageTemplate)
        .order_by(models.MessageTemplate.created_at.desc())
        .all()
    )


def create_template(
    db: Session, template: schemas.MessageTemplateCreate
) -> models.MessageTemplate:
    db_template = models.MessageTemplate(**template.dict())
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template


def log_interaction(
    db: Session, interaction: schemas.InteractionLogCreate
) -> models.InteractionLog:
    db_interaction = models.InteractionLog(**interaction.dict())
    db.add(db_interaction)
    db.commit()
    db.refresh(db_interaction)
    return db_interaction


def list_interactions(
    db: Session, customer_id: Optional[int] = None
) -> List[models.InteractionLog]:
    query = db.query(models.InteractionLog).order_by(
        models.InteractionLog.occurred_at.desc()
    )
    if customer_id is not None:
        query = query.filter(models.InteractionLog.customer_id == customer_id)
    return query.all()


def dashboard_summary(db: Session) -> schemas.DashboardSummary:
    total_customers = db.query(models.Customer).count()
    vip_customers = db.query(models.Customer).filter(models.Customer.is_vip.is_(True)).count()
    active_campaigns = db.query(models.Campaign).filter(models.Campaign.status == "active").count()
    queued_messages = db.query(models.MessageTemplate).filter(
        models.MessageTemplate.is_approved.is_(False)
    ).count()
    return schemas.DashboardSummary(
        total_customers=total_customers,
        vip_customers=vip_customers,
        active_campaigns=active_campaigns,
        queued_messages=queued_messages,
    )
