"""Notificações no Teams via webhook (Workflow do canal).

Usa a URL gerada pelo Workflow do Teams "Post to a channel when a webhook
request is received". Esse fluxo espera um Adaptive Card dentro de um envelope
{type: message, attachments: [...]}.

Não precisa de app do Azure nem de permissão do Graph — só da URL do webhook,
que fica em TEAMS_WEBHOOK_URL (.env).
"""
from __future__ import annotations

from typing import Any

import requests

import config


def _postar_card(card: dict[str, Any]) -> dict[str, Any]:
    """Envia um Adaptive Card para o webhook do canal."""
    if not config.TEAMS_WEBHOOK_URL:
        raise RuntimeError(
            "TEAMS_WEBHOOK_URL não configurado. Crie um Workflow no canal "
            "('Post to a channel when a webhook request is received'), copie a URL "
            "gerada e coloque no .env."
        )
    envelope = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": card,
            }
        ],
    }
    resp = requests.post(config.TEAMS_WEBHOOK_URL, json=envelope, timeout=30)
    # O Workflow costuma responder 202 (aceito). Aceitamos 200-299.
    if not (200 <= resp.status_code < 300):
        raise RuntimeError(f"Falha ao postar no Teams ({resp.status_code}): {resp.text[:300]}")
    return {"status": resp.status_code, "ok": True}


def publicar_card(card: dict[str, Any]) -> dict[str, Any]:
    """Publica um Adaptive Card já montado no canal."""
    return _postar_card(card)


def enviar_mensagem(texto: str, titulo: str = "Agente de Portfólio") -> dict[str, Any]:
    """Posta uma mensagem de texto simples no canal."""
    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": titulo, "weight": "Bolder", "size": "Medium"},
            {"type": "TextBlock", "text": texto, "wrap": True},
        ],
    }
    return _postar_card(card)


def notificar_mudanca_data(
    projeto: str,
    data_antiga: str,
    data_nova: str,
    unidade: str = "",
    cidade: str = "",
    campo: str = "Carregamento Install",
    responsavel: str = "",
    observacao: str = "",
) -> dict[str, Any]:
    """Notifica no Teams uma mudança de data (ex.: carregamento) de um projeto.

    Monta um cartão com destaque para a data antiga → nova.
    """
    titulo = f"⚠️ Mudança de data — Projeto {projeto}"
    subtitulo_partes = [p for p in [unidade, cidade] if p]
    subtitulo = " · ".join(subtitulo_partes)

    fatos = [
        {"title": "Campo:", "value": campo},
        {"title": "De:", "value": data_antiga or "—"},
        {"title": "Para:", "value": data_nova or "—"},
    ]
    if responsavel:
        fatos.append({"title": "Responsável:", "value": responsavel})

    body: list[dict[str, Any]] = [
        {"type": "TextBlock", "text": titulo, "weight": "Bolder", "size": "Medium", "color": "Warning"},
    ]
    if subtitulo:
        body.append({"type": "TextBlock", "text": subtitulo, "isSubtle": True, "spacing": "None", "wrap": True})
    body.append({"type": "FactSet", "facts": fatos})
    if observacao:
        body.append({"type": "TextBlock", "text": observacao, "wrap": True, "spacing": "Small"})

    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": body,
    }
    return _postar_card(card)
