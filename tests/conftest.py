import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db, habilitar_foreign_keys
from app.main import app
from app.auth.security import hash_senha
from app.models.models import Usuario


@pytest.fixture()
def db_session():
    """Banco SQLite em memória, novo a cada teste, com FKs ligadas como em produção."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    habilitar_foreign_keys(engine)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()

    # Cria usuários de teste no banco em memória (CPFs válidos)
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
def client(db_session):
    """Cliente sem autenticação (para testes de auth)."""
    test_client = _create_client(db_session)
    yield test_client
    app.dependency_overrides.clear()


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
    """Cliente autenticado como VENDEDOR (vendas + leitura rolos)."""
    test_client = _create_client(db_session)
    token = _login_and_get_token(test_client, "vendedor", "vendedor123")
    test_client.headers.update({"Authorization": f"Bearer {token}"})
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def client_cortador(db_session):
    """Cliente autenticado como CORTADOR (corte + leitura rolos)."""
    test_client = _create_client(db_session)
    token = _login_and_get_token(test_client, "cortador", "cortador123")
    test_client.headers.update({"Authorization": f"Bearer {token}"})
    yield test_client
    app.dependency_overrides.clear()


# ----------------------- fábricas de dados via API -----------------------
@pytest.fixture()
def tecido_base(client_gerente):
    """Cria um tecido base usando cliente gerente."""
    r = client_gerente.post("/api/v1/tecidos", json={
        "cd_tecido": "TEC-ALG-01", "nm_tecido": "Algodão Cru", "ds_composicao": "100% Algodão",
        "vl_largura_metros": 1.6, "vl_gramatura": 180, "vl_preco_metro": 25.5,
    })
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture()
def lote_base(client_gerente, tecido_base):
    """Cria um lote base usando cliente gerente."""
    r = client_gerente.post("/api/v1/lotes", json={
        "id_tecido": tecido_base["id_tecido"], "cd_partida": "LOTE-2026-AZ1",
        "dt_fabricacao": "2026-09-15", "ds_tonalidade_cor": "Azul Marinho",
    })
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture()
def rolo_factory(client_gerente, lote_base):
    """Factory para criar rolos usando cliente gerente."""
    contador = {"n": 0}

    def _criar(metragem=50.0, cd_barras=None):
        contador["n"] += 1
        codigo = cd_barras or f"ROL-T{contador['n']:05d}"
        r = client_gerente.post("/api/v1/rolos", json={
            "id_lote": lote_base["id_lote"], "cd_barras": codigo,
            "qt_metragem_inicial": metragem, "ds_localizacao": "PRAT-A1",
        })
        assert r.status_code == 201, r.text
        return r.json()

    return _criar


# Fixtures legadas (compatibilidade com testes antigos)
@pytest.fixture()
def cortador(db_session):
    """Usuário cortador existente no banco de teste."""
    usuario = db_session.query(Usuario).filter(Usuario.ds_login == "cortador").first()
    return {
        "id_usuario": usuario.id_usuario,
        "nm_usuario": usuario.nm_usuario,
        "cd_cpf": usuario.cd_cpf,
        "ds_cargo": usuario.ds_cargo,
        "ds_login": usuario.ds_login,
    }


@pytest.fixture()
def vendedor(db_session):
    """Usuário vendedor existente no banco de teste."""
    usuario = db_session.query(Usuario).filter(Usuario.ds_login == "vendedor").first()
    return {
        "id_usuario": usuario.id_usuario,
        "nm_usuario": usuario.nm_usuario,
        "cd_cpf": usuario.cd_cpf,
        "ds_cargo": usuario.ds_cargo,
        "ds_login": usuario.ds_login,
    }


@pytest.fixture()
def gerente(db_session):
    """Usuário gerente existente no banco de teste."""
    usuario = db_session.query(Usuario).filter(Usuario.ds_login == "gerente").first()
    return {
        "id_usuario": usuario.id_usuario,
        "nm_usuario": usuario.nm_usuario,
        "cd_cpf": usuario.cd_cpf,
        "ds_cargo": usuario.ds_cargo,
        "ds_login": usuario.ds_login,
    }


@pytest.fixture()
def lote(client_gerente, tecido_base):
    """Alias para lote_base."""
    return lote_base


@pytest.fixture()
def novo_rolo(client_gerente, lote_base):
    """Factory legada para criar rolos."""
    contador = {"n": 0}

    def _criar(metragem=50.0):
        contador["n"] += 1
        r = client_gerente.post("/api/v1/rolos", json={
            "id_lote": lote_base["id_lote"], "cd_barras": f"ROL-T{contador['n']:05d}",
            "qt_metragem_inicial": metragem, "ds_localizacao": "PRAT-A1",
        })
        assert r.status_code == 201, r.text
        return r.json()

    return _criar