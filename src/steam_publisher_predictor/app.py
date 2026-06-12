# Webber 2026/06/13 迭代: 校准种子游戏对比增强 (P2) — 多维偏差可视化 + 结构化详情卡片 + 单游戏选择 + 导出功能
from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path

import httpx
import pandas as pd
import streamlit as st

from steam_publisher_predictor.models import ManualInputs
from steam_publisher_predictor.services import calculator
from steam_publisher_predictor.services import benchmark as benchmark_service
from steam_publisher_predictor.services import scenarios as scenario_service
from steam_publisher_predictor.services import calibration as cal_service
from steam_publisher_predictor.services.steam_client import SteamClient, SteamClientError
from steam_publisher_predictor.services.storage import record as storage

# ---------------------------------------------------------------------------
# API helpers (used by Streamlit UI to talk to the FastAPI backend)
# ---------------------------------------------------------------------------

_API_BASE = os.environ.get("SP_API_URL", "http://localhost:8000")


def _fetch_discussion(game_query: str) -> dict | None:
    """Fetch discussion data via the FastAPI backend."""
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.post(f"{_API_BASE}/api/discussion", json={"query": game_query})
            if resp.status_code == 200:
                return resp.json()
            return None
    except Exception:
        return None


def _get_calibration() -> dict | None:
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{_API_BASE}/api/calibration")
            if resp.status_code == 200:
                return resp.json()
            return None
    except Exception:
        return None


def _update_calibration(updates: dict) -> dict | None:
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.put(f"{_API_BASE}/api/calibration", json=updates)
            if resp.status_code == 200:
                return resp.json()
            return None
    except Exception:
        return None


def _get_seed_cal_games() -> list[dict] | None:
    """Fetch calibration seed games from the FastAPI backend."""
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{_API_BASE}/api/cal_games")
            if resp.status_code == 200:
                return resp.json().get("games", [])
            return None
    except Exception:
        return None


def _run_calibrate_api() -> dict | None:
    """Run calibration on all seed games via the FastAPI backend."""
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(f"{_API_BASE}/api/calibrate", json={})
            if resp.status_code == 200:
                return resp.json()
            return None
    except Exception:
        return None


