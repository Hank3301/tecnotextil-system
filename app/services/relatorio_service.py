"""Serviço de relatórios gerenciais para o TecnoTêxtil.

Endpoints restritos ao perfil GERENTE.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case

from app.models.models import (
    Rolo, Tecido, LoteTingimento, ReservaTemporaria, OrdemCorte, MapeamentoDefeito
)
from app.utils import to_decimal


class RelatorioService:

    @staticmethod
    def relatorio_retalhos(db: Session) -> dict:
        """
        Retorna métricas do estoque de retalhos (rolos com fl_retalho = True).

        Inclui:
        - Quantidade total de rolos retalho
        - Metragem acumulada total em metros
        - Distribuição por tecido/lote
        """
        # Query base para rolos retalho
        query = db.query(Rolo).filter(Rolo.fl_retalho == True)

        # Contagem total
        total_rolos = query.count()

        # Metragem total
        metragem_total = query.with_entities(func.sum(Rolo.qt_metragem_atual)).scalar() or Decimal('0')

        # Distribuição por tecido/lote
        distribuicao = (
            db.query(
                Tecido.cd_tecido,
                Tecido.nm_tecido,
                LoteTingimento.cd_partida,
                LoteTingimento.ds_tonalidade_cor,
                func.count(Rolo.id_rolo).label('qtd_rolos'),
                func.sum(Rolo.qt_metragem_atual).label('metragem_total')
            )
            .join(LoteTingimento, Rolo.id_lote == LoteTingimento.id_lote)
            .join(Tecido, LoteTingimento.id_tecido == Tecido.id_tecido)
            .filter(Rolo.fl_retalho == True)
            .group_by(
                Tecido.cd_tecido, Tecido.nm_tecido,
                LoteTingimento.cd_partida, LoteTingimento.ds_tonalidade_cor
            )
            .all()
        )

        dist_lista = [
            {
                "cd_tecido": d.cd_tecido,
                "nm_tecido": d.nm_tecido,
                "cd_partida": d.cd_partida,
                "ds_tonalidade_cor": d.ds_tonalidade_cor,
                "qtd_rolos": d.qtd_rolos,
                "metragem_total": float(to_decimal(d.metragem_total))
            }
            for d in distribuicao
        ]

        return {
            "total_rolos_retalho": total_rolos,
            "metragem_total_metros": float(to_decimal(metragem_total)),
            "distribuicao_por_tecido_lote": dist_lista
        }

    @staticmethod
    def relatorio_perdas(db: Session) -> dict:
        """
        Retorna consolidado de desperdícios das ordens de corte concluídas.

        Inclui:
        - Soma total da metragem perdida
        - Contagem de ordens com fl_divergencia_perda = True
        - Detalhamento por partida/lote
        """
        # Query base para ordens concluídas com perda apurada
        query = db.query(OrdemCorte).filter(
            and_(
                OrdemCorte.st_ordem == "CONCLUIDA",
                OrdemCorte.qt_perda_apurada.isnot(None)
            )
        )

        # Soma total de perda apurada
        perda_total = query.with_entities(func.sum(OrdemCorte.qt_perda_apurada)).scalar() or Decimal('0')

        # Contagem de ordens com divergência
        ordens_com_divergencia = query.filter(OrdemCorte.fl_divergencia_perda == True).count()

        # Total de ordens concluídas
        total_ordens = query.count()

        # Detalhamento por partida/lote
        detalhe = (
            db.query(
                Tecido.cd_tecido,
                Tecido.nm_tecido,
                LoteTingimento.cd_partida,
                LoteTingimento.ds_tonalidade_cor,
                func.count(OrdemCorte.id_ordem).label('qtd_ordens'),
                func.sum(OrdemCorte.qt_perda_apurada).label('perda_total'),
                func.sum(OrdemCorte.qt_perda_justificada).label('perda_justificada'),
                func.sum(
                    func.coalesce(OrdemCorte.qt_perda_apurada, 0) - func.coalesce(OrdemCorte.qt_perda_justificada, 0)
                ).label('perda_nao_justificada'),
                func.sum(
                    case(
                        (OrdemCorte.fl_divergencia_perda == True, 1),
                        else_=0
                    )
                ).label('qtd_divergencias')
            )
            .join(Rolo, OrdemCorte.id_rolo == Rolo.id_rolo)
            .join(LoteTingimento, Rolo.id_lote == LoteTingimento.id_lote)
            .join(Tecido, LoteTingimento.id_tecido == Tecido.id_tecido)
            .filter(
                and_(
                    OrdemCorte.st_ordem == "CONCLUIDA",
                    OrdemCorte.qt_perda_apurada.isnot(None)
                )
            )
            .group_by(
                Tecido.cd_tecido, Tecido.nm_tecido,
                LoteTingimento.cd_partida, LoteTingimento.ds_tonalidade_cor
            )
            .all()
        )

        detalhe_lista = [
            {
                "cd_tecido": d.cd_tecido,
                "nm_tecido": d.nm_tecido,
                "cd_partida": d.cd_partida,
                "ds_tonalidade_cor": d.ds_tonalidade_cor,
                "qtd_ordens": d.qtd_ordens,
                "perda_total_metros": float(to_decimal(d.perda_total)),
                "perda_justificada_metros": float(to_decimal(d.perda_justificada)) if d.perda_justificada else 0.0,
                "perda_nao_justificada_metros": float(to_decimal(d.perda_nao_justificada)) if d.perda_nao_justificada else 0.0,
                "qtd_ordens_com_divergencia": d.qtd_divergencias or 0
            }
            for d in detalhe
        ]

        return {
            "total_ordens_concluidas": total_ordens,
            "perda_total_metros": float(to_decimal(perda_total)),
            "ordens_com_divergencia": ordens_com_divergencia,
            "detalhamento_por_partida_lote": detalhe_lista
        }

    @staticmethod
    def historico_rolo(db: Session, id_rolo: int) -> Optional[dict]:
        """
        Retorna a linha do tempo completa de um rolo.

        Inclui:
        - Dados cadastrais do rolo
        - Defeitos mapeados
        - Histórico de reservas com datas/status
        - Todas as ordens de corte executadas nele
        """
        # Buscar rolo com relacionamentos
        rolo = (
            db.query(Rolo)
            .filter(Rolo.id_rolo == id_rolo)
            .first()
        )

        if not rolo:
            return None

        # Dados cadastrais
        dados_cadastrais = {
            "id_rolo": rolo.id_rolo,
            "cd_barras": rolo.cd_barras,
            "qt_metragem_inicial": float(to_decimal(rolo.qt_metragem_inicial)),
            "qt_metragem_atual": float(to_decimal(rolo.qt_metragem_atual)),
            "ds_localizacao": rolo.ds_localizacao,
            "st_rolo": rolo.st_rolo,
            "fl_retalho": rolo.fl_retalho,
            "lote": {
                "id_lote": rolo.lote.id_lote,
                "cd_partida": rolo.lote.cd_partida,
                "ds_tonalidade_cor": rolo.lote.ds_tonalidade_cor,
                "dt_fabricacao": rolo.lote.dt_fabricacao.isoformat() if rolo.lote.dt_fabricacao else None,
                "tecido": {
                    "id_tecido": rolo.lote.tecido.id_tecido,
                    "cd_tecido": rolo.lote.tecido.cd_tecido,
                    "nm_tecido": rolo.lote.tecido.nm_tecido,
                    "ds_composicao": rolo.lote.tecido.ds_composicao,
                    "vl_largura_metros": float(to_decimal(rolo.lote.tecido.vl_largura_metros)),
                    "vl_gramatura": float(to_decimal(rolo.lote.tecido.vl_gramatura)),
                    "vl_preco_metro": float(to_decimal(rolo.lote.tecido.vl_preco_metro)),
                }
            }
        }

        # Defeitos mapeados
        defeitos = [
            {
                "id_defeito": d.id_defeito,
                "qt_metro_inicio": float(to_decimal(d.qt_metro_inicio)),
                "qt_metro_fim": float(to_decimal(d.qt_metro_fim)),
                "qt_metros_afetados": float(d.qt_metros_afetados),
                "ds_defeito": d.ds_defeito
            }
            for d in sorted(rolo.defeitos, key=lambda x: x.qt_metro_inicio)
        ]

        # Histórico de reservas
        reservas = [
            {
                "id_reserva": r.id_reserva,
                "qt_metragem_reservada": float(to_decimal(r.qt_metragem_reservada)),
                "dt_criacao": r.dt_criacao.isoformat() if r.dt_criacao else None,
                "dt_expiracao": r.dt_expiracao.isoformat() if r.dt_expiracao else None,
                "st_reserva": r.st_reserva,
                "tem_ordem_corte": r.ordem_corte is not None
            }
            for r in sorted(rolo.reservas, key=lambda x: x.dt_criacao, reverse=True)
        ]

        # Ordens de corte
        ordens = [
            {
                "id_ordem": o.id_ordem,
                "id_reserva": o.id_reserva,
                "id_usuario_cortador": o.id_usuario_cortador,
                "dt_emissao": o.dt_emissao.isoformat() if o.dt_emissao else None,
                "dt_execucao": o.dt_execucao.isoformat() if o.dt_execucao else None,
                "qt_metragem_solicitada": float(to_decimal(o.qt_metragem_solicitada)),
                "qt_sobra_informada": float(to_decimal(o.qt_sobra_informada)) if o.qt_sobra_informada else None,
                "qt_perda_apurada": float(to_decimal(o.qt_perda_apurada)) if o.qt_perda_apurada else None,
                "qt_perda_justificada": float(to_decimal(o.qt_perda_justificada)) if o.qt_perda_justificada else None,
                "qt_perda_nao_justificada": float(to_decimal(o.qt_perda_apurada) - to_decimal(o.qt_perda_justificada)) if o.qt_perda_apurada and o.qt_perda_justificada else None,
                "fl_divergencia_perda": o.fl_divergencia_perda,
                "st_ordem": o.st_ordem
            }
            for o in sorted(rolo.ordens_corte, key=lambda x: x.dt_emissao, reverse=True)
        ]

        return {
            "rolo": dados_cadastrais,
            "defeitos": defeitos,
            "reservas": reservas,
            "ordens_corte": ordens
        }