"""Utilitários compartilhados (sem dependência de framework)."""
import re
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

CENTESIMO = Decimal("0.01")


def utcnow() -> datetime:
    """Data/hora UTC *naive*, compatível com as colunas DateTime (sem timezone).

    Substitui `datetime.utcnow()`, depreciado desde o Python 3.12.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_decimal(valor) -> Decimal:
    """Converte float/int/str/Decimal/None para Decimal com 2 casas.

    Necessário porque as colunas Numeric retornam Decimal e os schemas
    Pydantic trabalham com float; `Decimal - float` levanta TypeError.
    Passa por `str()` para evitar artefatos binários (0.1 + 0.2).
    """
    if valor is None:
        return Decimal("0.00")
    if not isinstance(valor, Decimal):
        valor = Decimal(str(valor))
    return valor.quantize(CENTESIMO, rounding=ROUND_HALF_UP)


def validar_cpf(valor: str) -> str:
    """Normaliza (apenas dígitos) e valida o CPF, incluindo os dígitos verificadores."""
    cpf = re.sub(r"\D", "", valor or "")
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        raise ValueError("CPF inválido.")
    for i in (9, 10):
        soma = sum(int(cpf[n]) * (i + 1 - n) for n in range(i))
        if (soma * 10 % 11) % 10 != int(cpf[i]):
            raise ValueError("CPF inválido.")
    return cpf
