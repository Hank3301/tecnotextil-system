"""Testes para a expiração automática de reservas em segundo plano (RN-02).

Valida a rotina que expira reservas vencidas e libera os rolos associados.
"""
import asyncio
from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.security import hash_senha
from app.database import Base, get_db
from app.main import app
from app.models.models import Rolo, ReservaTemporaria, LoteTingimento, Tecido, Usuario
from app.services.background_tasks import (
    expirar_reservas_vencidas_job,
    start_scheduler,
    stop_scheduler,
)
from app.utils import utcnow


@pytest.fixture()
def db_session():
    """Banco SQLite em memória, novo a cada teste, com FKs ligadas como em produção."""
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.database import habilitar_foreign_keys

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    habilitar_foreign_keys(engine)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()

    # Cria usuários de teste
    usuarios_teste = [
        Usuario(
            nm_usuario="Gabriel Gerente",
            cd_cpf="54149766606",
            ds_cargo="GERENTE",
            ds_login="gerente",
            ds_senha_hash=hash_senha("gerente123"),
        ),
        Usuario(
            nm_usuario="Vera Vendedora",
            cd_cpf="67654177704",
            ds_cargo="VENDEDOR",
            ds_login="vendedor",
            ds_senha_hash=hash_senha("vendedor123"),
        ),
    ]
    for u in usuarios_teste:
        session.add(u)
    session.commit()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _create_client(db_session):
    """Cria um TestClient com override do get_db."""
    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    return TestClient(app)


def _login_and_get_token(client: TestClient, login: str, senha: str) -> str:
    """Helper para fazer login e retornar access token."""
    r = client.post("/api/v1/auth/login", json={"login": login, "senha": senha})
    assert r.status_code == 200, f"Login falhou para {login}: {r.text}"
    return r.json()["access_token"]


@pytest.fixture()
def client_gerente(db_session):
    """Cliente autenticado como GERENTE (acesso total)."""
    test_client = _create_client(db_session)
    token = _login_and_get_token(test_client, "gerente", "gerente123")
    test_client.headers.update({"Authorization": f"Bearer {token}"})
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def client_vendedor(db_session):
    """Cliente autenticado como VENDEDOR."""
    test_client = _create_client(db_session)
    token = _login_and_get_token(test_client, "vendedor", "vendedor123")
    test_client.headers.update({"Authorization": f"Bearer {token}"})
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def setup_dados_base(client_gerente):
    """Cria tecido, lote e rolo base para testes."""
    # Criar tecido
    r = client_gerente.post("/api/v1/tecidos", json={
        "cd_tecido": "TEC-TEST-01",
        "nm_tecido": "Tecido Teste",
        "ds_composicao": "100% Algodão",
        "vl_largura_metros": 1.5,
        "vl_gramatura": 160,
        "vl_preco_metro": 20.0,
    })
    assert r.status_code == 201, r.text
    tecido = r.json()

    # Criar lote
    r = client_gerente.post("/api/v1/lotes", json={
        "id_tecido": tecido["id_tecido"],
        "cd_partida": "LOTE-TEST-001",
        "dt_fabricacao": "2026-01-15",
        "ds_tonalidade_cor": "Branco",
    })
    assert r.status_code == 201, r.text
    lote = r.json()

    # Criar rolo
    r = client_gerente.post("/api/v1/rolos", json={
        "id_lote": lote["id_lote"],
        "cd_barras": "ROL-TEST-001",
        "qt_metragem_inicial": 100.0,
        "ds_localizacao": "PRAT-A1",
    })
    assert r.status_code == 201, r.text
    rolo = r.json()

    return {"tecido": tecido, "lote": lote, "rolo": rolo}


