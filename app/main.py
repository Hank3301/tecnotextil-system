from fastapi import FastAPI
from app.database import engine, Base
from app.models.models import *
from app.routers import vendas, corte  # <--- Inclui o router de corte

# Cria as tabelas no banco de dados se não existirem
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TecnoTêxtil API",
    description="MVP para controle de estoque, vendas por lote e mesa de corte têxtil.",
    version="0.1.0"
)

# Registra os dois módulos da API
app.include_router(vendas.router)
app.include_router(corte.router)

@app.get("/")
def home():
    return {
        "status": "online",
        "sistema": "TecnoTêxtil API MVP",
        "documentacao": "/docs"
    }