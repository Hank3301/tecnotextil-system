import pytest

from app.models.models import Usuario
from app.auth.security import verificar_senha

TECIDO = {
    "cd_tecido": "TEC-LIN-02", "nm_tecido": "Linho Misto", "ds_composicao": "55% Linho 45% Algodão",
    "vl_largura_metros": 1.4, "vl_gramatura": 160, "vl_preco_metro": 42.9,
}


# ----------------------------- Tecidos -----------------------------
def test_tecido_crud_completo(client_gerente):
    r = client_gerente.post("/api/v1/tecidos", json=TECIDO)
    assert r.status_code == 201, r.text
    id_tecido = r.json()["id_tecido"]

    assert client_gerente.post("/api/v1/tecidos", json=TECIDO).status_code == 409  # código duplicado

    r = client_gerente.patch(f"/api/v1/tecidos/{id_tecido}", json={"vl_preco_metro": 50})
    assert r.status_code == 200 and r.json()["vl_preco_metro"] == pytest.approx(50)
    assert r.json()["nm_tecido"] == "Linho Misto"  # campos omitidos permanecem

    assert len(client_gerente.get("/api/v1/tecidos", params={"busca": "linho"}).json()) == 1
    assert client_gerente.get("/api/v1/tecidos", params={"busca": "inexistente"}).json() == []

    assert client_gerente.delete(f"/api/v1/tecidos/{id_tecido}").status_code == 204
    assert client_gerente.get(f"/api/v1/tecidos/{id_tecido}").status_code == 404


def test_tecido_validacao_422(client_gerente):
    assert client_gerente.post("/api/v1/tecidos", json={**TECIDO, "vl_largura_metros": -1}).status_code == 422


def test_tecido_com_lotes_nao_pode_ser_excluido(client_gerente, lote_base):
    assert client_gerente.delete(f"/api/v1/tecidos/{lote_base['id_tecido']}").status_code == 409


def test_patch_codigo_de_tecido_para_um_ja_existente(client_gerente, lote_base, tecido_base):
    outro = client_gerente.post("/api/v1/tecidos", json=TECIDO).json()
    r = client_gerente.patch(f"/api/v1/tecidos/{outro['id_tecido']}", json={"cd_tecido": "TEC-ALG-01"})
    assert r.status_code == 409


# ----------------------------- Lotes -----------------------------
def test_lote_de_tecido_inexistente(client_gerente):
    r = client_gerente.post("/api/v1/lotes", json={
        "id_tecido": 999, "cd_partida": "P-1", "dt_fabricacao": "2026-09-15", "ds_tonalidade_cor": "Azul",
    })
    assert r.status_code == 404


def test_lote_partida_duplicada_no_mesmo_tecido(client_gerente, lote_base):
    r = client_gerente.post("/api/v1/lotes", json={
        "id_tecido": lote_base["id_tecido"], "cd_partida": lote_base["cd_partida"],
        "dt_fabricacao": "2026-09-16", "ds_tonalidade_cor": "Vermelho",
    })
    assert r.status_code == 409


def test_lote_detalhe_traz_rolos_e_lista_nao(client_gerente, lote_base, rolo_factory):
    rolo_factory(30)
    detalhe = client_gerente.get(f"/api/v1/lotes/{lote_base['id_lote']}").json()
    assert len(detalhe["rolos"]) == 1
    listagem = client_gerente.get("/api/v1/lotes", params={"id_tecido": lote_base["id_tecido"]}).json()
    assert len(listagem) == 1 and "rolos" not in listagem[0]


def test_lote_patch_nao_troca_de_tecido_e_exclusao_bloqueada_com_rolos(client_gerente, lote_base, rolo_factory):
    r = client_gerente.patch(f"/api/v1/lotes/{lote_base['id_lote']}", json={"ds_tonalidade_cor": "Verde", "id_tecido": 999})
    assert r.status_code == 200
    assert r.json()["ds_tonalidade_cor"] == "Verde" and r.json()["id_tecido"] == lote_base["id_tecido"]

    rolo_factory(10)
    assert client_gerente.delete(f"/api/v1/lotes/{lote_base['id_lote']}").status_code == 409


