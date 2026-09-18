"""Dashboard web (BI) de Carregamentos — projetos BR (Smartsheet ao vivo).

Rodar:
    .venv\\Scripts\\streamlit.exe run dashboard.py

Lê o workspace "BR Projetos" do Smartsheet, mostra KPIs, filtros, gráfico e
tabela, e permite publicar o resumo no canal do Teams.

Login: por enquanto sem autenticação (uso interno / local). A etapa seguinte é
adicionar login Microsoft (Entra ID) restrito ao tenant da INSTALL.
"""
from __future__ import annotations

import os

import streamlit as st

st.set_page_config(page_title="BI Carregamentos — Install", page_icon="🚚", layout="wide")

# Em deploy (Streamlit Cloud) os segredos vêm de st.secrets. Trazemos para as
# variáveis de ambiente ANTES de importar config (que lê o ambiente na importação).
try:
    for _k in st.secrets:
        os.environ.setdefault(_k, str(st.secrets[_k]))
except Exception:
    pass

from datetime import datetime  # noqa: E402

import pandas as pd  # noqa: E402

import config  # noqa: E402
from integrations import carregamentos as carg  # noqa: E402

_ORDEM = ["Atrasado", "Esta semana", "Próx. 2 semanas", "Futuro", "Sem data", "Concluído"]
_CORES = {
    "Atrasado": "#E74C3C", "Esta semana": "#F1C40F", "Próx. 2 semanas": "#2ECC71",
    "Futuro": "#5DADE2", "Sem data": "#BDC3C7", "Concluído": "#27AE60",
}
# Domínios de e-mail autorizados a ver o painel (login Microsoft).
_DOMINIOS_PERMITIDOS = ("installequipamentos.com.br",)


def _autenticar() -> None:
    """Se a seção [auth] existir nos secrets (deploy), exige login Microsoft do
    tenant da INSTALL. Sem [auth] (uso local), o app roda aberto normalmente."""
    try:
        tem_auth = "auth" in st.secrets
    except Exception:
        tem_auth = False
    if not tem_auth:
        return  # ambiente local sem login configurado

    if not getattr(st, "user", None) or not st.user.is_logged_in:
        st.title("🔒 Carregamentos Install — acesso restrito")
        st.write("Entre com sua conta **Microsoft da INSTALL** para ver o painel.")
        st.button("Entrar com a Microsoft", type="primary",
                  on_click=st.login, args=("microsoft",))
        st.stop()

    email = str(st.user.get("email") or st.user.get("preferred_username") or "").lower()
    if _DOMINIOS_PERMITIDOS and not any(email.endswith("@" + d) for d in _DOMINIOS_PERMITIDOS):
        st.error(f"Acesso não autorizado para: {email or 'conta sem e-mail'}.")
        st.button("Sair", on_click=st.logout)
        st.stop()


@st.cache_data(ttl=1800, show_spinner="Lendo cronogramas do Smartsheet (BR Projetos)...")
def carregar_dados() -> pd.DataFrame:
    linhas = carg.montar_visao()
    return pd.DataFrame(linhas)


def main() -> None:
    _autenticar()  # portão de login (só ativo quando [auth] está nos secrets)

    st.title("🚚 Carregamentos Install — Projetos BR")

    if not config.configurado(config.SMARTSHEET_ACCESS_TOKEN):
        st.error("SMARTSHEET_ACCESS_TOKEN não configurado no .env.")
        st.stop()

    # --- Sidebar: controles ---
    with st.sidebar:
        st.header("Filtros")
        if getattr(st, "user", None) and getattr(st.user, "is_logged_in", False):
            st.caption(f"👤 {st.user.get('name') or st.user.get('email', '')}")
            st.button("Sair", on_click=st.logout)
        if st.button("🔄 Atualizar dados (recarregar do Smartsheet)"):
            st.cache_data.clear()
            st.rerun()

    df = carregar_dados()
    if df.empty:
        st.warning("Nenhum projeto encontrado no workspace BR Projetos.")
        st.stop()

    with st.sidebar:
        cats = st.multiselect("Situação", _ORDEM,
                              default=[c for c in _ORDEM if c != "Concluído"])
        unidades = sorted(u for u in df["unidade"].unique() if u)
        filtro_unid = st.multiselect("Unidade", unidades)
        busca = st.text_input("Buscar (código ou projeto)").strip().lower()

    filt = df[df["categoria"].isin(cats)] if cats else df
    if filtro_unid:
        filt = filt[filt["unidade"].isin(filtro_unid)]
    if busca:
        filt = filt[filt["codigo"].astype(str).str.contains(busca, case=False)
                    | filt["projeto"].str.lower().str.contains(busca)]

    # --- KPIs ---
    st.caption(f"Atualizado em {datetime.now().strftime('%d/%m/%Y %H:%M')} · "
               f"{len(df)} projetos no total")
    cols = st.columns(len(_ORDEM))
    for col, cat in zip(cols, _ORDEM):
        col.metric(cat, int((df["categoria"] == cat).sum()))

    # --- Tabela ---
    st.subheader(f"Projetos ({len(filt)})")
    tabela = filt[["codigo", "unidade", "projeto", "data_fmt", "categoria",
                   "pct", "responsavel"]].rename(columns={
        "codigo": "Código", "unidade": "Unidade", "projeto": "Projeto",
        "data_fmt": "Carregamento", "categoria": "Situação",
        "pct": "% concl.", "responsavel": "Responsável"})

    def _cor(v):
        return f"background-color: {_CORES.get(v, '')}; color: #111"

    st.dataframe(
        tabela.style.map(_cor, subset=["Situação"]),
        use_container_width=True, hide_index=True, height=460,
    )

    # --- Ações ---
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        excel = carg.exportar_excel(df.to_dict("records"), config.OUTPUT_DIR)
        with open(excel, "rb") as f:
            st.download_button("⬇️ Baixar Excel completo", f.read(),
                               file_name=excel.name,
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with c2:
        if st.button("📢 Publicar resumo no Teams"):
            from integrations import teams_notifier
            try:
                teams_notifier.publicar_card(carg.montar_card(df.to_dict("records")))
                st.success("Resumo publicado no canal Carregamento install ✅")
            except Exception as e:
                st.error(f"Falha ao publicar: {e}")


if __name__ == "__main__":
    main()
