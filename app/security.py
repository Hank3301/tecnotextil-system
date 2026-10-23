"""Hash de senha com scrypt (biblioteca padrão, sem dependências extras)."""
import base64
import hashlib
import hmac
import secrets

_N, _R, _P, _DKLEN = 2**14, 8, 1, 32


def _b64(dados: bytes) -> str:
    return base64.b64encode(dados).decode("ascii")


def hash_senha(senha: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(senha.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN)
    return "$".join(["scrypt", str(_N), str(_R), str(_P), _b64(salt), _b64(dk)])


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    try:
        algoritmo, n, r, p, salt_b64, dk_b64 = hash_armazenado.split("$")
        if algoritmo != "scrypt":
            return False
        esperado = base64.b64decode(dk_b64)
        dk = hashlib.scrypt(
            senha.encode("utf-8"),
            salt=base64.b64decode(salt_b64),
            n=int(n), r=int(r), p=int(p), dklen=len(esperado),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(dk, esperado)
