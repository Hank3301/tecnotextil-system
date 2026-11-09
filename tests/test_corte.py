from datetime import timedelta
from decimal import Decimal

import pytest

from app.models.models import ReservaTemporaria, Rolo
from app.utils import utcnow

ORDENS = "/api/v1/corte/ordens"


# ----------------------------- helpers -----------------------------
def emitir(client, rolo, metros, id_reserva=None):
    corpo = {"id_rolo": rolo["id_rolo"], "qt_metragem_solicitada": metros}
    if id_reserva is not None:
        corpo["id_reserva"] = id_reserva
    return client.post(ORDENS, json=corpo)


def executar(client, id_ordem, cortador, sobra):
    return client.post(
        f"{ORDENS}/{id_ordem}/executar",
        json={"id_usuario_cortador": cortador["id_usuario"], "qt_sobra_informada": sobra},
    )


def reservar(client, rolo, metros):
    r = client.post("/api/v1/vendas/reservas", json={"id_rolo": rolo["id_rolo"], "qt_metragem_reservada": metros})
    assert r.status_code == 201, r.text
    return r.json()


def rolo_atual(client, rolo):
    return client.get(f"/api/v1/rolos/{rolo['id_rolo']}").json()


def defeito(client, rolo, inicio, fim):
    r = client.post(f"/api/v1/rolos/{rolo['id_rolo']}/defeitos", json={
        "qt_metro_inicio": inicio, "qt_metro_fim": fim, "ds_defeito": "Barramento de tingimento",
    })
    assert r.status_code == 201, r.text


# ----------------------- Rolo.baixar_metragem (bug principal) -----------------------
def test_baixar_metragem_abate_saldo():
    rolo = Rolo(qt_metragem_atual=Decimal("10.00"))
    assert rolo.baixar_metragem(3.5) == Decimal("6.50")
    assert rolo.qt_metragem_atual == Decimal("6.50")


def test_baixar_metragem_nao_deixa_estoque_negativo():
    rolo = Rolo(qt_metragem_atual=Decimal("10.00"))
    with pytest.raises(ValueError, match="Saldo insuficiente"):
        rolo.baixar_metragem(10.01)
    assert rolo.qt_metragem_atual == Decimal("10.00")  # inalterado


@pytest.mark.parametrize("valor", [0, -1])
def test_baixar_metragem_rejeita_quantidade_nao_positiva(valor):
    with pytest.raises(ValueError):
        Rolo(qt_metragem_atual=Decimal("10.00")).baixar_metragem(valor)


def test_baixar_metragem_aceita_decimal_vindo_do_banco_e_float_da_api():
    rolo = Rolo(qt_metragem_atual=Decimal("0.30"))
    assert rolo.baixar_metragem(0.1) == Decimal("0.20")  # sem TypeError Decimal x float


# ----------------------------- emissão da ordem -----------------------------
def test_ordem_rejeita_metragem_maior_que_saldo(client_cortador, rolo_factory):
    rolo = rolo_factory(10)
    r = emitir(client_cortador, rolo, 10.5)
    assert r.status_code == 400
    assert "saldo" in r.json()["detail"]
    assert rolo_atual(client_cortador, rolo)["st_rolo"] == "DISPONIVEL"


def test_ordem_em_rolo_inexistente(client_cortador):
    assert client_cortador.post(ORDENS, json={"id_rolo": 999, "qt_metragem_solicitada": 1}).status_code == 404


def test_ordem_rejeita_reserva_de_outro_rolo(client_cortador, client_vendedor, rolo_factory):
    rolo_a, rolo_b = rolo_factory(50), rolo_factory(50)
    reserva = reservar(client_vendedor, rolo_a, 10)
    r = emitir(client_cortador, rolo_b, 10, id_reserva=reserva["id_reserva"])
    assert r.status_code == 400
    assert "outro rolo" in r.json()["detail"]


