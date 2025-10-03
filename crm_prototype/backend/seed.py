from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .database import get_session
from . import models


def seed_initial_data() -> None:
    with get_session() as session:
        if session.query(models.Customer).first():
            return

        segments = _create_segments(session)
        customers = _create_customers(session, segments)
        _create_campaigns(session, segments)
        _create_templates(session)
        _create_interactions(session, customers)


def _create_segments(session: Session) -> list[models.Segment]:
    segments = [
        models.Segment(
            name="Clientes Nuevos",
            description="Clientes incorporados en los últimos 30 días",
            criteria="created_at >= now() - interval '30 day'",
        ),
        models.Segment(
            name="Club Mundo",
            description="Miembros activos del club Mundo",
            criteria="tags LIKE '%club_mundo%'",
        ),
        models.Segment(
            name="VIP",
            description="Clientes con alto valor de compra",
            criteria="is_vip = true",
        ),
    ]
    session.add_all(segments)
    session.flush()
    return segments


def _create_customers(
    session: Session, segments: list[models.Segment]
) -> list[models.Customer]:
    customers = [
        models.Customer(
            email="sofia@example.com",
            full_name="Sofía Martinez",
            phone_number="5491122334455",
            source="ecommerce",
            tags="club_mundo,newsletter",
            preferences="prefiere_whatsapp",
            is_vip=True,
            segments=[segments[1], segments[2]],
        ),
        models.Customer(
            email="martin@example.com",
            full_name="Martin Gomez",
            phone_number="5491144455566",
            source="pos",
            tags="newsletter",
            preferences="prefiere_email",
            is_vip=False,
            segments=[segments[0]],
        ),
        models.Customer(
            email="carla@example.com",
            full_name="Carla Diaz",
            phone_number="5491133344455",
            source="referido",
            tags="club_mundo",
            preferences="",
            is_vip=False,
            segments=[segments[1]],
        ),
    ]
    session.add_all(customers)
    session.flush()
    return customers


def _create_campaigns(
    session: Session, segments: list[models.Segment]
) -> None:
    campaigns = [
        models.Campaign(
            name="Bienvenida nuevos clientes",
            channel="email",
            status="active",
            scheduled_at=datetime.utcnow() + timedelta(days=1),
            budget=500,
            notes="Secuencia de onboarding para captar engagement inicial",
            segment=segments[0],
        ),
        models.Campaign(
            name="Club Mundo VIP",
            channel="whatsapp",
            status="draft",
            scheduled_at=datetime.utcnow() + timedelta(days=7),
            budget=300,
            notes="Campaña con beneficios exclusivos para miembros VIP",
            segment=segments[2],
        ),
    ]
    session.add_all(campaigns)


def _create_templates(session: Session) -> None:
    templates = [
        models.MessageTemplate(
            title="Bienvenida WhatsApp",
            channel="whatsapp",
            content="Hola {nombre}, ¡gracias por sumarte! ¿Querés conocer nuestras novedades?",
            language="es",
            is_approved=True,
        ),
        models.MessageTemplate(
            title="Newsletter Club Mundo",
            channel="email",
            content="Hola {nombre}, este mes tenemos beneficios exclusivos para vos.",
            language="es",
            is_approved=False,
        ),
    ]
    session.add_all(templates)


def _create_interactions(
    session: Session, customers: list[models.Customer]
) -> None:
    interactions = [
        models.InteractionLog(
            customer_id=customers[0].id,
            channel="whatsapp",
            direction="outbound",
            message="Mensaje de bienvenida enviado",
        ),
        models.InteractionLog(
            customer_id=customers[1].id,
            channel="email",
            direction="outbound",
            message="Se envió newsletter mensual",
        ),
        models.InteractionLog(
            customer_id=customers[0].id,
            channel="whatsapp",
            direction="inbound",
            message="Cliente solicitó información del Club Mundo",
        ),
    ]
    session.add_all(interactions)
