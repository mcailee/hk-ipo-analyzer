---
name: hk-ipo-analyzer
description: "港股 IPO 打新量化分析助手。输入新股代码，自动采集港交所、雪球公开数据及招股书 PDF，从 15 个维度（12 常规 + 3 条件性）进行量化评分，支持分阶段分析（招股期/认购期），支持机制 A/B 双轨定价，输出综合评分、概率预测、中签率计算、打新策略推荐（甲组/乙组分配模拟、甲乙双打、多账户矩阵、融资成本精算）、雷达图、结构化研报和投资建议。"
---

# HK IPO Analyzer — 港股打新分析助手 (v5.1)

Analyze Hong Kong IPO stocks with quantitative scoring across 15 dimensions (12 standard + 3 conditional). Generate comprehensive investment reports with probability predictions, allotment calculations, radar charts, structured analysis, and actionable recommendations.

**v5.1 基石分级增强版 (2026-04-09):**
- S/A/B/C 四级基石投资者分类体系（主权基金/国际顶级/国内大型/国内普通）
- WQS(数量加权) + AWQS(金额加权) 综合质量分，替代一刀切 +15 分
- 信心倍增器: S/A 级机构占发行额 ≥10%/20%/30% 时额外加分 +4/+8/+12
- 概率预测: cs_adj 从二值(±8pp)升级为连续函数(-12~+12pp) + 信心倍增修正
- 龙头修正: S 级大额占比算 3 个龙头信号，S/A 合计 >20% 算 2 个
- PDF 解析器: 机构名单按 S/A/B/C 四级分类（~80 家机构）

**v5.0 赛道增强版 (2026-03-31):**
- P0-1 赛道概念溢价因子 (AI/半导体/18C 等 28 个赛道)
- P0-2 暗盘绝对水平传导 (>50% 锚定模式)
- P1-1 小盘弹性系数 (募资<10亿 ×1.4)
- P1-2 卖出策略赛道热度豁免
- P1-3 期望偏差推算赛道修正
- P2-1 低超购龙头修正
- 回测验证: 5 只新股平均偏差 ↓46% (82pp→45pp)

## Trigger Conditions

Activate this skill when the user mentions any of: "打新分析", "IPO分析", "新股分析", "港股打新", "港股IPO", "analyze IPO", "新股评分", or provides a Hong Kong stock code for IPO analysis.

## Prerequisites

On first use, install Python dependencies:

```bash
python3 {SKILL_DIR}/scripts/install_deps.py
```

## Workflow

### Decision Tree

1. **User wants Phase 1 analysis** (new stock, first analysis, 招股期):
   → Execute `analyze.py` with stock code and optional PDF path
2. **User wants Phase 2 update** (subscription data available, 认购期):
   → Execute `update.py` with stock code and subscription parameters
3. **User asks about scoring methodology or dimensions**:
   → Load `references/scoring_methodology.md` and answer from it
4. **User asks about industry-specific indicators**:
   → Load `references/industry_indicators.md` and answer from it

### Phase 1 — 招股期基本面分析

Execute when the user provides a stock code for initial IPO analysis.

**Command:**
```bash
python3 {SKILL_DIR}/scripts/analyze.py <STOCK_CODE> [--pdf <PDF_PATH>] [--output <OUTPUT_DIR>]
```

**Parameters:**
- `STOCK_CODE` (required): Hong Kong stock code, e.g. `9999` or `09999`
- `--pdf` (optional): Path to the prospectus PDF file for additional data extraction
- `--output` (optional): Custom output directory
- `--no-html`: Skip HTML report generation
- `--no-chart`: Skip radar chart generation

**What it does:**
1. Scrape IPO data from HKEX (港交所披露易) and Xueqiu (雪球)
2. Optionally parse prospectus PDF for financial tables, cornerstone investors, legal info
3. Run 10 dimension analyzers: valuation (15%), financial (12%), industry (12%), cornerstone (10%), market_sentiment (9%), underwriting (8%), company (6%), greenshoe (3%), shareholder (1%), legal (1%), plus conditional: ah_stock (4%, if A+H data available)
4. Phase 1 re-weights active dimensions proportionally to 100%
5. Generate: terminal report + radar chart PNG + HTML report + Phase 1 JSON