def test_ordem_em_rolo_reservado_exige_id_reserva(client_cortador, client_vendedor, rolo_factory):
    rolo = rolo_factory(50)
    reservar(client_vendedor, rolo, 10)
    r = emitir(client_cortador, rolo, 10)
    assert r.status_code == 400
    assert "reservado" in r.json()["detail"]


def test_ordem_rejeita_reserva_expirada(client_cortador, client_vendedor, db_session, rolo_factory):
    rolo = rolo_factory(50)
    reserva = reservar(client_vendedor, rolo, 10)
    db_session.get(ReservaTemporaria, reserva["id_reserva"]).dt_expiracao = utcnow() - timedelta(minutes=1)
    db_session.commit()

    r = emitir(client_cortador, rolo, 10, id_reserva=reserva["id_reserva"])
    assert r.status_code == 400
    assert "ativa" in r.json()["detail"]


def test_ordem_rejeita_metragem_acima_da_reservada(client_cortador, client_vendedor, rolo_factory):
    rolo = rolo_factory(50)
    reserva = reservar(client_vendedor, rolo, 5)
    r = emitir(client_cortador, rolo, 6, id_reserva=reserva["id_reserva"])
    assert r.status_code == 400
    assert "reservada" in r.json()["detail"]


def test_ordem_com_reserva_confirma_reserva_e_poe_rolo_em_corte(client_cortador, db_session, client_vendedor, rolo_factory):
    rolo = rolo_factory(50)
    reserva = reservar(client_vendedor, rolo, 20)
    r = emitir(client_cortador, rolo, 20, id_reserva=reserva["id_reserva"])
    assert r.status_code == 201, r.text
    assert r.json()["st_ordem"] == "PENDENTE"
    assert r.json()["rolo"]["st_rolo"] == "EM_CORTE"
    assert db_session.get(ReservaTemporaria, reserva["id_reserva"]).st_reserva == "CONFIRMADA"

    # a reserva já consumida não pode gerar nova ordem
    assert emitir(client_cortador, rolo, 20, id_reserva=reserva["id_reserva"]).status_code == 400


# ----------------------------- execução / estoque / RN-05 -----------------------------
def test_fluxo_completo_baixa_estoque(client_cortador, rolo_factory, cortador):
    rolo = rolo_factory(50)
    ordem = emitir(client_cortador, rolo, 20).json()
    r = executar(client_cortador, ordem["id_ordem"], cortador, sobra=30)
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["st_ordem"] == "CONCLUIDA"
    assert corpo["id_usuario_cortador"] == cortador["id_usuario"]
    assert corpo["rolo"]["qt_metragem_atual"] == pytest.approx(30)
    assert corpo["rolo"]["st_rolo"] == "DISPONIVEL"
    assert corpo["rolo"]["fl_retalho"] is False
    assert corpo["qt_perda_apurada"] == pytest.approx(0)
    assert corpo["fl_divergencia_perda"] is False


@pytest.mark.parametrize(
    "inicial, corte, sobra, retalho",
    [
        (8, 3.5, 4.5, True),    # abaixo do limite
        (8, 3.0, 5.0, True),    # exatamente 5,00 m => retalho (<=)
        (8, 2.0, 6.0, False),   # acima do limite
    ],
)
def test_rn05_reclassifica_retalho(client_cortador, rolo_factory, cortador, inicial, corte, sobra, retalho):
    rolo = rolo_factory(inicial)
    ordem = emitir(client_cortador, rolo, corte).json()
    r = executar(client_cortador, ordem["id_ordem"], cortador, sobra)
    assert r.status_code == 200, r.text
    assert r.json()["rolo"]["fl_retalho"] is retalho
    assert r.json()["rolo"]["st_rolo"] == "DISPONIVEL"


