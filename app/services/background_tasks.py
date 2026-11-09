"""Background tasks for the TecnoTêxtil application.

This module manages periodic background jobs using APScheduler.
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.models import ReservaTemporaria, Rolo
from app.utils import utcnow


# Global scheduler instance
scheduler: Optional[AsyncIOScheduler] = None


def _expirar_reservas_vencidas_core(db: Session) -> int:
    """Core logic for expiring reservations - can be used with any session."""
    agora = utcnow()
    reservas_vencidas = (
        db.query(ReservaTemporaria)
        .filter(
            ReservaTemporaria.st_reserva == "ATIVA",
            ReservaTemporaria.dt_expiracao <= agora
        )
        .all()
    )

    qtd_expiradas = 0
    for reserva in reservas_vencidas:
        reserva.st_reserva = "EXPIRADA"

        # Se o rolo associado ainda estiver bloqueado pela reserva, libera seu status
        rolo = db.query(Rolo).filter(Rolo.id_rolo == reserva.id_rolo).first()
        if rolo and rolo.st_rolo == "RESERVADO":
            rolo.st_rolo = "DISPONIVEL"

        qtd_expiradas += 1

    if qtd_expiradas > 0:
        db.commit()

    return qtd_expiradas


def expirar_reservas_vencidas_job(db: Optional[Session] = None) -> int:
    """
    Job that runs periodically to expire reservations.

    If db is provided, uses that session (for testing).
    Otherwise creates its own database session to avoid connection leaks.
    Returns the number of reservations expired.
    """
    owns_session = db is None
    if owns_session:
        db = SessionLocal()

    try:
        qtd = _expirar_reservas_vencidas_core(db)

        if qtd > 0:
            print(f"[{datetime.now(timezone.utc).isoformat()}] Expiradas {qtd} reserva(s) vencida(s)")

        return qtd
    except Exception as e:
        db.rollback()
        print(f"[{datetime.now(timezone.utc).isoformat()}] Erro ao expirar reservas: {e}")
        raise
    finally:
        if owns_session:
            db.close()


def start_scheduler() -> AsyncIOScheduler:
    """Start the APScheduler with the expiration job."""
    global scheduler

    if scheduler is not None and scheduler.running:
        return scheduler

    scheduler = AsyncIOScheduler(timezone="UTC")

    # Add the expiration job - runs every 60 seconds
    scheduler.add_job(
        expirar_reservas_vencidas_job,
        trigger=IntervalTrigger(seconds=60),
        id="expirar_reservas",
        name="Expirar reservas vencidas (RN-02)",
        replace_existing=True,
        max_instances=1,  # Prevent overlapping executions
    )

    scheduler.start()
    print(f"[{datetime.now(timezone.utc).isoformat()}] Scheduler started - job 'expirar_reservas' scheduled every 60s")

    return scheduler


def stop_scheduler() -> None:
    """Stop the APScheduler gracefully."""
    global scheduler

    if scheduler is not None and scheduler.running:
        scheduler.shutdown(wait=True)
        print(f"[{datetime.now(timezone.utc).isoformat()}] Scheduler stopped")
        scheduler = None


@asynccontextmanager
async def scheduler_lifespan(app):
    """FastAPI lifespan context manager for the scheduler."""
    # Startup
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()


def get_scheduler() -> Optional[AsyncIOScheduler]:
    """Get the current scheduler instance."""
    return scheduler