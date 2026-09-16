"""Leitura do WhatsApp Desktop pela tela (Windows).

Como não usamos API não-oficial (para não arriscar banimento), a estratégia é:
  1. Localizar a janela do WhatsApp Desktop já aberta.
  2. Tirar um print da janela.
  3. Mandar a imagem para a visão do Claude, que transcreve as mensagens
     visíveis em texto estruturado.

IMPORTANTE: abra a conversa desejada no WhatsApp Desktop ANTES de rodar.
O programa lê o que estiver visível na tela naquele momento.
"""
from __future__ import annotations

import base64
import io
import time
from typing import Any

import anthropic

import config


def _capturar_janela_whatsapp() -> bytes:
    """Traz a janela do WhatsApp para frente e captura um PNG dela.

    Retorna os bytes PNG. Levanta RuntimeError com mensagem clara se a janela
    não for encontrada.
    """
    # Imports locais: essas libs só existem/funcionam bem no Windows.
    import mss
    import pygetwindow as gw
    from PIL import Image

    titulo = config.WHATSAPP_WINDOW_TITLE
    janelas = [j for j in gw.getWindowsWithTitle(titulo) if j.title]
    if not janelas:
        raise RuntimeError(
            f"Janela do WhatsApp (título contendo '{titulo}') não encontrada. "
            "Abra o WhatsApp Desktop e a conversa desejada antes de rodar. "
            "Se o título for diferente, ajuste WHATSAPP_WINDOW_TITLE no .env."
        )
    win = janelas[0]

    # Restaura se minimizada e traz para frente.
    if win.isMinimized:
        win.restore()
    try:
        win.activate()
    except Exception:
        # activate() às vezes falha por permissão do Windows; seguimos mesmo assim.
        pass
    time.sleep(0.6)  # dá tempo da janela renderizar em primeiro plano

    # Recorta a região da janela (mss captura por coordenadas do monitor).
    regiao = {"left": win.left, "top": win.top, "width": win.width, "height": win.height}
    if regiao["width"] <= 0 or regiao["height"] <= 0:
        raise RuntimeError("Janela do WhatsApp com tamanho inválido (minimizada?).")

    with mss.mss() as sct:
        shot = sct.grab(regiao)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def ler_conversa(contato: str = "", contexto: str = "") -> dict[str, Any]:
    """Captura a conversa aberta no WhatsApp e transcreve com a visão do Claude.

    Args:
        contato: nome da conversa (apenas para rotular o resultado).
        contexto: dica opcional do que procurar (ex.: 'pedidos e prazos').

    Returns:
        {'contato': ..., 'mensagens': 'texto transcrito das mensagens visíveis'}
    """
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY não configurado — necessário para ler a tela.")

    png = _capturar_janela_whatsapp()
    b64 = base64.standard_b64encode(png).decode("utf-8")

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    instrucao = (
        "Esta é uma captura de tela do WhatsApp Desktop. Transcreva as mensagens "
        "visíveis em ordem cronológica, no formato 'Remetente (hora): mensagem'. "
        "Inclua a data se aparecer. Não invente conteúdo que não esteja legível. "
        "Ignore a lista lateral de conversas; foque na conversa aberta à direita."
    )
    if contexto:
        instrucao += f" Dê atenção especial a: {contexto}."

    resposta = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=4000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": b64},
                    },
                    {"type": "text", "text": instrucao},
                ],
            }
        ],
    )
    texto = "".join(b.text for b in resposta.content if b.type == "text")
    return {"contato": contato or "(conversa aberta)", "mensagens": texto}
