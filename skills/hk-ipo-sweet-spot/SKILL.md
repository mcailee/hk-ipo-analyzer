---
name: hk-ipo-sweet-spot
description: "港股打新甜蜜区间分析器（V3.5 Ensemble混合版）。输入港股股票代码，自动判断已上市/未上市：已上市股票输出回测分析（所属区间定位、多因子评分、同类对比）；未上市新股输出卖出策略建议（暗盘/首日/3天/5天最优卖出时点）；不输入代码则生成全量回测报告。内置约128只港股新股历史数据集（2024H2~2026Q1），支持按市场状态（牛/熊/震荡）分别训练条件子模型。V3.5新增：小样本降级保护（二值维度动态权重缩放）、行业分层相似度（5大近亲组）、相似度+区间Ensemble混合、18C惩罚行业差异化。纯Python标准库，零外部依赖。"
---

# HK IPO Sweet Spot — 港股打新甜蜜区间分析器 V3.5

基于约128只港股新股历史数据的统计回测分析工具。通过多因子模型发现超购倍数的"甜蜜区间"，引入市场状态条件子模型（牛/熊/震荡）、多维相似度匹配（含小样本降级保护和Ensemble混合），为打新散户提供数据驱动的自适应卖出策略建议。

## Trigger Conditions

当用户提到以下关键词时激活本 Skill：
- "甜蜜区间"、"sweet spot"、"打新回测"、"新股回测"
- "卖出策略"、"什么时候卖"、"暗盘卖还是首日卖"
- "超购倍数分析"、"打新统计"、"打新数据"
- "新股表现回顾"、"港股打新历史"
- "18C"、"18A"、"B类上市"、"未盈利生物科技"、"特专科技"
- "暗盘联动"、"暗盘修正"、"暗盘操作策略"
- "同类群匹配"、"相似度分析"
- 用户提供港股代码并询问"打新策略"或"回测分析"

**与 hk-ipo-analyzer 的区别**：
- `hk-ipo-analyzer`：单只新股的实时数据爬取 + 15维度深度评分，回答"值不值得打"
- `hk-ipo-sweet-spot`：历史数据回测 + 统计规律 + 卖出策略，回答"中签了怎么卖最赚"

## Prerequisites

**无需安装任何依赖。** 本 Skill 使用纯 Python 3 标准库（math/json/os/sys/argparse），零外部依赖。

## Workflow

### Decision Tree

1. **用户要全量回测报告**（不提供股票代码）：
   → 运行 `analyze.py`（无 `--code` 参数），生成完整的甜蜜区间回测报告

2. **用户提供已上市股票代码**（在数据集中）：
   → 运行 `analyze.py --code XXXXX`，输出该股的回测定位分析

3. **用户提供未上市新股代码 + 参数**（不在数据集中）：
   → 运行 `analyze.py --code XXXXX --subscription-mult N --category CAT ...`，输出卖出策略建议

4. **用户询问甜蜜区间方法论**：
   → 加载 `references/methodology.md` 回答

### 模式 1 — 全量回测报告

生成覆盖全部约128只新股的深色主题HTML回测报告。

**Command:**
```bash
python3 {SKILL_DIR}/scripts/analyze.py [--output <OUTPUT_DIR>] [--market-state auto]
```

**What it does:**
1. 加载内置数据集（约128只港股新股，2024.06-2026.03）
2. 为每只新股打上市场状态标签（牛/熊/震荡）
3. 训练条件子模型：按市场状态分组，各组独立运行OLS + 信息增益双轨法
4. 运行基础统计分析：超购区间、基石效应、行业板块、募资规模
5. 生成甜蜜区间回测报告（HTML，暗色主题 + SVG图表 + 市场状态维度分析）

**Output:**
- `hk_ipo_sweet_spot.html` — 完整回测报告

生成后，使用 preview_url 展示给用户。

### 模式 2 — 已上市股票回测分析

输入一个已在数据集中的港股代码，输出该股的回测定位分析。

