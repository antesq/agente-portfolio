"""Importa um CSV exportado da planilha MELI para o portfólio.

Serve para a carga inicial ("bootstrap"): exporte a aba "Contratação Meli" como
CSV (no Google Sheets: Arquivo → Fazer download → .csv) e rode:

    python main.py --importar-csv caminho\\do\\arquivo.csv

O importador casa os cabeçalhos do CSV com os títulos oficiais das colunas
(definidos em portfolio.models.COLUNAS_PLANILHA), então a ordem das colunas
não importa — só os nomes.
"""
from __future__ import annotations

import csv
from pathlib import Path

from portfolio import store
from portfolio.models import COLUNAS_PLANILHA, ProjetoMeli

# Mapa "título da coluna (normalizado)" -> "campo do modelo".
_TITULO_PARA_CAMPO = {
    titulo.strip().lower(): campo for campo, titulo in COLUNAS_PLANILHA
}


def _normalizar(cabecalho: str) -> str:
    return (cabecalho or "").strip().lower()


def _achar_linha_cabecalho(linhas: list[list[str]]) -> int:
    """Descobre qual linha é o cabeçalho.

    A planilha MELI tem uma linha de agrupamento antes do cabeçalho real, então
    não dá para assumir que é a primeira. Escolhemos a linha que mais casa com os
    títulos oficiais das colunas.
    """
    melhor_idx, melhor_pontos = 0, -1
    for i, linha in enumerate(linhas[:10]):  # o cabeçalho está sempre no topo
        pontos = sum(1 for c in linha if _normalizar(c) in _TITULO_PARA_CAMPO)
        if pontos > melhor_pontos:
            melhor_idx, melhor_pontos = i, pontos
    return melhor_idx


def importar_csv(caminho: str | Path) -> dict:
    """Lê o CSV e faz upsert dos projetos no portfólio. Retorna um resumo."""
    caminho = Path(caminho)
    if not caminho.exists():
        raise RuntimeError(f"Arquivo CSV não encontrado: {caminho}")

    # utf-8-sig lida com o BOM que o Google/Excel costuma adicionar.
    with caminho.open("r", encoding="utf-8-sig", newline="") as f:
        linhas = list(csv.reader(f))
    if not linhas:
        raise RuntimeError("CSV vazio.")

    idx_cab = _achar_linha_cabecalho(linhas)
    cabecalho = linhas[idx_cab]
    # Mapeia índice de coluna -> campo do modelo.
    idx_para_campo = {
        j: _TITULO_PARA_CAMPO[_normalizar(col)]
        for j, col in enumerate(cabecalho)
        if _normalizar(col) in _TITULO_PARA_CAMPO
    }
    if not idx_para_campo:
        raise RuntimeError(
            "Nenhuma coluna reconhecida. Confirme que o CSV é da aba 'Contratação Meli'."
        )

    pf = store.carregar()
    novos = atualizados = ignorados = 0
    for linha in linhas[idx_cab + 1:]:
        dados = {
            campo: (linha[j].strip() if j < len(linha) else "")
            for j, campo in idx_para_campo.items()
        }
        codigo = dados.get("projeto", "").strip()
        if not codigo:              # linhas sem código de projeto são ignoradas
            ignorados += 1
            continue
        estado = pf.upsert(ProjetoMeli(**dados))
        novos += estado == "novo"
        atualizados += estado == "atualizado"

    store.salvar(pf)
    return {
        "novos": novos,
        "atualizados": atualizados,
        "linhas_ignoradas": ignorados,
        "total_no_portfolio": len(pf.projetos),
        "colunas_reconhecidas": sorted(set(idx_para_campo.values())),
    }
