---
name: hk-ipo-reversal
description: "港股新股暗盘反转猎手 V2（期望偏差版）。分析暗盘表现不及预期的股票后续修正概率，覆盖三类场景：暗盘下跌、暗盘涨幅不及预期、暗盘小涨但后续大涨（潜力释放）。核心概念：期望偏差(deviation) = 暗盘涨幅 - 预期涨幅。输入港股代码自动判断已上市/未上市：已上市输出修正路径回测；未上市新股+暗盘数据输出修正概率评分和买卖建议（支持 --expected-return 手动指定或自动推算）；不输入代码则生成全量偏差修正统计报告（含潜力释放分析）。内置约128只港股新股增强版数据集（含暗盘高低价、day2/day7/day10多时点、首日成交量、预期涨幅和偏差值），支持自动偏差阈值寻优、手写Logistic回归、价格路径聚类、Bootstrap置信区间。纯Python标准库，零外部依赖。"
---

# HK IPO Reversal Hunter V2 — 港股新股暗盘反转猎手 (期望偏差版)

专注港股新股"暗盘表现不及预期→后续修正"模式的量化分析工具。通过引入"期望偏差"概念，将分析范围从"仅暗盘下跌"扩展到"所有表现不及预期"的股票，为打新者提供更全面的决策支持。

## Trigger Conditions

当用户提到以下关键词时激活本 Skill：
- "反转"、"逆袭"、"低开反弹"、"暗盘抄底"
- "暗盘跌了还能涨回来吗"、"暗盘低开怎么办"
- "破发后能反弹吗"、"跌了要不要割"、"要不要止损"
- "反转概率"、"反弹概率"、"回升概率"、"修正概率"
- "暗盘大跌"、"暗盘低开"、"暗盘破发"
- **"涨幅不及预期"、"暗盘涨得少"、"远低于预期"、"没涨够"**
- **"后面还能涨吗"、"暗盘才涨一点"、"暗盘涨幅不够"**
- **"潜力释放"、"后续补涨"、"低估到补涨"**
- "V型反转"、"价格路径"、"走势模式"、"偏差分析"
- 用户提供港股代码并询问"暗盘涨幅不及预期怎么办"或"修正分析"

**与兄弟 Skill 的区别**：
- `hk-ipo-analyzer`：单只新股的实时数据爬取 + 15维评分，回答"值不值得打"
- `hk-ipo-sweet-spot`：历史回测 + 统计规律 + 卖出策略，回答"中签了怎么卖最赚"
- `hk-ipo-reversal`：偏差修正分析 + 修正概率预测，回答"暗盘表现不及预期还能修正吗"

## Prerequisites

**核心运行无需安装任何依赖。** 纯 Python 3 标准库，零外部依赖。

**可选增强：** 如安装了 Node.js（v18+），将自动通过 [skill:腾讯自选股数据工具]（westock-data）获取实时 K 线数据和恒指月度涨跌幅。未安装时静默 fallback 到内置历史数据。数据获取层共享自 hk-ipo-sweet-spot 的 fetcher.py。

### 数据获取优先级

同 hk-ipo-sweet-spot 的数据获取优先级规则。分析时优先使用 westock-data 获取 K 线、资金流向、财务报表等数据。

### 数据更新命令

批量从 westock-data 拉取最新数据更新 data.py（含 day2/day7/day10/换手率等增强字段）：
```bash
python3 {SKILL_DIR}/scripts/update_data.py                # 更新所有缺失数据
python3 {SKILL_DIR}/scripts/update_data.py --dry-run      # 仅预览
python3 {SKILL_DIR}/scripts/update_data.py --hsi-only     # 仅更新恒指
python3 {SKILL_DIR}/scripts/update_data.py --code 01021   # 更新指定股票
```

## Workflow

### Decision Tree

1. **用户要全量偏差修正统计报告**（不提供股票代码）：
   → 运行 `analyze.py`，生成完整的偏差修正统计报告（含潜力释放分析）

2. **用户提供已上市股票代码**（在数据集中）：
   → 运行 `analyze.py --code XXXXX`，输出该股的修正路径回测

