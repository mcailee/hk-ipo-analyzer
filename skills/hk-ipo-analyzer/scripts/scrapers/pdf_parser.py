"""招股书 PDF 解析器 — 从招股书提取关键数据。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.ipo_data import (
    IPOData, CompanyInfo, FinancialInfo, CornerstoneInfo,
    CornerstoneInvestor, LegalInfo, ValuationInfo,
    GreenshoeInfo, ShareholderInfo, UnderwritingInfo,
)
from utils.helpers import safe_float, safe_int, logger


# 各章节关键词（中英文/繁体）
SECTION_KEYWORDS = {
    "financial": [
        "财务资料", "Financial Information", "財務資料",
        "合并损益表", "Consolidated Statements of Profit",
    ],
    "risk": [
        "风险因素", "Risk Factors", "風險因素",
    ],
    "cornerstone": [
        "基石投资者", "Cornerstone Investors", "基石投資者",
    ],
    "underwriting": [
        "承销", "Underwriting", "包銷", "保荐人",
        "Sponsor", "Joint Bookrunners",
    ],
    "legal": [
        "法律诉讼", "Litigation", "訴訟", "法律程序",
        "Legal Proceedings",
    ],
    "greenshoe": [
        "超额配售", "Over-allotment", "Overallotment",
        "绿鞋", "Greenshoe", "穩定價格",
    ],
    "shareholder": [
        "股东", "Shareholders", "股東", "实际控制人",
        "Controlling Shareholders", "股權結構",
    ],
    "business": [
        "业务", "Business", "業務概覽", "公司简介",
        "Our Business", "Overview",
    ],
    "valuation": [
        "发售价", "Offer Price", "發售價", "招股价",
        "Price Range", "估值",
    ],
}


class PDFParser:
    """招股书 PDF 解析器。"""

    def __init__(self):
        try:
            import pdfplumber
            self.pdfplumber = pdfplumber
        except ImportError:
            logger.error("pdfplumber 未安装，请运行 install_deps.py")
            raise

    def parse(self, pdf_path: str, existing_data: Optional[IPOData] = None) -> IPOData:
        """解析招股书 PDF。"""
        data = existing_data or IPOData()
        path = Path(pdf_path)

        if not path.exists():
            logger.error(f"PDF 文件不存在: {pdf_path}")
            return data

        logger.info(f"[PDF] 开始解析: {path.name} ({path.stat().st_size / 1024 / 1024:.1f} MB)")

        try:
            with self.pdfplumber.open(str(path)) as pdf:
                total_pages = len(pdf.pages)
                logger.info(f"[PDF] 共 {total_pages} 页")

                # 按页流式处理，识别章节
                current_section = None
                section_text: dict[str, list[str]] = {k: [] for k in SECTION_KEYWORDS}
                section_tables: dict[str, list] = {k: [] for k in SECTION_KEYWORDS}

                for i, page in enumerate(pdf.pages):
                    if i % 50 == 0:
                        logger.info(f"[PDF] 处理进度: {i + 1}/{total_pages}")

                    text = page.extract_text() or ""

                    # 检测章节切换
                    detected = self._detect_section(text)
                    if detected:
                        current_section = detected

                    # 收集当前章节文本
                    if current_section and current_section in section_text:
                        section_text[current_section].append(text)
                        # 提取表格
                        tables = page.extract_tables()
                        if tables:
                            section_tables[current_section].extend(tables)

                # 解析各章节
                self._parse_financial(section_text["financial"],
                                      section_tables["financial"], data)
                self._parse_cornerstone(section_text["cornerstone"],
                                        section_tables["cornerstone"], data)
                self._parse_legal(section_text["legal"], data)
                self._parse_greenshoe(section_text["greenshoe"], data)
                self._parse_valuation(section_text["valuation"], data)
                self._parse_shareholder(section_text["shareholder"], data)
                self._parse_underwriting(section_text["underwriting"], data)
                self._parse_business(section_text["business"], data)

        except Exception as e:
            logger.error(f"[PDF] 解析异常: {e}")

        logger.info(f"[PDF] 解析完成")
        return data

    def _detect_section(self, text: str) -> Optional[str]:
        """检测当前页属于哪个章节。"""
        # 只看前 500 字符（标题通常在页面顶部）
        header = text[:500]
        for section, keywords in SECTION_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in header.lower():
                    return section
        return None

    def _parse_financial(self, texts: list[str], tables: list, data: IPOData):
        """解析财务数据章节。"""
        full_text = "\n".join(texts)
        if not full_text:
            return

        # 从表格中提取营收和利润
        for table in tables:
            if not table or len(table) < 2:
                continue
            for row in table:
                if not row:
                    continue
                row_text = " ".join([str(c) for c in row if c])

                # 营收
                if re.search(r"(收入|revenue|營業額|总收入)", row_text, re.I):
                    nums = re.findall(r'[\d,]+\.?\d*', row_text)
                    if nums:
                        vals = [safe_float(n) for n in nums]
                        vals = [v for v in vals if v and v > 0]
                        if vals:
                            data.financial.revenue_latest = vals[0]
                            if len(vals) > 1:
                                data.financial.revenue_prev = vals[1]
                            if len(vals) > 2:
                                data.financial.revenue_prev2 = vals[2]

                # 净利润
                if re.search(r"(净利润|net profit|純利|溢利)", row_text, re.I):
                    nums = re.findall(r'[\d,]+\.?\d*', row_text)
                    if nums:
                        vals = [safe_float(n) for n in nums]
                        vals = [v for v in vals if v is not None]
                        if vals:
                            data.financial.net_profit_latest = vals[0]

        # 计算增速
        if data.financial.revenue_latest and data.financial.revenue_prev:
            if data.financial.revenue_prev > 0:
                data.financial.revenue_cagr = (
                    (data.financial.revenue_latest / data.financial.revenue_prev - 1) * 100
                )

    def _parse_cornerstone(self, texts: list[str], tables: list, data: IPOData):
        """解析基石投资者。"""
        full_text = "\n".join(texts)
        if not full_text:
            return

        investors = []
        # 从表格提取
        for table in tables:
            if not table or len(table) < 2:
                continue
            header = table[0] if table[0] else []
            for row in table[1:]:
                if not row or len(row) < 2:
                    continue
                name = str(row[0]).strip() if row[0] else ""
                if len(name) < 2:
                    continue
                amount = None
                for cell in row[1:]:
                    val = safe_float(str(cell).replace(",", ""))
                    if val and val > 0:
                        amount = val
                        break
                inv = CornerstoneInvestor(name=name, amount=amount)
                # 判断是否关联方
                if re.search(r"(关联|connected|相关|associated)", name, re.I):
                    inv.is_related_party = True
                    inv.tier = "related"
                # 判断是否顶级机构
                top_names = ["GIC", "Temasek", "淡马锡", "高瓴", "红杉", "KKR",
                             "Sequoia", "Hillhouse", "BlackRock", "贝莱德"]
                for tn in top_names:
                    if tn.lower() in name.lower():
                        inv.tier = "top_pe"
                        break
                investors.append(inv)

        if investors:
            data.cornerstone.investors = investors
            total = sum(i.amount for i in investors if i.amount)
            data.cornerstone.total_amount = total if total > 0 else None

    def _parse_legal(self, texts: list[str], data: IPOData):
        """解析法律诉讼。"""
        full_text = "\n".join(texts)
        if not full_text:
            return

        # 检测刑事诉讼
        if re.search(r"(刑事|criminal)", full_text, re.I):
            data.legal.has_criminal_case = True

        # 检测监管调查
        if re.search(r"(立案调查|监管.*调查|regulatory.*investigation|enforcement)", full_text, re.I):
            data.legal.has_regulatory_investigation = True

        # 提取涉诉金额
        amounts = re.findall(r'(\d[\d,.]*)\s*(?:百万|million|千万|亿)', full_text, re.I)
        if amounts:
            total = sum(safe_float(a) or 0 for a in amounts)
            data.legal.total_amount = total

        # 统计案件数
        case_count = len(re.findall(r'(诉讼|lawsuit|litigation|案件|claim)', full_text, re.I))
        data.legal.total_cases = max(case_count, 0)

    def _parse_greenshoe(self, texts: list[str], data: IPOData):
        """解析绿鞋机制。"""
        full_text = "\n".join(texts)
        if not full_text:
            return

        data.greenshoe.has_greenshoe = True
        # 提取超额配售比例
        m = re.search(r'(\d+\.?\d*)\s*%', full_text)
        if m:
            data.greenshoe.overallotment_ratio = safe_float(m.group(1))

        # 提取稳价期
        m = re.search(r'(\d+)\s*(?:天|日|days|trading days)', full_text, re.I)
        if m:
            data.greenshoe.stabilization_period_days = safe_int(m.group(1))

    def _parse_valuation(self, texts: list[str], data: IPOData):
        """解析估值信息。"""
        full_text = "\n".join(texts)
        if not full_text:
            return

        # 招股价区间
        patterns = [
            r'HK\$\s*(\d+\.?\d*)\s*(?:to|至|—|-)\s*HK\$\s*(\d+\.?\d*)',
            r'(\d+\.?\d*)\s*港元\s*(?:至|—|-)\s*(\d+\.?\d*)\s*港元',
        ]
        for pat in patterns:
            m = re.search(pat, full_text)
            if m:
                data.valuation.offer_price_low = safe_float(m.group(1))
                data.valuation.offer_price_high = safe_float(m.group(2))
                break

    def _parse_shareholder(self, texts: list[str], data: IPOData):
        """解析股东信息。"""
        full_text = "\n".join(texts)
        if not full_text:
            return

        # 实控人持股比例
        m = re.search(r'(?:控制|controlling|实际控制人).*?(\d+\.?\d*)\s*%', full_text, re.I)
        if m:
            data.shareholder.controller_stake = safe_float(m.group(1))

        # 同股不同权
        if re.search(r'(不同投票权|weighted voting|dual[- ]class)', full_text, re.I):
            data.shareholder.has_dual_class = True

    def _parse_underwriting(self, texts: list[str], data: IPOData):
        """解析承销信息。"""
        full_text = "\n".join(texts)
        if not full_text:
            return

        # 保荐人
        sponsor_patterns = [
            r'(?:保荐人|Sponsor|保薦人)[：:\s]*([^\n,]+)',
            r'(?:联席保荐人|Joint Sponsors?)[：:\s]*([^\n]+)',
        ]
        for pat in sponsor_patterns:
            m = re.search(pat, full_text)
            if m:
                data.underwriting.sponsor = m.group(1).strip()
                break

    def _parse_business(self, texts: list[str], data: IPOData):
        """解析业务信息。"""
        full_text = "\n".join(texts)
        if not full_text:
            return

        # 主营业务（取前 200 字摘要）
        if len(full_text) > 50:
            data.company.main_business = full_text[:200].strip()
