# Changelog - TecnoTêxtil MVP

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [0.3.0] - 2026-11-09
### Adicionado
- **Alembic** configurado para migrações de banco de dados
  - Arquivo `alembic.ini` com configuração para SQLite/PostgreSQL
  - `alembic/env.py` carregando variáveis de ambiente e `Base.metadata` dos models
  - Migração inicial `0001_initial.py` espelhando todas as 7 tabelas do schema atual
- **Automação em segundo plano (RN-02)** com APScheduler
  - Serviço `app/services/background_tasks.py` com job periódico
  - Rotina `expirar_reservas_vencidas_job` executa a cada 60 segundos
  - Busca reservas `ATIVA` com `dt_expiracao <= agora` e altera para `EXPIRADA`
  - Libera rolos associados (status `RESERVADO` → `DISPONIVEL`)
  - Gerenciamento correto de sessão do banco (evita vazamento de conexões)
  - Integração com lifespan do FastAPI em `app/main.py`
- **Suíte de testes** para expiração automática
  - `tests/test_expiracao_background.py` com 8 testes
  - Testes unitários do job de expiração (com/sem reservas, múltiplas, status variados)
  - Testes do ciclo de vida do scheduler (start/stop/idempotência)
  - Teste de integração completa via API

### Modificado
- `requirements.txt`: adicionado `apscheduler>=3.10.0`
- `requirements.txt`: fixado `bcrypt<4.0.0` para compatibilidade com passlib
- `docs/ROADMAP.md`: Fases 2, 3 e 4 marcadas como concluídas

### Corrigido
- Compatibilidade bcrypt/passlib (downgrade bcrypt para 3.2.2)

---

## [0.2.0] - 2024-10-23
### Adicionado
- Modelos completos: Tecido, LoteTingimento, Rolo, MapeamentoDefeito, Usuario, ReservaTemporaria, OrdemCorte
- Schemas Pydantic v2 com validações rigorosas
- Services com regras de negócio RN-02 (reserva 20min) e RN-05 (retalho ≤5m)
- Conferência de perdas baseada em defeitos mapeados
- Routers REST organizados: `/tecidos`, `/lotes`, `/rolos`, `/usuarios`, `/vendas`, `/corte/ordens`
- Seeds idempotentes para desenvolvimento
- 28 testes automatizados (pytest)

### Regras de Negócio Implementadas
- **RN-02**: Reserva temporária de 20 min com expiração automática
- **RN-05**: Reclassificação para retalho (≤5m) e inativação (saldo zero)
- **Conferência de perdas**: Cálculo automático com justificativa por defeitos

---

## [0.1.0] - 2024-10-XX
### Adicionado
- Estrutura inicial do projeto FastAPI
- Configuração SQLAlchemy + SQLite
- Modelos básicos de Tecido e Rolo
- CRUDs iniciais

---

## [Unreleased] - Próximas Mudanças (Fase 5 - Relatórios)
### Adicionado (planejado)
- Relatório de estoque por lote/tecido
- Relatório de perdas e divergências
- Relatório de produtividade por cortador
- Exportação CSV/PDF