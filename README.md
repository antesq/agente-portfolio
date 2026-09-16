# Agente de Gestão de Portfólio — Install / MELI

Agente de IA (Claude) que **mantém o portfólio de projetos de transporte da Install
(cliente Mercado Livre) atualizado e organizado**, lendo múltiplas fontes e gerando
listas de ações e planilhas de acompanhamento.

O modelo de dados espelha a planilha oficial *"MELI Portfólio de Projetos de
Transportes da Install"* (aba **Contratação Meli**): escopo técnico, proposta técnica
contratada, prazos/milestones, status geral, bloqueios e responsáveis.

---

## O que ele faz (Fase 1 — CLI local)

- 📊 **Lê o Smartsheet** (portfólio atual) via API.
- 📧 **Lê e-mails do Outlook 365** (Microsoft Graph) para achar **propostas técnicas atualizadas**
  (ex.: `PPT-BR-2026-07-1704_01`) e outras informações.
- 📄 **Lê os documentos de proposta** (PDF técnico + relatórios de custo `.pdf`/`.xlsx`) direto
  da pasta do projeto no drive `Z:` e extrai escopo, número da proposta e custos.
- 💬 **Lê o WhatsApp Desktop pela tela** (captura + visão do Claude) — *somente na máquina local*.
- ✍️ **Atualiza o portfólio** (upsert por código de projeto) e aceita **preenchimento manual**.
- ✅ **Gera lista de ações** priorizada (foco em *Em risco* / *EM ATRASO* / bloqueados).
- 📁 **Exporta em Excel** no formato MELI (abas: Resumo, Contratação Meli, Plano de Ações).

### Roadmap
- **Fase 2 — Portal web** com **login Microsoft (Entra ID) restrito ao tenant da Install**,
  visão do portfólio para toda a equipe e exportação. (Reaproveita os módulos de `integrations/` e
  `portfolio/` deste repositório.)

---

## Arquitetura

```
agente-portfolio/
├── main.py                     # CLI: modo interativo, pedido único, --check
├── config.py                   # carrega .env e expõe as configurações
├── agent/
│   ├── prompts.py              # prompt de sistema do agente
│   ├── tools.py                # ferramentas (schema + execução) e estado do portfólio
│   └── claude_agent.py         # loop de tool use com a Claude API
├── integrations/
│   ├── smartsheet_client.py    # Smartsheet (SDK oficial)
│   ├── outlook_client.py       # Outlook 365 via Microsoft Graph (MSAL device code)
│   ├── documentos.py           # leitura de PDFs/XLSX de proposta (Z:) + extração via Claude
│   └── whatsapp_reader.py      # captura da tela do WhatsApp Desktop + visão do Claude
├── portfolio/
│   ├── models.py               # modelo de dados (espelha a planilha MELI)
│   ├── store.py                # persistência em JSON (dados/portfolio.json)
│   └── excel_builder.py        # geração do .xlsx (openpyxl)
├── requirements.txt
└── .env.example                # modelo de configuração (copie para .env)
```

---

## Instalação

> Requer **Python 3.10+**. No Windows, instale de https://python.org (marque
> "Add Python to PATH") ou via `winget install Python.Python.3.12`.

```bash
# 1. (Recomendado) crie um ambiente virtual
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Configure as credenciais
copy .env.example .env         # Windows (use 'cp' no Linux/Mac)
# edite o .env preenchendo as chaves

# 4. Verifique a configuração
python main.py --check
```

---

## Configuração das credenciais (`.env`)

### 1. Claude API (obrigatório)
Crie uma chave em https://console.anthropic.com/settings/keys e coloque em `ANTHROPIC_API_KEY`.

### 2. Smartsheet (opcional)
Em **Smartsheet → Account → Personal Settings → API Access**, gere um token e coloque em
`SMARTSHEET_ACCESS_TOKEN`.

### 3. Outlook 365 / Microsoft Graph (opcional)
1. Acesse https://portal.azure.com → **Azure Active Directory → App registrations → New registration**.
2. Conta: *"Accounts in this organizational directory only"*.
3. Em **Authentication**, habilite **"Allow public client flows" = Yes**.
4. Em **API permissions**, adicione **Microsoft Graph → Delegated → `Mail.Read`** e conceda consentimento.
5. Copie o **Application (client) ID** para `MS_CLIENT_ID` e o **Directory (tenant) ID** para `MS_TENANT_ID`.

Na primeira execução que usar e-mail, o programa mostra um código para você autorizar em
`microsoft.com/devicelogin`. O token fica em cache local para as próximas vezes.

### 4. WhatsApp (opcional, só local)
Abra o **WhatsApp Desktop** na conversa desejada **antes** de pedir a leitura. Ajuste
`WHATSAPP_WINDOW_TITLE` se o título da janela for diferente de "WhatsApp".

---

## Como usar

```bash
# Modo conversa (interativo)
python main.py

# Pedido único
python main.py "Leia a pasta Z:\PROJETOS\2026\Mercado Livre\Projeto 1677 Barueri e atualize o projeto 1677"
python main.py "Procure e-mails de proposta técnica e atualize o portfólio, depois gere a planilha"
```

Exemplos de pedido:
- *"Leia a planilha MELI do Smartsheet e me mostre os projetos em atraso e congelados."*
- *"Leia os documentos de proposta do Projeto 1677 e atualize o escopo e a proposta técnica."*
- *"Gere ações para todos os projetos Em risco e exporte a planilha."*

---

## Segurança

- O `.env`, o cache de token da Microsoft e as saídas ficam no `.gitignore` — **nunca** são versionados.
- Nenhuma credencial é gravada no código.
- O WhatsApp é lido **localmente pela tela** (sem API não-oficial), evitando risco de banimento.

---

## Status

**Fase 1 (agente CLI) — em desenvolvimento.** Fonte da verdade: Smartsheet + propostas por e-mail +
documentos no `Z:` + preenchimento manual. Portal web multiusuário planejado para a Fase 2.