**Command:**
```bash
python3 {SKILL_DIR}/scripts/analyze.py --code <STOCK_CODE> [--output <OUTPUT_DIR>]
```

**Parameters:**
- `STOCK_CODE`: 港股代码，如 `02097`（可以省略前导零，如 `2097`）

**What it does:**
1. 在数据集中查找该股
2. 定位其所属超购区间、行业、募资区间
3. 计算多因子评分和S/A/B/C/D档位
4. 与同区间、同行业、同档位股票横向对比
5. 输出单股回测分析卡片

**Output:**
- `sweet_spot_{code}.html` — 单股回测分析报告

### 模式 3 — 未上市新股卖出策略

输入未上市新股的代码和关键参数，基于历史同类群数据输出卖出策略建议。

**Command:**
```bash
python3 {SKILL_DIR}/scripts/analyze.py --code <STOCK_CODE> \
  --subscription-mult <X> \
  [--has-cornerstone] \
  [--is-18c] \
  [--category <CATEGORY>] \
  [--fundraising <X>] \
  [--dark-return <X>] \
  [--market-state <bull|bear|neutral|auto>] \
  [--output <OUTPUT_DIR>]
```

**Parameters:**
- `STOCK_CODE`: 港股代码
- `--subscription-mult`: 公开认购倍数（必须）
- `--has-cornerstone`: 是否有基石投资者（flag，不提供则默认无）
- `--is-18c`: 是否为18C/B类上市机制（允许未盈利企业上市的特殊机制）
- `--category`: 行业分类（如 "医药"/"AI"/"消费"/"机器人"/"半导体"等）
- `--fundraising`: 募资额（亿港元）
- `--dark-return`: 暗盘涨跌幅%（如有，用于暗盘联动修正）
- `--market-state`: 市场状态（bull/bear/neutral/auto，默认auto自动判定）

**What it does:**
1. 确认代码不在数据集中（未上市新股）
2. 用提供的参数计算多因子评分（18C 股自动应用评分惩罚）
3. 多维相似度匹配最相似的历史同类群（超购/基石/行业/募资/18C 5维加权）
4. 基于同类群的卖出时点统计，给出最优卖出策略
5. 若提供暗盘涨幅，触发暗盘联动修正引擎（修正首日/Day3/Day5预期）
6. 输出策略建议卡片（含SVG雷达图、相似度排名表、暗盘联动修正卡）

**Output:**
- `sweet_spot_{code}_strategy.html` — 卖出策略建议报告

## Data Set

内置约128只港股新股数据（2024年6月~2026年3月），每只股票包含：

| 字段 | 说明 |
|------|------|
| name | 证券简称 |
| code | 港股代码 |
| date | 上市日期 |
| subscription_mult | 公开认购倍数 |
| day1_return | 首日涨跌幅% |
| fundraising | 募资额（亿港元） |
| has_cornerstone | 是否有基石投资者 |
| category | 行业分类 |
| is_18c | 是否为18C/B类上市机制（V3.4新增） |
| _market_state | 市场状态标签（BULL/BEAR/NEUTRAL，自动计算） |

另含 `hsi_monthly` 恒指月度涨跌幅字典（2024.01~2026.03），用于市场状态分类。

## Analysis Modules

### 1. 基础统计分析
- 超购区间分组（<20x / 20-100x / 100-500x / 500-2000x / 2000-5000x / >5000x）
- 基石投资者效应对比
- 行业板块表现排名
- 募资规模与收益关系

### 2. 多因子评分模型
- 因子集：超购倍数（对数）、基石投资者（二值）、行业（目标编码）、募资规模（对数）
- 双轨权重：50% 线性回归标准化系数 + 50% 信息增益归一化
- 评分 0-100 → S/A/B/C/D 五档

### 3. 卖出时点分析（数据充分时）
- 4 个时点对比：暗盘 / 首日 / 第3天 / 第5天
- 交叉维度：各卖出时点 × 超购区间/行业/募资规模

### 4. 季节性分析
- 按季度/月份分组统计打新效应
- 识别打新旺季和淡季

