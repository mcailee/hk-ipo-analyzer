"""核心数据模型定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# ── 评分相关 ──────────────────────────────────────────────

@dataclass
class SubScore:
    """子指标评分。"""
    name: str
    score: float          # 0-100
    detail: str           # 评分说明文字
    raw_value: Any = None # 原始数值（可选）


@dataclass
class DimensionScore:
    """维度评分结果。"""
    dimension: str                              # 维度标识（对应 config key）
    display_name: str                           # 中文显示名
    score: float                                # 维度综合分 0-100
    weight: float                               # 配置权重
    sub_scores: list[SubScore] = field(default_factory=list)
    analysis: str = ""                          # 分析段落文字
    data_sufficient: bool = True                # 数据是否充足
    red_flags: list[str] = field(default_factory=list)  # 降级红线标记


@dataclass
class SellTimingAdvice:
    """卖出时机建议。"""
    strategy: str = ""                          # "quick_flip" / "short_hold" / "medium_hold"
    suggested_days: Optional[int] = None        # 建议持有天数
    rationale: str = ""                         # 建议理由
    stop_loss_pct: Optional[float] = None       # 止损线 (%)
    take_profit_pct: Optional[float] = None     # 止盈线 (%)
    confidence: str = "medium"                  # "high" / "medium" / "low"


@dataclass
class ProbabilityEstimate:
    """预测概率区间。"""
    first_day_up_prob: Optional[float] = None       # 首日上涨概率 (%)
    first_day_down_prob: Optional[float] = None     # 首日下跌概率 (%)
    expected_return_low: Optional[float] = None     # 预期收益下限 (%)
    expected_return_mid: Optional[float] = None     # 预期收益中位数 (%)
    expected_return_high: Optional[float] = None    # 预期收益上限 (%)
    confidence_level: str = "medium"                # "high"/"medium"/"low"
    methodology: str = ""                           # 计算方法说明


@dataclass
class AllotmentEstimate:
    """中签率估算。"""
    estimated_allocation_rate: Optional[float] = None  # 估算中签率 (%)
    estimated_one_hand_win_rate: Optional[float] = None  # 一手中签率 (%)
    optimal_hands: Optional[int] = None                # 建议认购手数
    expected_profit_per_hand: Optional[float] = None   # 每手预期盈利 (HKD)
    capital_required: Optional[float] = None           # 所需本金 (HKD)
    capital_efficiency: Optional[float] = None         # 资金效率 (年化收益率 %)
    methodology: str = ""


# ── 打新策略引擎数据模型 ─────────────────────────────────

@dataclass
class AccountAllocation:
    """单账户分配方案。"""
    account_id: int = 0                         # 账户编号
    group: str = "A"                            # "A"(甲组) / "B"(乙组)
    subscription_hands: int = 0                 # 认购手数
    subscription_amount: float = 0              # 认购金额 (HKD)
    own_capital: float = 0                      # 自有资金 (HKD)
    financing_amount: float = 0                 # 融资金额 (HKD)
    financing_mult: float = 0                   # 融资倍数 (0=现金, 10=10倍孖展)
    financing_cost: float = 0                   # 融资利息成本 (HKD)
    total_cost: float = 0                       # 总成本 (自有资金 + 利息)
    expected_winning_hands: float = 0           # 预期中签手数
    expected_profit: float = 0                  # 预期收益 (HKD，扣除成本前)
    expected_net_profit: float = 0              # 预期净收益 (HKD，扣除利息)
    roi: float = 0                              # 投资回报率 (%)


@dataclass
class GroupSimulation:
    """单组别分配模拟结果。"""
    group: str = "A"                            # "A" / "B"
    total_pool_shares: Optional[float] = None   # 该组分配总股数
    total_applicants_est: Optional[float] = None  # 预估申请人数
    allocation_rate: Optional[float] = None     # 中签率 (%)
    one_hand_rate: Optional[float] = None       # 一手中签率 (%，仅甲组有意义)
    hands_allocated: Optional[float] = None     # 预期分配手数
    methodology: str = ""


@dataclass
class StrategyRecommendation:
    """打新策略完整推荐。"""
    # 投资者画像
    investor_tier: str = ""                     # "retail_small"/"retail_mid"/"whale"/"ultra_whale"
    investor_tier_label: str = ""               # "小散"/"中户"/"大户"/"超大户"
    total_capital: float = 0                    # 可用总资金 (HKD)
    num_accounts: int = 1                       # 可用账户数

    # 甲组/乙组分配模拟
    group_a_sim: Optional[GroupSimulation] = None
    group_b_sim: Optional[GroupSimulation] = None

    # 最优策略
    recommended_strategy: str = ""              # "A_only"/"B_only"/"AB_dual"/"multi_A"/"multi_A_plus_B"
    strategy_label: str = ""                    # 策略中文标签
    strategy_rationale: str = ""                # 策略推荐理由

    # 各账户分配明细
    accounts: list[AccountAllocation] = field(default_factory=list)

    # 汇总数据
    total_subscription_amount: float = 0        # 总认购金额 (HKD)
    total_own_capital: float = 0                # 总自有资金 (HKD)
    total_financing_cost: float = 0             # 总融资成本 (HKD)
    total_expected_profit: float = 0            # 总预期收益 (HKD)
    total_expected_net_profit: float = 0        # 总预期净收益 (HKD)
    overall_roi: float = 0                      # 综合回报率 (%)
    capital_efficiency_annualized: float = 0    # 年化资金效率 (%)

    # 风控
    max_loss_scenario: float = 0                # 最大亏损情景 (HKD)
    breakeven_return: float = 0                 # 盈亏平衡所需涨幅 (%)

    methodology: str = ""


@dataclass
class FinalReport:
    """最终报告。"""
    stock_code: str
    company_name: str
    phase: int                                  # 1 or 2
    total_score: float
    rating: str                                 # 强烈推荐/推荐/中性/回避
    original_rating: Optional[str] = None       # 降级前评级（无降级时 None）
    downgrade_reasons: list[str] = field(default_factory=list)
    dimension_scores: list[DimensionScore] = field(default_factory=list)
    industry: Optional[str] = None
    industry_specific_scores: list[SubScore] = field(default_factory=list)
    summary: str = ""
    phase1_score: Optional[float] = None        # Phase2 时记录 Phase1 分数
    phase1_rating: Optional[str] = None
    sell_timing: Optional[SellTimingAdvice] = None  # 卖出时机建议
    exit_strategy: Optional[str] = None         # 卖出策略建议文本
    probability: Optional[ProbabilityEstimate] = None  # 预测概率区间
    allotment: Optional[AllotmentEstimate] = None      # 中签率估算
    strategy: Optional[StrategyRecommendation] = None  # 打新策略推荐


# ── IPO 数据 ─────────────────────────────────────────────

@dataclass
class CompanyInfo:
    """公司基本信息。"""
    name: Optional[str] = None
    name_en: Optional[str] = None
    stock_code: Optional[str] = None
    industry: Optional[str] = None
    sub_industry: Optional[str] = None
    founded_year: Optional[int] = None
    headquarters: Optional[str] = None
    main_business: Optional[str] = None
    employee_count: Optional[int] = None
    market_position: Optional[str] = None
    management_background: Optional[str] = None
    # v5.0 新增
    is_18c: bool = False                            # 是否18C章节上市（未盈利科技公司）
    chapter: Optional[str] = None                   # 上市章节："18C"/"18A"/"主板"/"GEM"


@dataclass
class ValuationInfo:
    """估值定价信息。"""
    offer_price_low: Optional[float] = None     # 招股价下限（港元）
    offer_price_high: Optional[float] = None    # 招股价上限
    final_price: Optional[float] = None         # 最终定价
    total_shares: Optional[int] = None          # 发行总股数
    market_cap: Optional[float] = None          # 上市时市值（港元）
    pe_ratio: Optional[float] = None            # 发行市盈率
    ps_ratio: Optional[float] = None            # 发行市销率
    peer_avg_pe: Optional[float] = None         # 同行平均 PE
    peer_avg_ps: Optional[float] = None         # 同行平均 PS
    price_range_position: Optional[float] = None  # 定价在区间中的位置 0-1
    comparable_ipo_first_day: Optional[float] = None  # 可比 IPO 首日涨幅均值


@dataclass
class FinancialInfo:
    """财务状况。"""
    revenue_latest: Optional[float] = None      # 最新年度营收（百万港元）
    revenue_prev: Optional[float] = None        # 上一年营收
    revenue_prev2: Optional[float] = None       # 前两年营收
    revenue_cagr: Optional[float] = None        # 营收复合增速 (%)
    net_profit_latest: Optional[float] = None
    net_profit_prev: Optional[float] = None
    net_margin: Optional[float] = None          # 净利润率 (%)
    gross_margin: Optional[float] = None        # 毛利率 (%)
    operating_cashflow: Optional[float] = None  # 经营现金流
    debt_ratio: Optional[float] = None          # 资产负债率 (%)
    roe: Optional[float] = None                 # ROE (%)
    total_assets: Optional[float] = None
    net_assets: Optional[float] = None


@dataclass
class ShareholderInfo:
    """股东构成。"""
    controller_name: Optional[str] = None
    controller_stake: Optional[float] = None    # 实控人持股比例 (%)
    top10_stake: Optional[float] = None         # 前十大股东合计 (%)
    has_dual_class: Optional[bool] = None       # 是否同股不同权
    has_trust_nominee: Optional[bool] = None    # 是否有代持
    mgmt_stake: Optional[float] = None          # 管理层持股 (%)


@dataclass
class CornerstoneInvestor:
    """单个基石投资者。

    tier 分级体系 (v5.1):
        - "sovereign"  : S级 — 主权基金 (GIC/淡马锡/中投/ADIA/CPPIB/挪威主权)
        - "intl_top"   : A级 — 国际顶级机构 (高瓴/贝莱德/高盛/红杉/KKR/UBS/富达/桥水)
        - "cn_major"   : B级 — 国内大型机构 (中信资本/博裕/景林/易方达/华夏/广发/工银/富国/CPE/春华/鼎晖)
        - "cn_normal"  : C级 — 国内普通机构 (其他非关联方)
        - "related"    : 关联方 (权重最低，高占比时扣分)

    向后兼容映射: top_pe → intl_top, industry → cn_major, other → cn_normal
    """
    name: str
    amount: Optional[float] = None              # 认购金额（百万港元）
    is_related_party: bool = False              # 是否关联方
    tier: str = "cn_normal"                     # "sovereign"/"intl_top"/"cn_major"/"cn_normal"/"related"
    lockup_months: Optional[int] = None


# v5.1 基石分级权重表（默认值，可被 config.yaml 覆盖）
CORNERSTONE_TIER_WEIGHTS: dict[str, float] = {
    "sovereign": 1.0,
    "intl_top": 0.8,
    "cn_major": 0.55,
    "cn_normal": 0.3,
    "related": 0.15,
    # 向后兼容旧 tier 值
    "top_pe": 0.8,
    "industry": 0.55,
    "other": 0.3,
}


@dataclass
class CornerstoneInfo:
    """基石投资者信息。"""
    investors: list[CornerstoneInvestor] = field(default_factory=list)
    total_amount: Optional[float] = None
    total_ratio: Optional[float] = None         # 占发行规模比例 (%)

    def calc_quality_scores(self, tier_weights: Optional[dict[str, float]] = None,
                            wqs_awqs_ratio: float = 0.4) -> dict[str, float]:
        """计算基石质量分 (v5.1)。

        Returns:
            dict with keys: wqs, awqs, combined, sa_ratio, conviction_bonus
        """
        weights = tier_weights or CORNERSTONE_TIER_WEIGHTS
        investors = self.investors
        if not investors:
            return {"wqs": 0, "awqs": 0, "combined": 0, "sa_ratio": 0, "conviction_bonus": 0}

        # WQS: 数量加权质量分 (0-100)
        wqs = sum(weights.get(inv.tier, 0.3) for inv in investors) / len(investors) * 100

        # AWQS: 金额加权质量分 (0-100)
        total_amount = sum(inv.amount for inv in investors if inv.amount)
        if total_amount > 0:
            awqs = sum(weights.get(inv.tier, 0.3) * (inv.amount or 0)
                       for inv in investors) / total_amount * 100
        else:
            awqs = wqs  # 无金额数据时退化为数量加权

        # 综合质量分
        combined = wqs_awqs_ratio * wqs + (1 - wqs_awqs_ratio) * awqs

        # S/A 级认购占比 (用于信心倍增器)
        sa_tiers = {"sovereign", "intl_top", "top_pe"}
        sa_amount = sum(inv.amount for inv in investors
                        if inv.tier in sa_tiers and inv.amount)
        # 用 total_amount 作为分母（基石总认购额），配合 total_ratio 可推算占发行额比例
        offering_amount = 0.0
        if self.total_ratio and self.total_ratio > 0 and total_amount > 0:
            # total_ratio 是基石占发行额的百分比
            ratio = self.total_ratio / 100 if self.total_ratio > 1 else self.total_ratio
            offering_amount = total_amount / ratio if ratio > 0 else 0
        sa_ratio = sa_amount / offering_amount if offering_amount > 0 else 0

        # 信心倍增器
        if sa_ratio >= 0.30:
            conviction_bonus = 12
        elif sa_ratio >= 0.20:
            conviction_bonus = 8
        elif sa_ratio >= 0.10:
            conviction_bonus = 4
        else:
            conviction_bonus = 0

        return {
            "wqs": round(wqs, 1),
            "awqs": round(awqs, 1),
            "combined": round(combined, 1),
            "sa_ratio": round(sa_ratio, 4),
            "conviction_bonus": conviction_bonus,
        }


@dataclass
class UnderwritingInfo:
    """承销发行。"""
    sponsor: Optional[str] = None               # 保荐人
    sponsor_tier: Optional[str] = None          # 保荐人层级
    sponsor_historical_break_rate: Optional[float] = None  # 历史首日破发率 (%)
    joint_sponsors: list[str] = field(default_factory=list)
    underwriters: list[str] = field(default_factory=list)
    offer_size: Optional[float] = None          # 发行规模（百万港元）
    listing_date: Optional[str] = None
    application_times: Optional[int] = None     # 递表次数


@dataclass
class GreenshoeInfo:
    """绿鞋机制。"""
    has_greenshoe: Optional[bool] = None
    overallotment_ratio: Optional[float] = None  # 超额配售权比例 (%)
    stabilization_period_days: Optional[int] = None


@dataclass
class LegalInfo:
    """法律诉讼。"""
    total_cases: Optional[int] = None
    total_amount: Optional[float] = None        # 涉诉总金额（百万港元）
    has_criminal_case: bool = False
    has_regulatory_investigation: bool = False
    major_cases_summary: Optional[str] = None


@dataclass
class MarketSentimentInfo:
    """市场情绪数据（Phase1/Phase2 均可用）。"""
    hsi_1m_change: Optional[float] = None               # 恒指近1月涨跌幅 (%)
    ipo_break_rate_30d: Optional[float] = None          # 近30日IPO破发率 (%)
    southbound_net_flow: Optional[float] = None         # 南向资金净流入（亿港元，正数=净流入）
    hsi_volatility: Optional[float] = None              # 恒指波动率 / VIX (%)


@dataclass
class SubscriptionInfo:
    """市场认购热度（Phase2）。"""
    public_subscription_mult: Optional[float] = None    # 公开认购倍数
    intl_placement_mult: Optional[float] = None         # 国际配售倍数
    clawback_triggered: Optional[bool] = None           # 是否触发回拨（机制A）
    concurrent_ipos: Optional[int] = None               # 同期上市新股数
    recent_break_rate: Optional[float] = None           # 近期破发率 (%)
    # ── 机制 A/B 适配字段 ──
    pricing_mechanism: Optional[str] = None             # "A" / "B" / None（未知）
    public_offer_ratio: Optional[float] = None          # 公开发售占比 (%)
    # 机制B 专属字段
    mech_b_price_vs_range: Optional[float] = None       # 最终定价相对指示区间位置 (0-1)
    mech_b_institutional_orders: Optional[float] = None # 机构投资者下单倍数
    mech_b_retail_indicated_mult: Optional[float] = None  # 散户意向认购倍数
    allocation_rate: Optional[float] = None             # 中签率 (%)


@dataclass
class LiquidityInfo:
    """上市后流动性（Phase2）。"""
    free_float_market_cap: Optional[float] = None       # 自由流通市值（百万港元）
    hk_connect_eligible: Optional[bool] = None          # 是否可纳入港股通
    has_market_maker: Optional[bool] = None
    estimated_daily_turnover: Optional[float] = None    # 预估日均成交（百万港元）


@dataclass
class IndustrySpecificData:
    """行业专属数据（动态字段）。"""
    industry_type: Optional[str] = None  # "tmt" / "pharma" / "consumer"
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class PeerIPO:
    """同批次 IPO 对比标的。"""
    stock_code: str
    company_name: str
    industry: Optional[str] = None
    offer_size: Optional[float] = None              # 发行规模（百万港元）
    pe_ratio: Optional[float] = None
    first_day_return: Optional[float] = None        # 首日涨跌幅 (%)
    subscription_mult: Optional[float] = None       # 公开认购倍数
    total_score: Optional[float] = None             # 本系统评分（如有）
    listing_date: Optional[str] = None


@dataclass
class PeerComparisonInfo:
    """同批次新股横向对比数据。"""
    peers: list[PeerIPO] = field(default_factory=list)
    batch_avg_first_day_return: Optional[float] = None   # 同批次平均首日涨幅 (%)
    batch_avg_subscription_mult: Optional[float] = None  # 同批次平均认购倍数
    batch_break_rate: Optional[float] = None             # 同批次破发率 (%)
    relative_rank: Optional[int] = None                  # 在同批次中的排名
    total_in_batch: Optional[int] = None                 # 同批次总数


@dataclass
class AHStockInfo:
    """A+H 股分析数据。"""
    has_a_share: bool = False                       # 是否有对应A股
    a_stock_code: Optional[str] = None              # A股代码
    a_stock_price: Optional[float] = None           # A股当前价格 (CNY)
    h_stock_price: Optional[float] = None           # H股当前/发行价 (HKD)
    ah_premium: Optional[float] = None              # A/H 溢价率 (%)，正=A股溢价
    exchange_rate: Optional[float] = None           # CNY/HKD 汇率
    a_share_pe: Optional[float] = None              # A股 PE
    h_share_pe: Optional[float] = None              # H股 PE（发行）
    sector_avg_ah_premium: Optional[float] = None   # 行业平均 A/H 溢价
    a_share_turnover_rate: Optional[float] = None   # A股日均换手率 (%)


@dataclass
class GreyMarketInfo:
    """暗盘数据。"""
    grey_market_price: Optional[float] = None       # 暗盘价格 (HKD)
    offer_price: Optional[float] = None             # 发行价 (HKD)
    grey_market_premium: Optional[float] = None     # 暗盘溢价率 (%)
    grey_market_volume: Optional[float] = None      # 暗盘成交量（手）
    grey_market_turnover: Optional[float] = None    # 暗盘成交额（百万港元）
    data_source: Optional[str] = None               # 数据来源（辉立/耀才等）
    last_update_time: Optional[str] = None          # 最后更新时间


@dataclass
class IPOData:
    """IPO 全量数据容器。"""
    company: CompanyInfo = field(default_factory=CompanyInfo)
    valuation: ValuationInfo = field(default_factory=ValuationInfo)
    financial: FinancialInfo = field(default_factory=FinancialInfo)
    shareholder: ShareholderInfo = field(default_factory=ShareholderInfo)
    cornerstone: CornerstoneInfo = field(default_factory=CornerstoneInfo)
    underwriting: UnderwritingInfo = field(default_factory=UnderwritingInfo)
    greenshoe: GreenshoeInfo = field(default_factory=GreenshoeInfo)
    legal: LegalInfo = field(default_factory=LegalInfo)
    subscription: SubscriptionInfo = field(default_factory=SubscriptionInfo)
    liquidity: LiquidityInfo = field(default_factory=LiquidityInfo)
    industry_specific: IndustrySpecificData = field(default_factory=IndustrySpecificData)
    market_sentiment: MarketSentimentInfo = field(default_factory=MarketSentimentInfo)
    # ── P2/P3 新增 ──
    peer_comparison: PeerComparisonInfo = field(default_factory=PeerComparisonInfo)
    ah_stock: AHStockInfo = field(default_factory=AHStockInfo)
    grey_market: GreyMarketInfo = field(default_factory=GreyMarketInfo)
