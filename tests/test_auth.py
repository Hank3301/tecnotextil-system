"""Testes de autenticação e autorização (RBAC)."""
import pytest
from fastapi.testclient import TestClient


class TestAuth:
    """Testes de login e tokens."""

    def test_login_sucesso_gerente(self, client):
        """Login com credenciais válidas de gerente retorna tokens."""
        r = client.post("/api/v1/auth/login", json={
            "login": "gerente",
            "senha": "gerente123",
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["usuario"]["ds_cargo"] == "GERENTE"
        assert data["usuario"]["ds_login"] == "gerente"

    def test_login_sucesso_vendedor(self, client):
        """Login com credenciais válidas de vendedor retorna tokens."""
        r = client.post("/api/v1/auth/login", json={
            "login": "vendedor",
            "senha": "vendedor123",
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["usuario"]["ds_cargo"] == "VENDEDOR"

    def test_login_sucesso_cortador(self, client):
        """Login com credenciais válidas de cortador retorna tokens."""
        r = client.post("/api/v1/auth/login", json={
            "login": "cortador",
            "senha": "cortador123",
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["usuario"]["ds_cargo"] == "CORTADOR"

    def test_login_senha_incorreta(self, client):
        """Login com senha errada retorna 401."""
        r = client.post("/api/v1/auth/login", json={
            "login": "gerente",
            "senha": "senhaerrada",
        })
        assert r.status_code == 401
        assert r.json()["detail"] == "Login ou senha inválidos"

    def test_login_usuario_inexistente(self, client):
        """Login com usuário inexistente retorna 401."""
        r = client.post("/api/v1/auth/login", json={
            "login": "naoexiste",
            "senha": "qualquer123",
        })
        assert r.status_code == 401
        assert r.json()["detail"] == "Login ou senha inválidos"

    def test_login_sem_credenciais(self, client):
        """Login sem enviar body retorna 422."""
        r = client.post("/api/v1/auth/login", json={})
        assert r.status_code == 422

    def test_refresh_token_valido(self, client):
        """Refresh token válido gera novo access token."""
        # Primeiro faz login
        r = client.post("/api/v1/auth/login", json={
            "login": "gerente",
            "senha": "gerente123",
        })
        assert r.status_code == 200
        refresh_token = r.json()["refresh_token"]
        old_access_token = r.json()["access_token"]

        # Usa refresh token
        r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert "refresh_token" in data
        # Verifica que o novo access token é válido (pode ser igual ao anterior se payload idêntico)
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 0
        # Refresh token pode ser o mesmo (JWT stateless)

    def test_refresh_token_invalido(self, client):
        """Refresh token inválido retorna 401."""
        r = client.post("/api/v1/auth/refresh", json={"refresh_token": "token.invalido.xxx"})
        assert r.status_code == 401
        assert "inválido" in r.json()["detail"].lower()

    def test_access_token_expirado(self, client):
        """Access token expirado não funciona (teste conceitual - requer mock de tempo)."""
        # Este teste seria implementado com freezegun ou similar em produção
        pass


class TestRBAC:
    """Testes de controle de acesso baseado em cargos."""

    def _auth_header(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def test_sem_token_retorna_401(self, client):
        """Requisição sem token em rota protegida retorna 401."""
        r = client.get("/api/v1/tecidos")
        assert r.status_code == 401
        assert "não fornecido" in r.json()["detail"].lower()

    def test_token_invalido_retorna_401(self, client):
        """Token inválido retorna 401."""
        r = client.get("/api/v1/tecidos", headers=self._auth_header("token.invalido"))
        assert r.status_code == 401
        assert "inválido" in r.json()["detail"].lower()

    # --- GERENTE: acesso total ---
    def test_gerente_acessa_tecidos_crud(self, client):
        """GERENTE consegue fazer CRUD em tecidos."""
        login = client.post("/api/v1/auth/login", json={"login": "gerente", "senha": "gerente123"})
        token = login.json()["access_token"]
        headers = self._auth_header(token)

        # CREATE
        r = client.post("/api/v1/tecidos", json={
            "cd_tecido": "TEC-TEST", "nm_tecido": "Teste", "ds_composicao": "100% Teste",
            "vl_largura_metros": 1.5, "vl_gramatura": 150, "vl_preco_metro": 10.0,
        }, headers=headers)
        assert r.status_code == 201

        # READ
        r = client.get("/api/v1/tecidos", headers=headers)
        assert r.status_code == 200

    def test_gerente_acessa_lotes_crud(self, client):
        """GERENTE consegue fazer CRUD em lotes."""
        login = client.post("/api/v1/auth/login", json={"login": "gerente", "senha": "gerente123"})
        token = login.json()["access_token"]
        headers = self._auth_header(token)

        # Precisa de um tecido primeiro
        t = client.post("/api/v1/tecidos", json={
            "cd_tecido": "TEC-LOTE", "nm_tecido": "Para Lote", "ds_composicao": "100% Lote",
            "vl_largura_metros": 1.5, "vl_gramatura": 150, "vl_preco_metro": 10.0,
        }, headers=headers)
        id_tecido = t.json()["id_tecido"]

        r = client.post("/api/v1/lotes", json={
            "id_tecido": id_tecido, "cd_partida": "LOTE-RBAC",
            "dt_fabricacao": "2026-01-01", "ds_tonalidade_cor": "Vermelho",
        }, headers=headers)
        assert r.status_code == 201

    def test_gerente_acessa_rolos_crud(self, client):
        """GERENTE consegue fazer CRUD em rolos."""
        login = client.post("/api/v1/auth/login", json={"login": "gerente", "senha": "gerente123"})
        token = login.json()["access_token"]
        headers = self._auth_header(token)

        # Setup: tecido + lote
        t = client.post("/api/v1/tecidos", json={
            "cd_tecido": "TEC-ROLO", "nm_tecido": "Para Rolo", "ds_composicao": "100% Rolo",
            "vl_largura_metros": 1.5, "vl_gramatura": 150, "vl_preco_metro": 10.0,
        }, headers=headers)
        l = client.post("/api/v1/lotes", json={
            "id_tecido": t.json()["id_tecido"], "cd_partida": "LOTE-ROLO",
            "dt_fabricacao": "2026-01-01", "ds_tonalidade_cor": "Verde",
        }, headers=headers)

        r = client.post("/api/v1/rolos", json={
            "id_lote": l.json()["id_lote"], "cd_barras": "ROL-RBAC-001",
            "qt_metragem_inicial": 50.0, "ds_localizacao": "PRAT-A1",
        }, headers=headers)
        assert r.status_code == 201

    def test_gerente_acessa_usuarios_crud(self, client):
        """GERENTE consegue fazer CRUD em usuários."""
        login = client.post("/api/v1/auth/login", json={"login": "gerente", "senha": "gerente123"})
        token = login.json()["access_token"]
        headers = self._auth_header(token)

        # CPF válido: 444.921.125-10 (não conflita com usuários de teste)
        r = client.post("/api/v1/usuarios", json={
            "nm_usuario": "Novo User", "cd_cpf": "44492112510",
            "ds_cargo": "CORTADOR", "ds_login": "novouser", "ds_senha": "senha123",
        }, headers=headers)
        assert r.status_code == 201

    def test_gerente_acessa_vendas(self, client):
        """GERENTE consegue acessar vendas (estoque, reservas)."""
        login = client.post("/api/v1/auth/login", json={"login": "gerente", "senha": "gerente123"})
        token = login.json()["access_token"]
        headers = self._auth_header(token)

        r = client.get("/api/v1/vendas/estoque/lotes?cd_tecido=TEC-ALG-01", headers=headers)
        # Pode ser 200 ou 404 se não houver tecido, mas não 403
        assert r.status_code != 403

    def test_gerente_acessa_corte(self, client):
        """GERENTE consegue acessar mesa de corte."""
        login = client.post("/api/v1/auth/login", json={"login": "gerente", "senha": "gerente123"})
        token = login.json()["access_token"]
        headers = self._auth_header(token)

        r = client.get("/api/v1/corte/ordens", headers=headers)
        assert r.status_code == 200

    # --- VENDEDOR: vendas e leitura de rolos ---
    def test_vendedor_acessa_vendas(self, client):
        """VENDEDOR consegue acessar vendas."""
        login = client.post("/api/v1/auth/login", json={"login": "vendedor", "senha": "vendedor123"})
        token = login.json()["access_token"]
        headers = self._auth_header(token)

        r = client.get("/api/v1/vendas/estoque/lotes?cd_tecido=TEC-ALG-01", headers=headers)
        assert r.status_code != 403

    def test_vendedor_nao_acessa_tecidos_crud(self, client):
        """VENDEDOR NÃO consegue fazer CRUD em tecidos (403)."""
        login = client.post("/api/v1/auth/login", json={"login": "vendedor", "senha": "vendedor123"})
        token = login.json()["access_token"]
        headers = self._auth_header(token)

        r = client.post("/api/v1/tecidos", json={
            "cd_tecido": "TEC-VEND", "nm_tecido": "Vendedor", "ds_composicao": "100% Vend",
            "vl_largura_metros": 1.5, "vl_gramatura": 150, "vl_preco_metro": 10.0,
        }, headers=headers)
        assert r.status_code == 403

    def test_vendedor_nao_acessa_usuarios(self, client):
        """VENDEDOR NÃO consegue acessar usuários (403)."""
        login = client.post("/api/v1/auth/login", json={"login": "vendedor", "senha": "vendedor123"})
        token = login.json()["access_token"]
        headers = self._auth_header(token)

        r = client.get("/api/v1/usuarios", headers=headers)
        assert r.status_code == 403

    def test_vendedor_le_rolos(self, client):
        """VENDEDOR consegue ler rolos (listar/consultar)."""
        login = client.post("/api/v1/auth/login", json={"login": "vendedor", "senha": "vendedor123"})
        token = login.json()["access_token"]
        headers = self._auth_header(token)

        r = client.get("/api/v1/rolos", headers=headers)
        assert r.status_code == 200

    def test_vendedor_nao_cria_rolos(self, client):
        """VENDEDOR NÃO consegue criar rolos (403)."""
        login = client.post("/api/v1/auth/login", json={"login": "vendedor", "senha": "vendedor123"})
        token = login.json()["access_token"]
        headers = self._auth_header(token)

        r = client.post("/api/v1/rolos", json={
            "id_lote": 1, "cd_barras": "ROL-VEND", "qt_metragem_inicial": 10.0,
            "ds_localizacao": "PRAT-A1",
        }, headers=headers)
        assert r.status_code == 403

    # --- CORTADOR: corte e leitura de rolos ---
    def test_cortador_acessa_corte(self, client):
        """CORTADOR consegue acessar mesa de corte."""
        login = client.post("/api/v1/auth/login", json={"login": "cortador", "senha": "cortador123"})
        token = login.json()["access_token"]
        headers = self._auth_header(token)

        r = client.get("/api/v1/corte/ordens", headers=headers)
        assert r.status_code == 200

    def test_cortador_nao_acessa_vendas(self, client):
        """CORTADOR NÃO consegue acessar vendas (403)."""
        login = client.post("/api/v1/auth/login", json={"login": "cortador", "senha": "cortador123"})
        token = login.json()["access_token"]
        headers = self._auth_header(token)

        r = client.get("/api/v1/vendas/estoque/lotes?cd_tecido=TEC-ALG-01", headers=headers)
        assert r.status_code == 403

    def test_cortador_nao_acessa_tecidos(self, client):
        """CORTADOR NÃO consegue acessar cadastros (403)."""
        login = client.post("/api/v1/auth/login", json={"login": "cortador", "senha": "cortador123"})
        token = login.json()["access_token"]
        headers = self._auth_header(token)

        r = client.get("/api/v1/tecidos", headers=headers)
        assert r.status_code == 403

    def test_cortador_le_rolos(self, client):
        """CORTADOR consegue ler rolos (listar/consultar)."""
        login = client.post("/api/v1/auth/login", json={"login": "cortador", "senha": "cortador123"})
        token = login.json()["access_token"]
        headers = self._auth_header(token)

        r = client.get("/api/v1/rolos", headers=headers)
        assert r.status_code == 200