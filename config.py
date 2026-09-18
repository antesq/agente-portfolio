"""Configuração central do agente de portfólio.

Carrega variáveis do arquivo .env e expõe constantes usadas pelo resto do
projeto. Nada de segredo é hard-coded aqui — tudo vem do ambiente.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Carrega o .env que fica ao lado deste arquivo.
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# --- Claude API -----------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5")

# --- Smartsheet -----------------------------------------------------------
SMARTSHEET_ACCESS_TOKEN = os.getenv("SMARTSHEET_ACCESS_TOKEN", "")

# --- Microsoft Graph / Outlook -------------------------------------------
MS_CLIENT_ID = os.getenv("MS_CLIENT_ID", "")
MS_TENANT_ID = os.getenv("MS_TENANT_ID", "common")
MS_TOKEN_CACHE = os.getenv("MS_TOKEN_CACHE", ".ms_token_cache.bin")
MS_SCOPES = ["Mail.Read"]  # permissões delegadas solicitadas ao Graph
# "interactive" = login pelo navegador (recomendado; usa sua sessão/MFA normal).
# "device"      = login por código (microsoft.com/devicelogin) — pode ser bloqueado.
MS_AUTH_MODE = os.getenv("MS_AUTH_MODE", "interactive")

# --- Teams ----------------------------------------------------------------
# URL do webhook (Workflow "Post to a channel when a webhook request is
# received") do canal onde as notificações serão postadas.
TEAMS_WEBHOOK_URL = os.getenv("TEAMS_WEBHOOK_URL", "")

# --- WhatsApp -------------------------------------------------------------
WHATSAPP_WINDOW_TITLE = os.getenv("WHATSAPP_WINDOW_TITLE", "WhatsApp")

# --- Saída ----------------------------------------------------------------
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", BASE_DIR / "saida"))


# Valores de exemplo do .env.example que NÃO contam como configurados.
_PLACEHOLDERS = {"sk-ant-...", ""}


def configurado(valor: str) -> bool:
    """True se o valor foi realmente preenchido (não vazio nem placeholder)."""
    return valor.strip() not in _PLACEHOLDERS


def validar(requeridos: list[str]) -> list[str]:
    """Retorna a lista de variáveis obrigatórias que estão vazias/placeholder.

    Use no início de cada comando para dar uma mensagem de erro amigável
    em vez de estourar uma exceção obscura lá na frente.
    """
    mapa = {
        "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
        "SMARTSHEET_ACCESS_TOKEN": SMARTSHEET_ACCESS_TOKEN,
        "MS_CLIENT_ID": MS_CLIENT_ID,
    }
    return [nome for nome in requeridos if not configurado(mapa.get(nome, ""))]
