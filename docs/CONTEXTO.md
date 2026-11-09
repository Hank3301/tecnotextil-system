# Contexto do Projeto TecnoTêxtil MVP

## Objetivo
Sistema de gestão de vendas, estoque e mesa de corte têxtil com rastreabilidade completa: **Tecido → Lote de Tingimento (partida/cor) → Rolo**.

## Stack Tecnológica
- **Framework**: FastAPI 0.100+
- **ORM**: SQLAlchemy 2.0
- **Banco de Dados**: SQLite (desenvolvimento) / PostgreSQL (produção via `DATABASE_URL`)
- **Validação**: Pydantic v2
- **Testes**: pytest
- **Servidor**: Uvicorn
- **Autenticação**: JWT (em implementação - TAREFA 2)
- **Hash de Senhas**: bcrypt via passlib

## Regras de Negócio Principais

### RN-02: Reserva Temporária (20 minutos)
- Vendedor reserva metragem de um rolo por **20 minutos**
- Status do rolo muda para `RESERVADO` durante a reserva
- Se expirar sem virar ordem de corte → rolo volta a `DISPONIVEL` e reserva fica `EXPIRADA`
- Ao emitir ordem de corte, reserva vira `CONFIRMADA` (deixa de expirar)

### RN-05: Retalho e Inativação
- Após corte, se saldo remanescente **≤ 5,00 m** → `fl_retalho = true`
- Se saldo zerar → rolo fica `INATIVO`

### Conferência de Perdas
- `perda = (saldo anterior − metragem cortada) − sobra informada`
- A sobra informada (medição física) vira o novo saldo
- Perda é justificada até o total de metros de defeitos mapeados no rolo que ainda não justificaram perdas anteriores
- Excedente acima de **0,10 m** marca `fl_divergencia_perda` para conferência

## Modelos de Dados
| Entidade | Descrição |
|----------|-----------|
| `Tecido` | Cadastro base (código, nome, composição, largura, gramatura, preço/m) |
| `LoteTingimento` | Partida/cor única por tecido (rastreabilidade) |
| `Rolo` | Estoque físico com código de barras, metragem, localização, status, defeitos |
| `MapeamentoDefeito` | Intervalos de defeito no rolo (início/fim em metros) |
| `Usuario` | Usuários com cargo (VENDEDOR, CORTADOR, GERENTE) |
| `ReservaTemporaria` | Bloqueio de metragem por 20 min (RN-02) |
| `OrdemCorte` | Execução do corte com conferência de perdas |

## Endpoints Atuais (`/api/v1`)
- `/tecidos` - CRUD completo
- `/lotes` - CRUD + rolos do lote
- `/rolos` - CRUD + busca por código de barras + defeitos
- `/rolos/{id}/defeitos` - CRUD de defeitos
- `/usuarios` - CRUD (sem auth ainda)
- `/vendas` - Estoque por lote, reservas temporárias
- `/corte/ordens` - Emissão, execução, cancelamento de ordens

## Usuários de Teste (Dev)
- `cortador` / `cortador123` (cargo: CORTADOR)
- `vendedor` / `vendedor123` (cargo: VENDEDOR)