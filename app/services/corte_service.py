from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.enums import StatusOrdem, StatusReserva, StatusRolo
from app.models.models import OrdemCorte, ReservaTemporaria, Rolo, Usuario
from app.schemas.schemas import OrdemCorteCreate, OrdemCorteExecucao
from app.services.reserva_service import ReservaService
from app.utils import to_decimal, utcnow

# Regra de Negócio RN-05: saldo remanescente <= 5 m => reclassifica como retalho
LIMITE_RETALHO_METROS = Decimal("5.00")

# Perda não explicada por defeitos acima desta folga é sinalizada para conferência
TOLERANCIA_PERDA_METROS = Decimal("0.10")

ZERO = Decimal("0.00")


def _erro(codigo: int, detalhe: str) -> HTTPException:
    return HTTPException(status_code=codigo, detail=detalhe)


class CorteService:

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    @staticmethod
    def obter_ordem(db: Session, id_ordem: int) -> OrdemCorte:
        ordem = db.query(OrdemCorte).filter(OrdemCorte.id_ordem == id_ordem).first()
        if not ordem:
            raise _erro(status.HTTP_404_NOT_FOUND, "Ordem de Corte não encontrada.")
        return ordem

    @staticmethod
    def listar_ordens(
        db: Session,
        st_ordem: Optional[str] = None,
        id_rolo: Optional[int] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[OrdemCorte]:
        query = db.query(OrdemCorte)
        if st_ordem:
            query = query.filter(OrdemCorte.st_ordem == st_ordem)
        if id_rolo:
            query = query.filter(OrdemCorte.id_rolo == id_rolo)
        return query.order_by(OrdemCorte.id_ordem.desc()).offset(skip).limit(limit).all()

    # ------------------------------------------------------------------
    # Emissão da ordem
    # ------------------------------------------------------------------
    @staticmethod
    def criar_ordem_corte(db: Session, dados_ordem: OrdemCorteCreate) -> OrdemCorte:
        """
        Gera uma Ordem de Corte e move o rolo para 'EM_CORTE'.

        Validações:
          - rolo existe e está DISPONIVEL ou RESERVADO;
          - metragem solicitada não excede o saldo do rolo (sem estoque negativo);
          - rolo RESERVADO exige o id_reserva correspondente (não dá para "furar" a reserva);
          - id_reserva informado: existe, pertence a este rolo, está ATIVA e não vencida,
            cobre a metragem solicitada e ainda não gerou outra ordem.

        A reserva passa a CONFIRMADA já na emissão: a venda foi efetivada e o prazo de
        20 min (RN-02) deixa de se aplicar. Se ficasse ATIVA até a execução, poderia
        expirar com a ordem ainda pendente.
        """
        # Libera reservas vencidas antes de validar (RN-02)
        ReservaService.expirar_reservas_vencidas(db)

        rolo = (
            db.query(Rolo).filter(Rolo.id_rolo == dados_ordem.id_rolo)
            .with_for_update().first()
        )
        if not rolo:
            raise _erro(status.HTTP_404_NOT_FOUND, "Rolo não encontrado.")

        if rolo.st_rolo not in (StatusRolo.DISPONIVEL, StatusRolo.RESERVADO):
            raise _erro(
                status.HTTP_400_BAD_REQUEST,
                f"Não é possível gerar ordem de corte para rolo com status '{rolo.st_rolo}'.",
            )

        solicitada = to_decimal(dados_ordem.qt_metragem_solicitada)
        saldo = to_decimal(rolo.qt_metragem_atual)
        if solicitada > saldo:
            raise _erro(
                status.HTTP_400_BAD_REQUEST,
                f"Metragem solicitada ({solicitada}m) excede o saldo do rolo ({saldo}m).",
            )

        reserva: Optional[ReservaTemporaria] = None
        if dados_ordem.id_reserva is not None:
            reserva = (
                db.query(ReservaTemporaria)
                .filter(ReservaTemporaria.id_reserva == dados_ordem.id_reserva)
                .with_for_update().first()
            )
            if not reserva:
                raise _erro(status.HTTP_404_NOT_FOUND, "Reserva não encontrada.")

            if reserva.id_rolo != rolo.id_rolo:
                raise _erro(
                    status.HTTP_400_BAD_REQUEST,
                    f"A reserva {reserva.id_reserva} pertence a outro rolo "
                    f"(rolo {reserva.id_rolo}), não ao rolo {rolo.id_rolo}.",
                )
            if reserva.st_reserva != StatusReserva.ATIVA:
                raise _erro(
                    status.HTTP_400_BAD_REQUEST,
                    f"A reserva {reserva.id_reserva} não está ativa (status atual: {reserva.st_reserva}).",
                )
            if reserva.dt_expiracao <= utcnow():
                raise _erro(
                    status.HTTP_400_BAD_REQUEST,
                    f"A reserva {reserva.id_reserva} expirou. Crie uma nova reserva.",
                )
            reservada = to_decimal(reserva.qt_metragem_reservada)
            if solicitada > reservada:
                raise _erro(
                    status.HTTP_400_BAD_REQUEST,
                    f"Metragem solicitada ({solicitada}m) excede a metragem reservada ({reservada}m).",
                )
            ordem_existente = (
                db.query(OrdemCorte)
                .filter(
                    OrdemCorte.id_reserva == reserva.id_reserva,
                    OrdemCorte.st_ordem != StatusOrdem.CANCELADA,
                ).first()
            )
            if ordem_existente:
                raise _erro(
                    status.HTTP_400_BAD_REQUEST,
                    f"A reserva {reserva.id_reserva} já está vinculada à ordem {ordem_existente.id_ordem}.",
                )
        elif rolo.st_rolo == StatusRolo.RESERVADO:
            raise _erro(
                status.HTTP_400_BAD_REQUEST,
                "O rolo está reservado. Informe o id_reserva correspondente para gerar a ordem de corte.",
            )

        nova_ordem = OrdemCorte(
            id_rolo=rolo.id_rolo,
            id_reserva=reserva.id_reserva if reserva else None,
            qt_metragem_solicitada=solicitada,
            st_ordem=StatusOrdem.PENDENTE,
            dt_emissao=utcnow(),
        )
        if reserva:
            reserva.st_reserva = StatusReserva.CONFIRMADA
        rolo.st_rolo = StatusRolo.EM_CORTE

        db.add(nova_ordem)
        db.commit()
        db.refresh(nova_ordem)
        return nova_ordem

    # ------------------------------------------------------------------
    # Execução do corte
    # ------------------------------------------------------------------
    @staticmethod
    def executar_corte_e_baixar_estoque(
        db: Session, id_ordem: int, dados_execucao: OrdemCorteExecucao
    ) -> OrdemCorte:
        """
        Executa o corte, baixa o estoque, confere perdas e aplica a RN-05.

        Conferência de perdas
        ---------------------
        saldo esperado = saldo anterior - metragem cortada
        perda apurada  = saldo esperado - sobra informada (o que o cortador mediu)
        A sobra informada é a medição física e passa a ser o novo saldo do rolo.
        A perda é "justificada" até o limite da metragem de defeitos mapeados no
        rolo ainda não usada para justificar perdas de cortes anteriores. O excedente
        acima da tolerância marca `fl_divergencia_perda` para conferência.
        """
        ordem = (
            db.query(OrdemCorte).filter(OrdemCorte.id_ordem == id_ordem)
            .with_for_update().first()
        )
        if not ordem:
            raise _erro(status.HTTP_404_NOT_FOUND, "Ordem de Corte não encontrada.")

        if ordem.st_ordem != StatusOrdem.PENDENTE:
            raise _erro(
                status.HTTP_400_BAD_REQUEST,
                f"Ordem com status '{ordem.st_ordem}' não pode ser executada "
                f"(apenas ordens {StatusOrdem.PENDENTE}).",
            )

        rolo = (
            db.query(Rolo).filter(Rolo.id_rolo == ordem.id_rolo)
            .with_for_update().first()
        )
        if rolo.st_rolo != StatusRolo.EM_CORTE:
            raise _erro(
                status.HTTP_400_BAD_REQUEST,
                f"Rolo em status '{rolo.st_rolo}' (esperado: {StatusRolo.EM_CORTE}). "
                "Verifique a consistência da ordem.",
            )

        cortador = db.query(Usuario).filter(Usuario.id_usuario == dados_execucao.id_usuario_cortador).first()
        if not cortador:
            raise _erro(status.HTTP_404_NOT_FOUND, "Usuário cortador não encontrado.")

        # 1. Validações de saldo (antes de alterar qualquer coisa)
        cortada = to_decimal(ordem.qt_metragem_solicitada)
        saldo_anterior = to_decimal(rolo.qt_metragem_atual)
        if cortada > saldo_anterior:
            raise _erro(
                status.HTTP_400_BAD_REQUEST,
                f"Metragem da ordem ({cortada}m) excede o saldo atual do rolo ({saldo_anterior}m).",
            )

        saldo_esperado = saldo_anterior - cortada
        sobra = to_decimal(dados_execucao.qt_sobra_informada)
        if sobra > saldo_esperado:
            raise _erro(
                status.HTTP_400_BAD_REQUEST,
                f"Sobra informada ({sobra}m) é maior que o saldo esperado após o corte ({saldo_esperado}m).",
            )

        # 2. Conferência de perdas x defeitos mapeados
        perda = saldo_esperado - sobra
        total_defeitos = sum((d.qt_metros_afetados for d in rolo.defeitos), ZERO)
        ja_justificada = sum(
            (
                to_decimal(o.qt_perda_justificada)
                for o in rolo.ordens_corte
                if o.st_ordem == StatusOrdem.CONCLUIDA and o.id_ordem != ordem.id_ordem
            ),
            ZERO,
        )
        defeito_disponivel = max(ZERO, total_defeitos - ja_justificada)
        perda_justificada = min(perda, defeito_disponivel)
        perda_nao_justificada = perda - perda_justificada

        # 3. Baixa de estoque: metragem cortada + perda apurada => saldo = sobra informada
        try:
            rolo.baixar_metragem(cortada + perda)
        except ValueError as exc:  # defesa em profundidade; já validado acima
            raise _erro(status.HTTP_400_BAD_REQUEST, str(exc))

        # 4. Atualiza a ordem
        ordem.id_usuario_cortador = cortador.id_usuario
        ordem.qt_sobra_informada = sobra
        ordem.qt_perda_apurada = perda
        ordem.qt_perda_justificada = perda_justificada
        ordem.fl_divergencia_perda = perda_nao_justificada > TOLERANCIA_PERDA_METROS
        ordem.dt_execucao = utcnow()
        ordem.st_ordem = StatusOrdem.CONCLUIDA

        # 5. RN-05 e status do rolo
        saldo_final = to_decimal(rolo.qt_metragem_atual)
        if saldo_final <= 0:
            rolo.st_rolo = StatusRolo.INATIVO
        else:
            rolo.st_rolo = StatusRolo.DISPONIVEL
            if saldo_final <= LIMITE_RETALHO_METROS:
                rolo.fl_retalho = True

        db.commit()
        db.refresh(ordem)
        return ordem

    # ------------------------------------------------------------------
    # Cancelamento
    # ------------------------------------------------------------------
    @staticmethod
    def cancelar_ordem(db: Session, id_ordem: int) -> OrdemCorte:
        """Cancela uma ordem PENDENTE, devolve o rolo a DISPONIVEL e cancela a reserva vinculada."""
        ordem = (
            db.query(OrdemCorte).filter(OrdemCorte.id_ordem == id_ordem)
            .with_for_update().first()
        )
        if not ordem:
            raise _erro(status.HTTP_404_NOT_FOUND, "Ordem de Corte não encontrada.")

        if ordem.st_ordem != StatusOrdem.PENDENTE:
            raise _erro(
                status.HTTP_400_BAD_REQUEST,
                f"Ordem com status '{ordem.st_ordem}' não pode ser cancelada "
                f"(apenas ordens {StatusOrdem.PENDENTE}).",
            )

        rolo = db.query(Rolo).filter(Rolo.id_rolo == ordem.id_rolo).with_for_update().first()
        if rolo and rolo.st_rolo == StatusRolo.EM_CORTE:
            rolo.st_rolo = StatusRolo.DISPONIVEL

        if ordem.reserva:
            ordem.reserva.st_reserva = StatusReserva.CANCELADA

        ordem.st_ordem = StatusOrdem.CANCELADA
        db.commit()
        db.refresh(ordem)
        return ordem
