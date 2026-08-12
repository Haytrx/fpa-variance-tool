"""
FP&A Variance Analysis Tool
Built by D. Hayden Link

An automated actual-vs-plan/forecast variance reporting tool. Upload a CSV
of financial line items (or use the included sample dataset) and instantly
get variance $, variance %, Favorable/Unfavorable classification, and
materiality flagging -- the same analysis performed manually in the USAA
Call Center Finance case study, now automated.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(page_title="FP&A Variance Analysis Tool", layout="wide")

# ---------------------------------------------------------------
# Sidebar: data input + settings
# ---------------------------------------------------------------
st.sidebar.title("Settings")

data_source = st.sidebar.radio(
    "Data source",
    ["Use sample dataset", "Upload my own CSV"],
)

st.sidebar.markdown("---")
st.sidebar.subheader("Materiality threshold")
materiality_pct = st.sidebar.slider(
    "Flag variances greater than (%)", min_value=1, max_value=50, value=10
)
materiality_dollar = st.sidebar.number_input(
    "OR flag variances greater than ($)", min_value=0, value=50000, step=10000
)

st.sidebar.markdown("---")
st.sidebar.subheader("Variance convention")
convention = st.sidebar.selectbox(
    "How is variance calculated?",
    [
        "Plan/Forecast minus Actual (negative = unfavorable expense)",
        "Actual minus Plan/Forecast (positive = unfavorable expense)",
    ],
)

# ---------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------
REQUIRED_COLS = ["Category", "Actual", "Plan"]

@st.cache_data
def load_sample_data():
    return pd.read_csv("sample_data.csv")


if data_source == "Use sample dataset":
    df = load_sample_data()
    st.sidebar.success("Using sample_data.csv")
else:
    uploaded = st.sidebar.file_uploader("Upload CSV", type=["csv"])
    if uploaded is not None:
        df = pd.read_csv(uploaded)
    else:
        st.info(
            "Upload a CSV with columns: **Category, Actual, Plan** "
            "(optional: PriorPeriodActual, PriorYearActual) to get started, "
            "or switch to the sample dataset in the sidebar."
        )
        st.stop()

missing = [c for c in REQUIRED_COLS if c not in df.columns]
if missing:
    st.error(f"Uploaded file is missing required column(s): {', '.join(missing)}")
    st.stop()

# ---------------------------------------------------------------
# Core variance calculations
# ---------------------------------------------------------------
if convention.startswith("Plan/Forecast"):
    df["Variance $"] = df["Plan"] - df["Actual"]
else:
    df["Variance $"] = df["Actual"] - df["Plan"]

df["Variance %"] = (df["Variance $"] / df["Plan"].replace(0, pd.NA)) * 100
df["F/U"] = df["Variance $"].apply(lambda x: "Favorable" if x >= 0 else "Unfavorable")
df["Material"] = (
    (df["Variance $"].abs() >= materiality_dollar)
    | (df["Variance %"].abs() >= materiality_pct)
)

# ---------------------------------------------------------------
# Header
# ---------------------------------------------------------------
st.title("FP&A Variance Analysis Tool")
st.caption(
    "Automated actual-vs-plan/forecast variance reporting with materiality "
    "flagging. Built in Python + Streamlit."
)

# ---------------------------------------------------------------
# Summary metrics
# ---------------------------------------------------------------
total_actual = df["Actual"].sum()
total_plan = df["Plan"].sum()
total_variance = df["Variance $"].sum()
total_variance_pct = (total_variance / total_plan * 100) if total_plan else 0
material_count = df["Material"].sum()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Actual", f"${total_actual:,.0f}")
c2.metric("Total Plan", f"${total_plan:,.0f}")
c3.metric(
    "Total Variance",
    f"${total_variance:,.0f}",
    f"{total_variance_pct:+.1f}%",
)
c4.metric("Material Line Items", int(material_count))

st.markdown("---")

# ---------------------------------------------------------------
# Variance table
# ---------------------------------------------------------------
st.subheader("Variance by Category")

def highlight_material(row):
    if row["Material"]:
        color = "background-color: #ffe6e6" if row["F/U"] == "Unfavorable" else "background-color: #e6ffe6"
        return [color] * len(row)
    return [""] * len(row)

display_df = df[["Category", "Actual", "Plan", "Variance $", "Variance %", "F/U", "Material"]].copy()
display_df["Actual"] = display_df["Actual"].map("${:,.0f}".format)
display_df["Plan"] = display_df["Plan"].map("${:,.0f}".format)
display_df["Variance $"] = display_df["Variance $"].map("${:,.0f}".format)
display_df["Variance %"] = display_df["Variance %"].map("{:+.1f}%".format)

st.dataframe(
    df.style.apply(highlight_material, axis=1).format(
        {
            "Actual": "${:,.0f}",
            "Plan": "${:,.0f}",
            "Variance $": "${:,.0f}",
            "Variance %": "{:+.1f}%",
        }
    ),
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "Rows highlighted red/green are flagged as material based on your sidebar threshold."
)

st.markdown("---")

# ---------------------------------------------------------------
# Waterfall chart: Plan -> Category variances -> Actual
# ---------------------------------------------------------------
st.subheader("Variance Waterfall")

waterfall_categories = ["Plan"] + df["Category"].tolist() + ["Actual"]
waterfall_values = [total_plan] + (-df["Variance $"]).tolist() + [total_actual]
measures = ["absolute"] + ["relative"] * len(df) + ["total"]

fig = go.Figure(
    go.Waterfall(
        x=waterfall_categories,
        measure=measures,
        y=waterfall_values,
        connector={"line": {"color": "rgb(180,180,180)"}},
        decreasing={"marker": {"color": "#d62728"}},
        increasing={"marker": {"color": "#2ca02c"}},
        totals={"marker": {"color": "#1f77b4"}},
    )
)
fig.update_layout(showlegend=False, height=450)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------------
# Category contribution bar chart
# ---------------------------------------------------------------
st.subheader("Variance Contribution by Category")

bar_fig = px.bar(
    df.sort_values("Variance $"),
    x="Variance $",
    y="Category",
    orientation="h",
    color="F/U",
    color_discrete_map={"Favorable": "#2ca02c", "Unfavorable": "#d62728"},
)
bar_fig.update_layout(height=400)
st.plotly_chart(bar_fig, use_container_width=True)

st.markdown("---")
st.caption(
    "Built by D. Hayden Link | "
    "[GitHub](https://github.com/) | "
    "Sample data structure inspired by public bank quarterly expense reporting."
)
