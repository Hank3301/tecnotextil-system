from typing import List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.models import Tecido
from app.schemas.schemas import TecidoCreate, TecidoUpdate
from app.services.common import conflito, confirmar, obter_ou_404


class TecidoService:

    @staticmethod
    def listar(db: Session, busca: Optional[str] = None, skip: int = 0, limit: int = 50) -> List[Tecido]:
        query = db.query(Tecido)
        if busca:
            padrao = f"%{busca}%"
            query = query.filter(or_(Tecido.cd_tecido.ilike(padrao), Tecido.nm_tecido.ilike(padrao)))
        return query.order_by(Tecido.nm_tecido).offset(skip).limit(limit).all()

    @staticmethod
    def obter(db: Session, id_tecido: int) -> Tecido:
        return obter_ou_404(db, Tecido, id_tecido, "Tecido")

    @staticmethod
    def criar(db: Session, dados: TecidoCreate) -> Tecido:
        if db.query(Tecido).filter(Tecido.cd_tecido == dados.cd_tecido).first():
            raise conflito(f"Já existe um tecido com o código '{dados.cd_tecido}'.")
        tecido = Tecido(**dados.model_dump())
        db.add(tecido)
        confirmar(db, "Já existe um tecido com este código.")
        db.refresh(tecido)
        return tecido

    @staticmethod
    def atualizar(db: Session, id_tecido: int, dados: TecidoUpdate) -> Tecido:
        tecido = TecidoService.obter(db, id_tecido)
        campos = dados.model_dump(exclude_none=True)

        novo_codigo = campos.get("cd_tecido")
        if novo_codigo and novo_codigo != tecido.cd_tecido:
            if db.query(Tecido).filter(Tecido.cd_tecido == novo_codigo).first():
                raise conflito(f"Já existe um tecido com o código '{novo_codigo}'.")

        for campo, valor in campos.items():
            setattr(tecido, campo, valor)
        confirmar(db, "Já existe um tecido com este código.")
        db.refresh(tecido)
        return tecido

    @staticmethod
    def excluir(db: Session, id_tecido: int) -> None:
        tecido = TecidoService.obter(db, id_tecido)
        if tecido.lotes:
            raise conflito(
                f"O tecido possui {len(tecido.lotes)} lote(s) de tingimento e não pode ser excluído."
            )
        db.delete(tecido)
        db.commit()
