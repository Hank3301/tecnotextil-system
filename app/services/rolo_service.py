from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.enums import StatusRolo
from app.models.models import LoteTingimento, MapeamentoDefeito, Rolo, Tecido
from app.schemas.schemas import MapeamentoDefeitoCreate, RoloCreate, RoloUpdate
from app.services.common import conflito, confirmar, obter_ou_404
from app.utils import to_decimal

# Transições que podem ser feitas manualmente via API.
# RESERVADO e EM_CORTE só mudam pelos fluxos de reserva/corte.
STATUS_MANUAIS = (StatusRolo.DISPONIVEL, StatusRolo.BLOQUEADO, StatusRolo.INATIVO)
STATUS_EM_OPERACAO = (StatusRolo.RESERVADO, StatusRolo.EM_CORTE)


class RoloService:

    @staticmethod
    def listar(
        db: Session,
        id_lote: Optional[int] = None,
        cd_tecido: Optional[str] = None,
        st_rolo: Optional[str] = None,
        fl_retalho: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Rolo]:
        query = db.query(Rolo)
        if cd_tecido:
            query = (
                query.join(LoteTingimento, Rolo.id_lote == LoteTingimento.id_lote)
                .join(Tecido, LoteTingimento.id_tecido == Tecido.id_tecido)
                .filter(Tecido.cd_tecido == cd_tecido)
            )
        if id_lote:
            query = query.filter(Rolo.id_lote == id_lote)
        if st_rolo:
            query = query.filter(Rolo.st_rolo == st_rolo)
        if fl_retalho is not None:
            query = query.filter(Rolo.fl_retalho == fl_retalho)
        return query.order_by(Rolo.id_rolo).offset(skip).limit(limit).all()

    @staticmethod
    def obter(db: Session, id_rolo: int) -> Rolo:
        return obter_ou_404(db, Rolo, id_rolo, "Rolo")

    @staticmethod
    def obter_por_codigo_barras(db: Session, cd_barras: str) -> Rolo:
        rolo = db.query(Rolo).filter(Rolo.cd_barras == cd_barras).first()
        if not rolo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rolo não encontrado.")
        return rolo

    @staticmethod
    def criar(db: Session, dados: RoloCreate) -> Rolo:
        obter_ou_404(db, LoteTingimento, dados.id_lote, "Lote")
        if db.query(Rolo).filter(Rolo.cd_barras == dados.cd_barras).first():
            raise conflito(f"Já existe um rolo com o código de barras '{dados.cd_barras}'.")

        metragem = to_decimal(dados.qt_metragem_inicial)
        rolo = Rolo(
            id_lote=dados.id_lote,
            cd_barras=dados.cd_barras,
            qt_metragem_inicial=metragem,
            qt_metragem_atual=metragem,  # rolo novo entra com saldo cheio
            ds_localizacao=dados.ds_localizacao,
            st_rolo=StatusRolo.DISPONIVEL,
            fl_retalho=False,
        )
        db.add(rolo)
        confirmar(db, "Já existe um rolo com este código de barras.")
        db.refresh(rolo)
        return rolo

    @staticmethod
    def atualizar(db: Session, id_rolo: int, dados: RoloUpdate) -> Rolo:
        rolo = RoloService.obter(db, id_rolo)

        if dados.ds_localizacao is not None:
            rolo.ds_localizacao = dados.ds_localizacao

        novo_status = dados.st_rolo
        if novo_status is not None and novo_status != rolo.st_rolo:
            if rolo.st_rolo in STATUS_EM_OPERACAO:
                raise conflito(
                    f"Rolo em operação (status '{rolo.st_rolo}'). "
                    "Cancele a reserva ou a ordem de corte antes de alterar o status."
                )
            if novo_status not in STATUS_MANUAIS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Status manual permitido apenas: " + ", ".join(STATUS_MANUAIS) + ".",
                )
            if novo_status == StatusRolo.DISPONIVEL and to_decimal(rolo.qt_metragem_atual) <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Rolo sem saldo não pode ficar DISPONIVEL.",
                )
            rolo.st_rolo = novo_status

        db.commit()
        db.refresh(rolo)
        return rolo

    @staticmethod
    def excluir(db: Session, id_rolo: int) -> None:
        rolo = RoloService.obter(db, id_rolo)
        if rolo.reservas or rolo.ordens_corte:
            raise conflito(
                "O rolo possui reservas/ordens de corte no histórico e não pode ser excluído. "
                "Use o status INATIVO."
            )
        db.delete(rolo)  # defeitos são removidos em cascata
        db.commit()

    # ---------------- Mapeamento de defeitos ----------------
    @staticmethod
    def listar_defeitos(db: Session, id_rolo: int) -> List[MapeamentoDefeito]:
        return RoloService.obter(db, id_rolo).defeitos

    @staticmethod
    def adicionar_defeito(db: Session, id_rolo: int, dados: MapeamentoDefeitoCreate) -> MapeamentoDefeito:
        rolo = RoloService.obter(db, id_rolo)
        limite = to_decimal(rolo.qt_metragem_inicial)
        if to_decimal(dados.qt_metro_fim) > limite:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"O defeito termina em {dados.qt_metro_fim}m, mas o rolo tem apenas {limite}m.",
            )
        defeito = MapeamentoDefeito(
            id_rolo=rolo.id_rolo,
            qt_metro_inicio=to_decimal(dados.qt_metro_inicio),
            qt_metro_fim=to_decimal(dados.qt_metro_fim),
            ds_defeito=dados.ds_defeito,
        )
        db.add(defeito)
        db.commit()
        db.refresh(defeito)
        return defeito

    @staticmethod
    def excluir_defeito(db: Session, id_rolo: int, id_defeito: int) -> None:
        defeito = (
            db.query(MapeamentoDefeito)
            .filter(MapeamentoDefeito.id_defeito == id_defeito, MapeamentoDefeito.id_rolo == id_rolo)
            .first()
        )
        if not defeito:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Defeito não encontrado neste rolo.")
        db.delete(defeito)
        db.commit()
