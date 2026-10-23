from decimal import Decimal

import pytest

from app.security import hash_senha, verificar_senha
from app.utils import to_decimal, validar_cpf


def test_cpf_valido_normaliza():
    assert validar_cpf("529.982.247-25") == "52998224725"


@pytest.mark.parametrize("cpf", ["52998224724", "11111111111", "123", ""])
def test_cpf_invalido(cpf):
    with pytest.raises(ValueError):
        validar_cpf(cpf)


def test_to_decimal_evita_artefatos_de_float():
    assert to_decimal(0.1) + to_decimal(0.2) == Decimal("0.30")
    assert to_decimal(None) == Decimal("0.00")


def test_hash_de_senha():
    h = hash_senha("abc12345")
    assert verificar_senha("abc12345", h)
    assert not verificar_senha("errada", h)
    assert not verificar_senha("abc12345", "formato-invalido")
    assert hash_senha("abc12345") != h  # salt aleatório
