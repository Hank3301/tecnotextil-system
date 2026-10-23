from datetime import datetime, date
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import StatusRolo
from app.utils import validar_cpf


# ==========================================
# 1. SCHEMAS DE MAPEAMENTO DE DEFEITO
# ==========================================
class MapeamentoDefeitoBase(BaseModel):
    qt_metro_inicio: float = Field(..., ge=0, description="Início do defeito em metros (0 = início do rolo)")
    qt_metro_fim: float = Field(..., gt=0, description="Fim do defeito em metros")
    ds_defeito: str = Field(..., min_length=3, max_length=150)

    @model_validator(mode="after")
    def _validar_intervalo(self):
        if self.qt_metro_fim <= self.qt_metro_inicio:
            raise ValueError("qt_metro_fim deve ser maior que qt_metro_inicio.")
        return self


class MapeamentoDefeitoCreate(MapeamentoDefeitoBase):
    """O id do rolo vem da URL (/rolos/{id_rolo}/defeitos)."""


class MapeamentoDefeitoResponse(MapeamentoDefeitoBase):
    id_defeito: int
    id_rolo: int

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 2. SCHEMAS DE ROLO
# ==========================================
class RoloBase(BaseModel):
    cd_barras: str = Field(..., min_length=5, max_length=50)
    qt_metragem_inicial: float = Field(..., gt=0, le=999999.99)
    ds_localizacao: str = Field(..., min_length=1, max_length=50)


class RoloCreate(RoloBase):
    """Saldo atual = metragem inicial; status/retalho são controlados pelo sistema."""
    id_lote: int


class RoloUpdate(BaseModel):
    ds_localizacao: Optional[str] = Field(None, min_length=1, max_length=50)
    st_rolo: Optional[StatusRolo] = Field(
        None, description="Transição manual: apenas DISPONIVEL, BLOQUEADO ou INATIVO."
    )


class RoloResumo(BaseModel):
    id_rolo: int
    cd_barras: str
    qt_metragem_atual: float
    st_rolo: str
    fl_retalho: bool

    model_config = ConfigDict(from_attributes=True)


