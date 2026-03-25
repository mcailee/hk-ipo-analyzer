# 🇭🇰 HK IPO Analyzer — 港股打新量化分析助手

> 输入新股代码，自动采集公开数据，11 个维度量化评分，生成专业 HTML 研报。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: WorkBuddy](https://img.shields.io/badge/Platform-WorkBuddy-purple.svg)](https://www.codebuddy.cn/docs/workbuddy/Overview)
[![Python](https://img.shields.io/badge/Python-≥3.10-yellow.svg)](https://python.org)

## ✨ 功能特点

- **📊 11 维度量化评分** — 估值、财务、行业、基石投资者、认购热度等全方位分析
- **🕷️ 自动数据采集** — 港交所披露易 + 雪球公开数据，无需手动输入
- **📄 招股书 PDF 解析** — 自动提取财务表格、基石投资者、法律风险等关键数据
- **📈 分阶段分析** — Phase 1 招股期基本面分析 → Phase 2 认购期热度更新
- **🎯 雷达图 + HTML 研报** — 可视化评分雷达图 + 专业格式研报一键生成
- **🏭 行业特化指标** — 自动识别 TMT / 医药 / 消费行业，加载专用分析模型

## 📸 报告示例

<details>
<summary>点击查看报告截图</summary>

报告包含：
- 综合评分 + 评级
- 关键指标速览
- 11 维度评分条 + 雷达图
- 同批次新股横向对比
- 策略建议 + 首日走势预测
- IPO 时间线

</details>

## 🚀 安装

### 方式一：通过 Marketplace 安装（推荐）

在 WorkBuddy 中执行：

```
/plugin marketplace add mcailee/hk-ipo-analyzer
/plugin install hk-ipo-analyzer@hk-ipo-tools
```

### 方式二：手动安装

1. 下载本仓库的 `skills/hk-ipo-analyzer` 目录
2. 复制到 `~/.workbuddy/skills/hk-ipo-analyzer`
3. 重启 WorkBuddy

### 依赖安装

首次使用时，Skill 会自动安装 Python 依赖（requests, beautifulsoup4, pdfplumber, matplotlib）。

## 📖 使用方法

### Phase 1 — 招股期分析

直接告诉 WorkBuddy：

```
帮我分析港股新股 06636
```

或带招股书 PDF：

```
分析 06636 这只新股，这是招股书 [附件：prospectus.pdf]
```

### Phase 2 — 认购期更新

当认购数据出来后：

```
06636 公开认购 3318.8 倍，国际配售 5 倍，触发了回拨
```

## 📊 评分体系

| 维度 | 权重 | 分析阶段 |
|------|------|----------|
| 估值定价 (Valuation) | 18% | Phase 1 |
| 市场认购热度 (Subscription) | 15% | Phase 2 |
| 财务状况 (Financial) | 14% | Phase 1 |
| 行业竞争 (Industry) | 10% | Phase 1 |
| 基石投资者 (Cornerstone) | 10% | Phase 1 |
| 公司基本面 (Company) | 8% | Phase 1 |
| 承销发行 (Underwriting) | 8% | Phase 1 |
| 上市后流动性 (Liquidity) | 7% | Phase 2 |
| 绿鞋机制 (Greenshoe) | 5% | Phase 1 |
| 股东构成 (Shareholder) | 3% | Phase 1 |
| 法律诉讼 (Legal) | 2% | Phase 1 |

### 评级标准

| 评分 | 评级 | 建议 |
|------|------|------|
| ≥ 80 | 🟢 强烈推荐 | Strong Buy |
| 65–79 | 🔵 推荐 | Buy |
| 50–64 | 🟡 中性 | Neutral |
| < 50 | 🔴 回避 | Avoid |

## 🏗️ 项目结构

```
hk-ipo-analyzer/
├── SKILL.md                    # Skill 定义（触发条件 + 工作流）
├── assets/
│   ├── config.yaml             # 评分权重 & 阈值配置
│   └── templates/
│       └── report.html         # HTML 报告模板
├── references/
│   ├── scoring_methodology.md  # 评分方法论
│   ├── industry_indicators.md  # 行业特化指标
│   └── data_sources.md         # 数据源说明
└── scripts/
    ├── analyze.py              # Phase 1 入口
    ├── update.py               # Phase 2 入口
    ├── install_deps.py         # 依赖安装
    ├── requirements.txt        # Python 依赖
    ├── models/                 # 数据模型
    ├── analyzers/              # 11 维度分析器
    │   └── industry_specific/  # 行业特化分析
    ├── scoring/                # 评分引擎
    ├── scrapers/               # 数据采集器
    ├── reports/                # 报告生成
    └── utils/                  # 工具函数
```

## ⚙️ 自定义配置

编辑 `assets/config.yaml` 可自定义：
- 各维度评分权重
- 评级阈值
- 数据采集间隔
- 行业判断关键词

## ⚠️ 免责声明

本工具仅供研究参考，**不构成投资建议**。投资有风险，入市需谨慎。所有数据来源为公开渠道（港交所、雪球），请自行核实关键数据。

## 📄 License

[MIT](LICENSE)