**Output files** are saved to `./output/{stock_code}_{date}/`:
- `phase1_data.json` — raw data snapshot
- `phase1_report.json` — scores and analysis
- `radar_phase1.png` — dimension radar chart
- `report_phase1.html` — full HTML research report

After Phase 1, present the HTML report to the user using preview_url.

### Phase 2 — 认购期更新

Execute when subscription data becomes available (公开认购倍数, 国际配售倍数, etc.).

**Command:**
```bash
python3 {SKILL_DIR}/scripts/update.py <STOCK_CODE> \
  --public-mult <X> --intl-mult <X> \
  [--clawback|--no-clawback] \
  [--mechanism A|B] \
  [--concurrent <N>] [--break-rate <X>] \
  [--free-float-cap <X>] [--hk-connect|--no-hk-connect] \
  [--market-maker|--no-market-maker] [--daily-turnover <X>] \
  [--grey-market-price <X>] [--grey-market-volume <X>] \
  [--a-stock-code <CODE>] [--a-stock-price <X>] [--ah-premium <X>] \
  [--batch-break-rate <X>] [--batch-avg-return <X>] [--batch-total <N>] \
  [--total-capital <X>] [--num-accounts <N>] [--financing-mult <X>] \
  [--output <OUTPUT_DIR>]
```

**Key parameters:**
- `--public-mult`: 公开认购倍数 (e.g. 120 means 120x oversubscribed)
- `--intl-mult`: 国际配售倍数
- `--clawback` / `--no-clawback`: 是否触发回拨
- `--mechanism`: IPO 定价机制（A=传统 / B=2025 年新机制）
- `--concurrent`: 同期上市新股数量
- `--break-rate`: 近期新股破发率 (%)
- `--free-float-cap`: 自由流通市值 (百万港元)
- `--hk-connect` / `--no-hk-connect`: 是否可能纳入港股通
- `--grey-market-price`: 暗盘价格 (港元)
- `--grey-market-volume`: 暗盘成交量 (手)
- `--a-stock-code`: 对应 A 股代码 (如有 A+H)
- `--a-stock-price`: A 股当前价格 (CNY)
- `--ah-premium`: A/H 溢价率 (%)
- `--batch-break-rate`: 同批次新股破发率 (%)
- `--batch-avg-return`: 同批次平均首日涨幅 (%)
- `--batch-total`: 同批次新股总数
- `--total-capital`: 可用总资金 (港元)，提供后启用策略引擎
- `--num-accounts`: 可用证券账户数量（默认 1）
- `--financing-mult`: 融资倍数（0=现金, 10=10倍孖展, 20=20倍孖展）

Phase 2 loads Phase 1 data, adds subscription (16%), liquidity (7%), and conditional dimensions — grey_market (6%), peer_comparison (5%), ah_stock (4%) — re-scores all 15 dimensions with full weights (auto-renormalization when conditional data absent), generates probability prediction, allotment estimation, sell timing advice, and comparison reports.

When `--total-capital` is provided, the **Strategy Engine** (策略引擎) is activated, which:
- Simulates Group A (甲组) and Group B (乙组) allocation based on subscription data
- Enumerates all viable strategies: 摸一手 / 甲尾 / 甲头 / 多账户甲组矩阵 / 纯乙组 / 甲乙双打 / 多甲+乙
- Calculates financing costs for each strategy (支持 0/1/5/10/20 倍孖展)
- Selects the optimal strategy by expected net profit
- Outputs per-account breakdown, risk metrics, and annualized capital efficiency

## 15 Scoring Dimensions

### Standard Dimensions (12)

| Dimension | Weight | Phase |
|-----------|--------|-------|
| 估值定价 (Valuation) | 15% | 1 |
| 市场认购热度 (Subscription) | 16% | 2 |
| 财务状况 (Financial) | 12% | 1 |
| 行业竞争 (Industry) | 12% | 1 |
| 基石投资者 (Cornerstone) | 10% | 1 |
| 市场情绪 (Market Sentiment) | 9% | 1 |
| 承销发行 (Underwriting) | 8% | 1 |
| 上市后流动性 (Liquidity) | 7% | 2 |
| 公司基本面 (Company) | 6% | 1 |
| 绿鞋机制 (Greenshoe) | 3% | 1 |
| 股东构成 (Shareholder) | 1% | 1 |
| 法律诉讼 (Legal) | 1% | 1 |

