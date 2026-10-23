from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def obter_ou_404(db: Session, modelo, id_, nome: str):
    """Busca por chave primária ou levanta 404 com mensagem em português."""
    obj = db.get(modelo, id_)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{nome} não encontrado(a).")
    return obj


def conflito(detalhe: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detalhe)


def confirmar(db: Session, detalhe_conflito: str) -> None:
    """Commit que converte violação de integridade (corrida entre requisições) em 409."""
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise conflito(detalhe_conflito)