def test_rolo_zerado_fica_inativo_e_nao_vira_retalho(client_cortador, rolo_factory, cortador):
    rolo = rolo_factory(10)
    ordem = emitir(client_cortador, rolo, 10).json()
    r = executar(client_cortador, ordem["id_ordem"], cortador, sobra=0)
    assert r.status_code == 200
    assert r.json()["rolo"]["st_rolo"] == "INATIVO"
    assert r.json()["rolo"]["fl_retalho"] is False
    assert r.json()["rolo"]["qt_metragem_atual"] == pytest.approx(0)


def test_executar_exige_ordem_pendente(client_cortador, rolo_factory, cortador):
    rolo = rolo_factory(50)
    ordem = emitir(client_cortador, rolo, 10).json()
    assert executar(client_cortador, ordem["id_ordem"], cortador, 40).status_code == 200

    segunda = executar(client_cortador, ordem["id_ordem"], cortador, 30)
    assert segunda.status_code == 400
    assert "CONCLUIDA" in segunda.json()["detail"]
    assert rolo_atual(client_cortador, rolo)["qt_metragem_atual"] == pytest.approx(40)  # não baixou duas vezes


def test_executar_ordem_cancelada_e_rejeitado(client_cortador, rolo_factory, cortador):
    rolo = rolo_factory(50)
    ordem = emitir(client_cortador, rolo, 10).json()
    assert client_cortador.patch(f"{ORDENS}/{ordem['id_ordem']}/cancelar").status_code == 200
    r = executar(client_cortador, ordem["id_ordem"], cortador, 40)
    assert r.status_code == 400
    assert "CANCELADA" in r.json()["detail"]


def test_executar_ordem_inexistente(client_cortador, cortador):
    assert executar(client_cortador, 999, cortador, 1).status_code == 404


def test_executar_com_cortador_inexistente_nao_altera_nada(client_cortador, rolo_factory):
    rolo = rolo_factory(50)
    ordem = emitir(client_cortador, rolo, 10).json()
    r = client_cortador.post(f"{ORDENS}/{ordem['id_ordem']}/executar",
                json={"id_usuario_cortador": 999, "qt_sobra_informada": 40})
    assert r.status_code == 404
    assert rolo_atual(client_cortador, rolo)["st_rolo"] == "EM_CORTE"
    assert client_cortador.get(f"{ORDENS}/{ordem['id_ordem']}").json()["st_ordem"] == "PENDENTE"


def test_sobra_maior_que_saldo_esperado_e_rejeitada(client_cortador, rolo_factory, cortador):
    rolo = rolo_factory(10)
    ordem = emitir(client_cortador, rolo, 4).json()
    r = executar(client_cortador, ordem["id_ordem"], cortador, 6.5)  # esperado: 6.0
    assert r.status_code == 400
    assert "Sobra informada" in r.json()["detail"]
    assert rolo_atual(client_cortador, rolo)["qt_metragem_atual"] == pytest.approx(10)


# ----------------------------- conferência de perdas -----------------------------
def test_perda_totalmente_justificada_por_defeito(client_cortador, client_gerente, rolo_factory, cortador):
    rolo = rolo_factory(50)
    defeito(client_gerente, rolo, 10, 11.5)  # 1,5 m de defeito
    ordem = emitir(client_cortador, rolo, 40).json()
    r = executar(client_cortador, ordem["id_ordem"], cortador, sobra=8.5)  # esperado 10 => perda 1,5
    corpo = r.json()
    assert r.status_code == 200, r.text
    assert corpo["qt_perda_apurada"] == pytest.approx(1.5)
    assert corpo["qt_perda_justificada"] == pytest.approx(1.5)
    assert corpo["qt_perda_nao_justificada"] == pytest.approx(0)
    assert corpo["fl_divergencia_perda"] is False
    assert corpo["rolo"]["qt_metragem_atual"] == pytest.approx(8.5)  # sobra medida vira o saldo