# ----------------------------- Rolos -----------------------------
def test_rolo_nasce_com_saldo_cheio_e_cliente_nao_forja_estado(client_gerente, lote_base):
    r = client_gerente.post("/api/v1/rolos", json={
        "id_lote": lote_base["id_lote"], "cd_barras": "ROL-00001", "qt_metragem_inicial": 50,
        "ds_localizacao": "A1", "qt_metragem_atual": 1, "st_rolo": "INATIVO", "fl_retalho": True,
    })
    assert r.status_code == 201, r.text
    corpo = r.json()
    assert corpo["qt_metragem_atual"] == pytest.approx(50)
    assert corpo["st_rolo"] == "DISPONIVEL" and corpo["fl_retalho"] is False


def test_rolo_codigo_de_barras_duplicado_e_lote_inexistente(client_gerente, lote_base, rolo_factory):
    rolo = rolo_factory(10)
    base = {"qt_metragem_inicial": 5, "ds_localizacao": "A1"}
    dup = client_gerente.post("/api/v1/rolos", json={**base, "id_lote": lote_base["id_lote"], "cd_barras": rolo["cd_barras"]})
    assert dup.status_code == 409
    sem_lote = client_gerente.post("/api/v1/rolos", json={**base, "id_lote": 999, "cd_barras": "ROL-99999"})
    assert sem_lote.status_code == 404


def test_rolo_busca_por_codigo_de_barras_e_filtros(client_gerente, rolo_factory):
    rolo = rolo_factory(10)
    r = client_gerente.get(f"/api/v1/rolos/codigo-barras/{rolo['cd_barras']}")
    assert r.status_code == 200 and r.json()["id_rolo"] == rolo["id_rolo"]
    assert client_gerente.get("/api/v1/rolos/codigo-barras/NAO-EXISTE").status_code == 404

    assert len(client_gerente.get("/api/v1/rolos", params={"cd_tecido": "TEC-ALG-01"}).json()) == 1
    assert client_gerente.get("/api/v1/rolos", params={"fl_retalho": True}).json() == []
    assert client_gerente.get("/api/v1/rolos", params={"st_rolo": "DISPONIVEL"}).json()[0]["id_rolo"] == rolo["id_rolo"]


def test_rolo_patch_status_manual(client_gerente, rolo_factory):
    rolo = rolo_factory(10)
    url = f"/api/v1/rolos/{rolo['id_rolo']}"
    r = client_gerente.patch(url, json={"ds_localizacao": "B2", "st_rolo": "BLOQUEADO"})
    assert r.status_code == 200
    assert r.json()["ds_localizacao"] == "B2" and r.json()["st_rolo"] == "BLOQUEADO"

    # estados operacionais não podem ser definidos à mão
    assert client_gerente.patch(url, json={"st_rolo": "EM_CORTE"}).status_code == 400
    assert client_gerente.patch(url, json={"st_rolo": "QUALQUER"}).status_code == 422


def test_rolo_em_operacao_nao_aceita_troca_manual_de_status(client_gerente, rolo_factory, client_vendedor):
    rolo = rolo_factory(10)
    client_vendedor.post("/api/v1/vendas/reservas", json={"id_rolo": rolo["id_rolo"], "qt_metragem_reservada": 5})
    r = client_gerente.patch(f"/api/v1/rolos/{rolo['id_rolo']}", json={"st_rolo": "INATIVO"})
    assert r.status_code == 409


def test_rolo_com_historico_nao_pode_ser_excluido(client_gerente, rolo_factory):
    com_historico, limpo = rolo_factory(10), rolo_factory(10)
    client_gerente.post("/api/v1/vendas/reservas", json={"id_rolo": com_historico["id_rolo"], "qt_metragem_reservada": 5})
    assert client_gerente.delete(f"/api/v1/rolos/{com_historico['id_rolo']}").status_code == 409
    assert client_gerente.delete(f"/api/v1/rolos/{limpo['id_rolo']}").status_code == 204


