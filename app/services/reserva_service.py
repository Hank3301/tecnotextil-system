from datetime import datetime, timedelta
from typing import List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.models import Rolo, ReservaTemporaria, LoteTingimento, Tecido
from app.schemas.schemas import ReservaCreate

# Regra de Negócio RN-02: Tempo limite de bloqueio temporário
TEMPO_EXPIRACAO_MINUTOS = 20


class ReservaService:

    @staticmethod
    def expirar_reservas_vencidas(db: Session) -> int:
        """
        Varre o banco em busca de reservas 'ATIVAS' cuja data de expiração já passou,
        libera o rolo (retorna para 'DISPONIVEL') e atualiza o status para 'EXPIRADA'.
        """
        agora = datetime.utcnow()
        reservas_vencidas = (
            db.query(ReservaTemporaria)
            .filter(
                ReservaTemporaria.st_reserva == "ATIVA",
                ReservaTemporaria.dt_expiracao <= agora
            )
            .all()
        )

        qtd_expiradas = 0
        for reserva in reservas_vencidas:
            reserva.st_reserva = "EXPIRADA"
            
            # Se o rolo associado ainda estiver bloqueado pela reserva, libera seu status
            rolo = db.query(Rolo).filter(Rolo.id_rolo == reserva.id_rolo).first()
            if rolo and rolo.st_rolo == "RESERVADO":
                rolo.st_rolo = "DISPONIVEL"
            
            qtd_expiradas += 1

        if qtd_expiradas > 0:
            db.commit()

        return qtd_expiradas

    @staticmethod
    def consultar_estoque_por_lote(
        db: Session, 
        cd_tecido: str, 
        ds_tonalidade_cor: str = None
    ) -> List[LoteTingimento]:
        """
        Consulta o estoque garantindo a manutenção do isolamento de partidas/lotes.
        Executa a limpeza prévia de reservas vencidas antes de retornar os saldos.
        """
        # Executa limpeza de reservas vencidas para entregar saldos reais
        ReservaService.expirar_reservas_vencidas(db)

        query = (
            db.query(LoteTingimento)
            .join(Tecido)
            .filter(Tecido.cd_tecido == cd_tecido)
        )

        if ds_tonalidade_cor:
            query = query.filter(LoteTingimento.ds_tonalidade_cor.ilike(f"%{ds_tonalidade_cor}%"))

        return query.all()

    @staticmethod
    def criar_reserva_temporaria(
        db: Session, 
        dados_reserva: ReservaCreate
    ) -> ReservaTemporaria:
        """
        Cria uma reserva temporária bloqueando o rolo por 20 minutos.
        Garante as validações de estoque mínimo e status operacional.
        """
        # 1. Atualiza reservas expiradas para não travar rolos liberados
        ReservaService.expirar_reservas_vencidas(db)

        # 2. Busca o rolo no banco
        rolo = db.query(Rolo).filter(Rolo.id_rolo == dados_reserva.id_rolo).first()

        if not rolo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rolo não encontrado."
            )

        # 3. Valida se o rolo está disponível para venda
        if rolo.st_rolo != "DISPONIVEL":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"O rolo selecionado não está disponível (Status atual: {rolo.st_rolo})."
            )

        # 4. Valida se a metragem solicitada é compatível com o saldo atual
        if float(rolo.qt_metragem_atual) < dados_reserva.qt_metragem_reservada:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Metragem solicitada ({dados_reserva.qt_metragem_reservada}m) "
                    f"é maior que o saldo disponível no rolo ({rolo.qt_metragem_atual}m)."
                )
            )

        # 5. Calcula o timestamp exato de expiração (20 min)
        agora = datetime.utcnow()
        expiracao = agora + timedelta(minutes=TEMPO_EXPIRACAO_MINUTOS)

        # 6. Registra a reserva e altera o status do rolo para RESERVADO
        nova_reserva = ReservaTemporaria(
            id_rolo=rolo.id_rolo,
            qt_metragem_reservada=dados_reserva.qt_metragem_reservada,
            dt_criacao=agora,
            dt_expiracao=expiracao,
            st_reserva="ATIVA"
        )

        rolo.st_rolo = "RESERVADO"

        db.add(nova_reserva)
        db.commit()
        db.refresh(nova_reserva)

        return nova_reserva

    @staticmethod
    def cancelar_reserva(db: Session, id_reserva: int) -> ReservaTemporaria:
        """
        Cancela uma reserva ativa manualmente pelo vendedor e libera o rolo imediatamente.
        """
        reserva = db.query(ReservaTemporaria).filter(ReservaTemporaria.id_reserva == id_reserva).first()

        if not reserva:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reserva não encontrada."
            )

        if reserva.st_reserva != "ATIVA":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Não é possível cancelar uma reserva com status '{reserva.st_reserva}'."
            )

        reserva.st_reserva = "CANCELADA"
        
        rolo = db.query(Rolo).filter(Rolo.id_rolo == reserva.id_rolo).first()
        if rolo and rolo.st_rolo == "RESERVADO":
            rolo.st_rolo = "DISPONIVEL"

        db.commit()
        db.refresh(reserva)

        return reserva