class RoloResponse(RoloBase):
    id_rolo: int
    id_lote: int
    qt_metragem_atual: float
    st_rolo: str
    fl_retalho: bool
    defeitos: List[MapeamentoDefeitoResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 3. SCHEMAS DE LOTE DE TINGIMENTO
# ==========================================
class LoteTingimentoBase(BaseModel):
    cd_partida: str = Field(..., min_length=2, max_length=50)
    dt_fabricacao: date
    ds_tonalidade_cor: str = Field(..., min_length=2, max_length=50)


class LoteTingimentoCreate(LoteTingimentoBase):
    id_tecido: int


class LoteTingimentoUpdate(BaseModel):
    """O tecido de um lote não pode ser trocado (quebraria a rastreabilidade)."""
    cd_partida: Optional[str] = Field(None, min_length=2, max_length=50)
    dt_fabricacao: Optional[date] = None
    ds_tonalidade_cor: Optional[str] = Field(None, min_length=2, max_length=50)


class LoteTingimentoResumo(LoteTingimentoBase):
    id_lote: int
    id_tecido: int

    model_config = ConfigDict(from_attributes=True)


class LoteTingimentoResponse(LoteTingimentoResumo):
    rolos: List[RoloResponse] = []


# ==========================================
# 4. SCHEMAS DE TECIDO
# ==========================================
class TecidoBase(BaseModel):
    cd_tecido: str = Field(..., min_length=3, max_length=30)
    nm_tecido: str = Field(..., min_length=3, max_length=100)
    ds_composicao: str = Field(..., min_length=3, max_length=150)
    vl_largura_metros: float = Field(..., gt=0, le=999.99)
    vl_gramatura: float = Field(..., gt=0, le=9999.99)
    vl_preco_metro: float = Field(..., ge=0, le=99999999.99)


class TecidoCreate(TecidoBase):
    pass


class TecidoUpdate(BaseModel):
    cd_tecido: Optional[str] = Field(None, min_length=3, max_length=30)
    nm_tecido: Optional[str] = Field(None, min_length=3, max_length=100)
    ds_composicao: Optional[str] = Field(None, min_length=3, max_length=150)
    vl_largura_metros: Optional[float] = Field(None, gt=0, le=999.99)
    vl_gramatura: Optional[float] = Field(None, gt=0, le=9999.99)
    vl_preco_metro: Optional[float] = Field(None, ge=0, le=99999999.99)


class TecidoResponse(TecidoBase):
    id_tecido: int

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 5. SCHEMAS DE USUÁRIO
# ==========================================
_LOGIN_REGEX = r"^[A-Za-z0-9_.-]+$"


class UsuarioBase(BaseModel):
    nm_usuario: str = Field(..., min_length=3, max_length=100)
    cd_cpf: str = Field(..., description="CPF com ou sem máscara; é armazenado só com dígitos.")
    ds_cargo: str = Field(..., min_length=2, max_length=50)
    ds_login: str = Field(..., min_length=3, max_length=50, pattern=_LOGIN_REGEX)

    @field_validator("cd_cpf")
    @classmethod
    def _cpf_valido(cls, v):
        return validar_cpf(v)

    @field_validator("ds_login")
    @classmethod
    def _login_minusculo(cls, v):
        return v.lower()


class UsuarioCreate(UsuarioBase):
    ds_senha: str = Field(..., min_length=8, max_length=128)


class UsuarioUpdate(BaseModel):
    nm_usuario: Optional[str] = Field(None, min_length=3, max_length=100)
    cd_cpf: Optional[str] = None
    ds_cargo: Optional[str] = Field(None, min_length=2, max_length=50)
    ds_login: Optional[str] = Field(None, min_length=3, max_length=50, pattern=_LOGIN_REGEX)
    ds_senha: Optional[str] = Field(None, min_length=8, max_length=128)

    @field_validator("cd_cpf")
    @classmethod
    def _cpf_valido(cls, v):
        return validar_cpf(v) if v is not None else v

    @field_validator("ds_login")
    @classmethod
    def _login_minusculo(cls, v):
        return v.lower() if v is not None else v


class UsuarioResponse(UsuarioBase):
    """Nunca expõe senha nem hash."""
    id_usuario: int

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 6. SCHEMAS DE RESERVA TEMPORÁRIA
# ==========================================
class ReservaCreate(BaseModel):
    id_rolo: int
    qt_metragem_reservada: float = Field(..., gt=0)


class ReservaResponse(BaseModel):
    id_reserva: int
    id_rolo: int
    qt_metragem_reservada: float
    dt_criacao: datetime
    dt_expiracao: datetime
    st_reserva: str

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 7. SCHEMAS DE ORDEM DE CORTE
# ==========================================
class OrdemCorteCreate(BaseModel):
    id_rolo: int
    id_reserva: Optional[int] = None
    qt_metragem_solicitada: float = Field(..., gt=0)


class OrdemCorteExecucao(BaseModel):
    id_usuario_cortador: int
    qt_sobra_informada: float = Field(
        ..., ge=0, description="Metragem que o cortador mediu fisicamente no rolo após o corte."
    )


class OrdemCorteResponse(BaseModel):
    id_ordem: int
    id_rolo: int
    id_reserva: Optional[int]
    id_usuario_cortador: Optional[int]
    dt_emissao: datetime
    dt_execucao: Optional[datetime]
    qt_metragem_solicitada: float
    qt_sobra_informada: Optional[float]
    qt_perda_apurada: Optional[float]
    qt_perda_justificada: Optional[float]
    qt_perda_nao_justificada: Optional[float]
    fl_divergencia_perda: bool
    st_ordem: str
    rolo: RoloResumo

    model_config = ConfigDict(from_attributes=True)