# ----------------------------- Defeitos -----------------------------
def test_defeito_crud_e_validacoes(client_gerente, rolo_factory):
    rolo = rolo_factory(20)
    base = f"/api/v1/rolos/{rolo['id_rolo']}/defeitos"

    assert client_gerente.post(base, json={"qt_metro_inicio": 5, "qt_metro_fim": 5, "ds_defeito": "Mancha"}).status_code == 422
    assert client_gerente.post(base, json={"qt_metro_inicio": 15, "qt_metro_fim": 25, "ds_defeito": "Mancha"}).status_code == 400

    r = client_gerente.post(base, json={"qt_metro_inicio": 0, "qt_metro_fim": 2, "ds_defeito": "Mancha de óleo"})
    assert r.status_code == 201
    id_defeito = r.json()["id_defeito"]
    assert len(client_gerente.get(base).json()) == 1
    assert len(client_gerente.get(f"/api/v1/rolos/{rolo['id_rolo']}").json()["defeitos"]) == 1

    assert client_gerente.delete(f"{base}/{id_defeito}").status_code == 204
    assert client_gerente.delete(f"{base}/{id_defeito}").status_code == 404


# ----------------------------- Usuários -----------------------------
def test_usuario_nao_expoe_senha_e_guarda_hash(client_gerente, db_session):
    # CPF válido: 311.770.548-17 (não conflita com usuários de teste)
    r = client_gerente.post("/api/v1/usuarios", json={
        "nm_usuario": "Novo Usuario", "cd_cpf": "31177054817", "ds_cargo": "VENDEDOR",
        "ds_login": "novouser", "ds_senha": "senha-segura-1",
    })
    assert r.status_code == 201, r.text
    corpo = r.json()
    assert "ds_senha" not in corpo and "ds_senha_hash" not in corpo
    assert corpo["cd_cpf"] == "31177054817" and corpo["ds_login"] == "novouser"

    salvo = db_session.get(Usuario, corpo["id_usuario"])
    assert salvo.ds_senha_hash.startswith("$2b$") and "senha-segura-1" not in salvo.ds_senha_hash
    assert verificar_senha("senha-segura-1", salvo.ds_senha_hash)


def test_usuario_validacoes_e_duplicidade(client_gerente, cortador):
    # CPF válido: 028.146.621-12 (não conflita com usuários de teste)
    base = {"nm_usuario": "Outro Nome", "cd_cpf": "02814662112", "ds_cargo": "VENDEDOR",
            "ds_login": "outro", "ds_senha": "12345678"}
    assert client_gerente.post("/api/v1/usuarios", json={**base, "cd_cpf": "11111111111"}).status_code == 422
    assert client_gerente.post("/api/v1/usuarios", json={**base, "ds_senha": "curta"}).status_code == 422
    assert client_gerente.post("/api/v1/usuarios", json={**base, "ds_login": "cortador"}).status_code == 409
    assert client_gerente.post("/api/v1/usuarios", json={**base, "cd_cpf": "52998224725"}).status_code == 409
    assert client_gerente.post("/api/v1/usuarios", json=base).status_code == 201


def test_usuario_patch_troca_senha_e_lista_por_cargo(client_gerente, db_session, cortador):
    antigo = db_session.get(Usuario, cortador["id_usuario"]).ds_senha_hash
    r = client_gerente.patch(f"/api/v1/usuarios/{cortador['id_usuario']}", json={"ds_senha": "nova-senha-123"})
    assert r.status_code == 200
    db_session.expire_all()
    novo = db_session.get(Usuario, cortador["id_usuario"]).ds_senha_hash
    assert novo != antigo and verificar_senha("nova-senha-123", novo)

    assert len(client_gerente.get("/api/v1/usuarios", params={"ds_cargo": "cortador"}).json()) == 1
    assert len(client_gerente.get("/api/v1/usuarios", params={"ds_cargo": "GERENTE"}).json()) == 1


def test_usuario_com_ordens_nao_pode_ser_excluido(client_gerente, cortador, rolo_factory):
    rolo = rolo_factory(50)
    ordem = client_gerente.post("/api/v1/corte/ordens", json={"id_rolo": rolo["id_rolo"], "qt_metragem_solicitada": 10}).json()
    client_gerente.post(f"/api/v1/corte/ordens/{ordem['id_ordem']}/executar",
                json={"id_usuario_cortador": cortador["id_usuario"], "qt_sobra_informada": 40})
    assert client_gerente.delete(f"/api/v1/usuarios/{cortador['id_usuario']}").status_code == 409