# 数据源说明

## 港交所披露易 (HKEX News)

- **URL**: https://www.hkexnews.hk
- **数据内容**: IPO 基本信息、招股文件列表、公告文件
- **搜索入口**: `/listedco/listconews/advancedsearchEHTC.htm`
- **参数**: `StockCode` (股票代码), `DocType` (文件类型: IPO/Prospectus/Announcement)
- **编码**: UTF-8，部分繁体中文
- **注意**: 反爬较弱，但需合理间隔请求

## 雪球 (Xueqiu)

- **URL**: https://xueqiu.com / https://stock.xueqiu.com
- **数据内容**: 实时行情、财务数据、行业分类、同行比较
- **API 示例**:
  - 行情: `/v5/stock/quote.json?symbol=HK09999&extend=detail`
  - 财务: `/v5/stock/finance/cn/indicator.json?symbol=HK09999&type=Q4&count=3`
  - 筛选: `/v5/stock/screener/quote/list.json?market=HK&industry=xxx`
- **认证**: 需先访问主页获取 cookie，后续请求自动携带
- **编码**: JSON UTF-8

## 招股书 PDF

- **来源**: 港交所披露易下载，或用户本地提供
- **格式**: PDF，通常 200-800 页
- **关键章节定位关键词**:
  - 财务: "财务资料", "Financial Information", "財務資料"
  - 风险: "风险因素", "Risk Factors", "風險因素"
  - 基石: "基石投资者", "Cornerstone Investors", "基石投資者"
  - 承销: "承销", "Underwriting", "包銷"
  - 法律: "法律诉讼", "Litigation", "訴訟"
  - 绿鞋: "超额配售", "Over-allotment", "穩定價格"
  - 股东: "股东", "Shareholders", "股東"
  - 业务: "业务", "Business", "業務概覽"
  - 估值: "发售价", "Offer Price", "發售價"
