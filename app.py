"""
Painel de Preço Justo - B3
Rodar com:  streamlit run app.py
Dependências: pip install streamlit yfinance plotly pandas
"""
from datetime import datetime
from math import sqrt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Preço Justo B3", page_icon="📈", layout="wide")

# ---------------------------------------------------------------- estilo
st.markdown(
    """
<style>
.stApp {background: linear-gradient(180deg,#0b1020 0%,#111936 100%);}
h1,h2,h3,p,label,span,div {color:#e8ecf8;}
section[data-testid="stSidebar"] {background:#0e1428;}
.card {background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.09);
       border-radius:20px; padding:18px 20px; margin-bottom:14px;}
.tk {font-size:1.5rem; font-weight:800; letter-spacing:.5px;}
.nm {font-size:.8rem; opacity:.6; margin-bottom:8px;}
.badge {display:inline-block; padding:4px 12px; border-radius:999px;
        font-size:.75rem; font-weight:700; float:right;}
.good {background:rgba(34,197,94,.18); color:#4ade80;}
.fair {background:rgba(250,204,21,.18); color:#facc15;}
.bad  {background:rgba(239,68,68,.18); color:#f87171;}
.na   {background:rgba(148,163,184,.18); color:#cbd5e1;}
.lbl {font-size:.72rem; opacity:.6; text-transform:uppercase; letter-spacing:.8px;}
.val {font-size:1.25rem; font-weight:700;}
.hero {font-size:2rem; font-weight:800;}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- estado
if "ativos" not in st.session_state:
    st.session_state.ativos = ["PETR4", "ITSA4", "BBAS3", "VALE3"]


def normaliza(t: str) -> str:
    return t.upper().strip().replace(".SA", "")


# ---------------------------------------------------------------- dados
@st.cache_data(ttl=900, show_spinner=False)
def buscar(ticker: str) -> dict:
    """Busca cotação, LPA, VPA e dividendos (Yahoo Finance, tickers .SA da B3)."""
    t = yf.Ticker(f"{ticker}.SA")
    try:
        info = t.info or {}
    except Exception:
        info = {}

    preco = info.get("currentPrice") or info.get("regularMarketPrice")
    if not preco:
        h = t.history(period="5d")
        preco = float(h["Close"].iloc[-1]) if not h.empty else None

    divs = t.dividends
    por_ano = pd.Series(dtype=float)
    if divs is not None and not divs.empty:
        idx = divs.index.tz_localize(None) if divs.index.tz is not None else divs.index
        por_ano = divs.groupby(idx.year).sum()
        por_ano = por_ano[por_ano.index < datetime.now().year].tail(5)

    return {
        "ticker": ticker,
        "nome": info.get("shortName") or info.get("longName") or ticker,
        "preco": preco,
        "lpa": info.get("trailingEps"),
        "vpa": info.get("bookValue"),
        "div_ano": por_ano,
        "div_medio": float(por_ano.mean()) if len(por_ano) else None,
    }


def analisar(d: dict, metodo: str, yield_alvo: float, margem_alvo: float) -> dict:
    graham = None
    if d["lpa"] and d["vpa"] and d["lpa"] > 0 and d["vpa"] > 0:
        graham = sqrt(22.5 * d["lpa"] * d["vpa"])

    bazin = None
    if d["div_medio"] and d["div_medio"] > 0:
        bazin = d["div_medio"] / (yield_alvo / 100)

    if metodo == "Graham":
        justo = graham
    elif metodo == "Bazin":
        justo = bazin
    else:
        vals = [v for v in (graham, bazin) if v]
        justo = sum(vals) / len(vals) if vals else None

    margem = None
    if justo and d["preco"]:
        margem = (justo - d["preco"]) / justo * 100

    if margem is None:
        status, cls = "Sem dados", "na"
    elif margem >= margem_alvo:
        status, cls = "Com margem", "good"
    elif margem >= 0:
        status, cls = "Preço justo", "fair"
    else:
        status, cls = "Acima do justo", "bad"

    return {**d, "graham": graham, "bazin": bazin, "justo": justo,
            "margem": margem, "status": status, "cls": cls}


def brl(v):
    return "—" if v is None else f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gauge(margem):
    v = 0 if margem is None else max(-60, min(60, margem))
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=v,
        number={"suffix": "%", "font": {"size": 30, "color": "#e8ecf8"}},
        gauge={
            "axis": {"range": [-60, 60], "tickcolor": "#64748b"},
            "bar": {"color": "#e8ecf8", "thickness": 0.25},
            "bgcolor": "rgba(0,0,0,0)",
            "steps": [
                {"range": [-60, 0], "color": "rgba(239,68,68,.45)"},
                {"range": [0, 20], "color": "rgba(250,204,21,.45)"},
                {"range": [20, 60], "color": "rgba(34,197,94,.45)"},
            ],
        },
    ))
    fig.update_layout(height=170, margin=dict(l=10, r=10, t=10, b=0),
                      paper_bgcolor="rgba(0,0,0,0)", font={"color": "#e8ecf8"})
    return fig


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("## ⚙️ Configurações")
    metodo = st.radio("Método do preço justo", ["Média (Graham + Bazin)", "Graham", "Bazin"])
    yield_alvo = st.slider("Dividend yield desejado (Bazin)", 4.0, 12.0, 6.0, 0.5, format="%.1f%%")
    margem_alvo = st.slider("Margem de segurança alvo", 5, 50, 20, 5, format="%d%%")
    st.caption("Graham = √(22,5 × LPA × VPA)  ·  Bazin = dividendo médio 5 anos ÷ yield desejado")

    st.markdown("## ➕ Adicionar ativos")
    with st.form("add", clear_on_submit=True):
        novo = st.text_input("Ticker(s)", placeholder="Ex.: WEGE3, TAEE11")
        if st.form_submit_button("Adicionar", use_container_width=True):
            for t in novo.replace(";", ",").replace(" ", ",").split(","):
                t = normaliza(t)
                if t and t not in st.session_state.ativos:
                    st.session_state.ativos.append(t)

    st.session_state.ativos = st.multiselect(
        "Ativos na análise", options=st.session_state.ativos, default=st.session_state.ativos
    )
    if st.button("🔄 Atualizar cotações", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ---------------------------------------------------------------- corpo
st.markdown('<div class="hero">📈 Preço Justo · B3</div>', unsafe_allow_html=True)
st.caption(f"Atualizado em {datetime.now():%d/%m/%Y %H:%M} · fonte: dados de mercado da B3 via Yahoo Finance")

if not st.session_state.ativos:
    st.info("Adicione um ticker na barra lateral para começar.")
    st.stop()

resultados = []
with st.spinner("Buscando dados..."):
    for tk in st.session_state.ativos:
        try:
            resultados.append(analisar(buscar(tk), metodo.split(" ")[0], yield_alvo, margem_alvo))
        except Exception as e:
            st.warning(f"Não consegui carregar {tk}: {e}")

tab1, tab2, tab3 = st.tabs(["🃏 Painel", "📊 Comparativo", "💰 Dividendos"])

with tab1:
    cols_por_linha = 3
    for i in range(0, len(resultados), cols_por_linha):
        cols = st.columns(cols_por_linha)
        for col, r in zip(cols, resultados[i:i + cols_por_linha]):
            with col:
                st.markdown(
                    f"""<div class="card">
                    <span class="badge {r['cls']}">{r['status']}</span>
                    <div class="tk">{r['ticker']}</div>
                    <div class="nm">{r['nome']}</div>
                    <div style="display:flex; gap:22px;">
                      <div><div class="lbl">Preço atual</div><div class="val">{brl(r['preco'])}</div></div>
                      <div><div class="lbl">Preço justo</div><div class="val">{brl(r['justo'])}</div></div>
                    </div>
                    <div style="margin-top:10px;">
                      <div class="lbl">Média de dividendos (5 anos)</div>
                      <div class="val">{brl(r['div_medio'])} <span style="font-size:.75rem;opacity:.6">/ ano</span></div>
                    </div></div>""",
                    unsafe_allow_html=True,
                )
                st.plotly_chart(gauge(r["margem"]), use_container_width=True,
                                key=f"g_{r['ticker']}", config={"displayModeBar": False})
                st.caption(f"Margem de segurança · Graham {brl(r['graham'])} · Bazin {brl(r['bazin'])}")

with tab2:
    df = pd.DataFrame([{
        "Ticker": r["ticker"], "Preço": r["preco"], "Preço justo": r["justo"],
        "Margem (%)": r["margem"], "Div. médio 5a": r["div_medio"], "Status": r["status"],
    } for r in resultados])

    fig = go.Figure()
    fig.add_bar(x=df["Ticker"], y=df["Preço"], name="Preço atual", marker_color="#60a5fa")
    fig.add_bar(x=df["Ticker"], y=df["Preço justo"], name="Preço justo", marker_color="#34d399")
    fig.update_layout(barmode="group", height=360, paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font={"color": "#e8ecf8"},
                      legend=dict(orientation="h", y=1.1), margin=dict(t=30))
    st.plotly_chart(fig, use_container_width=True)

    d2 = df.dropna(subset=["Margem (%)"]).sort_values("Margem (%)")
    fig2 = go.Figure(go.Bar(
        x=d2["Margem (%)"], y=d2["Ticker"], orientation="h",
        marker_color=["#f87171" if m < 0 else "#4ade80" if m >= margem_alvo else "#facc15"
                      for m in d2["Margem (%)"]],
        text=[f"{m:.1f}%" for m in d2["Margem (%)"]], textposition="outside"))
    fig2.update_layout(title="Margem de segurança", height=60 + 50 * len(d2),
                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                       font={"color": "#e8ecf8"})
    st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(df.style.format({"Preço": "R$ {:.2f}", "Preço justo": "R$ {:.2f}",
                                  "Margem (%)": "{:.1f}%", "Div. médio 5a": "R$ {:.2f}"},
                                 na_rep="—"),
                 use_container_width=True, hide_index=True)

with tab3:
    fig3 = go.Figure()
    for r in resultados:
        if len(r["div_ano"]):
            fig3.add_bar(x=[str(a) for a in r["div_ano"].index], y=r["div_ano"].values, name=r["ticker"])
    fig3.update_layout(barmode="group", title="Dividendos por ação (R$/ano)", height=380,
                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                       font={"color": "#e8ecf8"})
    st.plotly_chart(fig3, use_container_width=True)

st.caption("⚠️ Ferramenta educacional. Graham e Bazin são modelos simplificados e não são recomendação de investimento.")
