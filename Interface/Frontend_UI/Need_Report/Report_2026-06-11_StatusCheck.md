# Webber 2026/06/11 迭代报告 - Streamlit 版本功能对齐

**岗位**: 前端/UI工程师  
**项目**: SteamPublisher (Steam 发行销量预测器)  
**迭代日期**: 2026/06/11  
**状态**: ✅ 完成

## 迭代目标
将 index.html（GitHub Pages 前端）的核心功能对齐到 Streamlit 版本，补齐讨论数据面板、校准控制面板和数据导出功能。

## 变更摘要

### 1. 讨论数据面板 ✅
- 新增 `💬 讨论数据面板`，集成 FastAPI `/api/discussion` 接口
- 4 张指标卡片：讨论源总数、成功源数、讨论质量评分、数据置信度
- 讨论质量贡献卡片：数量信号、互动信号、强度综合、数据置信度
- 各平台详细数据以 expander 展示 Top 10 视频
- 质量置信度操作建议（低/中置信度引导）

### 2. 校准控制面板 ✅
- 新增 `⚙️ 校准控制面板`
- 权重分配：Rating / Proof / Discussion / Persistence（实时总和验证）
- 上限控制：Showmanship cap、CL cap、Quality threshold
- 保存调用 `PUT /api/calibration` 持久化到后端

### 3. 数据导出 ✅
- CSV 导出：Benchmark Comparison + Scenario Summary
- JSON 导出：完整分析结果（游戏信息、销量、质量、用户池、手动参数）
- 文件名格式：`steam_predictor_{game_name}_{YYYYMMDD}.{csv|json}`

### 4. SteamDB 与质量评分联动 ✅
- 新增联动按钮，提示 SteamDB 信号对质量评估的补充作用

## 产出物
- `src/steam_publisher_predictor/app.py` — 新增约 207 行（总计 672 行）
- 新增辅助函数：`_fetch_discussion()`, `_get_calibration()`, `_update_calibration()`, `_export_csv()`, `_export_json()`

## 验证
- 代码语法检查通过（无编译错误）
- API 辅助函数与后端端点签名匹配
- 校准字段与 `CalibrationUpdate` Pydantic model 对齐

## 下次迭代建议
1. Streamlit 版本补充校准种子游戏对比功能
2. 统一 index.html 与 Streamlit 讨论面板展示逻辑
3. 补充 Streamlit 版本自动化测试
