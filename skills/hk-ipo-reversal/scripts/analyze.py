#!/usr/bin/env python3
"""港股新股暗盘反转猎手 V2 - 主入口 (CLI) (期望偏差版)
Usage:
  python3 analyze.py                                              # 全量偏差修正统计报告
  python3 analyze.py --code 02715                                 # 已上市股票修正回测
  python3 analyze.py --code 01021 --dark-return 5 --subscription-mult 5000 --expected-return 30  # 新股预测
"""
import sys
import os
import argparse
import json
import csv

# 确保能导入同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data import ipo_data, hsi_monthly
from utils import (
    label_data_market_state, classify_market_state, get_current_market_state,
    BULL, BEAR, NEUTRAL, STATE_LABELS,
)
from reversal_engine import (
    run_full_analysis, analyze_single_reversal, extract_price_path,
    train_reversal_model, auto_estimate_expected_return, compute_deviation,
    classify_deviation_type, DEVIATION_CATEGORIES,
)
from predictor import predict_reversal
from report import generate_full_report, generate_single_report, generate_predict_report


def find_stock(code, data):
    """在数据集中查找股票"""
    code = code.zfill(5)
    for d in data:
        if d["code"] == code or d["code"].lstrip("0") == code.lstrip("0"):
            return d
    return None


def export_data(result, output_dir):
    """导出CSV和JSON数据"""
    data = result.get("data", [])

    # JSON
    json_path = os.path.join(output_dir, "hk_ipo_reversal_data.json")
    export_records = []
    for d in data:
        rec = {k: v for k, v in d.items() if not k.startswith("_")}
        export_records.append(rec)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(export_records, f, ensure_ascii=False, indent=2)

    # CSV
    csv_path = os.path.join(output_dir, "hk_ipo_reversal_data.csv")
    if export_records:
        keys = list(export_records[0].keys())
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for rec in export_records:
                writer.writerow(rec)

    return json_path, csv_path