def _export_csv(result, game) -> bytes:
    """Export benchmark comparison + scenario summary as CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Section", "Metric", "Value"])
    # Benchmark comparison
    writer.writerow(["Benchmark Comparison", "", ""])
    benchmark_file = benchmark_service.load_benchmark_file()
    if benchmark_file and benchmark_file.records:
        comparison_rows = benchmark_service.compare_vs_benchmarks(result, benchmark_file.records)
        writer.writerow(["Benchmark", "Game", "Quality", "Quality Δ", "CL", "CL Δ", "User Pool", "Pool Δ", "Sales", "Sales Δ"])
        for r in comparison_rows:
            writer.writerow([
                r.benchmark_game,
                r.benchmark_game,
                f"{r.quality_score:.1f}",
                f"{r.quality_diff:+.2f}",
                f"{r.cl_score:.2f}",
                f"{r.cl_diff:+.2f}",
                f"{r.user_pool:,}",
                f"{r.pool_diff:,.0f}",
                f"{r.sales:,}",
                f"{r.sales_diff:,.0f}",
            ])
    # Scenario summary
    writer.writerow(["Scenario Comparison", "", ""])
    scenarios_data = st.session_state.get("scenarios_data", {})
    for sname, sr in scenarios_data.items():
        writer.writerow([sname, "Sales", f"{sr.result.sales:,.0f}"])
        writer.writerow([sname, "CL Score", f"{sr.result.cl_score:.3f}"])
        writer.writerow([sname, "Quality", f"{sr.result.quality.quality_score:.2f}"])
        writer.writerow([sname, "User Pool", f"{sr.result.user_pool.estimated_user_pool:,}"])
    return output.getvalue().encode("utf-8")


def _export_json(result, game) -> bytes:
    """Export full analysis result as JSON."""
    from dataclasses import asdict
    export_data = {
        "game": {
            "name": game.name,
            "app_id": game.app_id,
            "price_usd": game.price_usd,
            "release_date": game.release_date,
        },
        "sales": result.sales,
        "cl_score": result.cl_score,
        "quality": asdict(result.quality) if hasattr(result.quality, "__dataclass_fields__") else vars(result.quality),
        "user_pool": {
            "estimated_user_pool": result.user_pool.estimated_user_pool,
        },
        "manual_inputs": asdict(result.manual_inputs) if hasattr(result.manual_inputs, "__dataclass_fields__") else vars(result.manual_inputs),
    }
    return json.dumps(export_data, indent=2, ensure_ascii=False).encode("utf-8")


def main() -> None:
    st.set_page_config(page_title="Steam Publisher Predictor", page_icon="chart_with_upwards_trend", layout="wide")
    st.markdown("""
    <style>
    /* Webber 2026/06/12 移动端响应式优化 */
    @media (max-width: 768px) {
        .stDataFrame { font-size: 12px !important; }
        .stMetric { font-size: 14px !important; }
        .stSubheader { font-size: 18px !important; }
        .stCaption { font-size: 12px !important; }
        .css-1r6slb0 { padding: 8px !important; }
        section.main > div { padding-top: 2rem !important; }
        .stNumberInput > div > div { font-size: 14px !important; }
        .stSlider > div { padding: 0 4px !important; }
    }
    /* Touch-friendly number inputs */
    input[type="number"] { min-height: 44px !important; font-size: 16px !important; }
    /* Wider tables on mobile */
    .stDataFrame div[role="table"] { overflow-x: auto !important; }
    </style>
    """, unsafe_allow_html=True)
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

        # ★ Next-iteration: SteamDB + Quality linkage
        if st.button("📊 查看 SteamDB 与质量评分联动", use_container_width=True):
            st.info(f"SteamDB 信号用于补充质量评估的 **Discussion strength** 和 **Persistence strength** 计算。"
                    f"当前质量评估置信度: {confidence_pct:.0f}%。"
                    f"SteamDB 的 Current Players ({game.steamdb.current_players or 'N/A'}) "
                    f"和 24h Peak ({game.steamdb.peak_24h or 'N/A'}) 可作为讨论强度的辅助信号。")

    # ★ New: Discussion Data Panel
    st.markdown("---")
    st.subheader("💬 讨论数据面板")
    st.caption("Across-platform discussion data: Reddit, YouTube, Bilibili. Improves quality confidence.")

    col_disc_left, col_disc_right = st.columns([3, 1])
    with col_disc_left:
        disc_query = st.text_input(
            "Game query for discussion",
            value=query.strip(),
            key="disc_query_input",
        )
    with col_disc_right:
        disc_fetch = st.button("🔍 Fetch Discussion Data", type="primary", use_container_width=True)

    disc_results = st.session_state.get("disc_results")
    if disc_fetch and disc_query.strip():
        with st.spinner("Fetching discussion data across platforms..."):
            disc_data = _fetch_discussion(disc_query.strip())
            if disc_data:
                st.session_state["disc_results"] = disc_data
                disc_results = disc_data
                st.session_state["disc_game_name"] = disc_query.strip()
            else:
                st.warning("Discussion API returned no data. Backend may be running on a different URL. Set SP_API_URL env var.")

    if disc_results:
        # Show registered sources summary
        sources = disc_results.get("sources", [])
        total_sources = len(sources)
        success_sources = sum(1 for s in sources if s.get("status") == "normal")
        disc_confidence = success_sources / total_sources if total_sources > 0 else 0

        metric_cols = st.columns(4)
        metric_cols[0].metric("讨论源总数", total_sources)
        metric_cols[1].metric("成功源数", success_sources)
        metric_cols[2].metric("讨论质量评分", f"{disc_confidence:.0%}")

        success_sources_list = [s for s in sources if s.get("status") == "normal"]
        failed_sources_list = [s for s in sources if s.get("status") != "normal"]

        # Discussion quality summary cards — aligned with index.html progress bars
        st.markdown("**📊 讨论数据 → 质量评分贡献**")

        # Aggregate detail text (aligned with index.html renderDiscussionQualitySummary)
        total_items = sum(src.get("total_results", 0) for src in sources)
        detail_text = f"共 {total_items} 条讨论结果，来自 {success_sources}/{total_sources} 个可用源"

        # Derive discussion quality signals from the analysis result (Webber 2026/06/12 fix)
        disc_count_signal = result.quality.discussion_count_signal
        disc_engagement_signal = result.quality.discussion_engagement_signal
        disc_strength = result.quality.discussion_strength
        confidence_pct = result.quality.quality_confidence * 100

        # Helper: progress bar helper
        def _disc_progress_bar(label: str, value: float, total: float, detail: str, confidence_pct: float = None) -> None:
            pct = min(1.0, value / total) if total > 0 else 0.0
            color = "#1f7a52" if value >= 6 else ("#d55b2d" if value >= 3 else "#888")
            st.markdown(
                f"**{label}**: <span style='font-size:20px;font-weight:700;color:{color};'>{value:.1f}</span>"
                f" <span style='color:#666;'>/ {total}</span> — {detail}",
                unsafe_allow_html=True,
            )
            st.progress(pct)

        _disc_progress_bar(
            "讨论数量信号",
            disc_count_signal,
            10.0,
            detail_text,
        )
        _disc_progress_bar(
            "讨论互动信号",
            disc_engagement_signal,
            10.0,
            f"总互动信号来自 {total_sources} 个数据源",
        )
        _disc_progress_bar(
            "讨论强度综合评分",
            disc_strength,
            10.0,
            f"权重: 数量45% + 互动45% + 热点10%",
        )
        _disc_progress_bar(
            "数据置信度",
            disc_confidence * 100,
            100.0,
            f"{'数据来源充分' if disc_confidence >= 0.7 else '部分数据源不可用，评分可能不完整'}",
        )

        # Per-source detailed data — aligned with index.html discussion cards
        available_sources_text = " | ".join(f"✅ {s}" for s in [src.get("source_type", "?") for src in sources if src.get("status") == "normal"]) if sources else "无"
        failed_sources_text = " | ".join(f"❌ {s}" for s in [src.get("source_type", "?") for src in sources if src.get("status") != "normal"]) if sources else "无"
        st.markdown(f"**可用源**: {available_sources_text}  |  **不可用源**: {failed_sources_text}")

        if success_sources_list:
            st.markdown("**📋 各平台详细数据**")
            for src in success_sources_list:
                with st.expander(f"📌 {src.get('source_type', 'unknown')} ({src.get('total_results', 0)} 条结果)", expanded=False):
                    # Show summary table
                    src_items = src.get("normalized", [])
                    if src_items:
                        item_rows = [
                            {
                                "标题": item.get("title", "N/A")[:60],
                                "👍": item.get("upvotes", 0),
                                "💬": item.get("comments", 0),
                                "📅": item.get("published", "N/A"),
                            }
                            for item in src_items[:20]
                        ]
                        st.dataframe(pd.DataFrame(item_rows), use_container_width=True, hide_index=True)

                        # Top videos by engagement (YouTube/Bilibili specific)
                        top_videos = src.get("top_videos", [])
                        if top_videos:
                            st.markdown("**🎬 Top 10 热门视频**")
                            video_rows = [
                                {
                                    "标题": v.get("title", "N/A")[:50],
                                    "播放量": v.get("total_views", 0),
                                    "点赞": v.get("likes", 0),
                                    "评论": v.get("comments", 0),
                                    "情感分": f"{v.get('sentiment', 0):.3f}",
                                }
                                for v in top_videos[:10]
                            ]
                            st.dataframe(pd.DataFrame(video_rows), use_container_width=True, hide_index=True)
                    else:
                        st.caption(f"{src.get('source_type', 'unknown')}: 未找到相关讨论")

        # Show failed sources with error messages
        if failed_sources_list:
            st.markdown("**⚠️ 获取失败的数据源**")
            for src in failed_sources_list:
                err_msg = src.get("error_message", "Unknown error")
                st.warning(f"**{src.get('source_type', 'unknown')}**: {err_msg}")

        # Quality confidence action suggestions (aligned with index.html)
        if confidence_pct < 40 or len(result.quality.missing_quality_sources) >= 3:
            st.warning(
                f"⚠️ **低置信度建议**: 当前质量评估置信度仅 {confidence_pct:.0f}%。"
                "以上讨论数据可作为补充信息，帮助提升讨论强度信号 → 提升整体质量评分。"
                "建议前往手动参数面板人工校准讨论相关评分。"
            )
        elif confidence_pct < 70:
            st.info(
                f"🔸 **中等置信度建议**: 当前质量评估置信度 {confidence_pct:.0f}%。"
                "建议参考以上讨论数据，并在手动参数面板中调整 Discussion manual score。"
            )

        # Discussion data export (aligned with index.html discussion export)
        st.markdown("---")
        col_export1, col_export2 = st.columns(2)
        with col_export1:
            if st.button("📥 导出讨论数据 CSV", use_container_width=True):
                if disc_results and sources:
                    # Flatten all discussion items into rows
                    export_rows = []
                    for src in sources:
                        src_name = src.get("source_type", "unknown")
                        items = src.get("normalized", [])
                        for item in items:
                            export_rows.append({
                                "source": src_name,
                                "title": item.get("title", ""),
                                "upvotes": item.get("upvotes", 0),
                                "comments": item.get("comments", 0),
                                "views": item.get("views", 0),
                                "published": item.get("published", ""),
                                "url": item.get("url", ""),
                                "has_hot_content": item.get("has_hot_content", False),
                            })
                    # Add summary row
                    export_rows.insert(0, {"source": "SUMMARY", "title": "讨论汇总", "upvotes": "", "comments": "", "views": "", "published": "", "url": "", "has_hot_content": ""})
                    if export_rows:
                        df_export = pd.DataFrame(export_rows)
                        csv_buffer = io.StringIO()
                        df_export.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
                        st.download_button(
                            label="下载 CSV",
                            data=csv_buffer.getvalue(),
                            file_name=f"discussion_data_{query.strip()}.csv",
                            mime="text/csv",
                            use_container_width=True,
                        )
                        st.success(f"导出 {total_items} 条讨论数据（{total_sources} 个数据源）")
                else:
                    st.info("暂无讨论数据可导出")
        with col_export2:
            if st.button("📥 导出讨论数据 JSON", use_container_width=True):
                if disc_results:
                    json_str = json.dumps(disc_results, ensure_ascii=False, indent=2)
                    st.download_button(
                        label="下载 JSON",
                        data=json_str,
                        file_name=f"discussion_data_{query.strip()}.json",
                        mime="application/json",
                        use_container_width=True,
                    )
                    st.success("JSON 数据已准备下载")
                else:
                    st.info("暂无讨论数据可导出")

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

    # ★ New: Calibration Controls Panel
    st.markdown("---")
    st.subheader("⚙️ 校准控制面板")
    st.caption("Adjust quality weight distribution and upper limits. Changes affect subsequent analysis calculations.")

    col_cal1, col_cal2 = st.columns([2, 1])
    with col_cal1:
        cal_cfg = _get_calibration()
        if cal_cfg and "calibration" in cal_cfg:
            cfg = cal_cfg["calibration"]
            st.markdown("**权重分配** (总和应为 1.0)")
            w_cols = st.columns(4)
            new_rating_w = w_cols[0].number_input("Rating", min_value=0.0, max_value=1.0, value=cfg.get("rating_weight", 0.35), step=0.05, key="cal_rating_w")
            new_proof_w = w_cols[1].number_input("Proof", min_value=0.0, max_value=1.0, value=cfg.get("proof_weight", 0.25), step=0.05, key="cal_proof_w")
            new_disc_w = w_cols[2].number_input("Discussion", min_value=0.0, max_value=1.0, value=cfg.get("discussion_weight", 0.25), step=0.05, key="cal_disc_w")
            new_persist_w = w_cols[3].number_input("Persistence", min_value=0.0, max_value=1.0, value=cfg.get("persistence_weight", 0.15), step=0.05, key="cal_persist_w")
            total_w = new_rating_w + new_proof_w + new_disc_w + new_persist_w
            w_color = "🟢" if abs(total_w - 1.0) < 0.01 else "🔴"
            st.caption(f"{w_color} 权重总和: {total_w:.2f}")
        else:
            st.info("校准配置加载失败。请确保 FastAPI 后端正在运行（SP_API_URL 环境变量已设置）。")
    with col_cal2:
        st.markdown("**上限控制**")
        showmanship_cap = st.number_input("Showmanship cap", min_value=0.0, max_value=1.0, value=0.6, step=0.05, key="cal_showcap")
        cl_cap = st.number_input("CL cap", min_value=0.0, max_value=5.0, value=3.0, step=0.1, key="cal_clcap")
        quality_threshold = st.number_input("Quality threshold", min_value=0.0, max_value=10.0, value=4.0, step=0.5, key="cal_qthresh")

    if cal_cfg and "calibration" in cal_cfg:
        if st.button("💾 保存校准配置", type="primary", use_container_width=True):
            try:
                updates = {
                    "rating_weight": new_rating_w,
                    "proof_weight": new_proof_w,
                    "discussion_weight": new_disc_w,
                    "persistence_weight": new_persist_w,
                    "showmanship_cap": showmanship_cap,
                    "cl_cap": cl_cap,
                    "quality_threshold": quality_threshold,
                }
                result_resp = _update_calibration(updates)
                if result_resp:
                    st.success("✅ 校准配置已保存")
                else:
                    st.error("保存失败，请检查后端日志。")
            except Exception as exc:
                st.error(f"校准保存失败: {exc}")

    # ★ New: Export section (after model notes)
    st.markdown("---")
    st.subheader("📦 数据导出")
    st.caption("Export benchmark comparison and analysis results.")

    exp_col1, exp_col2 = st.columns(2)
    with exp_col1:
        if st.button("📄 导出为 CSV", use_container_width=True):
            csv_data = _export_csv(result, game)
            st.download_button(
                label="下载 CSV",
                data=csv_data,
                file_name=f"steam_predictor_{game.name.replace(' ', '_')}_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
    with exp_col2:
        if st.button("📋 导出为 JSON", use_container_width=True):
            json_data = _export_json(result, game)
            st.download_button(
                label="下载 JSON",
                data=json_data,
                file_name=f"steam_predictor_{game.name.replace(' ', '_')}_{pd.Timestamp.now().strftime('%Y%m%d')}.json",
                mime="application/json",
            )

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
            # Save to session_state for export
            st.session_state["scenarios_data"] = scenario_results
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

    # ★ Calibration Seed Game Comparison (Enhanced P2 - 对标 index.html 的校准面板)
    st.markdown("---")
    st.subheader("🎯 校准种子游戏对比")
    st.caption("对预定义的标杆游戏运行完整的销量预测公式，将计算结果与预期范围对照，识别模型偏差方向与幅度。")

    if "cal_games_data" not in st.session_state:
        st.session_state["cal_games_data"] = None
    if "cal_loading" not in st.session_state:
        st.session_state["cal_loading"] = False
    if "cal_results" not in st.session_state:
        st.session_state["cal_results"] = None

    # Control bar: run button + select individual game
    col_cal_ui1, col_cal_ui2, col_cal_ui3 = st.columns([3, 1, 2])
    with col_cal_ui2:
        cal_run_btn = st.button("🚀 运行校准计算", type="primary", use_container_width=True)

    if cal_run_btn and not st.session_state.get("cal_loading", False):
        st.session_state["cal_loading"] = True
        with st.spinner("正在运行校准计算（后台）..."):
            cal_api_result = _run_calibrate_api()
            if cal_api_result:
                st.session_state["cal_results"] = cal_api_result.get("results", [])
                st.session_state["cal_loading"] = False
                st.success(f"✅ 校准计算完成，共 {len(st.session_state['cal_results'])} 个种子游戏")
            else:
                st.session_state["cal_loading"] = False
                st.warning("校准 API 不可用。请确保 FastAPI 后端正在运行（SP_API_URL 环境变量已设置）。")
                # Fallback: use local seed games
                local_games = cal_service.get_seed_cal_games()
                cal_results_local = []
                for g in local_games:
                    cr = cal_service.run_calibration(g)
                    cal_results_local.append(cr)
                st.session_state["cal_results"] = cal_results_local
                st.session_state["cal_loading"] = False
                st.info("✅ 已使用本地种子游戏数据完成校准计算（后端 API 不可用时的降级方案）")

    cal_results = st.session_state.get("cal_results")
    if cal_results:
        # ── Build unified summary data ──
        cal_games_list = []
        for cr in cal_results:
            if isinstance(cr, dict):
                dev = cr.get("deviation", {})
                comp = cr.get("computed", {})
                cal_games_list.append({
                    "game_name": cr.get("game_name", cr.get("game_id", "N/A")),
                    "game_id": cr.get("game_id", ""),
                    "sales": comp.get("sales", 0),
                    "quality_score": comp.get("quality_score", 0),
                    "cl_score": comp.get("cl_score", 0),
                    "user_pool": comp.get("user_pool", 0),
                    "sales_pct": dev.get("sales_pct", 0),
                    "quality_pct": dev.get("quality_pct", 0),
                    "cl_pct": dev.get("cl_pct", 0),
                    "pool_pct": dev.get("pool_pct", 0),
                })
            else:
                cal_games_list.append({
                    "game_name": cr.game_name,
                    "game_id": cr.game_id,
                    "sales": cr.computed.get("sales", 0),
                    "quality_score": cr.computed.get("quality_score", 0),
                    "cl_score": cr.computed.get("cl_score", 0),
                    "user_pool": cr.computed.get("user_pool", 0),
                    "sales_pct": cr.deviation.get("sales_pct", 0),
                    "quality_pct": cr.deviation.get("quality_pct", 0),
                    "cl_pct": cr.deviation.get("cl_pct", 0),
                    "pool_pct": cr.deviation.get("pool_pct", 0),
                })

        if cal_games_list:
            # ── 1. Summary table with deviation color coding ──
            st.subheader("📊 校准汇总")
            summary_df = pd.DataFrame(cal_games_list)
            display_cols = ["game_name", "sales", "quality_score", "cl_score", "user_pool",
                           "sales_pct", "quality_pct", "cl_pct", "pool_pct"]
            df_display = summary_df[display_cols].copy()
            df_display = df_display.rename(columns={
                "game_name": "游戏", "sales": "销量", "quality_score": "质量",
                "cl_score": "CL", "user_pool": "用户池",
                "sales_pct": "销量偏差%", "quality_pct": "质量偏差%",
                "cl_pct": "CL偏差%", "pool_pct": "池偏差%"
            })
            df_display["销量"] = df_display["销量"].map("{:,.0f}".format)
            df_display["用户池"] = df_display["用户池"].map("{:,.0f}".format)
            df_display["质量"] = df_display["质量"].map("{:.2f}".format)
            df_display["CL"] = df_display["CL"].map("{:.3f}".format)
            st.dataframe(df_display, use_container_width=True, hide_index=True)

            # Deviation legend
            st.caption("🟢 偏差 < 20% | 🟡 偏差 20-50% | 🔴 偏差 > 50%")

            # ── 2. 多维偏差可视化 (4维雷达对比 + 独立偏差进度条) ──
            st.markdown("---")
            st.subheader("📈 多维偏差可视化")

            # 2a. 四维偏差水平条形图 (Sales/Quality/CL/Pool 四轴)
            with st.expander("四维偏差对比图", expanded=True):
                multi_dev_data = []
                for g in cal_games_list:
                    for metric, dev_key in [
                        ("销量", "sales_pct"), ("质量", "quality_pct"),
                        ("CL", "cl_pct"), ("用户池", "pool_pct"),
                    ]:
                        multi_dev_data.append({
                            "游戏": g["game_name"],
                            "指标": metric,
                            "偏差 %": g[dev_key],
                        })
                df_multi = pd.DataFrame(multi_dev_data)
                # Color encode: positive = orange-ish, negative = blue-ish
                st.bar_chart(
                    df_multi.set_index(["游戏", "指标"]).unstack()["偏差 %"],
                    horizontal=True,
                    y_min=-50,
                    y_max=50,
                )
                st.caption("蓝色柱 = 负偏差（模型低估），橙色柱 = 正偏差（模型高估）。理想值为 0%。")

            # 2b. 各维度独立偏差进度条
            with st.expander("逐维度偏差进度条", expanded=False):
                col_prog1, col_prog2 = st.columns(2)
                for i, g in enumerate(cal_games_list):
                    col = col_prog1 if i % 2 == 0 else col_prog2
                    with col:
                        st.markdown(f"**{g['game_name']}**")
                        for label, pct_key in [("销量", "sales_pct"), ("质量", "quality_pct"), ("CL", "cl_pct"), ("用户池", "pool_pct")]:
                            pct_val = g[pct_key]
                            pct_abs = abs(pct_val)
                            if pct_abs < 20:
                                color = "🟢"
                            elif pct_abs < 50:
                                color = "🟡"
                            else:
                                color = "🔴"
                            bar_width = min(pct_abs / 100 * 100, 100)
                            st.progress(bar_width / 100, text=f"{color} {label} 偏差: {pct_val:+.1f}%")

            # ── 3. 逐游戏结构化详情卡片 ──
            st.markdown("---")
            st.subheader("🔍 逐游戏详情")

            game_names = [g["game_name"] for g in cal_games_list]
            selected_game = st.selectbox("选择游戏查看详情", game_names)
            if selected_game:
                game_data = next((g for g in cal_games_list if g["game_name"] == selected_game), None)
                if game_data:
                    with st.container():
                        # Header row
                        col_det1, col_det2, col_det3 = st.columns([1, 1, 1])
                        with col_det1:
                            st.metric("销量预测", f"{game_data['sales']:,.0f}")
                        with col_det2:
                            st.metric("质量评分", f"{game_data['quality_score']:.2f}")
                        with col_det3:
                            st.metric("CL 分数", f"{game_data['cl_score']:.3f}")

                        # User pool metric
                        st.metric("用户池规模", f"{game_data['user_pool']:,.0f}")

                        st.markdown("---")
                        # 4维度偏差卡片
                        st.markdown("### 偏差分析")
                        dev_cols = st.columns(4)
                        for j, (label, pct_key, color_map) in enumerate([
                            ("销量", "sales_pct", {"good": "🟢", "warn": "🟡", "bad": "🔴"}),
                            ("质量", "quality_pct", {"good": "🟢", "warn": "🟡", "bad": "🔴"}),
                            ("CL", "cl_pct", {"good": "🟢", "warn": "🟡", "bad": "🔴"}),
                            ("用户池", "pool_pct", {"good": "🟢", "warn": "🟡", "bad": "🔴"}),
                        ]):
                            with dev_cols[j]:
                                pct_val = game_data[pct_key]
                                pct_abs = abs(pct_val)
                                if pct_abs < 20:
                                    icon = color_map["good"]
                                    badge_color = "rgba(46, 125, 50, 0.12)"
                                elif pct_abs < 50:
                                    icon = color_map["warn"]
                                    badge_color = "rgba(255, 152, 0, 0.12)"
                                else:
                                    icon = color_map["bad"]
                                    badge_color = "rgba(244, 67, 54, 0.12)"
                                st.markdown(
                                    f'<div style="background:{badge_color};border-radius:8px;padding:10px;margin-bottom:6px;">'
                                    f'<div style="font-size:13px;font-weight:600;margin-bottom:4px;">{icon} {label} 偏差</div>'
                                    f'<div style="font-size:22px;font-weight:700;">{pct_val:+.1f}%</div></div>',
                                    unsafe_allow_html=True,
                                )

                    # ── 4. 原始数据（JSON） ──
                    st.markdown("---")
                    with st.expander("查看原始计算数据 (JSON)", expanded=False):
                        st.json({
                            "computed": {
                                "sales": game_data["sales"],
                                "quality_score": game_data["quality_score"],
                                "cl_score": game_data["cl_score"],
                                "user_pool": game_data["user_pool"],
                            },
                            "deviation": {
                                "sales_pct": game_data["sales_pct"],
                                "quality_pct": game_data["quality_pct"],
                                "cl_pct": game_data["cl_pct"],
                                "pool_pct": game_data["pool_pct"],
                            },
                        })

            # ── 5. 校准结果导出 ──
            st.markdown("---")
            st.subheader("💾 导出校准结果")
            cal_export_btn = st.button("📄 导出校准结果 (CSV)", use_container_width=True, type="primary")
            if cal_export_btn:
                csv_buffer = io.StringIO()
                writer = csv.writer(csv_buffer)
                writer.writerow(["游戏", "销量", "质量评分", "CL", "用户池", "销量偏差%", "质量偏差%", "CL偏差%", "池偏差%"])
                for g in cal_games_list:
                    writer.writerow([
                        g["game_name"],
                        int(g["sales"]),
                        f"{g['quality_score']:.2f}",
                        f"{g['cl_score']:.3f}",
                        int(g["user_pool"]),
                        f"{g['sales_pct']:+.1f}%",
                        f"{g['quality_pct']:+.1f}%",
                        f"{g['cl_pct']:+.1f}%",
                        f"{g['pool_pct']:+.1f}%",
                    ])
                st.download_button(
                    label="✅ 下载 CSV 文件",
                    data=csv_buffer.getvalue(),
                    file_name=f"calibration_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

    if cal_results is None and not st.session_state.get("cal_loading"):
        st.info("点击「运行校准计算」按钮，对所有种子游戏进行校准分析。结果将展示计算值与预期范围的偏差。")
        st.caption("种子游戏包括：Balatro、Stardew Valley、Minecraft、Palworld、暖雪、完蛋、VS。")


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
