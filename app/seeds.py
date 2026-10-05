from datetime import date
from app.database import SessionLocal, engine, Base
from app.models.models import Tecido, LoteTingimento, Rolo

def popular_banco():
    # Garantir criação das tabelas
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    # Verificar se já existem dados
    if db.query(Tecido).first():
        print("O banco de dados já contém dados cadastrados.")
        db.close()
        return

    print("Populando banco de dados com dados de teste...")

    # 1. Cadastrar Tecido
    tecido_algodao = Tecido(
        cd_tecido="TEC-ALG-01",
        nm_tecido="Algodão Cru 100%",
        ds_composicao="100% Algodão",
        vl_largura_metros=1.60,
        vl_gramatura=180.00,
        vl_preco_metro=25.50
    )
    db.add(tecido_algodao)
    db.flush()

    # 2. Cadastrar Lote de Tingimento (Partida A)
    lote_azul = LoteTingimento(
        id_tecido=tecido_algodao.id_tecido,
        cd_partida="LOTE-2026-AZ1",
        dt_fabricacao=date(2026, 9, 15),
        ds_tonalidade_cor="Azul Marinho"
    )
    db.add(lote_azul)
    db.flush()

    # 3. Cadastrar Rolos de Tecido para o Lote Azul
    rolo_1 = Rolo(
        id_lote=lote_azul.id_lote,
        cd_barras="ROL-789001",
        qt_metragem_inicial=50.00,
        qt_metragem_atual=50.00,
        ds_localizacao="PRAT-A1-01",
        st_rolo="DISPONIVEL",
        fl_retalho=False
    )
    
    rolo_2 = Rolo(
        id_lote=lote_azul.id_lote,
        cd_barras="ROL-789002",
        qt_metragem_inicial=100.00,
        qt_metragem_atual=100.00,
        ds_localizacao="PRAT-A1-02",
        st_rolo="DISPONIVEL",
        fl_retalho=False
    )

    db.add_all([rolo_1, rolo_2])
    db.commit()
    db.close()
    print("Banco de dados populado com sucesso!")

if __name__ == "__main__":
    popular_banco()