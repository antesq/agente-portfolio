# Deploy grátis do Dashboard (Streamlit Community Cloud)

O dashboard (`dashboard.py`) pode ser publicado de graça no **Streamlit Community
Cloud**, lendo o Smartsheet ao vivo. A equipe acessa por um link.

## Pré-requisitos
- Repositório no GitHub: `antesq/agente-portfolio` (já existe, privado).
- Uma conta no Streamlit Community Cloud (login com o GitHub): https://share.streamlit.io

## Passo a passo

1. Acesse https://share.streamlit.io e faça login com o **GitHub** (conta `ronan-antesq`).
2. Autorize o **Streamlit** a acessar a organização **antesq** (para repositório privado,
   um admin da org pode precisar aprovar o app do Streamlit no GitHub).
3. Clique em **Create app → Deploy a public app from GitHub** (mesmo sendo repo privado):
   - **Repository:** `antesq/agente-portfolio`
   - **Branch:** `main`
   - **Main file path:** `dashboard.py`
4. Em **Advanced settings → Secrets**, cole (formato TOML):

   ```toml
   SMARTSHEET_ACCESS_TOKEN = "SEU_TOKEN_SMARTSHEET_DE_HOMOLOGACAO"
   TEAMS_WEBHOOK_URL = "SUA_URL_DO_WEBHOOK_DO_TEAMS"
   # ANTHROPIC_API_KEY = "..."   # opcional, só se o app usar IA
   ```

   > Os valores estão no seu `.env` local. **Não** comite segredos — eles ficam só aqui.

5. Clique **Deploy**. Em ~2 min o app sobe e você recebe uma **URL pública**
   (ex.: `https://agente-portfolio-xxxx.streamlit.app`).

## Restringir o acesso (equipe interna)
- No painel do app → **Settings → Sharing**, você pode tornar o app **privado** e
  convidar por e-mail quem pode ver (cada pessoa entra com a própria conta).
- A etapa seguinte do projeto é adicionar **login Microsoft (Entra ID)** restrito ao
  tenant da INSTALL — aí o controle de acesso fica pela conta corporativa.

## Atualização
- Todo `git push` na branch `main` **redeploya** o app automaticamente.
- Dentro do app, o botão **"Atualizar dados"** recarrega do Smartsheet (cache de 30 min).

## Observações
- O deploy usa o `requirements.txt` da raiz (já preparado para Linux).
- As libs de desktop do WhatsApp ficam no `requirements-desktop.txt` (não vão para a nuvem).
