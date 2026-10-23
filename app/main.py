from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import engine, Base
from app.models.models import *  # noqa: F401,F403  (registra as tabelas no metadata)
from app.routers import vendas, corte, tecidos, lotes, rolos, usuarios


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Cria as tabelas no startup (e não no import, para não tocar o banco em testes)
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="TecnoTêxtil API",
    description="MVP para controle de estoque, vendas por lote e mesa de corte têxtil.",
    version="0.2.0",
    lifespan=lifespan,
)

# Cadastros
app.include_router(tecidos.router)
app.include_router(lotes.router)
app.include_router(rolos.router)
app.include_router(usuarios.router)

# Operação
app.include_router(vendas.router)
app.include_router(corte.router)


@app.get("/")
def home():
    return {
        "status": "online",
        "sistema": "TecnoTêxtil API MVP",
        "documentacao": "/docs"
    }
