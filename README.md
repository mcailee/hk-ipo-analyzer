# 🇭🇰 HK IPO Tools — 港股打新量化工具套件

> 三合一港股新股分析工具：量化评分 × 甜蜜区间 × 暗盘反转，覆盖打新全流程。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: WorkBuddy](https://img.shields.io/badge/Platform-WorkBuddy-purple.svg)](https://www.codebuddy.cn/docs/workbuddy/Overview)
[![Python](https://img.shields.io/badge/Python-≥3.10-yellow.svg)](https://python.org)

## 🧰 三大工具概览

| 工具 | 定位 | 核心能力 | 依赖 |
|------|------|----------|------|
| **[IPO Analyzer](#-ipo-analyzer--量化评分)** | 招股期全面体检 | 11维度量化评分 + 自动数据采集 + 招股书PDF解析 | requests, bs4, pdfplumber, matplotlib |
| **[Sweet Spot](#-sweet-spot--甜蜜区间)** | 卖出时点决策 | 多因子回归 + 余弦相似度匹配 + 暗盘联动修正 | **零依赖**（纯标准库） |
| **[Reversal](#-reversal--暗盘反转猎手)** | 暗盘不及预期后的修正机会 | 期望偏差分析 + Logistic回归 + 路径聚类 | **零依赖**（纯标准库） |

### 🔗 协作流程

```
招股期 ──→ IPO Analyzer（基本面评分）
                │
认购截止 ──→ Sweet Spot（甜蜜区间定位 + 卖出策略）
                │
暗盘开盘 ──→ Reversal（偏差分析 + 修正概率预测）
                │
            ╰──→ Sweet Spot（暗盘联动修正）
```

---

## 📊 IPO Analyzer — 量化评分

> 输入新股代码，自动采集公开数据，11 个维度量化评分，生成专业 HTML 研报。

### 功能特点

- **📊 11 维度量化评分** — 估值、财务、行业、基石投资者、认购热度等全方位分析
- **🕷️ 自动数据采集** — 港交所披露易 + 雪球公开数据，无需手动输入
- **📄 招股书 PDF 解析** — 自动提取财务表格、基石投资者、法律风险等关键数据
- **📈 分阶段分析** — Phase 1 招股期基本面 → Phase 2 认购期热度更新
- **🎯 雷达图 + HTML 研报** — 可视化评分雷达图 + 专业格式研报

### 评分体系

| 维度 | 权重 | 阶段 |
|------|------|------|
| 估值定价 | 18% | Phase 1 |
| 市场认购热度 | 15% | Phase 2 |
| 财务状况 | 14% | Phase 1 |
| 行业竞争 | 10% | Phase 1 |
| 基石投资者 | 10% | Phase 1 |
| 公司基本面 | 8% | Phase 1 |
| 承销发行 | 8% | Phase 1 |
| 上市后流动性 | 7% | Phase 2 |
| 绿鞋机制 | 5% | Phase 1 |
| 股东构成 | 3% | Phase 1 |
| 法律诉讼 | 2% | Phase 1 |

### 使用方法

```
# 在 WorkBuddy 中对话
帮我分析港股新股 06636

# 带招股书 PDF
分析 06636 这只新股，这是招股书 [附件：prospectus.pdf]

# 认购期更新
06636 公开认购 3318.8 倍，国际配售 5 倍，触发了回拨
```

---

## 🎯 Sweet Spot — 甜蜜区间

> 128只港股新股历史数据驱动，多因子模型定位最佳卖出时点。**V3.4 精准匹配与暗盘联动版。**

### 功能特点

- **🧮 Ridge 回归多因子模型** — 超购(含二次项)、基石、行业(LOO编码)、募资额、时间衰减WLS
- **🔍 5维余弦相似度匹配** — 超购35% / 基石20% / 行业15% / 募资15% / 18C 15%
- **🌙 暗盘联动修正引擎** — 5种模式识别（超预期/符合/轻微不及/大幅不及/严重偏离）
- **🏷️ 18C/B类风险因子** — 无基石-8% / 有基石-3% 惩罚
- **📊 分档位卖出策略** — S/A/B/C 四档 × 暗盘/首日/Day3/Day5 最优卖出时点
- **📈 SVG 雷达图可视化** — 内嵌报告，零依赖
- **🐂🐻 市场状态子模型** — 牛/熊/震荡分别建模，恒指3月累计回报±8%阈值
- **🔬 Bootstrap 置信区间** — 1000次重采样，量化预测不确定性

### 模型表现

| 指标 | 数值 |
|------|------|
| 全局 R² | 0.3996 |
| 牛市 R² | 0.4124 |
| 震荡 R² | 0.4744 |
| 时序CV Spearman ρ | 0.763 |
| 档位准确率 | 86% |

### 使用方法

```
# 在 WorkBuddy 中对话
分析港股新股 01021 的甜蜜区间

# 带暗盘数据
01021 暗盘涨了 15%，帮我修正卖出策略

# 不输入代码：生成全量回测报告
帮我跑一下港股新股甜蜜区间全量回测
```

### CLI 参数

```bash
python analyze.py                           # 全量回测报告
python analyze.py --code 01021              # 已上市股票回测
python analyze.py --code 09999 \            # 未上市新股预测
    --subscription-mult 500 \
    --has-cornerstone \
    --industry "科技" \
    --fundraise-hkd 1000 \
    --market-state auto \
    --is-18c \
    --dark-return 15.0                      # 暗盘联动修正
```

---

## 🔄 Reversal — 暗盘反转猎手

> 暗盘表现不及预期？V2 期望偏差版，分析后续修正概率与最佳买入时机。

### 功能特点

- **📐 期望偏差模型** — deviation = 暗盘涨幅 - 预期涨幅，覆盖三类场景：
  - 暗盘下跌（33只）
  - 涨幅不及预期（44只）
  - 潜力释放（小涨→后续大涨，9只）
- **🤖 Logistic 回归** — 手写实现，AUC=1.000，准确率 96.1%
- **📊 8因子模型** — 暗盘涨跌幅 / 超购 / 基石 / 换手率 / 募资 / 期望偏差 / 偏差绝对值 / 波幅
- **🎯 路径聚类** — 识别 V型反弹 / 持续下探 / 震荡修复三种修正模式
- **📈 Bootstrap 置信区间** — 量化修正概率的不确定性
- **🔮 自动偏差阈值寻优** — 数据驱动确定最优训练样本

### 使用方法

```
# 在 WorkBuddy 中对话
帮我跑一下港股暗盘反转全量报告

# 已上市股票回测
分析 01021 的暗盘反转修正情况

# 未上市新股预测（带暗盘数据）
01021 暗盘跌了 5%，超购 800 倍，帮我分析修正概率
```

---

## 📁 项目结构

```
hk-ipo-analyzer/
├── README.md
├── LICENSE (MIT)
├── .gitignore
│
├── skills/
│   ├── hk-ipo-analyzer/          # 量化评分 skill
│   │   ├── SKILL.md
│   │   ├── assets/               # 配置 + 报告模板
│   │   ├── references/           # 评分方法论文档
│   │   └── scripts/              # Python 源码（含 analyzers/, scrapers/ 等子模块）
│   │
│   ├── hk-ipo-sweet-spot/        # 甜蜜区间 skill（零依赖）
│   │   ├── SKILL.md
│   │   ├── references/           # 方法论文档
│   │   └── scripts/              # analyze.py, data.py, engine.py, report.py
│   │
│   └── hk-ipo-reversal/          # 暗盘反转猎手 skill（零依赖）
│       ├── SKILL.md
│       ├── references/           # 方法论文档
│       └── scripts/              # analyze.py, data.py, predictor.py, reversal_engine.py 等
```

## 🚀 安装

### 方式一：通过 Marketplace 安装（推荐）

在 WorkBuddy 中执行：

```
/plugin marketplace add mcailee/hk-ipo-analyzer
```

安装单个 skill：

```
/plugin install hk-ipo-analyzer@hk-ipo-analyzer     # 量化评分
/plugin install hk-ipo-analyzer@hk-ipo-sweet-spot    # 甜蜜区间
/plugin install hk-ipo-analyzer@hk-ipo-reversal      # 暗盘反转
```

### 方式二：手动安装

1. 下载本仓库对应的 `skills/<skill-name>` 目录
2. 复制到 `~/.workbuddy/skills/<skill-name>`
3. 重启 WorkBuddy

> 💡 Sweet Spot 和 Reversal 是**纯 Python 标准库**实现，无需安装任何依赖。IPO Analyzer 首次使用时会自动安装依赖。

## 📊 数据集

三个工具共享同一份港股新股历史数据集：

- **覆盖范围**: 128 只港股新股（2024年6月 — 2026年3月）
- **数据字段**: 22+ 字段（含暗盘高低价、多时点涨跌幅、基石投资者、18C标记等）
- **数据来源**: 港交所公开数据、雪球公开行情
- **更新机制**: 内嵌在各 skill 的 `data.py` 中，随版本更新

## ⚠️ 免责声明

本工具仅供研究参考，**不构成投资建议**。投资有风险，入市需谨慎。所有数据来源为公开渠道（港交所、雪球），请自行核实关键数据。

## 📄 License

[MIT](LICENSE)