3. **用户提供未上市新股代码 + 暗盘数据**（不在数据集中）：
   → 运行 `analyze.py --code XXXXX --dark-return X --subscription-mult X [--expected-return X] ...`

4. **用户询问分析方法论**：
   → 加载 `references/methodology.md` 回答

### 模式 1 — 全量偏差修正统计报告

```bash
python3 {SKILL_DIR}/scripts/analyze.py [--output <OUTPUT_DIR>]
```

### 模式 2 — 已上市股票修正回测

```bash
python3 {SKILL_DIR}/scripts/analyze.py --code <STOCK_CODE> [--output <OUTPUT_DIR>]
```

### 模式 3 — 未上市新股修正预测

```bash
python3 {SKILL_DIR}/scripts/analyze.py --code <STOCK_CODE> \
  --dark-return <X> \
  --subscription-mult <X> \
  [--has-cornerstone] \
  [--category <CATEGORY>] \
  [--fundraising <X>] \
  [--expected-return <X>] \
  [--day1-return <X>] \
  [--output <OUTPUT_DIR>]
```

**Parameters:**
- `--code`: 港股代码
- `--dark-return`: 暗盘涨跌幅%（必须，可以是正数如+5）
- `--subscription-mult`: 公开认购倍数（必须）
- `--has-cornerstone`: 是否有基石投资者
- `--category`: 行业分类
- `--fundraising`: 募资额(亿港元)
- `--expected-return`: 预期涨幅%（可选，来自 hk-ipo-analyzer 或用户判断；不指定则自动推算）
- `--day1-return`: 首日涨跌幅%（如已知）

**Output:** `reversal_{code}_predict.html`

## Data Set

128只港股新股增强版数据集（2024.06~2026.03），新增字段：

| 字段 | 说明 |
|------|------|
| expected_return | 预期首日涨幅%（基于分档统计映射推算） |
| deviation | 期望偏差% = dark_return - expected_return |

## Analysis Modules

### 1. 期望偏差模型 (V2新增)
- deviation = dark_return - expected_return
- expected_return 基于超购区间/基石/行业/募资的分档统计映射
- 三种偏差类型：暗盘下跌 / 涨幅不及预期 / 潜力释放

### 2. 自动偏差阈值寻优
- 扫描偏差阈值 × 回正窗口 × 回正标准的全排列组合
- 样本量从V1的27只扩展到50+只

### 3. 多因子修正模型
- 新增"期望偏差"和"暗盘涨跌幅"因子（8因子总计）
- Logistic回归 + 信息增益双轨验证

### 4. 潜力释放分析 (V2新增)
- 暗盘小涨但后续Day5-Day10大幅补涨的模式
- 共性特征统计和路径展示

### 5. 价格路径聚类
- 扩展为对所有偏差为负的股票聚类（不限暗盘下跌）
- V型修正 / U型缓慢修正 / L型持续低迷 / 断崖式

## Examples

**Example 1 — 暗盘涨了但不及预期（V2核心场景）：**
User: "华沿机器人 01021 暗盘涨了5%，但我觉得应该涨30%，后面还能修正吗"
→ Run: `python3 {SKILL_DIR}/scripts/analyze.py --code 01021 --dark-return 5 --subscription-mult 5000 --has-cornerstone --category 机器人 --fundraising 14 --expected-return 30`

**Example 2 — 暗盘下跌预测：**
User: "XX新股暗盘跌了15%，还能涨回来吗"
→ Run: `python3 {SKILL_DIR}/scripts/analyze.py --code XXXXX --dark-return -15 --subscription-mult 500 --has-cornerstone`

**Example 3 — 全量统计报告：**
User: "帮我分析港股新股反转修正的规律"
→ Run: `python3 {SKILL_DIR}/scripts/analyze.py`

## Notes

- V2相比V1的核心变化：引入"期望偏差"概念，分析范围从33只暗盘下跌→72只表现不及预期
- 不再硬性要求"暗盘必须下跌"才能分析
- 支持用户手动指定预期涨幅（来自 hk-ipo-analyzer）或自动推算
- 所有分析基于历史回测，不构成投资建议
