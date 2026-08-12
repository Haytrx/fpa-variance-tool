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
# Optional Period selector (only shown if a Period column exists)
# ---------------------------------------------------------------
if "Period" in df.columns:
    periods = df["Period"].unique().tolist()
    selected_period = st.sidebar.selectbox("Period", periods)
    df = df[df["Period"] == selected_period].reset_index(drop=True)
else:
    selected_period = None

# ---------------------------------------------------------------
# Dynamic title: pulls from an optional "Company" column in the CSV
# so the dashboard re-labels itself for whatever dataset is loaded,
# rather than staying generic regardless of what's uploaded.
# ---------------------------------------------------------------
company_name = df["Company"].iloc[0] if "Company" in df.columns and len(df) else None
page_title = f"{company_name} — FP&A Variance Analysis" if company_name else "FP&A Variance Analysis Tool"

# ---------------------------------------------------------------
# Materiality threshold (placed here, after data + period are
# loaded, so the dollar default/step can scale to the actual size
# of this dataset -- a fixed $50,000 default is meaningless for a
# multi-billion-dollar bank and makes the $ and % sliders both
# appear broken, since a trivially-satisfied $ side always wins
# the OR check regardless of where % is set)
# ---------------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.subheader("Materiality threshold")

plan_scale = df["Plan"].abs().sum() if len(df) else 0
suggested_dollar = max(int(round(plan_scale * 0.01, -3)), 1000) if plan_scale else 50000
dollar_step = max(int(round(suggested_dollar / 10, -2)), 100)

materiality_pct = st.sidebar.slider(
    "Flag variances greater than (%)", min_value=1, max_value=50, value=10
)
materiality_dollar = st.sidebar.number_input(
    "OR flag variances greater than ($)",
    min_value=0,
    value=suggested_dollar,
    step=dollar_step,
    help=(
        f"Auto-suggested at ~1% of this dataset's total Plan "
        f"(${plan_scale:,.0f}). Adjust as needed -- a fixed default "
        f"doesn't make sense across datasets of very different scale."
    ),
)

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
st.title(page_title)
if selected_period:
    st.caption(f"Showing: **{selected_period}**")