### Conditional Dimensions (3) — 有数据时参与加权，无数据时 weight=0

| Dimension | Weight | Phase |
|-----------|--------|-------|
| 暗盘数据 (Grey Market) | 6% | 2 |
| 同批次对比 (Peer Comparison) | 5% | 2 |
| A+H 股分析 (AH Stock) | 4% | 2 |

> **权重归一化**：条件维度无数据时自动退出评分，剩余维度按比例重归一化至 100%。

## Rating Scale

| Score | Rating | Action |
|-------|--------|--------|
| ≥ 80 | 强烈推荐 | Strong Buy |
| 65–79 | 推荐 | Buy |
| 50–64 | 中性 | Neutral |
| < 50 | 回避 | Avoid |

**Legal downgrade rule:** If major litigation exceeds 20% of net assets, or criminal/regulatory red flags exist, the rating is automatically downgraded one level.

## Industry-Specific Indicators

The system auto-detects industry type (TMT / Pharma / Consumer) and loads specialized sub-indicators:

- **TMT**: Rule of 40, MAU, ARPU, LTV/CAC, recurring revenue %, customer concentration
- **Pharma**: Pipeline count, clinical stage, indication market size, R&D ratio, innovation vs generic
- **Consumer**: Same-store sales growth, store expansion, inventory turnover, gross margin, channel mix

For detailed methodology, load `references/scoring_methodology.md` or `references/industry_indicators.md`.

## Examples

**Example 1 — Phase 1 analysis:**
User: "帮我分析港股新股 9999"
→ Run: `python3 {SKILL_DIR}/scripts/analyze.py 9999`

**Example 2 — With prospectus PDF:**
User: "分析 2048 这只新股，这是招股书"
→ Run: `python3 {SKILL_DIR}/scripts/analyze.py 2048 --pdf /path/to/prospectus.pdf`

**Example 3 — Phase 2 update:**
User: "9999 公开认购120倍，国际配售5倍，触发了回拨"
→ Run: `python3 {SKILL_DIR}/scripts/update.py 9999 --public-mult 120 --intl-mult 5 --clawback`

**Example 4 — Phase 2 with grey market and A+H data:**
User: "9999 暗盘价 25 港元，成交 5000 手，A 股代码 600999，A 股价 30 元"
→ Run: `python3 {SKILL_DIR}/scripts/update.py 9999 --public-mult 120 --intl-mult 5 --clawback --grey-market-price 25 --grey-market-volume 5000 --a-stock-code 600999 --a-stock-price 30`

**Example 5 — Phase 2 with batch comparison:**
User: "同批 5 只新股，破发率 20%，平均首日涨幅 8%"
→ Run: `python3 {SKILL_DIR}/scripts/update.py 9999 --public-mult 120 --intl-mult 5 --batch-total 5 --batch-break-rate 20 --batch-avg-return 8`

**Example 6 — Phase 2 with strategy engine (小散现金):**
User: "我有 20 万，想分析一下 9999 该怎么打"
→ Run: `python3 {SKILL_DIR}/scripts/update.py 9999 --public-mult 120 --intl-mult 5 --clawback --total-capital 200000`

**Example 7 — Phase 2 with strategy engine (中户孖展):**
User: "200 万资金，2 个账户，10 倍孖展打新"
→ Run: `python3 {SKILL_DIR}/scripts/update.py 9999 --public-mult 120 --intl-mult 5 --clawback --total-capital 2000000 --num-accounts 2 --financing-mult 10`

**Example 8 — Phase 2 with strategy engine (大户甲乙双打):**
User: "2000 万资金，5 个账户，分析最优打新策略"
→ Run: `python3 {SKILL_DIR}/scripts/update.py 9999 --public-mult 120 --intl-mult 5 --clawback --total-capital 20000000 --num-accounts 5 --financing-mult 10`

## Notes

- All data scraping uses public sources only (HKEX, Xueqiu). Request delays of 1-2 seconds are applied.
- Missing data fields are scored at 50 (neutral) with a "data insufficient" flag.
- Reports are for research reference only and do not constitute investment advice.
- Configuration (weights, thresholds) can be customized in `assets/config.yaml`.
