from __future__ import annotations

import pandas as pd
import streamlit as st

from steam_publisher_predictor.models import ManualInputs
from steam_publisher_predictor.services import calculator
from steam_publisher_predictor.services import benchmark as benchmark_service
from steam_publisher_predictor.services import scenarios as scenario_service
from steam_publisher_predictor.services.steam_client import SteamClient, SteamClientError
from steam_publisher_predictor.services.storage import record as storage


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

    result = calculator.calculate_sales(game, manual_inputs)

    metric_columns = st.columns(4)
    metric_columns[0].metric("Estimated sales", f"{result.sales:,.0f}")
    metric_columns[1].metric("CL score", f"{result.cl_score:.2f} / 3.00")
    metric_columns[2].metric("Quality score", f"{result.quality.quality_score:.2f} / 10")
    metric_columns[3].metric("User pool", f"{result.user_pool.estimated_user_pool:,}")

    # Save record button
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("💾 Save Prediction", type="primary", use_container_width=True):
            try:
                filepath = storage.save_prediction_record(result, query.strip())
                st.success(f"Saved to: `{filepath.name}`")
                st.session_state["save_message"] = f"Saved to: {filepath.name}"
            except Exception as exc:
                st.error(f"Save failed: {exc}")
                st.session_state["save_message"] = f"Save failed: {exc}"

    if st.session_state.get("save_message"):
        st.info(st.session_state["save_message"])
        st.session_state["save_message"] = ""

    top_left, top_right = st.columns(2)
    with top_left:
        st.subheader("Quality Breakdown")
        # Quality confidence warning
        quality_confidence = result.quality.quality_confidence
        confidence_pct = quality_confidence * 100
        missing_sources = result.quality.missing_quality_sources
        if confidence_pct < 40 or len(missing_sources) >= 3:
            st.warning(
                f"⚠️ **质量评估置信度低 ({confidence_pct:.0f}%)** — 部分数据源缺失，建议人工校准。"
                + (f" 缺失源：{', '.join(missing_sources)}" if missing_sources else "")
            )
        elif confidence_pct < 70:
            st.info(
                f"🔸 **质量评估置信度中等 ({confidence_pct:.0f}%)** — 基于部分公开数据，"
                + (f"缺失源：{', '.join(missing_sources)}" if missing_sources else "结果仅供参考，建议人工校准。")
            )
        else:
            st.success(f"✅ **质量评估置信度高 ({confidence_pct:.0f}%)** — 基于充足的数据源，结果可信度较高。")

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

    if game.steamdb:
        st.subheader("SteamDB Signals")
        steamdb_rows = [
            ["Current players", f"{game.steamdb.current_players:,}" if game.steamdb.current_players else "N/A"],
            ["24h peak", f"{game.steamdb.peak_24h:,}" if game.steamdb.peak_24h else "N/A"],
            ["All-time peak", f"{game.steamdb.all_time_peak:,}" if game.steamdb.all_time_peak else "N/A"],
            ["Followers", f"{game.steamdb.followers:,}" if game.steamdb.followers else "N/A"],
            ["SteamDB rating", f"{game.steamdb.steamdb_rating:.2f}%" if game.steamdb.steamdb_rating else "N/A"],
            ["DAU rank", f"#{game.steamdb.daily_active_users_rank}" if game.steamdb.daily_active_users_rank else "N/A"],
            ["Top sellers rank", f"#{game.steamdb.top_sellers_rank}" if game.steamdb.top_sellers_rank else "N/A"],
            [
                "Wishlist rank",
                f"#{game.steamdb.wishlist_activity_rank}" if game.steamdb.wishlist_activity_rank else "N/A",
            ],
            ["Last 30 days peak", f"{game.steamdb.last_30_days_peak:,}" if game.steamdb.last_30_days_peak else "N/A"],
        ]
        st.table(pd.DataFrame(steamdb_rows, columns=["Metric", "Value"]))
        st.caption("SteamDB data is fetched from the public charts page through a browser-backed adapter.")
        if game.steamdb.unavailable_reason:
            st.warning(f"SteamDB unavailable: {game.steamdb.unavailable_reason}")

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

    # Scenario Comparison section
    st.markdown("---")
    st.subheader("⚖️ Scenario Comparison")
    st.caption("Compare Conservative, Baseline, and Optimistic scenarios side by side.")

    if "scenarios_data" not in st.session_state:
        st.session_state["scenarios_data"] = {}
    if "selected_scenarios" not in st.session_state:
        st.session_state["selected_scenarios"] = ["Conservative", "Baseline", "Optimistic"]

    col_sc1, col_sc2 = st.columns([3, 1])
    with col_sc2:
        preset_names = scenario_service.get_preset_names()
        new_scenario_name = st.text_input(
            "Custom scenario name",
            placeholder="e.g. MyScenario",
            key="new_scenario_name",
        )
        if st.button("Add Custom Scenario", use_container_width=True):
            name = new_scenario_name.strip()
            if name and name not in preset_names and name not in st.session_state.get("saved_scenario_names", []):
                st.session_state.setdefault("saved_scenario_names", []).append(name)
                preset_names.append(name)
                st.success(f"Custom scenario '{name}' added.")
                st.rerun()

    selected = st.multiselect(
        "Select scenarios to compare",
        options=preset_names,
        default=st.session_state["selected_scenarios"],
        key="selected_scenarios_multi",
    )
    if selected != st.session_state["selected_scenarios"]:
        st.session_state["selected_scenarios"] = selected

    if selected:
        scenario_results = {}
        for sname in selected:
            scenario = scenario_service.load_preset(sname)
            sr = scenario_service.run_scenario(scenario, game)
            scenario_results[sname] = sr

        if scenario_results:
            comp_cols = st.columns(len(scenario_results))
            for idx, (sname, sr) in enumerate(scenario_results.items()):
                with comp_cols[idx]:
                    st.markdown(f"### {sname}")
                    risk_colors = {"Conservative": "🟡", "Baseline": "🟢", "Optimistic": "🔴"}
                    emoji = risk_colors.get(sname, "🔵")
                    st.metric(
                        f"{emoji} Estimated Sales",
                        f"{sr.result.sales:,.0f}",
                    )
                    st.metric("CL Score", f"{sr.result.cl_score:.3f}")
                    st.metric("Quality", f"{sr.result.quality.quality_score:.2f}")
                    st.metric("User Pool", f"{sr.result.user_pool.estimated_user_pool:,}")

                    if sr.result.annual_long_tail_sales:
                        st.metric("Annual Long Tail", f"{sr.result.annual_long_tail_sales:,.0f}")

                    st.divider()

                    # Per-scenario manual input sliders
                    st.subheader(f"Edit {sname} Inputs")
                    s = sr.result.manual_inputs
                    s.art_base = st.number_input("Art base", min_value=1.0, max_value=10.0, value=s.art_base, step=0.5, key=f"{sname}_art")
                    s.gameplay_depth = st.number_input("Gameplay depth", min_value=1.0, max_value=10.0, value=s.gameplay_depth, step=0.5, key=f"{sname}_gameplay")
                    s.scope = st.number_input("Scope", min_value=1.0, max_value=10.0, value=s.scope, step=0.5, key=f"{sname}_scope")
                    s.narrative = st.number_input("Narrative", min_value=1.0, max_value=10.0, value=s.narrative, step=0.5, key=f"{sname}_narrative")
                    s.ip_factor = st.slider("IP factor", 0.0, 1.0, s.ip_factor, 0.05, key=f"{sname}_ip")
                    s.influencer_factor = st.slider("Influencer factor", 0.0, 1.0, s.influencer_factor, 0.05, key=f"{sname}_infl")
                    s.exposure_base = st.slider("Exposure base", 0.0, 1.0, s.exposure_base, 0.01, key=f"{sname}_expo")
                    s.intent_base = st.slider("Intent base", 0.0, 1.0, s.intent_base, 0.01, key=f"{sname}_intent")
                    s.purchase_base = st.slider("Purchase base", 0.0, 1.0, s.purchase_base, 0.01, key=f"{sname}_pur")

        # Summary table
        st.markdown("---")
        st.subheader("Scenario Summary Table")
        summary_rows = []
        for sname, sr in scenario_results.items():
            summary_rows.append({
                "Scenario": sname,
                "Sales": f"{sr.result.sales:,.0f}",
                "CL Score": f"{sr.result.cl_score:.3f}",
                "CL Base": f"{sr.result.cl_base:.4f}",
                "Showmanship": f"{sr.result.showmanship_effect:.3f}",
                "Brand Factor": f"{sr.result.brand_factor:.3f}",
                "Quality": f"{sr.result.quality.quality_score:.2f}",
                "Quality Conf": f"{sr.result.quality.quality_confidence:.0%}",
                "User Pool": f"{sr.result.user_pool.estimated_user_pool:,}",
                "Exposure": f"{sr.result.manual_inputs.exposure_base:.2f}",
                "Intent": f"{sr.result.manual_inputs.intent_base:.2f}",
                "Purchase": f"{sr.result.manual_inputs.purchase_base:.2f}",
            })
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

        # Saved scenarios list
        saved = scenario_service.list_saved_scenarios()
        if saved:
            st.markdown("---")
            st.subheader("Saved Scenarios")
            col_del1, col_del2 = st.columns([4, 1])
            with col_del1:
                st.info(f"Saved scenarios: {', '.join(saved)}")
            with col_del2:
                del_name = st.selectbox("Delete", saved, key="delete_scenario_select")
                if st.button("Delete", use_container_width=True):
                    scenario_service.delete_scenario(del_name)
                    st.rerun()

    # Saved Records section
    st.markdown("---")
    st.subheader("Saved Predictions")
    records = storage.list_records(limit=20)
    if records:
        record_rows = [
            {
                "Time": r.get("created_at", "")[:19],
                "Game": r.get("game_name") or r.get("query", "Unknown"),
                "Sales": f"{r.get('sales', 0):,.0f}" if r.get("sales") else "N/A",
                "ID": r.get("record_id", "")[:8],
            }
            for r in records
        ]
        st.dataframe(pd.DataFrame(record_rows), use_container_width=True, hide_index=True)
        st.caption(f"Showing {len(records)} most recent records.")
    else:
        st.info("No saved predictions yet. Run an analysis and click 'Save Prediction' to persist it.")

    # Benchmark Comparison section
    st.markdown("---")
    st.subheader("📊 Benchmark Comparison")
    st.caption("Compare current analysis against reference games with known sales figures.")

    # Load benchmark data
    benchmark_file = benchmark_service.load_benchmark_file()
    if benchmark_file is None:
        benchmark_service.ensure_benchmark_exists()
        benchmark_file = benchmark_service.load_benchmark_file()

    if benchmark_file and benchmark_file.records:
        comparison_rows = benchmark_service.compare_vs_benchmarks(result, benchmark_file.records)

        diff_rows = [
            {
                "Benchmark": r.benchmark_game,
                "Quality": f"{r.quality_score:.1f}",
                "Quality Δ": f"{r.quality_diff:+.2f}",
                "CL": f"{r.cl_score:.2f}",
                "CL Δ": f"{r.cl_diff:+.2f}",
                "User Pool": f"{r.user_pool:,}",
                "Pool Δ": f"{r.pool_diff:,.0f}",
                "Sales": f"{r.sales:,}",
                "Sales Δ": f"{r.sales_diff:,.0f}",
                "SAO Δ": f"{r.sao_diff:,.0f}" if r.sao_diff is not None else "N/A",
            }
            for r in comparison_rows
        ]

        st.dataframe(pd.DataFrame(diff_rows), use_container_width=True, hide_index=True)

        st.markdown("**Reference data sources:**")
        ref_rows = [
            ["Game", "Sales", "Quality", "SAO Anchor", "Source"],
        ]
        for rec in benchmark_file.records:
            ref_rows.append([
                rec.game_name,
                f"{rec.sales:,}",
                f"{rec.quality_score:.1f}",
                f"{rec.sao_anchor:,}" if rec.sao_anchor else "N/A",
                rec.source_label,
            ])
        st.table(pd.DataFrame(ref_rows, columns=["Game", "Sales", "Quality", "SAO Anchor", "Source"]))
        st.caption("⚠ SAO_Anchor is a virtual ceiling (SAO = Sales as Of date), not a real sample. Differences are computed as: Current Result − Benchmark Value.")
    else:
        st.info("No benchmark data available. Benchmark seed records will be created automatically on the next run.")


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
                ["SteamDB", game.steamdb.url if game.steamdb else "Unavailable"],
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
