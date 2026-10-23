from decimal import Decimal

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Date, ForeignKey, Numeric,
    CheckConstraint, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils import to_decimal, utcnow


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
    __table_args__ = (
        # A mesma partida não pode se repetir dentro do mesmo tecido (rastreabilidade).
        UniqueConstraint("id_tecido", "cd_partida", name="uq_lote_tecido_partida"),
    )

    id_lote = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_tecido = Column(Integer, ForeignKey("tb_tecido.id_tecido"), nullable=False)
    cd_partida = Column(String(50), nullable=False, index=True)
    dt_fabricacao = Column(Date, nullable=False)
    ds_tonalidade_cor = Column(String(50), nullable=False)

    tecido = relationship("Tecido", back_populates="lotes")
    rolos = relationship("Rolo", back_populates="lote", cascade="all, delete-orphan")


class Rolo(Base):
    __tablename__ = "tb_rolo"
    __table_args__ = (
        # Última linha de defesa contra estoque negativo (a regra principal está no service).
        CheckConstraint("qt_metragem_atual >= 0", name="ck_rolo_saldo_nao_negativo"),
    )

    id_rolo = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_lote = Column(Integer, ForeignKey("tb_lote_tingimento.id_lote"), nullable=False)
    cd_barras = Column(String(50), unique=True, nullable=False, index=True)
    qt_metragem_inicial = Column(Numeric(8, 2), nullable=False)
    qt_metragem_atual = Column(Numeric(8, 2), nullable=False)
    ds_localizacao = Column(String(50), nullable=False)
    st_rolo = Column(String(20), nullable=False, default="DISPONIVEL")
    fl_retalho = Column(Boolean, nullable=False, default=False)

    lote = relationship("LoteTingimento", back_populates="rolos")
    defeitos = relationship(
        "MapeamentoDefeito", back_populates="rolo", cascade="all, delete-orphan",
        order_by="MapeamentoDefeito.qt_metro_inicio",
    )
    reservas = relationship("ReservaTemporaria", back_populates="rolo")
    ordens_corte = relationship("OrdemCorte", back_populates="rolo")

    def baixar_metragem(self, metros) -> Decimal:
        """Abate `metros` do saldo atual do rolo e devolve o novo saldo.

        Levanta ValueError se a quantidade for <= 0 ou maior que o saldo, de modo
        que o estoque nunca fique negativo. Não faz commit (responsabilidade do service).
        """
        quantidade = to_decimal(metros)
        if quantidade <= 0:
            raise ValueError("A metragem a baixar deve ser maior que zero.")

        saldo = to_decimal(self.qt_metragem_atual)
        if quantidade > saldo:
            raise ValueError(
                f"Saldo insuficiente: tentativa de baixar {quantidade}m de um rolo com {saldo}m."
            )

        self.qt_metragem_atual = saldo - quantidade
        return self.qt_metragem_atual


class MapeamentoDefeito(Base):
    __tablename__ = "tb_mapeamento_defeito"

    id_defeito = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_rolo = Column(Integer, ForeignKey("tb_rolo.id_rolo"), nullable=False)
    qt_metro_inicio = Column(Numeric(8, 2), nullable=False)
    qt_metro_fim = Column(Numeric(8, 2), nullable=False)
    ds_defeito = Column(String(150), nullable=False)

    rolo = relationship("Rolo", back_populates="defeitos")

    @property
    def qt_metros_afetados(self) -> Decimal:
        return to_decimal(self.qt_metro_fim) - to_decimal(self.qt_metro_inicio)


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
    dt_criacao = Column(DateTime, nullable=False, default=utcnow)
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
    dt_emissao = Column(DateTime, nullable=False, default=utcnow)
    dt_execucao = Column(DateTime, nullable=True)
    qt_metragem_solicitada = Column(Numeric(8, 2), nullable=False)
    qt_sobra_informada = Column(Numeric(8, 2), nullable=True)
    # Conferência de perdas (preenchidos na execução do corte)
    qt_perda_apurada = Column(Numeric(8, 2), nullable=True)
    qt_perda_justificada = Column(Numeric(8, 2), nullable=True)
    fl_divergencia_perda = Column(Boolean, nullable=False, default=False)
    st_ordem = Column(String(20), nullable=False, default="PENDENTE")

    reserva = relationship("ReservaTemporaria", back_populates="ordem_corte")
    rolo = relationship("Rolo", back_populates="ordens_corte")
    cortador = relationship("Usuario", back_populates="ordens_corte")

    @property
    def qt_perda_nao_justificada(self):
        """Perda que os defeitos mapeados não explicam (None se a ordem não foi executada)."""
        if self.qt_perda_apurada is None:
            return None
        return to_decimal(self.qt_perda_apurada) - to_decimal(self.qt_perda_justificada)