class TestExpiracaoReservasBackground:
    """Testes para a rotina de expiração de reservas em background."""

    def test_expirar_reservas_vencidas_job_sem_reservas(self, db_session: Session):
        """Testa o job quando não há reservas vencidas."""
        qtd = expirar_reservas_vencidas_job(db_session)
        assert qtd == 0

    def test_expirar_reservas_vencidas_job_com_reserva_vencida(self, db_session: Session, setup_dados_base):
        """Testa o job expira uma reserva vencida e libera o rolo."""
        rolo_id = setup_dados_base["rolo"]["id_rolo"]

        # Criar reserva vencida (expiração no passado)
        agora = utcnow()
        reserva_vencida = ReservaTemporaria(
            id_rolo=rolo_id,
            qt_metragem_reservada=Decimal("10.0"),
            dt_criacao=agora - timedelta(minutes=30),
            dt_expiracao=agora - timedelta(minutes=10),  # Já expirou
            st_reserva="ATIVA",
        )
        db_session.add(reserva_vencida)

        # Colocar rolo como RESERVADO
        rolo = db_session.query(Rolo).filter(Rolo.id_rolo == rolo_id).first()
        rolo.st_rolo = "RESERVADO"
        db_session.commit()

        # Executar job
        qtd = expirar_reservas_vencidas_job(db_session)

        # Verificar resultado
        assert qtd == 1

        # Verificar reserva ficou EXPIRADA
        db_session.refresh(reserva_vencida)
        assert reserva_vencida.st_reserva == "EXPIRADA"

        # Verificar rolo voltou a DISPONIVEL
        db_session.refresh(rolo)
        assert rolo.st_rolo == "DISPONIVEL"

    def test_expirar_reservas_vencidas_job_nao_expira_ativa(self, db_session: Session, setup_dados_base):
        """Testa que reservas ainda válidas não são expiradas."""
        rolo_id = setup_dados_base["rolo"]["id_rolo"]

        # Criar reserva ainda válida (expiração no futuro)
        agora = utcnow()
        reserva_ativa = ReservaTemporaria(
            id_rolo=rolo_id,
            qt_metragem_reservada=Decimal("10.0"),
            dt_criacao=agora,
            dt_expiracao=agora + timedelta(minutes=20),  # Ainda válida
            st_reserva="ATIVA",
        )
        db_session.add(reserva_ativa)

        rolo = db_session.query(Rolo).filter(Rolo.id_rolo == rolo_id).first()
        rolo.st_rolo = "RESERVADO"
        db_session.commit()

        # Executar job
        qtd = expirar_reservas_vencidas_job(db_session)

        # Verificar que nada foi expirado
        assert qtd == 0
        db_session.refresh(reserva_ativa)
        assert reserva_ativa.st_reserva == "ATIVA"

    def test_expirar_reservas_vencidas_job_multiplas(self, db_session: Session, setup_dados_base):
        """Testa expiração de múltiplas reservas vencidas."""
        rolo_id = setup_dados_base["rolo"]["id_rolo"]

        # Criar segundo rolo
        rolo2 = Rolo(
            id_lote=setup_dados_base["lote"]["id_lote"],
            cd_barras="ROL-TEST-002",
            qt_metragem_inicial=Decimal("50.0"),
            qt_metragem_atual=Decimal("50.0"),
            ds_localizacao="PRAT-A2",
            st_rolo="RESERVADO",
        )
        db_session.add(rolo2)
        db_session.commit()
        db_session.refresh(rolo2)

        agora = utcnow()

        # Reservas vencidas em dois rolos diferentes
        reserva1 = ReservaTemporaria(
            id_rolo=rolo_id,
            qt_metragem_reservada=Decimal("10.0"),
            dt_criacao=agora - timedelta(minutes=30),
            dt_expiracao=agora - timedelta(minutes=5),
            st_reserva="ATIVA",
        )
        reserva2 = ReservaTemporaria(
            id_rolo=rolo2.id_rolo,
            qt_metragem_reservada=Decimal("5.0"),
            dt_criacao=agora - timedelta(minutes=25),
            dt_expiracao=agora - timedelta(minutes=3),
            st_reserva="ATIVA",
        )
        db_session.add_all([reserva1, reserva2])
        db_session.commit()

        # Executar job
        qtd = expirar_reservas_vencidas_job(db_session)

        assert qtd == 2
        db_session.refresh(reserva1)
        db_session.refresh(reserva2)
        assert reserva1.st_reserva == "EXPIRADA"
        assert reserva2.st_reserva == "EXPIRADA"

        # Verificar ambos os rolos liberados
        db_session.refresh(rolo2)
        rolo1 = db_session.query(Rolo).filter(Rolo.id_rolo == rolo_id).first()
        assert rolo1.st_rolo == "DISPONIVEL"
        assert rolo2.st_rolo == "DISPONIVEL"

    def test_expirar_reservas_vencidas_job_reserva_ja_cancelada(self, db_session: Session, setup_dados_base):
        """Testa que reservas não-ATIVAS não são processadas."""
        rolo_id = setup_dados_base["rolo"]["id_rolo"]

        agora = utcnow()

        # Reserva CANCELADA vencida
        reserva_cancelada = ReservaTemporaria(
            id_rolo=rolo_id,
            qt_metragem_reservada=Decimal("10.0"),
            dt_criacao=agora - timedelta(minutes=30),
            dt_expiracao=agora - timedelta(minutes=10),
            st_reserva="CANCELADA",
        )
        db_session.add(reserva_cancelada)

        # Reserva EXPIRADA vencida
        reserva_expirada = ReservaTemporaria(
            id_rolo=rolo_id,
            qt_metragem_reservada=Decimal("5.0"),
            dt_criacao=agora - timedelta(minutes=40),
            dt_expiracao=agora - timedelta(minutes=20),
            st_reserva="EXPIRADA",
        )
        db_session.add(reserva_expirada)

        # Reserva CONFIRMADA vencida (virou ordem de corte)
        reserva_confirmada = ReservaTemporaria(
            id_rolo=rolo_id,
            qt_metragem_reservada=Decimal("8.0"),
            dt_criacao=agora - timedelta(minutes=50),
            dt_expiracao=agora - timedelta(minutes=30),
            st_reserva="CONFIRMADA",
        )
        db_session.add(reserva_confirmada)
        db_session.commit()

        # Executar job
        qtd = expirar_reservas_vencidas_job(db_session)

        assert qtd == 0  # Nenhuma reserva ATIVA para expirar


