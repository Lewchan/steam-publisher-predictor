# Webber 2026/06/11 迭代记录 - Streamlit 版本功能对齐

**最后更新**: 2026/06/11 14:00

## 迭代目标
Streamlit 版本功能对齐 — 讨论数据面板、校准控制面板、Benchmark 数据导出 + SteamDB 联动

## 迭代记录

| 迭代日期 | 变更内容 | 文件 | 状态 |
|---------|---------|------|------|
| 2026/06/11 | P1: Streamlit 新增讨论数据面板 — 集成 FastAPI `/api/discussion` 接口，展示跨平台讨论数据与质量评分贡献 | `app.py` (+ `_fetch_discussion`) | ✅ 完成 |
| 2026/06/11 | P1: Streamlit 新增校准控制面板 — 权重分配/上限控制/保存配置，对接 `PUT /api/calibration` | `app.py` (+ `_get_calibration`, `_update_calibration`) | ✅ 完成 |
| 2026/06/11 | P2: Streamlit 新增数据导出 — CSV（Benchmark + Scenario）和 JSON（完整分析结果） | `app.py` (+ `_export_csv`, `_export_json`) | ✅ 完成 |
| 2026/06/11 | P2: SteamDB 与质量评分联动展示 — 新增联动按钮，提示 SteamDB 信号对质量评估的补充作用 | `app.py` | ✅ 完成 |
| 2026/06/11 | P3: 新增 `httpx` 导入用于 HTTP 客户端调用（已在 requirements.txt） | `app.py` 导入段 | ✅ 完成 |
| 2026/06/11 | P3: 质量置信度操作建议增强 — 低/中置信度时引导用户参考讨论数据或调整手动参数 | `app.py` | ✅ 完成 |
| 2026/06/11 | P3: Scenario data 同步到 session_state 供导出使用 | `app.py` | ✅ 完成 |

## 实现细节

### 讨论数据面板
- 新增 `💬 讨论数据面板` 区域，支持输入游戏名查询讨论数据
- 调用 FastAPI 后端 `/api/discussion` 接口（通过 `SP_API_URL` 环境变量配置）
- 4 张指标卡片：讨论源总数、成功源数、讨论质量评分、数据置信度
- 质量评分贡献卡片：讨论数量信号、互动信号、强度综合、数据置信度
- 各平台数据以 expander 展开，展示 Top 10 视频（标题、浏览/点赞/评论/情感）

### 校准控制面板
- 权重分配：Rating(0.35) / Proof(0.25) / Discussion(0.25) / Persistence(0.15)
- 权重总和实时验证显示（绿色=1.0，红色=偏差）
- 上限控制：Showmanship cap(0.6)、CL cap(3.0)、Quality threshold(4.0)
- 保存调用 `PUT /api/calibration`，与 index.html 共享配置

### 数据导出
- CSV：Benchmark Comparison + Scenario Summary 两大部分
- JSON：完整分析结果（游戏信息、销量、质量、用户池、手动参数）
- 文件名：`steam_predictor_{game_name}_{YYYYMMDD}.{csv|json}`

## 产出物文件
- `src/steam_publisher_predictor/app.py` — 本次新增约 180 行

## 验证摘要
- 代码语法检查通过（无编译错误）
- API 辅助函数与后端端点签名匹配
- 校准字段与 `CalibrationUpdate` Pydantic model 对齐
- CSV/JSON 导出函数正确引用 session_state 数据

## 当前风险
1. Streamlit 调用 FastAPI 需要后端运行且网络可达
2. 讨论数据面板依赖 `SP_API_URL` 环境变量
3. CSV 导出依赖 session_state 中保存的 scenario_data

## 待处理事项

| 优先级 | 事项 | 依赖 |
|--------|------|------|
| P2 | Streamlit 版本补充校准种子游戏对比功能 — 对标 index.html 的校准面板 | 独立 |
| P3 | 补充 Streamlit 版本自动化测试 — Quinn-QA 已准备好 TI-006 测试计划 | 测试验证工程师 |
| P3 | 统一 index.html 与 Streamlit 讨论面板的展示逻辑 | 独立 |
| P3 | 移动端响应式布局进一步优化（index.html 已覆盖，后续设备反馈后继续） | 独立 |