### 5. 市场状态条件子模型（V3新增）
- 基于恒指前3月滚动收益率自动分类：牛市（>+8%）/ 熊市（<-8%）/ 震荡
- 按状态分组独立训练因子权重
- 智能降级：样本<5自动回退全局模型
- 预测时自动识别当前市场状态，选择对应子模型

### 6. 18C / B类上市机制分析（V3.4新增，V3.5增强）
- 20只18C股票独立标记和统计
- [V3.5] 评分惩罚行业差异化：医药无基石-10% / 非医药无基石-4% / 有基石-2%
- 全量报告：18C vs 非18C 对比分析板块
- 策略报告：18C 专项分析板块（含有/无基石内部对比）

### 7. 多维相似度匹配引擎（V3.4新增，V3.5增强）
- 5维加权相似度：超购40% / 基石15% / 行业20% / 募资15% / 18C 10%（基础权重）
- [V3.5] 小样本降级保护：当二值维度特征组<5只时自动缩放权重，释放到连续维度
- [V3.5] 行业分层相似度：科技/医药/消费/工业/金融5大近亲组，组内0.7/组外0.3
- SVG雷达图可视化、相似度排名详情表

### 8. Ensemble混合引擎（V3.5新增）
- 相似度匹配 + 区间匹配双轨混合，避免单一方法的极端失真
- 自动检测小样本陷阱：Top3来自<5只特征组时，区间权重提升到80%
- 均衡模式：两种方法都有充足数据时50/50混合
- 在傅里叶03625案例中：V3.4偏差164% → V3.5偏差11.7%（改善93%）

### 8. 暗盘联动修正引擎（V3.4新增）
- 输入暗盘涨幅 → 计算偏差 → 修正首日/Day3/Day5预期
- 5种模式识别：暗盘透支/蓄力/不及预期/破发/符合预期
- 暗盘→首日转换率（中位数）+ 最相似暗盘历史案例

## Technical Constraints

- **零依赖**：纯 Python 3 标准库，不使用 pandas/numpy/sklearn 等
- **模块化**：data.py（数据）+ engine.py（引擎）+ report.py（报告）+ analyze.py（入口）
- **手写算法**：矩阵运算（高斯-约旦消元）、线性回归（正规方程）、信息增益
- **null-safe**：所有统计函数自动过滤 None 值
- **条件子模型**：按市场状态分组训练，支持降级机制

## Examples

**Example 1 — 全量回测报告：**
User: "帮我做一个港股打新甜蜜区间回测分析"
→ Run: `python3 {SKILL_DIR}/scripts/analyze.py`

**Example 2 — 已上市股票回测：**
User: "蜜雪集团 02097 的打新回测表现怎么样"
→ Run: `python3 {SKILL_DIR}/scripts/analyze.py --code 02097`

**Example 3 — 未上市新股策略：**
User: "华沿机器人 01021 超购5063倍，有基石，机器人行业，募资8.5亿，暗盘涨12%，什么时候卖合适"
→ Run: `python3 {SKILL_DIR}/scripts/analyze.py --code 01021 --subscription-mult 5063 --has-cornerstone --category 机器人 --fundraising 8.5 --dark-return 12`

**Example 4 — 18C新股策略（V3.4）：**
User: "傅里叶 03625 超购3118倍，半导体行业，募资5亿，18C无基石，暗盘跌了5%，怎么操作"
→ Run: `python3 {SKILL_DIR}/scripts/analyze.py --code 03625 --subscription-mult 3118 --category 半导体 --fundraising 5 --is-18c --dark-return -5 --name 傅里叶`

**Example 5 — 查询方法论：**
User: "甜蜜区间是怎么算出来的"
→ Load: `references/methodology.md`

## Notes

- 数据集基于东方财富、华盛通、财联社等公开数据整理
- 所有统计结论基于历史回测，不构成投资建议
- 行业分类为人工标注，可能存在主观偏差
- 新增数据可直接编辑 `analyze.py` 中的 `ipo_data` 数组
