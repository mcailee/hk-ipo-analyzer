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
    """单个基石投资者。"""
    name: str
    amount: Optional[float] = None              # 认购金额（百万港元）
    is_related_party: bool = False              # 是否关联方
    tier: str = "other"                         # "sovereign"/"top_pe"/"industry"/"related"/"other"
    lockup_months: Optional[int] = None


@dataclass
class CornerstoneInfo:
    """基石投资者信息。"""
    investors: list[CornerstoneInvestor] = field(default_factory=list)
    total_amount: Optional[float] = None
    total_ratio: Optional[float] = None         # 占发行规模比例 (%)


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
class SubscriptionInfo:
    """市场认购热度（Phase2）。"""
    public_subscription_mult: Optional[float] = None    # 公开认购倍数
    intl_placement_mult: Optional[float] = None         # 国际配售倍数
    clawback_triggered: Optional[bool] = None           # 是否触发回拨
    concurrent_ipos: Optional[int] = None               # 同期上市新股数
    recent_break_rate: Optional[float] = None           # 近期破发率 (%)


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
