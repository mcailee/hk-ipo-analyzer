---
name: hk-ipo-analyzer
description: "港股 IPO 打新量化分析助手。输入新股代码，自动采集港交所、雪球公开数据及招股书 PDF，从 11 个维度进行量化评分，支持分阶段分析（招股期/认购期），输出综合评分、雷达图、结构化研报和投资建议。"
---

# HK IPO Analyzer — 港股打新分析助手

Analyze Hong Kong IPO stocks with quantitative scoring across 11 dimensions. Generate comprehensive investment reports with radar charts, structured analysis, and actionable recommendations.

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
3. Run 9 dimension analyzers (valuation 18%, financial 14%, industry 10%, cornerstone 10%, company 8%, underwriting 8%, greenshoe 5%, shareholder 3%, legal 2%)
4. Phase 1 re-weights the 9 dimensions proportionally to 100%
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
  [--concurrent <N>] [--break-rate <X>] \
  [--free-float-cap <X>] [--hk-connect|--no-hk-connect] \
  [--market-maker|--no-market-maker] [--daily-turnover <X>] \
  [--output <OUTPUT_DIR>]
```

**Key parameters:**
- `--public-mult`: 公开认购倍数 (e.g. 120 means 120x oversubscribed)
- `--intl-mult`: 国际配售倍数
- `--clawback` / `--no-clawback`: 是否触发回拨
- `--concurrent`: 同期上市新股数量
- `--break-rate`: 近期新股破发率 (%)
- `--free-float-cap`: 自由流通市值 (百万港元)
- `--hk-connect` / `--no-hk-connect`: 是否可能纳入港股通

Phase 2 loads Phase 1 data, adds subscription (15%) and liquidity (7%) dimensions, re-scores all 11 dimensions with full weights, and generates comparison reports.

## 11 Scoring Dimensions

| Dimension | Weight | Phase |
|-----------|--------|-------|
| 估值定价 (Valuation) | 18% | 1 |
| 市场认购热度 (Subscription) | 15% | 2 |
| 财务状况 (Financial) | 14% | 1 |
| 行业竞争 (Industry) | 10% | 1 |
| 基石投资者 (Cornerstone) | 10% | 1 |
| 公司基本面 (Company) | 8% | 1 |
| 承销发行 (Underwriting) | 8% | 1 |
| 上市后流动性 (Liquidity) | 7% | 2 |
| 绿鞋机制 (Greenshoe) | 5% | 1 |
| 股东构成 (Shareholder) | 3% | 1 |
| 法律诉讼 (Legal) | 2% | 1 |

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

## Notes

- All data scraping uses public sources only (HKEX, Xueqiu). Request delays of 1-2 seconds are applied.
- Missing data fields are scored at 50 (neutral) with a "data insufficient" flag.
- Reports are for research reference only and do not constitute investment advice.
- Configuration (weights, thresholds) can be customized in `assets/config.yaml`.
