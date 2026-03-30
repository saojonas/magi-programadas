import json
import pandas as pd
import streamlit as st
from supabase import create_client

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Inspeções Programadas", layout="wide")

# =========================
# CONEXÃO
# =========================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================
# HELPERS
# =========================
def parse_eq(x):
    try:
        return json.loads(x) if isinstance(x, str) else x
    except:
        return {}

def fmt_dt(s):
    s = pd.to_datetime(s, utc=True, errors="coerce")
    return s.dt.tz_convert("America/Sao_Paulo").dt.strftime("%d/%m %H:%M")

# =========================
# DATA
# =========================
@st.cache_data(ttl=60)
def load():

    # OS base
    resp = supabase.table("os").select("*") \
        .gte("created_at", (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=7)).isoformat()) \
        .in_("type", ["OS", "PRE_OS"]) \
        .in_("status", ["RTE", "EM_EXECUCAO"]) \
        .eq("motivo", "Inspeção programada") \
        .order("created_at", desc=True) \
        .execute()

    df = pd.DataFrame(resp.data or [])

    if df.empty:
        return df

    # vínculos
    ids = df["id"].tolist()

    vinc = supabase.table("os_manutentores") \
        .select("os_id, manutentor_id") \
        .in_("os_id", ids) \
        .execute()

    df_v = pd.DataFrame(vinc.data or [])

    if not df_v.empty:
        mant_ids = df_v["manutentor_id"].unique().tolist()

        mant = supabase.table("manutentores") \
            .select("id, nome, apelido") \
            .in_("id", mant_ids) \
            .execute()

        df_m = pd.DataFrame(mant.data or [])

        df_vm = df_v.merge(df_m, left_on="manutentor_id", right_on="id", how="left")

        df_vm["nome"] = df_vm.apply(
            lambda r: r["apelido"] if r["apelido"] else r["nome"], axis=1
        )

        df_mecs = df_vm.groupby("os_id")["nome"] \
            .agg(lambda x: ", ".join(sorted(set(x)))) \
            .reset_index() \
            .rename(columns={"nome": "mecanicos"})

        df = df.merge(df_mecs, left_on="id", right_on="os_id", how="left")

    df["mecanicos"] = df["mecanicos"].fillna("—")

    # equipamento
    eq = df["equipamento"].apply(parse_eq)
    df["equip"] = eq.apply(lambda x: f"{x.get('id','')} - {x.get('desc','')}")

    # datas
    df["created"] = fmt_dt(df["created_at"])
    df["inicio"] = fmt_dt(df["started_real_at"])

    return df

df = load()

# =========================
# UI
# =========================
st.title("Magi@Programadas")

if df.empty:
    st.warning("Nada encontrado.")
    st.stop()

# KPIs
c1, c2, c3 = st.columns(3)
c1.metric("Total", len(df))
c2.metric("PRE_OS", (df["type"] == "PRE_OS").sum())
c3.metric("OS", (df["type"] == "OS").sum())

st.divider()

# TABELA
st.dataframe(
    df[[
        "id",
        "type",
        "status",
        "equip",
        "descricao",
        "solicitante",
        "mecanicos",
        "created",
        "inicio"
    ]].rename(columns={
        "id": "Ordem",
        "type": "Tipo",
        "status": "Status",
        "equip": "Equipamento",
        "descricao": "Descrição",
        "solicitante": "Solicitante",
        "mecanicos": "Mecânicos",
        "created": "Criada",
        "inicio": "Início"
    }),
    use_container_width=True,
    hide_index=True
)

st.divider()

# CARDS
for _, r in df.iterrows():
    st.markdown(f"""
**{r['equip']}**

{r['descricao']}

- Ordem: `{r['id']}`
- Tipo: {r['type']} | Status: {r['status']}
- Mecânicos: {r['mecanicos']}
- Criada: {r['created']} | Início: {r['inicio']}
""")