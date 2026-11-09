from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.models import Usuario
from app.schemas.schemas import UsuarioCreate, UsuarioUpdate
from app.auth.security import hash_senha
from app.services.common import conflito, confirmar, obter_ou_404


class UsuarioService:

    @staticmethod
    def _checar_duplicidade(db: Session, cd_cpf: Optional[str], ds_login: Optional[str], ignorar_id: Optional[int] = None):
        if cd_cpf:
            q = db.query(Usuario).filter(Usuario.cd_cpf == cd_cpf)
            if ignorar_id:
                q = q.filter(Usuario.id_usuario != ignorar_id)
            if q.first():
                raise conflito("Já existe um usuário cadastrado com este CPF.")
        if ds_login:
            q = db.query(Usuario).filter(Usuario.ds_login == ds_login)
            if ignorar_id:
                q = q.filter(Usuario.id_usuario != ignorar_id)
            if q.first():
                raise conflito(f"O login '{ds_login}' já está em uso.")

    @staticmethod
    def listar(db: Session, ds_cargo: Optional[str] = None, skip: int = 0, limit: int = 50) -> List[Usuario]:
        query = db.query(Usuario)
        if ds_cargo:
            query = query.filter(Usuario.ds_cargo.ilike(ds_cargo))
        return query.order_by(Usuario.nm_usuario).offset(skip).limit(limit).all()

    @staticmethod
    def obter(db: Session, id_usuario: int) -> Usuario:
        return obter_ou_404(db, Usuario, id_usuario, "Usuário")

    @staticmethod
    def criar(db: Session, dados: UsuarioCreate) -> Usuario:
        UsuarioService._checar_duplicidade(db, dados.cd_cpf, dados.ds_login)
        usuario = Usuario(
            nm_usuario=dados.nm_usuario,
            cd_cpf=dados.cd_cpf,
            ds_cargo=dados.ds_cargo,
            ds_login=dados.ds_login,
            ds_senha_hash=hash_senha(dados.ds_senha),
        )
        db.add(usuario)
        confirmar(db, "CPF ou login já cadastrado.")
        db.refresh(usuario)
        return usuario

    @staticmethod
    def atualizar(db: Session, id_usuario: int, dados: UsuarioUpdate) -> Usuario:
        usuario = UsuarioService.obter(db, id_usuario)
        campos = dados.model_dump(exclude_none=True)

        UsuarioService._checar_duplicidade(
            db,
            cd_cpf=campos.get("cd_cpf") if campos.get("cd_cpf") != usuario.cd_cpf else None,
            ds_login=campos.get("ds_login") if campos.get("ds_login") != usuario.ds_login else None,
            ignorar_id=usuario.id_usuario,
        )

        nova_senha = campos.pop("ds_senha", None)
        for campo, valor in campos.items():
            setattr(usuario, campo, valor)
        if nova_senha:
            usuario.ds_senha_hash = hash_senha(nova_senha)

        confirmar(db, "CPF ou login já cadastrado.")
        db.refresh(usuario)
        return usuario

    @staticmethod
    def excluir(db: Session, id_usuario: int) -> None:
        usuario = UsuarioService.obter(db, id_usuario)
        if usuario.ordens_corte:
            raise conflito("O usuário possui ordens de corte no histórico e não pode ser excluído.")
        db.delete(usuario)
        db.commit()
