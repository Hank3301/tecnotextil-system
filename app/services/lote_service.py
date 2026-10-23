from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.models import LoteTingimento, Tecido
from app.schemas.schemas import LoteTingimentoCreate, LoteTingimentoUpdate
from app.services.common import conflito, confirmar, obter_ou_404

_MSG_DUPLICADO = "Já existe um lote com esta partida para o tecido informado."


class LoteService:

    @staticmethod
    def listar(
        db: Session,
        id_tecido: Optional[int] = None,
        cd_partida: Optional[str] = None,
        ds_tonalidade_cor: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[LoteTingimento]:
        query = db.query(LoteTingimento)
        if id_tecido:
            query = query.filter(LoteTingimento.id_tecido == id_tecido)
        if cd_partida:
            query = query.filter(LoteTingimento.cd_partida.ilike(f"%{cd_partida}%"))
        if ds_tonalidade_cor:
            query = query.filter(LoteTingimento.ds_tonalidade_cor.ilike(f"%{ds_tonalidade_cor}%"))
        return query.order_by(LoteTingimento.id_lote).offset(skip).limit(limit).all()

    @staticmethod
    def obter(db: Session, id_lote: int) -> LoteTingimento:
        return obter_ou_404(db, LoteTingimento, id_lote, "Lote")

    @staticmethod
    def criar(db: Session, dados: LoteTingimentoCreate) -> LoteTingimento:
        obter_ou_404(db, Tecido, dados.id_tecido, "Tecido")
        duplicado = (
            db.query(LoteTingimento)
            .filter(
                LoteTingimento.id_tecido == dados.id_tecido,
                LoteTingimento.cd_partida == dados.cd_partida,
            ).first()
        )
        if duplicado:
            raise conflito(_MSG_DUPLICADO)

        lote = LoteTingimento(**dados.model_dump())
        db.add(lote)
        confirmar(db, _MSG_DUPLICADO)
        db.refresh(lote)
        return lote

    @staticmethod
    def atualizar(db: Session, id_lote: int, dados: LoteTingimentoUpdate) -> LoteTingimento:
        lote = LoteService.obter(db, id_lote)
        campos = dados.model_dump(exclude_none=True)

        nova_partida = campos.get("cd_partida")
        if nova_partida and nova_partida != lote.cd_partida:
            duplicado = (
                db.query(LoteTingimento)
                .filter(
                    LoteTingimento.id_tecido == lote.id_tecido,
                    LoteTingimento.cd_partida == nova_partida,
                ).first()
            )
            if duplicado:
                raise conflito(_MSG_DUPLICADO)

        for campo, valor in campos.items():
            setattr(lote, campo, valor)
        confirmar(db, _MSG_DUPLICADO)
        db.refresh(lote)
        return lote

    @staticmethod
    def excluir(db: Session, id_lote: int) -> None:
        lote = LoteService.obter(db, id_lote)
        if lote.rolos:
            raise conflito(f"O lote possui {len(lote.rolos)} rolo(s) e não pode ser excluído.")
        db.delete(lote)
        db.commit()
