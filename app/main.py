from fastapi import FastAPI

app = FastAPI(
    title="TecnoTêxtil API",
    description="Sistema de Gestão de Estoque, Vendas por Lote e Mesa de Corte Têxtil",
    version="0.1.0"
)

@app.get("/")
def home():
    return {
        "sistema": "TecnoTêxtil",
        "status": "Online",
        "mensagem": "API do MVP rodando com sucesso!"
    }