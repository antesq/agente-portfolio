"""Dashboard web (BI) de Carregamentos — projetos BR (Smartsheet ao vivo).

Rodar:
    .venv\\Scripts\\streamlit.exe run dashboard.py

Lê o workspace "BR Projetos" do Smartsheet, mostra KPIs, filtros, gráfico e
tabela, e permite publicar o resumo no canal do Teams.

Login: por enquanto sem autenticação (uso interno / local). A etapa seguinte é
adicionar login Microsoft (Entra ID) restrito ao tenant da INSTALL.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

import config
from integrations import carregamentos as carg

st.set_page_config(page_title="BI Carregamentos — Install", page_icon="🚚", layout="wide")

_ORDEM = ["Atrasado", "Esta semana", "Próx. 2 semanas", "Futuro", "Sem data", "Concluído"]
_CORES = {
    "Atrasado": "#E74C3C", "Esta semana": "#F1C40F", "Próx. 2 semanas": "#2ECC71",
    "Futuro": "#5DADE2", "Sem data": "#BDC3C7", "Concluído": "#27AE60",
}


@st.cache_data(ttl=1800, show_spinner="Lendo cronogramas do Smartsheet (BR Projetos)...")
def carregar_dados() -> pd.DataFrame:
    linhas = carg.montar_visao()
    return pd.DataFrame(linhas)


def main() -> None:
    st.title("🚚 Carregamentos Install — Projetos BR")

    if not config.configurado(config.SMARTSHEET_ACCESS_TOKEN):
        st.error("SMARTSHEET_ACCESS_TOKEN não configurado no .env.")
        st.stop()

    # --- Sidebar: controles ---
    with st.sidebar:
        st.header("Filtros")
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

    # --- Gráfico por situação ---
    st.subheader("Distribuição por situação")
    contagem = (df["categoria"].value_counts()
                .reindex(_ORDEM).dropna().astype(int))
    st.bar_chart(contagem, color="#1F4E78", horizontal=True)

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
