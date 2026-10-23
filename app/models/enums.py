from enum import StrEnum


class StatusRolo(StrEnum):
    DISPONIVEL = "DISPONIVEL"
    RESERVADO = "RESERVADO"
    EM_CORTE = "EM_CORTE"
    BLOQUEADO = "BLOQUEADO"   # quarentena manual (ex.: problema de qualidade)
    INATIVO = "INATIVO"       # rolo zerado ou baixado manualmente


class StatusReserva(StrEnum):
    ATIVA = "ATIVA"
    EXPIRADA = "EXPIRADA"
    CANCELADA = "CANCELADA"
    CONFIRMADA = "CONFIRMADA"


class StatusOrdem(StrEnum):
    PENDENTE = "PENDENTE"
    CONCLUIDA = "CONCLUIDA"
    CANCELADA = "CANCELADA"
