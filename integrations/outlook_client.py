"""Leitura de e-mails do Outlook 365 via Microsoft Graph.

Usa MSAL com o fluxo "device code": na primeira execução, o programa mostra
um código e um link (microsoft.com/devicelogin) para você autorizar no
navegador. O token fica em cache (MS_TOKEN_CACHE) para as próximas vezes.

Requer um App Registration no Azure AD com:
  - Permissão delegada: Mail.Read
  - "Allow public client flows" = Yes
"""
from __future__ import annotations

import atexit
import os
from typing import Any

import msal
import requests

import config

_GRAPH = "https://graph.microsoft.com/v1.0"


def _cache_tokens() -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()
    caminho = config.MS_TOKEN_CACHE
    if os.path.exists(caminho):
        cache.deserialize(open(caminho, "r", encoding="utf-8").read())
    # Salva o cache ao encerrar o programa, se houve mudança.
    atexit.register(
        lambda: open(caminho, "w", encoding="utf-8").write(cache.serialize())
        if cache.has_state_changed else None
    )
    return cache


def _obter_token() -> str:
    if not config.MS_CLIENT_ID:
        raise RuntimeError(
            "MS_CLIENT_ID não configurado. Registre um app no Azure AD (Mail.Read, "
            "public client flows = Yes) e coloque o Application (client) ID no .env."
        )
    autoridade = f"https://login.microsoftonline.com/{config.MS_TENANT_ID}"
    cache = _cache_tokens()
    app = msal.PublicClientApplication(
        config.MS_CLIENT_ID, authority=autoridade, token_cache=cache
    )

    # 1) Tenta reaproveitar um token em cache (silencioso).
    contas = app.get_accounts()
    if contas:
        resultado = app.acquire_token_silent(config.MS_SCOPES, account=contas[0])
        if resultado and "access_token" in resultado:
            return resultado["access_token"]

    # 2) Sem token válido: inicia o device code flow.
    flow = app.initiate_device_flow(scopes=config.MS_SCOPES)
    if "user_code" not in flow:
        raise RuntimeError(f"Falha ao iniciar login Microsoft: {flow}")
    print("\n" + "=" * 60)
    print("AUTORIZAÇÃO MICROSOFT NECESSÁRIA")
    print(flow["message"])  # ex.: acesse microsoft.com/devicelogin e digite XXXX
    print("=" * 60 + "\n")
    resultado = app.acquire_token_by_device_flow(flow)  # bloqueia até você autorizar

    if "access_token" not in resultado:
        raise RuntimeError(
            f"Login Microsoft falhou: {resultado.get('error_description', resultado)}"
        )
    return resultado["access_token"]


def ler_emails(
    quantidade: int = 15,
    pasta: str = "inbox",
    busca: str | None = None,
    apenas_nao_lidos: bool = False,
) -> list[dict[str, Any]]:
    """Lê e-mails recentes da caixa do usuário.

    Args:
        quantidade: quantos e-mails retornar (máx recomendado 50).
        pasta: 'inbox', 'sentitems', 'drafts' ou o nome de uma pasta.
        busca: texto para filtrar (assunto/corpo/remetente) via $search.
        apenas_nao_lidos: se True, filtra por não lidos.
    """
    token = _obter_token()
    headers = {"Authorization": f"Bearer {token}"}

    url = f"{_GRAPH}/me/mailFolders/{pasta}/messages"
    params: dict[str, Any] = {
        "$top": min(quantidade, 50),
        "$select": "subject,from,receivedDateTime,bodyPreview,isRead,importance,webLink",
        "$orderby": "receivedDateTime desc",
    }
    if busca:
        # $search não combina com $orderby no Graph; removemos o orderby.
        params.pop("$orderby")
        headers["ConsistencyLevel"] = "eventual"
        params["$search"] = f'"{busca}"'
    if apenas_nao_lidos and not busca:
        params["$filter"] = "isRead eq false"

    resp = requests.get(url, headers=headers, params=params, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Erro do Graph ({resp.status_code}): {resp.text}")

    emails = []
    for m in resp.json().get("value", []):
        remetente = (m.get("from") or {}).get("emailAddress", {})
        emails.append(
            {
                "assunto": m.get("subject", "(sem assunto)"),
                "de": remetente.get("name") or remetente.get("address", ""),
                "email_remetente": remetente.get("address", ""),
                "recebido_em": m.get("receivedDateTime", ""),
                "previa": m.get("bodyPreview", ""),
                "lido": m.get("isRead", True),
                "importancia": m.get("importance", "normal"),
            }
        )
    return emails