class TestSchedulerLifecycle:
    """Testes para o ciclo de vida do scheduler."""

    @pytest.mark.asyncio
    async def test_scheduler_start_stop(self):
        """Testa inicialização e parada do scheduler."""
        # Start scheduler
        scheduler = start_scheduler()
        assert scheduler is not None
        assert scheduler.running

        # Verificar que o job foi adicionado
        jobs = scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == "expirar_reservas"

        # Stop scheduler
        stop_scheduler()
        # Give the event loop a moment to process the shutdown
        await asyncio.sleep(0.1)
        assert scheduler.running is False

    @pytest.mark.asyncio
    async def test_scheduler_idempotent_start(self):
        """Testa que chamar start_scheduler múltiplas vezes não cria duplicatas."""
        scheduler1 = start_scheduler()
        assert scheduler1.running

        scheduler2 = start_scheduler()
        assert scheduler2 is scheduler1
        assert scheduler2.running

        # Deve ter apenas um job
        jobs = scheduler1.get_jobs()
        assert len(jobs) == 1

        stop_scheduler()
        await asyncio.sleep(0.1)


class TestIntegracaoComAPI:
    """Testes de integração com a API real."""

    def test_reserva_expirada_via_job_libera_rolo_para_nova_reserva(self, client_vendedor, setup_dados_base, db_session):
        """Testa fluxo completo: reserva expira via job -> rolo disponível -> nova reserva."""
        rolo_id = setup_dados_base["rolo"]["id_rolo"]

        # 1. Criar reserva via API
        r = client_vendedor.post("/api/v1/vendas/reservas", json={
            "id_rolo": rolo_id,
            "qt_metragem_reservada": 10.0,
        })
        assert r.status_code == 201, r.text
        reserva = r.json()
        reserva_id = reserva["id_reserva"]

        # 2. Manipular banco diretamente para simular expiração
        reserva_db = db_session.query(ReservaTemporaria).filter(ReservaTemporaria.id_reserva == reserva_id).first()
        assert reserva_db is not None, "Reserva não encontrada no banco de teste"
        reserva_db.dt_expiracao = utcnow() - timedelta(minutes=1)

        rolo_db = db_session.query(Rolo).filter(Rolo.id_rolo == rolo_id).first()
        rolo_db.st_rolo = "RESERVADO"
        db_session.commit()

        # 3. Executar job de expiração
        qtd = expirar_reservas_vencidas_job(db_session)
        assert qtd == 1

        # 4. Tentar criar nova reserva no mesmo rolo (deve funcionar)
        r = client_vendedor.post("/api/v1/vendas/reservas", json={
            "id_rolo": rolo_id,
            "qt_metragem_reservada": 5.0,
        })
        assert r.status_code == 201, r.text
        nova_reserva = r.json()
        assert nova_reserva["id_reserva"] != reserva_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])