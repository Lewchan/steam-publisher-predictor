from __future__ import annotations

import pandas as pd
import streamlit as st

from steam_publisher_predictor.models import ManualInputs
from steam_publisher_predictor.services.calculator import calculate_sales
from steam_publisher_predictor.services.steam_client import SteamClient, SteamClientError


def main() -> None:
    st.set_page_config(page_title="Steam Publisher Predictor", page_icon="chart_with_upwards_trend", layout="wide")
    st.title("Steam Publisher Predictor")
    st.caption("Fetch Steam data, score quality, map user pool, then estimate sales with the structured model.")

    client = SteamClient()
    query = st.text_input(
        "Game name, Steam URL, or app id",
        placeholder="e.g. Balatro or https://store.steampowered.com/app/2379780/",
    )

    if st.button("Fetch Steam Data", type="primary", use_container_width=True):
        if not query.strip():
            st.warning("Enter a game name, Steam URL, or app id first.")
        else:
            with st.spinner("Fetching Steam store data..."):
                try:
                    st.session_state["fetched_game"] = client.fetch_game(query)
                except SteamClientError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"Unexpected error: {exc}")

    game = st.session_state.get("fetched_game")
    if not game:
        st.info("Fetch a Steam game first. The calculator form appears after data is loaded.")
        return

    left, right = st.columns([1.05, 0.95])
    with left:
        _render_game_summary(game)
    with right:
        manual_inputs = _render_manual_inputs(game.price_usd)

    result = calculate_sales(game, manual_inputs)

    metric_columns = st.columns(4)
    metric_columns[0].metric("Estimated sales", f"{result.sales:,.0f}")
    metric_columns[1].metric("CL score", f"{result.cl_score:.2f} / 3.00")
    metric_columns[2].metric("Quality score", f"{result.quality.quality_score:.2f} / 10")
    metric_columns[3].metric("User pool", f"{result.user_pool.estimated_user_pool:,}")

    top_left, top_right = st.columns(2)
    with top_left:
        st.subheader("Quality Breakdown")
        quality_rows = [
            ["Rating strength", f"{result.quality.rating_strength:.2f}"],
            ["Rating confidence", f"{result.quality.rating_confidence:.2%}"],
            ["Proof strength", f"{result.quality.proof_strength:.2f}"],
            ["Discussion count signal", f"{result.quality.discussion_count_signal:.2f}"],
            ["Discussion engagement signal", f"{result.quality.discussion_engagement_signal:.2f}"],
            ["Discussion sentiment signal", f"{result.quality.discussion_sentiment_signal:.2f}"],
            ["Discussion strength", f"{result.quality.discussion_strength:.2f}"],
            ["Persistence strength", f"{result.quality.persistence_strength:.2f}"],
            ["Analyst adjustment", f"{result.quality.analyst_adjustment:+.2f}"],
            ["Quality confidence", f"{result.quality.quality_confidence:.2%}"],
        ]
        st.table(pd.DataFrame(quality_rows, columns=["Metric", "Value"]))
        if result.quality.missing_quality_sources:
            st.caption("Missing quality sources: " + ", ".join(result.quality.missing_quality_sources))

    with top_right:
        st.subheader("User Pool Breakdown")
        if result.user_pool.matches:
            pool_rows = [
                {
                    "bucket": match.genre_name,
                    "source": match.source_label,
                    "mapping_weight": round(match.mapping_weight, 2),
                    "base_pool": match.base_pool,
                    "weighted_pool": int(match.weighted_pool),
                }
                for match in result.user_pool.matches
            ]
            st.dataframe(pd.DataFrame(pool_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No pool buckets matched the current Steam tags yet.")

        st.table(
            pd.DataFrame(
                [
                    ["Weighted genre sum", f"{result.user_pool.weighted_genre_sum:,.0f}"],
                    ["Overlap adjustment", f"{result.user_pool.overlap_adjustment:.2f}"],
                    ["Platform fit", f"{result.user_pool.platform_fit:.2f}"],
                    ["Region fit", f"{result.user_pool.region_fit:.2f}"],
                    ["Price fit", f"{result.user_pool.price_fit:.2f}"],
                    ["Final user pool", f"{result.user_pool.estimated_user_pool:,}"],
                ],
                columns=["Metric", "Value"],
            )
        )

    bottom_left, bottom_right = st.columns(2)
    with bottom_left:
        st.subheader("CL Breakdown")
        st.table(
            pd.DataFrame(
                [
                    ["CL base raw", f"{result.cl_base_raw:,.0f}"],
                    ["CL base", f"{result.cl_base:.4f}"],
                    ["Amplification total", f"{result.amplification_tag_total:.2f}"],
                    ["Showmanship raw", f"{result.showmanship_raw:.3f}"],
                    ["Showmanship effect", f"{result.showmanship_effect:.3f}"],
                    ["Brand factor", f"{result.brand_factor:.3f}"],
                    ["CL raw", f"{result.cl_raw:.3f}"],
                    ["CL capped", f"{result.cl_score:.3f}"],
                ],
                columns=["Metric", "Value"],
            )
        )

    with bottom_right:
        st.subheader("Sales Breakdown")
        sales_rows = [
            ["Base conversion", f"{result.base_conversion:.4f}"],
            ["Exposure", f"{result.manual_inputs.exposure_base:.2f}"],
            ["Intent", f"{result.manual_inputs.intent_base:.2f}"],
            ["Purchase", f"{result.manual_inputs.purchase_base:.2f}"],
            ["Estimated sales", f"{result.sales:,.0f}"],
            [
                "Annual long tail",
                "N/A" if result.annual_long_tail_sales is None else f"{result.annual_long_tail_sales:,.0f}",
            ],
        ]
        st.table(pd.DataFrame(sales_rows, columns=["Metric", "Value"]))

    with st.expander("Model notes"):
        st.markdown(
            """
            - `CL` uses a weighted linear model with a hard cap of `3.0`.
            - Quality is estimated from Steam reviews, review volume, discussion proxies, and analyst adjustment.
            - User pool is table-driven from Steam genres, tags, and category hints.
            - This build favors transparent intermediate values over false precision.
            """
        )


def _render_game_summary(game) -> None:
    st.subheader(game.name)
    st.link_button("Open Steam page", game.url)
    st.write(game.short_description or "No short description found.")
    st.table(
        pd.DataFrame(
            [
                ["App ID", game.app_id],
                ["Price (USD)", game.price_usd],
                ["Reviews", game.review_count],
                ["Review score", game.review_score],
                ["Metacritic", game.metacritic_score],
                ["Release date", game.release_date or "Unknown"],
                ["Coming soon", "Yes" if game.coming_soon else "No"],
                ["Developers", ", ".join(game.developer_names) or "Unknown"],
                ["Publishers", ", ".join(game.publisher_names) or "Unknown"],
                ["Genres", ", ".join(game.genres) or "Unknown"],
                ["Steam tags", ", ".join(game.steam_tags[:12]) or "Unknown"],
            ],
            columns=["Field", "Value"],
        )
    )


def _render_manual_inputs(default_price: float) -> ManualInputs:
    st.subheader("Manual Inputs")
    design_left, design_right = st.columns(2)
    with design_left:
        art_base = st.slider("Art base", 1.0, 10.0, 6.0, 0.5)
        gameplay_depth = st.slider("Gameplay depth", 1.0, 10.0, 7.0, 0.5)
        scope = st.slider("Scope", 1.0, 10.0, 6.0, 0.5)
        narrative = st.slider("Narrative", 1.0, 10.0, 5.0, 0.5)
        ip_factor = st.slider("IP factor", 0.0, 1.0, 0.2, 0.05)
        influencer_factor = st.slider("Influencer factor", 0.0, 1.0, 0.25, 0.05)

    with design_right:
        exposure_base = st.slider("Exposure base", 0.0, 1.0, 0.2, 0.01)
        intent_base = st.slider("Intent base", 0.0, 1.0, 0.25, 0.01)
        purchase_base = st.slider("Purchase base", 0.0, 1.0, 0.3, 0.01)
        platform_fit = st.slider("Platform fit", 0.5, 1.2, 1.0, 0.05)
        region_fit = st.slider("Region fit", 0.5, 1.2, 1.0, 0.05)
        price_fit_default = 1.0 if default_price <= 25 else 0.9
        price_fit = st.slider("Price fit", 0.5, 1.2, price_fit_default, 0.05)

    pool_left, pool_right = st.columns(2)
    with pool_left:
        overlap_adjustment = st.slider("Overlap adjustment", 0.55, 0.95, 0.75, 0.01)
        user_pool_override = st.number_input("User pool override", min_value=0, value=0, step=100000)
        peak_dau = st.number_input("Peak DAU", min_value=0, value=0, step=1000)
        median_line = st.slider("Median line", 0.0, 1.0, 0.0, 0.01)
    with pool_right:
        discussion_manual_score = st.slider("Discussion manual score", 0.0, 10.0, 5.0, 0.5)
        persistence_manual_score = st.slider("Persistence manual score", 0.0, 10.0, 5.0, 0.5)
        analyst_adjustment = st.slider("Analyst adjustment", -1.5, 1.5, 0.0, 0.1)

    st.markdown("**Amplification tags**")
    tag_columns = st.columns(3)
    sexual_or_gore = tag_columns[0].checkbox("Sexual or gore")
    extreme_novelty = tag_columns[1].checkbox("Extreme novelty")
    real_time_juice = tag_columns[2].checkbox("Real-time juice")
    systemic_interlock = tag_columns[0].checkbox("Systemic interlock")
    complex_system = tag_columns[1].checkbox("Complex system")
    linear_experience = tag_columns[2].checkbox("Linear experience")

    return ManualInputs(
        art_base=art_base,
        gameplay_depth=gameplay_depth,
        scope=scope,
        narrative=narrative,
        ip_factor=ip_factor,
        influencer_factor=influencer_factor,
        exposure_base=exposure_base,
        intent_base=intent_base,
        purchase_base=purchase_base,
        platform_fit=platform_fit,
        region_fit=region_fit,
        price_fit=price_fit,
        overlap_adjustment=overlap_adjustment,
        user_pool_override=user_pool_override,
        discussion_manual_score=discussion_manual_score,
        persistence_manual_score=persistence_manual_score,
        analyst_adjustment=analyst_adjustment,
        peak_dau=peak_dau,
        median_line=median_line,
        sexual_or_gore=sexual_or_gore,
        extreme_novelty=extreme_novelty,
        real_time_juice=real_time_juice,
        systemic_interlock=systemic_interlock,
        complex_system=complex_system,
        linear_experience=linear_experience,
    )
