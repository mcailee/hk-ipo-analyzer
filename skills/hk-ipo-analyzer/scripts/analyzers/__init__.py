"""分析器注册表。"""
from analyzers.company import CompanyAnalyzer
from analyzers.industry import IndustryAnalyzer
from analyzers.valuation import ValuationAnalyzer
from analyzers.financial import FinancialAnalyzer
from analyzers.shareholder import ShareholderAnalyzer
from analyzers.cornerstone import CornerstoneAnalyzer
from analyzers.underwriting import UnderwritingAnalyzer
from analyzers.greenshoe import GreenshoeAnalyzer
from analyzers.legal import LegalAnalyzer
from analyzers.subscription import SubscriptionAnalyzer
from analyzers.liquidity import LiquidityAnalyzer
from analyzers.sentiment import MarketSentimentAnalyzer
# P2/P3 新增分析器
from analyzers.peer_comparison import PeerComparisonAnalyzer
from analyzers.ah_stock import AHStockAnalyzer
from analyzers.grey_market import GreyMarketAnalyzer


def get_phase1_analyzers() -> list:
    """Phase1 招股期：10 个基本面分析器（含市场情绪）+ 条件性 A+H 分析。"""
    return [
        ValuationAnalyzer(),
        FinancialAnalyzer(),
        IndustryAnalyzer(),
        CornerstoneAnalyzer(),
        MarketSentimentAnalyzer(),
        CompanyAnalyzer(),
        UnderwritingAnalyzer(),
        GreenshoeAnalyzer(),
        ShareholderAnalyzer(),
        LegalAnalyzer(),
        AHStockAnalyzer(),          # P2: A+H股分析（条件性，无A股时 weight=0）
    ]


def get_phase2_analyzers() -> list:
    """Phase2 认购期：新增 4 个维度（含条件性维度）。"""
    return [
        SubscriptionAnalyzer(),
        LiquidityAnalyzer(),
        PeerComparisonAnalyzer(),   # P2: 同批次新股横向对比（条件性）
        GreyMarketAnalyzer(),       # P3: 暗盘数据分析（条件性）
    ]


def get_all_analyzers() -> list:
    """全部 15 个分析器（含 3 个条件性维度）。"""
    return get_phase1_analyzers() + get_phase2_analyzers()
