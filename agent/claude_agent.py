"""Loop do agente: conversa com o Claude usando o padrão de tool use manual.

Mantemos um loop manual (em vez do tool runner beta) para ter controle total
sobre execução de ferramentas, logs e persistência.
"""
from __future__ import annotations

import anthropic

import config
from agent import prompts
from agent.tools import DEFINICOES, CaixaDeFerramentas

_MAX_ITERACOES = 25  # trava de segurança contra loops infinitos


class AgentePortfolio:
    def __init__(self) -> None:
        if not config.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY não configurado no .env.")
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.ferramentas = CaixaDeFerramentas()
        self.mensagens: list[dict] = []

    def enviar(self, pedido_usuario: str) -> str:
        """Envia um pedido ao agente e roda o loop até ele concluir.

        Retorna o texto final do agente. Imprime o progresso conforme executa.
        """
        self.mensagens.append({"role": "user", "content": pedido_usuario})
        texto_final = ""

        for _ in range(_MAX_ITERACOES):
            resposta = self.client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=16000,
                system=prompts.SISTEMA,
                tools=DEFINICOES,
                messages=self.mensagens,
            )

            # Mostra o texto que o Claude produziu nesta rodada.
            for bloco in resposta.content:
                if bloco.type == "text" and bloco.text.strip():
                    print(f"\n🤖 {bloco.text.strip()}\n")
                    texto_final = bloco.text.strip()

            if resposta.stop_reason != "tool_use":
                break

            # Guarda a resposta do assistente (inclui os blocos tool_use).
            self.mensagens.append({"role": "assistant", "content": resposta.content})

            # Executa cada ferramenta pedida e coleta os resultados.
            resultados = []
            for bloco in resposta.content:
                if bloco.type == "tool_use":
                    print(f"   ⚙️  {bloco.name}({_resumo_entrada(bloco.input)})")
                    saida = self.ferramentas.executar(bloco.name, bloco.input)
                    resultados.append({
                        "type": "tool_result",
                        "tool_use_id": bloco.id,
                        "content": saida,
                    })
            self.mensagens.append({"role": "user", "content": resultados})
        else:
            print("⚠️  Limite de iterações atingido — encerrando o loop.")

        return texto_final


def _resumo_entrada(entrada: dict) -> str:
    """Resumo curto dos argumentos, para o log não ficar gigante."""
    partes = []
    for k, v in entrada.items():
        texto = str(v)
        if len(texto) > 60:
            texto = texto[:57] + "..."
        partes.append(f"{k}={texto}")
    return ", ".join(partes)
