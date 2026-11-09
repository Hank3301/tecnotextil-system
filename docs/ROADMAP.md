# Roadmap - TecnoTêxtil MVP

## ✅ Fase 1 - Núcleo de Regras e CRUDs (CONCLUÍDA)
- [x] Modelos SQLAlchemy: Tecido, LoteTingimento, Rolo, MapeamentoDefeito, Usuario, ReservaTemporaria, OrdemCorte
- [x] Schemas Pydantic com validações
- [x] Services com regras de negócio (RN-02, RN-05, conferência de perdas)
- [x] Routers REST organizados por recurso
- [x] Seeds idempotentes para dados de teste
- [x] 28 testes passando (cadastros, corte, utils)

---

## 🔄 Fase 2 - Autenticação JWT e RBAC (EM ANDAMENTO - TAREFA 2)
- [ ] Adicionar dependências: `passlib[bcrypt]`, `python-jose[cryptography]`
- [ ] Hash de senhas com bcrypt
- [ ] Geração/validação de tokens JWT (access + refresh)
- [ ] Rota `POST /api/v1/auth/login`
- [ ] Dependências FastAPI: `get_current_user`, `require_role`
- [ ] Perfis de acesso:
  - **VENDEDOR**: `/vendas`, `/rolos` (leitura), `/reservas`
  - **CORTADOR**: `/corte/ordens`, `/rolos` (leitura)
  - **GERENTE**: Acesso total (CRUDs de cadastro + operação)
- [ ] Proteger todos os routers existentes
- [ ] Atualizar seeds para criar usuários com senhas hasheadas

---

## 📋 Fase 3 - Background Tasks e Observabilidade
- [ ] Task periódica para expirar reservas vencidas (APScheduler ou similar)
- [ ] Logs estruturados (structlog)
- [ ] Health check endpoint
- [ ] Métricas básicas (Prometheus)

---

## 📋 Fase 4 - Migrações e Banco de Produção
- [ ] Configurar Alembic
- [ ] Migração inicial (schema atual)
- [ ] Suporte a PostgreSQL em produção
- [ ] Scripts de seed/migration para produção

---

## 📋 Fase 5 - Relatórios e Dashboards
- [ ] Relatório de estoque por lote/tecido
- [ ] Relatório de perdas e divergências
- [ ] Relatório de produtividade por cortador
- [ ] Exportação CSV/PDF

---

## 📋 Fase 6 - Qualidade e Entrega
- [ ] Testes de integração completos
- [ ] CI/CD (GitHub Actions)
- [ ] Dockerfile + docker-compose
- [ ] Documentação OpenAPI aprimorada