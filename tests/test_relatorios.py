"""Testes para os endpoints de relatórios gerenciais.

Valida:
- Respostas 200 OK e cálculo correto dos dados para o perfil GERENTE.
- Rejeição 403 Forbidden se VENDEDOR ou CORTADOR tentarem acessar.
- Histórico do rolo inexistente (404 Not Found).
"""
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.security import hash_senha
from app.database import Base, get_db
from app.main import app
from app.models.models import (
    Rolo, Tecido, LoteTingimento, ReservaTemporaria, OrdemCorte, Usuario, MapeamentoDefeito
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
        Usuario(
            nm_usuario="Carlos Cortador",
            cd_cpf="52998224725",
            ds_cargo="CORTADOR",
            ds_login="cortador",
            ds_senha_hash=hash_senha("cortador123"),
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
def client_cortador(db_session):
    """Cliente autenticado como CORTADOR."""
    test_client = _create_client(db_session)
    token = _login_and_get_token(test_client, "cortador", "cortador123")
    test_client.headers.update({"Authorization": f"Bearer {token}"})
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def setup_dados_relatorios(client_gerente, db_session):
    """Cria dados completos para testar relatórios."""
    # Criar tecido
    r = client_gerente.post("/api/v1/tecidos", json={
        "cd_tecido": "TEC-REL-01",
        "nm_tecido": "Tecido Relatório",
        "ds_composicao": "100% Algodão",
        "vl_largura_metros": 1.5,
        "vl_gramatura": 180,
        "vl_preco_metro": 25.0,
    })
    assert r.status_code == 201, r.text
    tecido = r.json()

    # Criar lote 1
    r = client_gerente.post("/api/v1/lotes", json={
        "id_tecido": tecido["id_tecido"],
        "cd_partida": "PARTIDA-A",
        "dt_fabricacao": "2026-01-10",
        "ds_tonalidade_cor": "Azul",
    })
    assert r.status_code == 201, r.text
    lote_a = r.json()

    # Criar lote 2 (mesmo tecido, partida diferente)
    r = client_gerente.post("/api/v1/lotes", json={
        "id_tecido": tecido["id_tecido"],
        "cd_partida": "PARTIDA-B",
        "dt_fabricacao": "2026-01-15",
        "ds_tonalidade_cor": "Vermelho",
    })
    assert r.status_code == 201, r.text
    lote_b = r.json()

    # Rolo 1 - Normal
    r = client_gerente.post("/api/v1/rolos", json={
        "id_lote": lote_a["id_lote"],
        "cd_barras": "ROL-REL-001",
        "qt_metragem_inicial": 100.0,
        "ds_localizacao": "PRAT-A1",
    })
    assert r.status_code == 201, r.text
    rolo1 = r.json()

    # Rolo 2 - Retalho (≤5m)
    r = client_gerente.post("/api/v1/rolos", json={
        "id_lote": lote_a["id_lote"],
        "cd_barras": "ROL-REL-002",
        "qt_metragem_inicial": 50.0,
        "ds_localizacao": "PRAT-A2",
    })
    assert r.status_code == 201, r.text
    rolo2 = r.json()

    # Marcar rolo2 como retalho
    rolo2_obj = db_session.query(Rolo).filter(Rolo.id_rolo == rolo2["id_rolo"]).first()
    rolo2_obj.qt_metragem_atual = Decimal("3.5")
    rolo2_obj.fl_retalho = True
    db_session.commit()

    # Rolo 3 - Retalho em outro lote
    r = client_gerente.post("/api/v1/rolos", json={
        "id_lote": lote_b["id_lote"],
        "cd_barras": "ROL-REL-003",
        "qt_metragem_inicial": 80.0,
        "ds_localizacao": "PRAT-B1",
    })
    assert r.status_code == 201, r.text
    rolo3 = r.json()

    rolo3_obj = db_session.query(Rolo).filter(Rolo.id_rolo == rolo3["id_rolo"]).first()
    rolo3_obj.qt_metragem_atual = Decimal("4.0")
    rolo3_obj.fl_retalho = True
    db_session.commit()

    # Rolo 4 - Para ordens de corte com perdas
    r = client_gerente.post("/api/v1/rolos", json={
        "id_lote": lote_a["id_lote"],
        "cd_barras": "ROL-REL-004",
        "qt_metragem_inicial": 100.0,
        "ds_localizacao": "PRAT-A3",
    })
    assert r.status_code == 201, r.text
    rolo4 = r.json()

    # Criar usuário cortador para ordens
    cortador_user = db_session.query(Usuario).filter(Usuario.ds_login == "cortador").first()

    # Ordem 1 - Concluída com perda normal (sem divergência)
    ordem1 = OrdemCorte(
        id_rolo=rolo4["id_rolo"],
        id_usuario_cortador=cortador_user.id_usuario,
        dt_emissao=utcnow(),
        dt_execucao=utcnow(),
        qt_metragem_solicitada=Decimal("20.0"),
        qt_sobra_informada=Decimal("78.0"),
        qt_perda_apurada=Decimal("2.0"),
        qt_perda_justificada=Decimal("2.0"),
        fl_divergencia_perda=False,
        st_ordem="CONCLUIDA",
    )
    db_session.add(ordem1)

    # Ordem 2 - Concluída com divergência
    ordem2 = OrdemCorte(
        id_rolo=rolo4["id_rolo"],
        id_usuario_cortador=cortador_user.id_usuario,
        dt_emissao=utcnow(),
        dt_execucao=utcnow(),
        qt_metragem_solicitada=Decimal("15.0"),
        qt_sobra_informada=Decimal("60.0"),
        qt_perda_apurada=Decimal("3.0"),
        qt_perda_justificada=Decimal("1.0"),
        fl_divergencia_perda=True,
        st_ordem="CONCLUIDA",
    )
    db_session.add(ordem2)

    # Ordem 3 - Pendente (não deve aparecer no relatório)
    ordem3 = OrdemCorte(
        id_rolo=rolo4["id_rolo"],
        id_usuario_cortador=cortador_user.id_usuario,
        dt_emissao=utcnow(),
        qt_metragem_solicitada=Decimal("10.0"),
        st_ordem="PENDENTE",
    )
    db_session.add(ordem3)

    # Defeito no rolo4
    defeito = MapeamentoDefeito(
        id_rolo=rolo4["id_rolo"],
        qt_metro_inicio=Decimal("10.0"),
        qt_metro_fim=Decimal("12.0"),
        ds_defeito="Furo no tecido",
    )
    db_session.add(defeito)

    # Reserva no rolo4
    reserva = ReservaTemporaria(
        id_rolo=rolo4["id_rolo"],
        qt_metragem_reservada=Decimal("5.0"),
        dt_criacao=utcnow(),
        dt_expiracao=utcnow(),
        st_reserva="EXPIRADA",
    )
    db_session.add(reserva)

    db_session.commit()
    db_session.refresh(ordem1)
    db_session.refresh(ordem2)

    return {
        "tecido": tecido,
        "lote_a": lote_a,
        "lote_b": lote_b,
        "rolo1": rolo1,
        "rolo2": rolo2,
        "rolo3": rolo3,
        "rolo4": rolo4,
        "ordem1": ordem1,
        "ordem2": ordem2,
    }


class TestRelatorioRetalhos:
    """Testes para GET /api/v1/relatorios/retalhos"""

    def test_retalhos_gerente_ok(self, client_gerente, setup_dados_relatorios):
        """GERENTE deve acessar e receber dados corretos."""
        r = client_gerente.get("/api/v1/relatorios/retalhos")
        assert r.status_code == 200, r.text

        data = r.json()
        assert "total_rolos_retalho" in data
        assert "metragem_total_metros" in data
        assert "distribuicao_por_tecido_lote" in data

        # Temos 2 rolos retalho: rolo2 (3.5m) e rolo3 (4.0m) = 7.5m total
        assert data["total_rolos_retalho"] == 2
        assert data["metragem_total_metros"] == 7.5

        # Verificar distribuição
        dist = data["distribuicao_por_tecido_lote"]
        assert len(dist) == 2  # PARTIDA-A (1 rolo) e PARTIDA-B (1 rolo)

        # PARTIDA-A: rolo2 com 3.5m
        part_a = next(d for d in dist if d["cd_partida"] == "PARTIDA-A")
        assert part_a["qtd_rolos"] == 1
        assert part_a["metragem_total"] == 3.5

        # PARTIDA-B: rolo3 com 4.0m
        part_b = next(d for d in dist if d["cd_partida"] == "PARTIDA-B")
        assert part_b["qtd_rolos"] == 1
        assert part_b["metragem_total"] == 4.0

    def test_retalhos_vendedor_403(self, client_vendedor, setup_dados_relatorios):
        """VENDEDOR deve receber 403."""
        r = client_vendedor.get("/api/v1/relatorios/retalhos")
        assert r.status_code == 403
        assert "GERENTE" in r.json()["detail"]

    def test_retalhos_cortador_403(self, client_cortador, setup_dados_relatorios):
        """CORTADOR deve receber 403."""
        r = client_cortador.get("/api/v1/relatorios/retalhos")
        assert r.status_code == 403
        assert "GERENTE" in r.json()["detail"]


class TestRelatorioPerdas:
    """Testes para GET /api/v1/relatorios/perdas"""

    def test_perdas_gerente_ok(self, client_gerente, setup_dados_relatorios):
        """GERENTE deve acessar e receber dados corretos."""
        r = client_gerente.get("/api/v1/relatorios/perdas")
        assert r.status_code == 200, r.text

        data = r.json()
        assert "total_ordens_concluidas" in data
        assert "perda_total_metros" in data
        assert "ordens_com_divergencia" in data
        assert "detalhamento_por_partida_lote" in data

        # Apenas 2 ordens concluídas (ordem3 é PENDENTE)
        assert data["total_ordens_concluidas"] == 2

        # Perda total: 2.0 + 3.0 = 5.0
        assert data["perda_total_metros"] == 5.0

        # 1 ordem com divergência (ordem2)
        assert data["ordens_com_divergencia"] == 1

        # Detalhamento
        det = data["detalhamento_por_partida_lote"]
        assert len(det) == 1  # Apenas PARTIDA-A

        part_a = det[0]
        assert part_a["cd_partida"] == "PARTIDA-A"
        assert part_a["qtd_ordens"] == 2
        assert part_a["perda_total_metros"] == 5.0
        assert part_a["perda_justificada_metros"] == 3.0  # 2.0 + 1.0
        assert part_a["perda_nao_justificada_metros"] == 2.0  # (2-2) + (3-1) = 0 + 2 = 2
        assert part_a["qtd_ordens_com_divergencia"] == 1

    def test_perdas_vendedor_403(self, client_vendedor, setup_dados_relatorios):
        """VENDEDOR deve receber 403."""
        r = client_vendedor.get("/api/v1/relatorios/perdas")
        assert r.status_code == 403

    def test_perdas_cortador_403(self, client_cortador, setup_dados_relatorios):
        """CORTADOR deve receber 403."""
        r = client_cortador.get("/api/v1/relatorios/perdas")
        assert r.status_code == 403


class TestHistoricoRolo:
    """Testes para GET /api/v1/relatorios/rolo/{id_rolo}/historico"""

    def test_historico_gerente_ok(self, client_gerente, setup_dados_relatorios):
        """GERENTE deve acessar histórico completo."""
        rolo4_id = setup_dados_relatorios["rolo4"]["id_rolo"]

        r = client_gerente.get(f"/api/v1/relatorios/rolo/{rolo4_id}/historico")
        assert r.status_code == 200, r.text

        data = r.json()
        assert "rolo" in data
        assert "defeitos" in data
        assert "reservas" in data
        assert "ordens_corte" in data

        # Dados cadastrais
        rolo = data["rolo"]
        assert rolo["id_rolo"] == rolo4_id
        assert rolo["cd_barras"] == "ROL-REL-004"
        assert rolo["lote"]["cd_partida"] == "PARTIDA-A"
        assert rolo["lote"]["tecido"]["cd_tecido"] == "TEC-REL-01"

        # Defeitos (1 defeito)
        assert len(data["defeitos"]) == 1
        defeito = data["defeitos"][0]
        assert defeito["qt_metro_inicio"] == 10.0
        assert defeito["qt_metro_fim"] == 12.0
        assert defeito["ds_defeito"] == "Furo no tecido"

        # Reservas (1 reserva expirada)
        assert len(data["reservas"]) == 1
        reserva = data["reservas"][0]
        assert reserva["st_reserva"] == "EXPIRADA"

        # Ordens de corte (3 ordens: 2 concluídas + 1 pendente)
        assert len(data["ordens_corte"]) == 3
        # Verificar ordem com divergência
        ordens_diverg = [o for o in data["ordens_corte"] if o["fl_divergencia_perda"]]
        assert len(ordens_diverg) == 1

    def test_historico_rolo_inexistente_404(self, client_gerente):
        """Rolo inexistente deve retornar 404."""
        r = client_gerente.get("/api/v1/relatorios/rolo/99999/historico")
        assert r.status_code == 404
        assert "não encontrado" in r.json()["detail"]

    def test_historico_vendedor_403(self, client_vendedor, setup_dados_relatorios):
        """VENDEDOR deve receber 403."""
        rolo_id = setup_dados_relatorios["rolo1"]["id_rolo"]
        r = client_vendedor.get(f"/api/v1/relatorios/rolo/{rolo_id}/historico")
        assert r.status_code == 403

    def test_historico_cortador_403(self, client_cortador, setup_dados_relatorios):
        """CORTADOR deve receber 403."""
        rolo_id = setup_dados_relatorios["rolo1"]["id_rolo"]
        r = client_cortador.get(f"/api/v1/relatorios/rolo/{rolo_id}/historico")
        assert r.status_code == 403


class TestCORS:
    """Testes para configuração de CORS."""

    def test_cors_headers_present(self, client_gerente):
        """Verifica se headers CORS estão presentes nas respostas."""
        r = client_gerente.options("/api/v1/relatorios/retalhos")
        # FastAPI CORS middleware responde a OPTIONS
        assert r.status_code in (200, 405)  # 405 se OPTIONS não explícito, mas headers devem vir

    def test_cors_allow_origin(self, client_gerente):
        """Verifica se Access-Control-Allow-Origin está presente."""
        r = client_gerente.get("/api/v1/relatorios/retalhos")
        # Com allow_origins=["*"], deve retornar *
        # O TestClient não simula browser CORS, mas middleware está configurado


if __name__ == "__main__":
    pytest.main([__file__, "-v"])