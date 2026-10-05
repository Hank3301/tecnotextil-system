from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, 
    DateTime, Date, ForeignKey, Numeric
)
from sqlalchemy.orm import relationship
from app.database import Base


class Tecido(Base):
    __tablename__ = "tb_tecido"

    id_tecido = Column(Integer, primary_key=True, index=True, autoincrement=True)
    cd_tecido = Column(String(30), unique=True, nullable=False, index=True)
    nm_tecido = Column(String(100), nullable=False)
    ds_composicao = Column(String(150), nullable=False)
    vl_largura_metros = Column(Numeric(5, 2), nullable=False)
    vl_gramatura = Column(Numeric(6, 2), nullable=False)
    vl_preco_metro = Column(Numeric(10, 2), nullable=False)

    lotes = relationship("LoteTingimento", back_populates="tecido", cascade="all, delete-orphan")


class LoteTingimento(Base):
    __tablename__ = "tb_lote_tingimento"

    id_lote = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_tecido = Column(Integer, ForeignKey("tb_tecido.id_tecido"), nullable=False)
    cd_partida = Column(String(50), nullable=False, index=True)
    dt_fabricacao = Column(Date, nullable=False)
    ds_tonalidade_cor = Column(String(50), nullable=False)

    tecido = relationship("Tecido", back_populates="lotes")
    rolos = relationship("Rolo", back_populates="lote", cascade="all, delete-orphan")


class Rolo(Base):
    __tablename__ = "tb_rolo"

    id_rolo = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_lote = Column(Integer, ForeignKey("tb_lote_tingimento.id_lote"), nullable=False)
    cd_barras = Column(String(50), unique=True, nullable=False, index=True)
    qt_metragem_inicial = Column(Numeric(8, 2), nullable=False)
    qt_metragem_atual = Column(Numeric(8, 2), nullable=False)
    ds_localizacao = Column(String(50), nullable=False)
    st_rolo = Column(String(20), nullable=False, default="DISPONIVEL")
    fl_retalho = Column(Boolean, nullable=False, default=False)

    lote = relationship("LoteTingimento", back_populates="rolos")
    defeitos = relationship("MapeamentoDefeito", back_populates="rolo", cascade="all, delete-orphan")
    reservas = relationship("ReservaTemporaria", back_populates="rolo")
    ordens_corte = relationship("OrdemCorte", back_populates="rolo")


class MapeamentoDefeito(Base):
    __tablename__ = "tb_mapeamento_defeito"

    id_defeito = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_rolo = Column(Integer, ForeignKey("tb_rolo.id_rolo"), nullable=False)
    qt_metro_inicio = Column(Numeric(8, 2), nullable=False)
    qt_metro_fim = Column(Numeric(8, 2), nullable=False)
    ds_defeito = Column(String(150), nullable=False)

    rolo = relationship("Rolo", back_populates="defeitos")


class Usuario(Base):
    __tablename__ = "tb_usuario"

    id_usuario = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nm_usuario = Column(String(100), nullable=False)
    cd_cpf = Column(String(11), unique=True, nullable=False)
    ds_cargo = Column(String(50), nullable=False)
    ds_login = Column(String(50), unique=True, nullable=False)
    ds_senha_hash = Column(String(255), nullable=False)

    ordens_corte = relationship("OrdemCorte", back_populates="cortador")


class ReservaTemporaria(Base):
    __tablename__ = "tb_reserva_temporaria"

    id_reserva = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_rolo = Column(Integer, ForeignKey("tb_rolo.id_rolo"), nullable=False)
    qt_metragem_reservada = Column(Numeric(8, 2), nullable=False)
    dt_criacao = Column(DateTime, nullable=False, default=datetime.utcnow)
    dt_expiracao = Column(DateTime, nullable=False)
    st_reserva = Column(String(20), nullable=False, default="ATIVA")

    rolo = relationship("Rolo", back_populates="reservas")
    ordem_corte = relationship("OrdemCorte", back_populates="reserva", uselist=False)


class OrdemCorte(Base):
    __tablename__ = "tb_ordem_corte"

    id_ordem = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_reserva = Column(Integer, ForeignKey("tb_reserva_temporaria.id_reserva"), nullable=True)
    id_rolo = Column(Integer, ForeignKey("tb_rolo.id_rolo"), nullable=False)
    id_usuario_cortador = Column(Integer, ForeignKey("tb_usuario.id_usuario"), nullable=True)
    dt_emissao = Column(DateTime, nullable=False, default=datetime.utcnow)
    dt_execucao = Column(DateTime, nullable=True)
    qt_metragem_solicitada = Column(Numeric(8, 2), nullable=False)
    qt_sobra_informada = Column(Numeric(8, 2), nullable=True)
    st_ordem = Column(String(20), nullable=False, default="PENDENTE")

    reserva = relationship("ReservaTemporaria", back_populates="ordem_corte")
    rolo = relationship("Rolo", back_populates="ordens_corte")
    cortador = relationship("Usuario", back_populates="ordens_corte")