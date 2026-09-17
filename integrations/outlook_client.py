"""Leitura de e-mails do Outlook 365 via Microsoft Graph.

Usa MSAL com o fluxo "device code": na primeira execução, o programa mostra
um código e um link (microsoft.com/devicelogin) para você autorizar no
navegador. O token fica em cache (MS_TOKEN_CACHE) para as próximas vezes.

Requer um App Registration no Azure AD com:
  - Permissão delegada: Mail.Read
  - "Allow public client flows" = Yes

Funções principais:
  - ler_emails(...)          -> lista e-mails (caixa inteira ou uma pasta)
  - baixar_anexos(id, dst)   -> baixa os anexos de um e-mail para uma pasta
  - baixar_propostas(...)    -> busca e-mails de proposta e baixa os PDFs/XLSX
"""
from __future__ import annotations

import atexit
import base64
import os
import re
from pathlib import Path
from typing import Any

import msal
import requests

import config

_GRAPH = "https://graph.microsoft.com/v1.0"
# Onde os anexos baixados dos e-mails ficam (fonte para o extrator de propostas).
_PASTA_ANEXOS = config.BASE_DIR / "dados" / "anexos_email"
# Extensões que interessam para propostas.
_EXT_PROPOSTA = (".pdf", ".xlsx", ".xls")


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


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_obter_token()}"}


def ler_emails(
    quantidade: int = 15,
    pasta: str | None = None,
    busca: str | None = None,
    apenas_nao_lidos: bool = False,
    apenas_com_anexo: bool = False,
) -> list[dict[str, Any]]:
    """Lê e-mails da caixa do usuário.

    Args:
        quantidade: quantos e-mails retornar (máx 50 por chamada).
        pasta: None = TODA a caixa (histórico completo). Ou 'inbox', 'sentitems'...
        busca: texto para filtrar (assunto/corpo/remetente) via $search.
        apenas_nao_lidos: se True, filtra por não lidos.
        apenas_com_anexo: se True, retorna só e-mails com anexos.
    """
    headers = _headers()
    base = f"{_GRAPH}/me/messages" if not pasta else f"{_GRAPH}/me/mailFolders/{pasta}/messages"
    params: dict[str, Any] = {
        "$top": min(quantidade, 50),
        "$select": "id,subject,from,receivedDateTime,bodyPreview,isRead,importance,hasAttachments,webLink",
    }
    filtros = []
    if apenas_nao_lidos:
        filtros.append("isRead eq false")
    if apenas_com_anexo:
        filtros.append("hasAttachments eq true")

    if busca:
        # $search não combina com $orderby/$filter no Graph.
        headers["ConsistencyLevel"] = "eventual"
        params["$search"] = f'"{busca}"'
    else:
        params["$orderby"] = "receivedDateTime desc"
        if filtros:
            params["$filter"] = " and ".join(filtros)

    resp = requests.get(base, headers=headers, params=params, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Erro do Graph ({resp.status_code}): {resp.text}")

    emails = []
    for m in resp.json().get("value", []):
        # Com $search não dá para filtrar anexo no servidor; filtramos aqui.
        if apenas_com_anexo and not m.get("hasAttachments"):
            continue
        remetente = (m.get("from") or {}).get("emailAddress", {})
        emails.append({
            "id": m.get("id"),
            "assunto": m.get("subject", "(sem assunto)"),
            "de": remetente.get("name") or remetente.get("address", ""),
            "email_remetente": remetente.get("address", ""),
            "recebido_em": m.get("receivedDateTime", ""),
            "previa": m.get("bodyPreview", ""),
            "lido": m.get("isRead", True),
            "tem_anexo": m.get("hasAttachments", False),
            "importancia": m.get("importance", "normal"),
        })
    return emails


def _slug(texto: str, limite: int = 60) -> str:
    """Transforma um assunto em nome de pasta seguro."""
    limpo = re.sub(r"[^\w\-. ]+", "_", texto).strip().strip(".")
    return (limpo[:limite] or "email").rstrip()


def baixar_anexos(message_id: str, destino: str | Path | None = None,
                  apenas_documentos: bool = True) -> dict[str, Any]:
    """Baixa os anexos de um e-mail para uma pasta local.

    Args:
        message_id: id do e-mail (vem de ler_emails).
        destino: pasta onde salvar. Se None, cria uma subpasta em dados/anexos_email.
        apenas_documentos: se True, baixa só PDF/XLSX (ignora imagens inline etc.).

    Returns:
        {'pasta': ..., 'arquivos': [...], 'assunto': ...}
    """
    headers = _headers()
    # Metadados do e-mail (para nomear a pasta pelo assunto).
    meta = requests.get(
        f"{_GRAPH}/me/messages/{message_id}",
        headers=headers, params={"$select": "subject,receivedDateTime"}, timeout=30,
    )
    assunto = meta.json().get("subject", "email") if meta.status_code == 200 else "email"

    if destino is None:
        destino = _PASTA_ANEXOS / _slug(assunto)
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)

    resp = requests.get(
        f"{_GRAPH}/me/messages/{message_id}/attachments", headers=headers, timeout=60,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Erro ao listar anexos ({resp.status_code}): {resp.text}")

    salvos: list[str] = []
    for att in resp.json().get("value", []):
        if att.get("@odata.type") != "#microsoft.graph.fileAttachment":
            continue  # ignora anexos de item/referência
        nome = att.get("name", "anexo")
        if apenas_documentos and not nome.lower().endswith(_EXT_PROPOSTA):
            continue
        conteudo_b64 = att.get("contentBytes")
        if not conteudo_b64:  # às vezes vem só na leitura individual
            ind = requests.get(
                f"{_GRAPH}/me/messages/{message_id}/attachments/{att['id']}",
                headers=headers, timeout=60,
            )
            conteudo_b64 = ind.json().get("contentBytes") if ind.status_code == 200 else None
        if not conteudo_b64:
            continue
        caminho = destino / nome
        caminho.write_bytes(base64.b64decode(conteudo_b64))
        salvos.append(str(caminho))

    return {"pasta": str(destino), "arquivos": salvos, "assunto": assunto}


def baixar_propostas(
    busca: str = "proposta",
    max_emails: int = 10,
    pasta: str | None = None,
) -> list[dict[str, Any]]:
    """Busca e-mails de proposta (com anexo) e baixa os PDFs/XLSX de cada um.

    Cada e-mail vira uma subpasta em dados/anexos_email. Depois use
    documentos.extrair_dados_proposta(pasta) em cada pasta retornada.

    Returns:
        Lista de {'assunto', 'de', 'recebido_em', 'pasta', 'arquivos'} — só os
        e-mails que realmente tinham documentos anexados.
    """
    emails = ler_emails(quantidade=max_emails, pasta=pasta, busca=busca,
                        apenas_com_anexo=True)
    resultado = []
    for e in emails:
        try:
            baixado = baixar_anexos(e["id"])
        except Exception as ex:
            baixado = {"pasta": "", "arquivos": [], "erro": str(ex)}
        if baixado.get("arquivos"):
            resultado.append({
                "assunto": e["assunto"],
                "de": e["de"],
                "recebido_em": e["recebido_em"],
                "pasta": baixado["pasta"],
                "arquivos": [Path(a).name for a in baixado["arquivos"]],
            })
    return resultado
