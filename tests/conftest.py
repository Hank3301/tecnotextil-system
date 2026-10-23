import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db, habilitar_foreign_keys
from app.main import app


@pytest.fixture()
def db_session():
    """Banco SQLite em memória, novo a cada teste, com FKs ligadas como em produção."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    habilitar_foreign_keys(engine)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    # Sem `with`: não dispara o lifespan (que criaria tabelas no banco de arquivo).
    yield TestClient(app)
    app.dependency_overrides.clear()


# ----------------------- fábricas de dados via API -----------------------
@pytest.fixture()
def cortador(client):
    r = client.post("/api/v1/usuarios", json={
        "nm_usuario": "Carlos Cortador", "cd_cpf": "52998224725", "ds_cargo": "CORTADOR",
        "ds_login": "cortador", "ds_senha": "cortador123",
    })
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture()
def lote(client):
    t = client.post("/api/v1/tecidos", json={
        "cd_tecido": "TEC-ALG-01", "nm_tecido": "Algodão Cru", "ds_composicao": "100% Algodão",
        "vl_largura_metros": 1.6, "vl_gramatura": 180, "vl_preco_metro": 25.5,
    })
    assert t.status_code == 201, t.text
    r = client.post("/api/v1/lotes", json={
        "id_tecido": t.json()["id_tecido"], "cd_partida": "LOTE-001",
        "dt_fabricacao": "2026-09-15", "ds_tonalidade_cor": "Azul Marinho",
    })
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture()
def novo_rolo(client, lote):
    contador = {"n": 0}

    def _criar(metragem=50.0):
        contador["n"] += 1
        r = client.post("/api/v1/rolos", json={
            "id_lote": lote["id_lote"], "cd_barras": f"ROL-T{contador['n']:05d}",
            "qt_metragem_inicial": metragem, "ds_localizacao": "PRAT-A1",
        })
        assert r.status_code == 201, r.text
        return r.json()

    return _criar
