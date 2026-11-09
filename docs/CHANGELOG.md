# Changelog - TecnoTêxtil MVP

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

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

## [Unreleased] - Próximas Mudanças (Fase 2 - Auth JWT)
### Adicionado (planejado)
- Autenticação JWT com access/refresh tokens
- Hash de senhas com bcrypt
- RBAC com 3 perfis: VENDEDOR, CORTADOR, GERENTE
- Rota `POST /api/v1/auth/login`
- Proteção de rotas existentes via `Depends`
- Testes de autenticação e autorização

### Modificado (planejado)
- Seeds atualizados para usar senhas hasheadas
- Testes existentes adaptados para enviar token JWT
- `requirements.txt` e `requirements-dev.txt` com novas dependências