st.caption(
    "Automated actual-vs-plan/forecast variance reporting with materiality "
    "flagging. Built in Python + Streamlit."
)
with st.expander("How to read this dashboard"):
    st.markdown(
        "- **Actual / Plan**: the reported result vs. the comparison baseline "
        "for the selected period (budget, prior period, prior year, or "
        "published guidance, depending on what's selected above).\n"
        "- **Variance $ / %**: the gap between Actual and Plan, using the "
        "sign convention chosen in the sidebar.\n"
        "- **F/U (Favorable/Unfavorable)**: whether that gap is good or bad "
        "news for an expense line — favorable means the actual result was "
        "lower than plan.\n"
        "- **Material**: flagged when a variance exceeds the $ or % "
        "threshold set in the sidebar — these are the line items worth "
        "investigating further, not every variance."
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
st.caption(
    f"Totals across {len(df)} line item{'s' if len(df) != 1 else ''}"
    + (f" for {selected_period}." if selected_period else ".")
)

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
# Charts: two modes depending on data shape
#
# Mode A (multi-category): Variance Bridge + Contribution charts,
# as before -- these need several categories to be meaningful.
#
# Mode B (single total row, e.g. full-year guidance vs actual):
# a bridge/contribution chart of ONE item is meaningless (it just
# repeats the same bar twice). Instead, show a range-check visual:
# where did Actual land relative to the low/high guided range.
# ---------------------------------------------------------------
has_range = (
    len(df) == 1
    and "PlanLow" in df.columns
    and "PlanHigh" in df.columns
    and pd.notna(df["PlanLow"].iloc[0])
    and pd.notna(df["PlanHigh"].iloc[0])
)

if len(df) == 1 and has_range:
    st.subheader("Actual vs. Guided Range")

    row = df.iloc[0]
    low, high, actual = row["PlanLow"], row["PlanHigh"], row["Actual"]

    def fmt_b(v):
        return f"${v/1_000_000_000:,.3f}B" if abs(v) >= 1_000_000_000 else f"${v/1_000_000:,.1f}M"

    if low <= actual <= high:
        position_note = "Landed within the guided range."
    elif actual > high:
        position_note = f"Landed {fmt_b(actual - high)} above the top of the guided range."
    else:
        position_note = f"Landed {fmt_b(low - actual)} below the bottom of the guided range."

    st.caption(
        f"Guided range: {fmt_b(low)} \u2013 {fmt_b(high)}  |  "
        f"Actual: {fmt_b(actual)}  |  {position_note}"
    )

    fig = go.Figure()

    # Shaded band = guided range
    fig.add_shape(
        type="rect", x0=low, x1=high, y0=0, y1=1,
        fillcolor="rgba(31,119,180,0.2)", line=dict(width=0),
    )
    # Marker line = actual
    actual_color = "#2ca02c" if low <= actual <= high else "#d62728"
    fig.add_shape(
        type="line", x0=actual, x1=actual, y0=0, y1=1,
        line=dict(color=actual_color, width=4),
    )
    fig.add_annotation(
        x=actual, y=1.08, text=f"Actual: {fmt_b(actual)}",
        showarrow=False, font=dict(color=actual_color, size=13),
    )
    fig.add_annotation(
        x=low, y=-0.15, text=f"Low: {fmt_b(low)}", showarrow=False, font=dict(size=11, color="gray"),
    )
    fig.add_annotation(
        x=high, y=-0.15, text=f"High: {fmt_b(high)}", showarrow=False, font=dict(size=11, color="gray"),
    )

    fig.update_xaxes(range=[low - (high - low) * 0.3, high + (high - low) * 0.3], showgrid=False)
    fig.update_yaxes(visible=False, range=[-0.3, 1.3])
    fig.update_layout(height=220, margin=dict(t=50, b=40))
    st.plotly_chart(fig, use_container_width=True)

elif len(df) == 1:
    st.info("Single line item selected \u2014 no category breakdown available for this period.")

else:
    # ---------------------------------------------------------------
    # Variance Bridge (waterfall of deltas only -- not anchored to
    # Plan/Actual absolute totals, which are usually orders of magnitude
    # larger than individual category variances and make a traditional
    # Plan-to-Actual waterfall unreadable)
    # ---------------------------------------------------------------
    st.subheader("Variance Bridge")
    st.caption(
        "Shows each category's dollar contribution to the total variance, "
        "starting at $0 and building to Net Variance. Plan and Actual totals "
        "are shown in the KPI cards above."
    )

    bridge_df = df.sort_values("Variance $", ascending=False).reset_index(drop=True)

    bridge_categories = bridge_df["Category"].tolist() + ["Net Variance"]
    bridge_values = bridge_df["Variance $"].tolist() + [0]  # Plotly auto-sums the total
    bridge_measures = ["relative"] * len(bridge_df) + ["total"]

    bridge_text = [
        f"${v:,.0f}" if abs(v) < 1_000_000 else f"${v/1_000_000:,.1f}M"
        for v in bridge_df["Variance $"].tolist()
    ] + [f"${total_variance:,.0f}" if abs(total_variance) < 1_000_000 else f"${total_variance/1_000_000:,.1f}M"]

    fig = go.Figure(
        go.Waterfall(
            x=bridge_categories,
            measure=bridge_measures,
            y=bridge_values,
            text=bridge_text,
            textposition="outside",
            connector={"line": {"color": "rgb(180,180,180)"}},
            decreasing={"marker": {"color": "#d62728"}},
            increasing={"marker": {"color": "#2ca02c"}},
            totals={"marker": {"color": "#1f77b4"}},
        )
    )
    fig.add_hline(y=0, line_width=1, line_color="rgba(0,0,0,0.3)")
    fig.update_layout(showlegend=False, height=480, margin=dict(t=20, b=120))
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
