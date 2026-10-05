from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.models import Rolo, OrdemCorte, ReservaTemporaria
from app.schemas.schemas import OrdemCorteCreate, OrdemCorteExecucao

# Regra de Negócio RN-05: Limite de metragem para reclassificação automática como retalho
LIMITE_RETALHO_METROS = 5.00


class CorteService:

    @staticmethod
    def criar_ordem_corte(
        db: Session, 
        dados_ordem: OrdemCorteCreate
    ) -> OrdemCorte:
        """
        Gera uma Ordem de Corte associada a um rolo/reserva.
        Altera o status do rolo para 'EM_CORTE'.
        """
        rolo = db.query(Rolo).filter(Rolo.id_rolo == dados_ordem.id_rolo).first()

        if not rolo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rolo não encontrado."
            )

        if rolo.st_rolo not in ["DISPONIVEL", "RESERVADO"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Não é possível gerar ordem de corte para rolo com status '{rolo.st_rolo}'."
            )

        nova_ordem = OrdemCorte(
            id_rolo=rolo.id_rolo,
            id_reserva=dados_ordem.id_reserva,
            qt_metragem_solicitada=dados_ordem.qt_metragem_solicitada,
            st_ordem="PENDENTE",
            dt_emissao=datetime.utcnow()
        )

        rolo.st_rolo = "EM_CORTE"

        db.add(nova_ordem)
        db.commit()
        db.refresh(nova_ordem)

        return nova_ordem

    @staticmethod
    def executar_corte_e_baixar_estoque(
        db: Session, 
        id_ordem: int, 
        dados_execucao: OrdemCorteExecucao
    ) -> OrdemCorte:
        """
        Executa o corte no rolo, baixa o saldo de metragem no estoque e verifica
        se o saldo remanescente deve ser reclassificado como RETALHO (RN-05).
        """
        ordem = db.query(OrdemCorte).filter(OrdemCorte.id_ordem == id_ordem).first()

        if not ordem:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ordem de Corte não encontrada."
            )

        if ordem.st_ordem == "CONCLUIDA":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Esta ordem de corte já foi concluída."
            )

        rolo = db.query(Rolo).filter(Rolo.id_rolo == ordem.id_rolo).first()

        # 1. Abatimento da metragem solicitada do rolo
        metragem_cortada = float(ordem.qt_metragem_solicitada)
        rolo.baixar_metragem(metragem_cortada)

        # 2. Atualização das informações da Ordem
        ordem.id_usuario_cortador = dados_execucao.id_usuario_cortador
        ordem.qt_sobra_informada = dados_execucao.qt_sobra_informada
        ordem.dt_execucao = datetime.utcnow()
        ordem.st_ordem = "CONCLUIDA"

        # 3. Finalizar Reserva associada (se existir)
        if ordem.id_reserva:
            reserva = db.query(ReservaTemporaria).filter(
                ReservaTemporaria.id_reserva == ordem.id_reserva
            ).first()
            if reserva:
                reserva.st_reserva = "CONFIRMADA"

        # 4. Avaliar Regra de Retalhos (RN-05) e Status do Rolo
        saldo_restante = float(rolo.qt_metragem_atual)
        if saldo_restante <= 0:
            rolo.st_rolo = "INATIVO"
        else:
            rolo.st_rolo = "DISPONIVEL"
            if saldo_restante <= LIMITE_RETALHO_METROS:
                rolo.fl_retalho = True

        db.commit()
        db.refresh(ordem)

        return ordem