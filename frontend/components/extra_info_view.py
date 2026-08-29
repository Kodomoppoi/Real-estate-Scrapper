import re
from collections import Counter
import streamlit as st
import pandas as pd


def _clean_price(price_str: str) -> float:
    if not isinstance(price_str, str):
        return 0.0
    cleaned = re.sub(r"[^\d,.]", "", price_str)
    if not cleaned:
        return 0.0
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    elif "." in cleaned and cleaned.count(".") > 1:
        parts = cleaned.split(".")
        cleaned = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def render_extra_info_view(df: pd.DataFrame):
    """
    Renders the 'Extra Details' tab highlighting amenities frequency,
    title highlights, financing status, and price-per-m² insights (in English).
    """
    if df.empty:
        st.info("No data available to display extra details.")
        return

    st.markdown('<div class="section-title">Highlights, Amenities & Commercial Terms</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1])

    # 1. Amenities breakdown
    with col1:
        st.markdown("**Most Frequent Amenities & Features**")
        amenities_list = []
        if "amenities" in df.columns:
            for item in df["amenities"].dropna():
                if isinstance(item, list):
                    amenities_list.extend([str(a).strip() for a in item if str(a).strip()])
                elif isinstance(item, str) and item.startswith("["):
                    try:
                        import ast
                        parsed = ast.literal_eval(item)
                        if isinstance(parsed, list):
                            amenities_list.extend([str(a).strip() for a in parsed if str(a).strip()])
                    except Exception:
                        pass
                elif isinstance(item, str) and item.strip():
                    amenities_list.append(item.strip())

        if amenities_list:
            counts = Counter(amenities_list).most_common(10)
            pills_html = " ".join([
                f'<span class="badge badge-gold">{name} <strong>({qty})</strong></span>'
                for name, qty in counts
            ])
            st.markdown(f'<div style="line-height: 2.2;">{pills_html}</div>', unsafe_allow_html=True)
        else:
            st.caption("No specific amenities detected in the texts.")

    # 2. Financing and suites metrics
    with col2:
        st.markdown("**Structure & Financing Conditions**")
        financing_count = 0
        if "financing_accepted" in df.columns:
            financing_count = int(df["financing_accepted"].fillna(False).astype(bool).sum())
        
        has_suites_count = 0
        if "suites" in df.columns:
            has_suites_count = int((pd.to_numeric(df["suites"], errors="coerce") > 0).sum())

        st.markdown(
            f"""
            <div style="background: var(--bg-surface); border: 1px solid var(--border-card); 
                        border-radius: 8px; padding: 14px 16px; font-size: 13px; line-height: 1.8;">
                <div><strong>Financing / Mortgages Accepted:</strong> {financing_count} properties</div>
                <div><strong>Confirmed Suite(s):</strong> {has_suites_count} properties</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("---")

    # 3. Best Price per m² Table
    st.markdown("**Properties by Price per Square Meter (R$/m²)**")
    calc_df = df.copy()
    calc_df["num_price"] = calc_df["price"].dropna().apply(_clean_price)
    calc_df["num_area"] = pd.to_numeric(calc_df.get("area_m2"), errors="coerce")
    calc_df["price_per_m2"] = calc_df.apply(
        lambda r: (r["num_price"] / r["num_area"]) if r["num_price"] > 0 and r["num_area"] > 0 else None,
        axis=1
    )

    valid_m2 = calc_df.dropna(subset=["price_per_m2"]).sort_values("price_per_m2", ascending=True)
    if not valid_m2.empty:
        preview_m2 = valid_m2[["title", "price", "area_m2", "price_per_m2", "neighborhood", "source_url"]].head(8).copy()
        preview_m2["price_per_m2"] = preview_m2["price_per_m2"].apply(lambda v: f"R$ {v:,.2f}/m²".replace(",", "X").replace(".", ",").replace("X", "."))
        
        st.dataframe(
            preview_m2,
            column_config={
                "title": st.column_config.TextColumn("Title", width="large"),
                "price": st.column_config.TextColumn("Total Price"),
                "area_m2": st.column_config.NumberColumn("Area (m²)", format="%.0f m²"),
                "price_per_m2": st.column_config.TextColumn("Price / m²"),
                "neighborhood": st.column_config.TextColumn("Neighborhood"),
                "source_url": st.column_config.LinkColumn("Link")
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.caption("Insufficient area and price data to calculate price per square meter.")