def test_perda_acima_dos_defeitos_gera_divergencia(client_cortador, client_gerente, rolo_factory, cortador):
    rolo = rolo_factory(50)
    defeito(client_gerente, rolo, 10, 11.5)
    ordem = emitir(client_cortador, rolo, 40).json()
    corpo = executar(client_cortador, ordem["id_ordem"], cortador, sobra=8.0).json()  # perda 2,0
    assert corpo["qt_perda_justificada"] == pytest.approx(1.5)
    assert corpo["qt_perda_nao_justificada"] == pytest.approx(0.5)
    assert corpo["fl_divergencia_perda"] is True


def test_perda_sem_defeito_mapeado_gera_divergencia(client_cortador, rolo_factory, cortador):
    rolo = rolo_factory(50)
    ordem = emitir(client_cortador, rolo, 40).json()
    corpo = executar(client_cortador, ordem["id_ordem"], cortador, sobra=9.0).json()
    assert corpo["qt_perda_apurada"] == pytest.approx(1.0)
    assert corpo["qt_perda_justificada"] == pytest.approx(0)
    assert corpo["fl_divergencia_perda"] is True


def test_perda_dentro_da_tolerancia_nao_diverge(client_cortador, rolo_factory, cortador):
    rolo = rolo_factory(50)
    ordem = emitir(client_cortador, rolo, 40).json()
    corpo = executar(client_cortador, ordem["id_ordem"], cortador, sobra=9.95).json()  # perda 0,05 m
    assert corpo["fl_divergencia_perda"] is False


def test_defeito_nao_justifica_perdas_de_dois_cortes(client_cortador, client_gerente, rolo_factory, cortador):
    rolo = rolo_factory(100)
    defeito(client_gerente, rolo, 10, 11.5)

    o1 = emitir(client_cortador, rolo, 10).json()
    c1 = executar(client_cortador, o1["id_ordem"], cortador, sobra=88.5).json()  # perda 1,5 usa o defeito
    assert c1["fl_divergencia_perda"] is False

    o2 = emitir(client_cortador, rolo, 10).json()
    c2 = executar(client_cortador, o2["id_ordem"], cortador, sobra=77.0).json()  # nova perda 1,5, defeito já usado
    assert c2["qt_perda_justificada"] == pytest.approx(0)
    assert c2["fl_divergencia_perda"] is True


# ----------------------------- cancelamento -----------------------------
def test_cancelar_ordem_libera_rolo_e_cancela_reserva(client_cortador, db_session, client_vendedor, rolo_factory):
    rolo = rolo_factory(50)
    reserva = reservar(client_vendedor, rolo, 10)
    ordem = emitir(client_cortador, rolo, 10, id_reserva=reserva["id_reserva"]).json()

    r = client_cortador.patch(f"{ORDENS}/{ordem['id_ordem']}/cancelar")
    assert r.status_code == 200
    assert r.json()["st_ordem"] == "CANCELADA"
    assert r.json()["rolo"]["st_rolo"] == "DISPONIVEL"
    assert db_session.get(ReservaTemporaria, reserva["id_reserva"]).st_reserva == "CANCELADA"
    assert emitir(client_cortador, rolo, 10).status_code == 201  # rolo volta a aceitar ordens


def test_cancelar_ordem_concluida_e_rejeitado(client_cortador, rolo_factory, cortador):
    rolo = rolo_factory(50)
    ordem = emitir(client_cortador, rolo, 10).json()
    executar(client_cortador, ordem["id_ordem"], cortador, 40)
    assert client_cortador.patch(f"{ORDENS}/{ordem['id_ordem']}/cancelar").status_code == 400


def test_listar_ordens_com_filtro(client_cortador, rolo_factory):
    rolo = rolo_factory(50)
    emitir(client_cortador, rolo, 10)
    r = client_cortador.get(ORDENS, params={"st_ordem": "PENDENTE", "id_rolo": rolo["id_rolo"]})
    assert r.status_code == 200 and len(r.json()) == 1