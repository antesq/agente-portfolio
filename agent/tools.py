"""Ferramentas que o Claude pode chamar (definições JSON + execução).

A `CaixaDeFerramentas` guarda o portfólio em memória durante a sessão do agente,
executa as ferramentas e persiste as mudanças no store JSON.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import config
from integrations import documentos, outlook_client, smartsheet_client, whatsapp_reader
from portfolio import excel_builder, store
from portfolio.models import Acao, Portfolio, ProjetoMeli, _so_campos

# --------------------------------------------------------------------------
# Definições das ferramentas (esquema enviado ao Claude).
# --------------------------------------------------------------------------
DEFINICOES: list[dict[str, Any]] = [
    {
        "name": "listar_planilhas_smartsheet",
        "description": "Lista as planilhas (sheets) disponíveis na conta do Smartsheet.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "ler_planilha_smartsheet",
        "description": "Lê o conteúdo de uma planilha do Smartsheet (colunas e linhas).",
        "input_schema": {
            "type": "object",
            "properties": {
                "id_ou_nome": {"type": "string", "description": "ID numérico ou nome exato da sheet."},
                "max_linhas": {"type": "integer", "description": "Máximo de linhas (padrão 200)."},
            },
            "required": ["id_ou_nome"],
        },
    },
    {
        "name": "ler_emails_outlook",
        "description": (
            "Lê e-mails recentes do Outlook 365. Use 'busca' para achar propostas "
            "(ex.: 'proposta técnica', 'PPT-BR', nome da unidade ou cidade)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "quantidade": {"type": "integer", "description": "Quantos e-mails (padrão 15, máx 50)."},
                "pasta": {"type": "string", "description": "inbox (padrão), sentitems, etc."},
                "busca": {"type": "string", "description": "Texto para filtrar assunto/corpo/remetente."},
                "apenas_nao_lidos": {"type": "boolean"},
            },
        },
    },
    {
        "name": "listar_documentos_pasta",
        "description": "Lista PDFs/planilhas de uma pasta de projeto no drive (ex.: pasta no Z:).",
        "input_schema": {
            "type": "object",
            "properties": {"pasta": {"type": "string", "description": "Caminho completo da pasta."}},
            "required": ["pasta"],
        },
    },
    {
        "name": "ler_documentos_proposta",
        "description": (
            "Lê os documentos de proposta (PDF técnico + relatórios de custo) de uma pasta "
            "de projeto e extrai: número da proposta técnica, escopo, unidade, cidade e custos."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"pasta": {"type": "string", "description": "Caminho completo da pasta do projeto."}},
            "required": ["pasta"],
        },
    },
    {
        "name": "ler_whatsapp",
        "description": (
            "Captura a conversa ABERTA no WhatsApp Desktop (na tela) e transcreve as mensagens. "
            "Só funciona na máquina local com o app aberto na conversa desejada."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "contato": {"type": "string", "description": "Nome da conversa (apenas rótulo)."},
                "contexto": {"type": "string", "description": "O que procurar (ex.: 'prazos e pendências')."},
            },
        },
    },
    {
        "name": "ver_portfolio",
        "description": "Mostra o estado atual do portfólio em memória (projetos e ações).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "atualizar_projetos",
        "description": (
            "Insere ou atualiza projetos no portfólio (upsert pelo código do projeto). "
            "Só preencha os campos que você tem certeza; campos vazios não sobrescrevem dados existentes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "projetos": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "projeto": {"type": "string", "description": "Código do projeto (obrigatório)."},
                            "unidade_meli": {"type": "string"},
                            "pm_meli": {"type": "string"},
                            "aplicacoes_install": {"type": "string"},
                            "cidade": {"type": "string"},
                            "escopo_atual": {"type": "string"},
                            "layout_em_proposta": {"type": "string"},
                            "proposta_tecnica_contratada": {"type": "string"},
                            "prazo_fr_contratado": {"type": "string"},
                            "recebimento_layout_meli": {"type": "string"},
                            "data_limite_recebimento_layout": {"type": "string"},
                            "layout_enviado_aprovacao": {"type": "string"},
                            "data_limite_envio_layout": {"type": "string"},
                            "layout_aprovado": {"type": "string"},
                            "data_limite_aprovacao_layout": {"type": "string"},
                            "carregamento_install": {"type": "string"},
                            "fr_install": {"type": "string"},
                            "status_geral": {"type": "string"},
                            "motivo_bloqueio": {"type": "string"},
                            "responsavel_pendencia": {"type": "string"},
                            "observacoes": {"type": "string"},
                        },
                        "required": ["projeto"],
                    },
                }
            },
            "required": ["projetos"],
        },
    },
    {
        "name": "registrar_acoes",
        "description": "Adiciona itens à lista de ações do portfólio.",
        "input_schema": {
            "type": "object",
            "properties": {
                "acoes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "acao": {"type": "string"},
                            "projeto": {"type": "string"},
                            "origem": {"type": "string"},
                            "responsavel": {"type": "string"},
                            "prazo": {"type": "string"},
                            "prioridade": {"type": "string", "enum": ["Baixa", "Média", "Alta", "Urgente"]},
                            "status": {"type": "string"},
                        },
                        "required": ["acao"],
                    },
                }
            },
            "required": ["acoes"],
        },
    },
    {
        "name": "exportar_planilha",
        "description": "Gera o arquivo Excel (.xlsx) do portfólio no formato MELI e retorna o caminho.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


class CaixaDeFerramentas:
    """Estado + execução das ferramentas durante uma sessão do agente."""

    def __init__(self) -> None:
        self.portfolio: Portfolio = store.carregar()

    # -- despacho principal -------------------------------------------------
    def executar(self, nome: str, entrada: dict[str, Any]) -> str:
        """Executa a ferramenta e devolve o resultado como texto (JSON quando faz sentido)."""
        try:
            metodo = getattr(self, f"_ft_{nome}", None)
            if metodo is None:
                return f"Erro: ferramenta desconhecida '{nome}'."
            return metodo(entrada)
        except Exception as e:  # devolve o erro ao Claude em vez de derrubar o loop
            return f"Erro ao executar '{nome}': {e}"

    # -- implementações -----------------------------------------------------
    def _ft_listar_planilhas_smartsheet(self, _: dict) -> str:
        return _json(smartsheet_client.listar_planilhas())

    def _ft_ler_planilha_smartsheet(self, e: dict) -> str:
        return _json(smartsheet_client.ler_planilha(e["id_ou_nome"], e.get("max_linhas", 200)))

    def _ft_ler_emails_outlook(self, e: dict) -> str:
        return _json(outlook_client.ler_emails(
            quantidade=e.get("quantidade", 15),
            pasta=e.get("pasta", "inbox"),
            busca=e.get("busca"),
            apenas_nao_lidos=e.get("apenas_nao_lidos", False),
        ))

    def _ft_listar_documentos_pasta(self, e: dict) -> str:
        return _json(documentos.listar_documentos(e["pasta"]))

    def _ft_ler_documentos_proposta(self, e: dict) -> str:
        return _json(documentos.extrair_dados_proposta(e["pasta"]))

    def _ft_ler_whatsapp(self, e: dict) -> str:
        return _json(whatsapp_reader.ler_conversa(e.get("contato", ""), e.get("contexto", "")))

    def _ft_ver_portfolio(self, _: dict) -> str:
        resumo = {
            "total_projetos": len(self.portfolio.projetos),
            "projetos": [p.resumo_curto() for p in self.portfolio.projetos],
            "total_acoes": len(self.portfolio.acoes),
        }
        return _json(resumo)

    def _ft_atualizar_projetos(self, e: dict) -> str:
        resultados = []
        for p in e.get("projetos", []):
            projeto = ProjetoMeli(**_so_campos(p, ProjetoMeli))
            estado = self.portfolio.upsert(projeto)
            resultados.append(f"{projeto.projeto}: {estado}")
        store.salvar(self.portfolio)
        return "Projetos processados -> " + "; ".join(resultados)

    def _ft_registrar_acoes(self, e: dict) -> str:
        for a in e.get("acoes", []):
            self.portfolio.acoes.append(Acao(**_so_campos(a, Acao)))
        store.salvar(self.portfolio)
        return f"{len(e.get('acoes', []))} ação(ões) registrada(s). Total agora: {len(self.portfolio.acoes)}."

    def _ft_exportar_planilha(self, _: dict) -> str:
        caminho = excel_builder.gerar_planilha(self.portfolio, config.OUTPUT_DIR)
        return f"Planilha gerada em: {caminho}"


def _json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)
