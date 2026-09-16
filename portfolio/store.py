"""Persistência do portfólio de trabalho em JSON.

Na Fase 1 (agente CLI local) o portfólio vive em um arquivo JSON. Quando o
portal web entrar (Fase 2), este módulo pode ser trocado por um banco (SQLite/
Postgres) mantendo a mesma interface carregar()/salvar().
"""
from __future__ import annotations

import json
from pathlib import Path

from .models import Portfolio, portfolio_de_dict, portfolio_para_dict

_ARQUIVO_PADRAO = Path(__file__).resolve().parent.parent / "dados" / "portfolio.json"


def carregar(caminho: Path | None = None) -> Portfolio:
    """Carrega o portfólio do disco. Se não existir, retorna um vazio."""
    caminho = caminho or _ARQUIVO_PADRAO
    if not caminho.exists():
        return Portfolio()
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return portfolio_de_dict(dados)


def salvar(portfolio: Portfolio, caminho: Path | None = None) -> Path:
    """Grava o portfólio no disco (cria a pasta se necessário)."""
    caminho = caminho or _ARQUIVO_PADRAO
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(portfolio_para_dict(portfolio), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return caminho
