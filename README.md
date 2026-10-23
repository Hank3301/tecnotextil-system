# tecnotextil-system
MVP do Sistema de Gestão de Vendas, Estoque e Mesa de Corte Têxtil

Rastreabilidade: **Tecido → Lote de Tingimento (partida/cor) → Rolo**.

## Como rodar

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# IMPORTANTE (upgrade da v0.1): o schema mudou (novas colunas em tb_ordem_corte,
# constraints em tb_rolo e tb_lote_tingimento). Apague o banco antigo antes:
rm -f tecnotextil.db

python -m app.seeds                 # massa de teste (idempotente)
uvicorn app.main:app --reload       # docs interativas em http://localhost:8000/docs
```

Usuários de teste (somente desenvolvimento): `cortador` / `cortador123` e `vendedor` / `vendedor123`.
Outro banco: variável de ambiente `DATABASE_URL`.

## Testes

```bash
pip install -r requirements-dev.txt
pytest
```

## Endpoints (`/api/v1`)

| Recurso | Rotas |
|---|---|
| `/tecidos` | `POST`, `GET` (busca, skip, limit), `GET /{id}`, `PATCH /{id}`, `DELETE /{id}` |
| `/lotes` | `POST`, `GET` (id_tecido, cd_partida, cor), `GET /{id}` (com rolos), `PATCH /{id}`, `DELETE /{id}` |
| `/rolos` | `POST`, `GET` (id_lote, cd_tecido, st_rolo, fl_retalho), `GET /{id}`, `GET /codigo-barras/{cd}`, `PATCH /{id}`, `DELETE /{id}` |
| `/rolos/{id}/defeitos` | `GET`, `POST`, `DELETE /{id_defeito}` |
| `/usuarios` | `POST`, `GET` (ds_cargo), `GET /{id}`, `PATCH /{id}`, `DELETE /{id}` |
| `/vendas` | estoque por lote, reservas temporárias (RN-02) |
| `/corte/ordens` | `POST`, `GET`, `GET /{id}`, `POST /{id}/executar`, `PATCH /{id}/cancelar` |

Erros seguem o padrão FastAPI `{"detail": "mensagem"}`:
`404` não encontrado · `409` duplicidade/dependência (CRUD) · `400` regra de negócio · `422` payload inválido.

## Regras de negócio

- **RN-02** – reserva temporária de 20 min; vencida, o rolo volta a `DISPONIVEL`. Ao emitir a ordem de corte a reserva vira `CONFIRMADA` (deixa de expirar).
- **RN-05** – após o corte, saldo do rolo `<= 5,00 m` ⇒ `fl_retalho = true`. Saldo zero ⇒ `INATIVO`.
- **Conferência de perdas** – `perda = (saldo anterior − metragem cortada) − sobra informada`. A sobra informada (medição física) vira o novo saldo. A perda é justificada até o total de metros de defeitos mapeados no rolo que ainda não justificaram perdas anteriores; o excedente acima de 0,10 m marca `fl_divergencia_perda`.
