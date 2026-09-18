"""Agente de Gestão de Portfólio — ponto de entrada (CLI).

Uso:
    python main.py                        # modo conversa (interativo)
    python main.py "seu pedido"           # executa um pedido único e sai
    python main.py --check                # verifica a configuração (chaves/credenciais)
    python main.py --importar-csv arq.csv # carga inicial a partir de um CSV da planilha
    python main.py --exportar             # gera a planilha Excel do portfólio atual
    python main.py --carregamentos        # visão de carregamentos BR (Smartsheet) e publica no Teams
    python main.py --carregamentos --sem-publicar  # só gera o Excel, sem postar no canal

Exemplos de pedido:
    "Leia a planilha MELI do Smartsheet e me mostre os projetos em atraso."
    "Leia a pasta Z:\\PROJETOS\\2026\\Mercado Livre\\Projeto 1677 Barueri e atualize o projeto 1677."
    "Procure e-mails de proposta técnica dos últimos dias e atualize o portfólio."
    "Gere a planilha de portfólio em Excel."
"""
from __future__ import annotations

import sys

import config


def verificar_config() -> None:
    """Imprime o estado de cada credencial (sem revelar valores)."""
    print("Verificação de configuração:\n")
    checagens = [
        ("ANTHROPIC_API_KEY (Claude)", config.configurado(config.ANTHROPIC_API_KEY)),
        ("SMARTSHEET_ACCESS_TOKEN", config.configurado(config.SMARTSHEET_ACCESS_TOKEN)),
        ("MS_CLIENT_ID (Outlook/Graph)", config.configurado(config.MS_CLIENT_ID)),
    ]
    for nome, ok in checagens:
        print(f"  {'✅' if ok else '❌'}  {nome}")
    print(f"\n  Modelo Claude: {config.CLAUDE_MODEL}")
    print(f"  Pasta de saída: {config.OUTPUT_DIR}")
    faltando = config.validar(["ANTHROPIC_API_KEY"])
    if faltando:
        print("\n⚠️  Sem ANTHROPIC_API_KEY o agente não roda. Preencha o arquivo .env.")
    else:
        print("\n✅ Pronto para rodar o agente (as demais integrações são opcionais).")


def modo_interativo() -> None:
    from agent.claude_agent import AgentePortfolio

    print("=" * 64)
    print(" Agente de Gestão de Portfólio — Install / MELI")
    print(" Digite seu pedido. Comandos: 'sair' para encerrar.")
    print("=" * 64)
    agente = AgentePortfolio()
    while True:
        try:
            pedido = input("\n👤 Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAté logo!")
            break
        if not pedido:
            continue
        if pedido.lower() in ("sair", "exit", "quit"):
            print("Até logo!")
            break
        agente.enviar(pedido)


def modo_unico(pedido: str) -> None:
    from agent.claude_agent import AgentePortfolio

    AgentePortfolio().enviar(pedido)


def importar_csv(caminho: str) -> None:
    from integrations import csv_importer

    resumo = csv_importer.importar_csv(caminho)
    print("Importação concluída:")
    print(f"  Novos projetos:      {resumo['novos']}")
    print(f"  Projetos atualizados:{resumo['atualizados']}")
    print(f"  Linhas ignoradas:    {resumo['linhas_ignoradas']}")
    print(f"  Total no portfólio:  {resumo['total_no_portfolio']}")
    print(f"  Colunas reconhecidas:{', '.join(resumo['colunas_reconhecidas'])}")


def exportar() -> None:
    from portfolio import excel_builder, store

    pf = store.carregar()
    caminho = excel_builder.gerar_planilha(pf, config.OUTPUT_DIR)
    print(f"✅ Planilha gerada em: {caminho}")


def carregamentos(publicar: bool = True) -> None:
    from integrations import carregamentos as carg

    print("Lendo cronogramas dos projetos BR no Smartsheet (pode demorar)...")
    r = carg.gerar_e_publicar(publicar=publicar)
    print(f"✅ {r['total_projetos']} projetos processados.")
    print(f"📄 Excel: {r['excel']}")
    if publicar:
        print(f"📢 Publicado no Teams: {r.get('teams')}")


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "--check":
        verificar_config()
        return
    if args and args[0] == "--importar-csv":
        if len(args) < 2:
            print("Uso: python main.py --importar-csv caminho\\do\\arquivo.csv")
            sys.exit(1)
        importar_csv(args[1])
        return
    if args and args[0] == "--exportar":
        exportar()
        return
    if args and args[0] == "--carregamentos":
        # --carregamentos [--sem-publicar]
        carregamentos(publicar="--sem-publicar" not in args)
        return
    # Barreira mínima: precisa da chave do Claude.
    if config.validar(["ANTHROPIC_API_KEY"]):
        print("❌ ANTHROPIC_API_KEY não configurado. Copie .env.example para .env e preencha.")
        print("   Rode 'python main.py --check' para ver o estado da configuração.")
        sys.exit(1)
    if args:
        modo_unico(" ".join(args))
    else:
        modo_interativo()


if __name__ == "__main__":
    main()
