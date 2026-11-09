"""Massa de teste. Executar com:  python -m app.seeds

É idempotente: cada registro só é criado se ainda não existir, então pode ser
rodado novamente sem duplicar nada (inclusive em bancos já populados).

ATENÇÃO: as senhas abaixo são apenas para desenvolvimento local.
"""
from datetime import date

from app.database import SessionLocal, engine, Base
from app.models.models import Tecido, LoteTingimento, Rolo, Usuario, MapeamentoDefeito
from app.auth.security import hash_senha


def _obter_ou_criar(db, modelo, filtro: dict, valores: dict):
    obj = db.query(modelo).filter_by(**filtro).first()
    if obj:
        return obj, False
    obj = modelo(**filtro, **valores)
    db.add(obj)
    db.flush()
    return obj, True


def popular_banco():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    criados = []

    try:
        # 1. Usuários (CPFs de teste com dígito verificador válido)
        cortador, novo = _obter_ou_criar(
            db, Usuario, {"ds_login": "cortador"},
            {
                "nm_usuario": "Carlos Cortador",
                "cd_cpf": "52998224725",
                "ds_cargo": "CORTADOR",
                "ds_senha_hash": hash_senha("cortador123"),
            },
        )
        if novo:
            criados.append(f"usuário cortador (id={cortador.id_usuario}, login=cortador, senha=cortador123)")

        vendedor, novo = _obter_ou_criar(
            db, Usuario, {"ds_login": "vendedor"},
            {
                "nm_usuario": "Vera Vendedora",
                "cd_cpf": "11144477735",
                "ds_cargo": "VENDEDOR",
                "ds_senha_hash": hash_senha("vendedor123"),
            },
        )
        if novo:
            criados.append(f"usuário vendedor (id={vendedor.id_usuario}, login=vendedor, senha=vendedor123)")

        gerente, novo = _obter_ou_criar(
            db, Usuario, {"ds_login": "gerente"},
            {
                "nm_usuario": "Gabriel Gerente",
                "cd_cpf": "22255588899",
                "ds_cargo": "GERENTE",
                "ds_senha_hash": hash_senha("gerente123"),
            },
        )
        if novo:
            criados.append(f"usuário gerente (id={gerente.id_usuario}, login=gerente, senha=gerente123)")

        # 2. Tecido
        tecido, novo = _obter_ou_criar(
            db, Tecido, {"cd_tecido": "TEC-ALG-01"},
            {
                "nm_tecido": "Algodão Cru 100%",
                "ds_composicao": "100% Algodão",
                "vl_largura_metros": 1.60,
                "vl_gramatura": 180.00,
                "vl_preco_metro": 25.50,
            },
        )
        if novo:
            criados.append("tecido TEC-ALG-01")

        # 3. Lote de tingimento (partida)
        lote, novo = _obter_ou_criar(
            db, LoteTingimento,
            {"id_tecido": tecido.id_tecido, "cd_partida": "LOTE-2026-AZ1"},
            {"dt_fabricacao": date(2026, 9, 15), "ds_tonalidade_cor": "Azul Marinho"},
        )
        if novo:
            criados.append("lote LOTE-2026-AZ1")

        # 4. Rolos: dois cheios + um pequeno (8 m) para testar a RN-05 com um corte de 3,5 m
        rolos = {}
        for cd_barras, metragem, local in [
            ("ROL-789001", 50.00, "PRAT-A1-01"),
            ("ROL-789002", 100.00, "PRAT-A1-02"),
            ("ROL-789003", 8.00, "PRAT-A1-03"),
        ]:
            rolo, novo = _obter_ou_criar(
                db, Rolo, {"cd_barras": cd_barras},
                {
                    "id_lote": lote.id_lote,
                    "qt_metragem_inicial": metragem,
                    "qt_metragem_atual": metragem,
                    "ds_localizacao": local,
                    "st_rolo": "DISPONIVEL",
                    "fl_retalho": False,
                },
            )
            rolos[cd_barras] = rolo
            if novo:
                criados.append(f"rolo {cd_barras} ({metragem} m)")

        # 5. Um defeito mapeado no rolo de 50 m (para testar a conferência de perdas)
        rolo_1 = rolos["ROL-789001"]
        if not db.query(MapeamentoDefeito).filter_by(id_rolo=rolo_1.id_rolo).first():
            db.add(MapeamentoDefeito(
                id_rolo=rolo_1.id_rolo, qt_metro_inicio=10.00, qt_metro_fim=11.50,
                ds_defeito="Barramento de tingimento",
            ))
            criados.append("defeito de 1,5 m no rolo ROL-789001")

        db.commit()
    finally:
        db.close()

    if criados:
        print("Seeds aplicados:")
        for item in criados:
            print(f"  + {item}")
    else:
        print("Nada a fazer: todos os registros de teste já existem.")


if __name__ == "__main__":
    popular_banco()