def main():
    parser = argparse.ArgumentParser(description="港股新股暗盘反转猎手 V2 (期望偏差版)")
    parser.add_argument("--code", type=str, help="港股代码")
    parser.add_argument("--dark-return", type=float, help="暗盘涨跌幅%%")
    parser.add_argument("--day1-return", type=float, help="首日涨跌幅%% (如已知)")
    parser.add_argument("--subscription-mult", type=float, help="公开认购倍数")
    parser.add_argument("--has-cornerstone", action="store_true", help="是否有基石投资者")
    parser.add_argument("--category", type=str, default="其他", help="行业分类")
    parser.add_argument("--fundraising", type=float, default=5.0, help="募资额(亿港元)")
    parser.add_argument("--name", type=str, help="证券简称")
    parser.add_argument("--expected-return", type=float, help="预期涨幅%% (可选，不指定则自动推算)")
    parser.add_argument("--output", type=str, help="输出目录")
    parser.add_argument("--no-export", action="store_true", help="不导出CSV/JSON")
    args = parser.parse_args()

    output_dir = args.output or os.getcwd()
    os.makedirs(output_dir, exist_ok=True)

    print("🔄 港股新股暗盘反转猎手 V2 (期望偏差版)")
    print(f"📊 数据集: {len(ipo_data)} 只新股")

    # 标注市场状态
    label_data_market_state(ipo_data, hsi_monthly)

    # 统计概览
    dev_neg = [d for d in ipo_data if d.get("deviation") is not None and d["deviation"] < 0]
    dark_down = [d for d in ipo_data if d.get("dark_return") is not None and d["dark_return"] < 0]
    print(f"   偏差为负(不及预期): {len(dev_neg)} 只 | 其中暗盘下跌: {len(dark_down)} 只")

    if args.code:
        stock = find_stock(args.code, ipo_data)
        if stock:
            # ======== 模式2: 已上市股票修正回测 ========
            print(f"\n📈 分析已上市股票: {stock['name']} ({stock['code']})")
            analysis = analyze_single_reversal(stock, ipo_data)

            html = generate_single_report(analysis)
            out_path = os.path.join(output_dir, f"reversal_{stock['code']}.html")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(html)

            dr = stock.get("dark_return")
            dev = stock.get("deviation")
            exp = stock.get("expected_return")
            d10 = stock.get("day10_return")
            dt = classify_deviation_type(stock)
            print(f"   类型: {DEVIATION_CATEGORIES.get(dt, dt)}")
            print(f"   暗盘: {dr:+.1f}%" if dr is not None else "   暗盘: N/A")
            print(f"   预期: {exp:+.1f}%" if exp is not None else "   预期: N/A")
            print(f"   偏差: {dev:+.1f}%" if dev is not None else "   偏差: N/A")
            print(f"   Day10: {d10:+.1f}%" if d10 is not None else "   Day10: N/A")
            print(f"   修正: {'✅ 是' if analysis['did_correct'] else '❌ 否'}")
            print(f"   相似案例: {len(analysis.get('similar_cases', []))} 只")
            print(f"\n✅ 报告已生成: {out_path}")

        else:
            # ======== 模式3: 未上市新股修正预测 ========
            if args.dark_return is None or args.subscription_mult is None:
                print(f"❌ 股票代码 {args.code} 不在数据集中（未上市新股）")
                print("   请提供 --dark-return 和 --subscription-mult 参数")
                sys.exit(1)

            params = {
                "code": args.code.zfill(5),
                "name": args.name or args.code.zfill(5),
                "dark_return": args.dark_return,
                "day1_return": args.day1_return,
                "subscription_mult": args.subscription_mult,
                "has_cornerstone": args.has_cornerstone,
                "category": args.category,
                "fundraising": args.fundraising,
                "date": "未上市",
            }

            print(f"\n🎯 预测修正概率: {params['name']} ({params['code']})")
            print(f"   暗盘: {params['dark_return']:+.1f}% | 超购: {params['subscription_mult']:.0f}倍")

            prediction = predict_reversal(
                params, ipo_data, hsi_monthly,
                expected_return=args.expected_return
            )

            html = generate_predict_report(prediction)
            out_path = os.path.join(output_dir, f"reversal_{params['code']}_predict.html")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(html)

            dev = params.get("deviation")
            exp_r = params.get("expected_return")
            dt = prediction.get("deviation_type", "normal")
            print(f"   预期涨幅: {exp_r:+.1f}%" if exp_r is not None else "   预期: 自动推算")
            print(f"   偏差: {dev:+.1f}%" if dev is not None else "   偏差: N/A")
            print(f"   类型: {DEVIATION_CATEGORIES.get(dt, dt)}")

            if prediction.get("not_applicable"):
                print(f"   ⚠️ {prediction.get('reason', '不适用')}")
            else:
                prob = prediction["probability"]
                conf = prediction["confidence"]
                advice = prediction["advice"]
                print(f"   修正概率: {prob:.0%} | 信心: {'★'*conf}{'☆'*(5-conf)}")
                print(f"   建议: {advice.get('action', '')}")
                print(f"   风险等级: {advice.get('risk_level', '')}")

            print(f"\n✅ 预测报告已生成: {out_path}")

    else:
        # ======== 模式1: 全量偏差修正统计报告 ========
        print("\n📊 运行全量偏差修正分析...")

        result = run_full_analysis(ipo_data, hsi_monthly)

        html = generate_full_report(result)
        out_path = os.path.join(output_dir, "hk_ipo_reversal.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\n✅ 报告已生成: {out_path}")

        # 导出数据
        if not args.no_export:
            json_path, csv_path = export_data(result, output_dir)
            print(f"📁 JSON导出: {json_path}")
            print(f"📁 CSV导出: {csv_path}")

        # 输出关键发现
        best = result.get("best_threshold")
        if best:
            print(f"\n🎯 最优修正定义:")
            print(f"   偏差 ≤ {best['deviation_threshold']}% + {best['window']}窗口 + {best['criterion']}")
            print(f"   修正率: {best['correction_rate']:.1f}% ({best['corrected']}/{best['total_underperform']})")

        model = result.get("model")
        if model:
            print(f"\n🧠 修正预测模型:")
            print(f"   样本: {model['n_samples']} | 正例: {model['n_positive']} | 负例: {model['n_negative']}")
            print(f"   准确率: {model['accuracy']:.1%} | AUC: {model['auc']:.3f}")
            imp = model.get("feature_importance", {})
            for name, val in sorted(imp.items(), key=lambda x: -x[1]):
                print(f"   {name}: {val:.1%}")

        # 偏差类型统计
        dev_types = result.get("deviation_types", {})
        print(f"\n📋 偏差类型分布:")
        for dt, count in dev_types.items():
            print(f"   {DEVIATION_CATEGORIES.get(dt, dt)}: {count}只")


if __name__ == "__main__":
    main()
