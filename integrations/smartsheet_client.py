"""Integração com o Smartsheet usando o SDK oficial.

Fornece funções simples que o agente chama como ferramentas:
  - listar_planilhas(): quais sheets existem na conta.
  - ler_planilha(id_ou_nome): conteúdo de uma sheet como linhas/colunas.
"""
from __future__ import annotations

from typing import Any

import smartsheet

import config


def _cliente() -> smartsheet.Smartsheet:
    if not config.SMARTSHEET_ACCESS_TOKEN:
        raise RuntimeError(
            "SMARTSHEET_ACCESS_TOKEN não configurado. Gere um token em "
            "Smartsheet > Account > Personal Settings > API Access e coloque no .env."
        )
    ss = smartsheet.Smartsheet(config.SMARTSHEET_ACCESS_TOKEN)
    ss.errors_as_exceptions(True)  # falhas viram exceções em vez de retorno silencioso
    return ss


def listar_planilhas() -> list[dict[str, Any]]:
    """Retorna [{id, nome, modificado_em}] de todas as sheets acessíveis."""
    ss = _cliente()
    resposta = ss.Sheets.list_sheets(include_all=True)
    return [
        {
            "id": s.id,
            "nome": s.name,
            "modificado_em": str(s.modified_at) if s.modified_at else "",
        }
        for s in resposta.data
    ]


def _resolver_id(ss: smartsheet.Smartsheet, id_ou_nome: str | int) -> int:
    """Aceita um ID numérico ou o nome da sheet e devolve o ID."""
    # Se já for um número (ou string numérica), usa direto.
    try:
        return int(id_ou_nome)
    except (TypeError, ValueError):
        pass
    alvo = str(id_ou_nome).strip().lower()
    for s in ss.Sheets.list_sheets(include_all=True).data:
        if s.name.strip().lower() == alvo:
            return s.id
    raise RuntimeError(f"Planilha '{id_ou_nome}' não encontrada no Smartsheet.")


def ler_planilha(id_ou_nome: str | int, max_linhas: int = 200) -> dict[str, Any]:
    """Lê uma sheet e devolve colunas + linhas (limitado a max_linhas)."""
    ss = _cliente()
    sheet_id = _resolver_id(ss, id_ou_nome)
    sheet = ss.Sheets.get_sheet(sheet_id)

    colunas = [c.title for c in sheet.columns]
    mapa_col = {c.id: c.title for c in sheet.columns}

    linhas: list[dict[str, Any]] = []
    for row in sheet.rows[:max_linhas]:
        registro: dict[str, Any] = {}
        for cell in row.cells:
            titulo = mapa_col.get(cell.column_id, str(cell.column_id))
            # display_value é o texto visível; value é o valor bruto.
            registro[titulo] = cell.display_value if cell.display_value is not None else cell.value
        linhas.append(registro)

    return {
        "nome": sheet.name,
        "id": sheet.id,
        "colunas": colunas,
        "total_linhas": sheet.total_row_count,
        "linhas": linhas,
        "truncado": sheet.total_row_count > max_linhas,
    }
