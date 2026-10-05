from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


# ==========================================
# 1. SCHEMAS DE MAPEAMENTO DE DEFEITO
# ==========================================
class MapeamentoDefeitoBase(BaseModel):
    qt_metro_inicio: float = Field(..., gt=0, description="Início do defeito em metros")
    qt_metro_fim: float = Field(..., gt=0, description="Fim do defeito em metros")
    ds_defeito: str = Field(..., min_length=3, max_length=150)

class MapeamentoDefeitoCreate(MapeamentoDefeitoBase):
    id_rolo: int

class MapeamentoDefeitoResponse(MapeamentoDefeitoBase):
    id_defeito: int
    id_rolo: int

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 2. SCHEMAS DE ROLO
# ==========================================
class RoloBase(BaseModel):
    cd_barras: str = Field(..., min_length=5, max_length=50)
    qt_metragem_inicial: float = Field(..., gt=0)
    qt_metragem_atual: float = Field(..., ge=0)
    ds_localizacao: str = Field(..., max_length=50)
    st_rolo: str = Field(default="DISPONIVEL", max_length=20)
    fl_retalho: bool = Field(default=False)

class RoloCreate(RoloBase):
    id_lote: int

class RoloResponse(RoloBase):
    id_rolo: int
    id_lote: int
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

class LoteTingimentoResponse(LoteTingimentoBase):
    id_lote: int
    id_tecido: int
    rolos: List[RoloResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 4. SCHEMAS DE TECIDO
# ==========================================
class TecidoBase(BaseModel):
    cd_tecido: str = Field(..., min_length=3, max_length=30)
    nm_tecido: str = Field(..., min_length=3, max_length=100)
    ds_composicao: str = Field(..., min_length=3, max_length=150)
    vl_largura_metros: float = Field(..., gt=0)
    vl_gramatura: float = Field(..., gt=0)
    vl_preco_metro: float = Field(..., ge=0)

class TecidoCreate(TecidoBase):
    pass

class TecidoResponse(TecidoBase):
    id_tecido: int

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 5. SCHEMAS DE RESERVA TEMPORÁRIA
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
# 6. SCHEMAS DE ORDEM DE CORTE
# ==========================================
class OrdemCorteCreate(BaseModel):
    id_rolo: int
    id_reserva: Optional[int] = None
    qt_metragem_solicitada: float = Field(..., gt=0)

class OrdemCorteExecucao(BaseModel):
    id_usuario_cortador: int
    qt_sobra_informada: float = Field(..., ge=0)

class OrdemCorteResponse(BaseModel):
    id_ordem: int
    id_rolo: int
    id_reserva: Optional[int]
    id_usuario_cortador: Optional[int]
    dt_emissao: datetime
    dt_execucao: Optional[datetime]
    qt_metragem_solicitada: float
    qt_sobra_informada: Optional[float]
    st_ordem: str

    model_config = ConfigDict(from_attributes=True)