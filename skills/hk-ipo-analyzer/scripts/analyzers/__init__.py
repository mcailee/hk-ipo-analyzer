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


def get_phase1_analyzers() -> list:
    """Phase1 招股期：9 个基本面分析器。"""
    return [
        ValuationAnalyzer(),
        FinancialAnalyzer(),
        IndustryAnalyzer(),
        CornerstoneAnalyzer(),
        CompanyAnalyzer(),
        UnderwritingAnalyzer(),
        GreenshoeAnalyzer(),
        ShareholderAnalyzer(),
        LegalAnalyzer(),
    ]


def get_phase2_analyzers() -> list:
    """Phase2 认购期：新增 2 个维度。"""
    return [
        SubscriptionAnalyzer(),
        LiquidityAnalyzer(),
    ]


def get_all_analyzers() -> list:
    """全部 11 个分析器。"""
    return get_phase1_analyzers() + get_phase2_analyzers()
