# -*- coding: utf-8 -*-
"""
舆情监控引擎 — 通用版
======================
通用舆情监控引擎，所有监控对象、关键词、接收人等均通过配置文件驱动。

核心能力：
1. 四色预警等级（蓝黄橙红）
2. 热度评估算法（平台权重 + 排名 + 新鲜度）
3. SnowNLP 本地情感初筛（零 token）+ LLM 精判（省 token 策略）
4. 语义去重（内容指纹 + 编辑距离）
5. 趋势追踪（跨报告对比）
6. 配置驱动的关键词管理（核心/产品/技术/关联/变体 5 类）

依赖：pip install snownlp
"""

import json
import os
import sys
import hashlib
from datetime import datetime, timedelta

# ============================================================
# 配置管理
# ============================================================

DEFAULT_CONFIG = {
    "target_name": "",
    "target_aliases": [],
    "keywords": {
        "core": [],
        "products": [],
        "tech": [],
        "people": [],
        "variants": [],
    },
    "email_to": "",
    "platforms": [],
    "data_dir": "",
    "history_file": "",
    "trends_file": "",
}

# 四色预警等级
ALERT_BLUE = "blue"
ALERT_YELLOW = "yellow"
ALERT_ORANGE = "orange"
ALERT_RED = "red"

ALERT_CONFIG = {
    "blue":   {"label": "蓝色预警", "color": "#3498db", "bg": "#eaf2f8", "icon": "I", "tag": "关注"},
    "yellow": {"label": "黄色预警", "color": "#f39c12", "bg": "#fef9e7", "icon": "!!", "tag": "注意"},
    "orange": {"label": "橙色预警", "color": "#e67e22", "bg": "#fdf2e9", "icon": "!!!", "tag": "警告"},
    "red":    {"label": "红色预警", "color": "#c0392b", "bg": "#fdedec", "icon": "URGENT", "tag": "紧急"},
    "none":   {"label": "无预警", "color": "#95a5a6", "bg": "#f8f9fa", "icon": "-", "tag": "-"},
}

# 平台权重
PLATFORM_WEIGHT = {
    "微博": 3, "小红书": 3, "知乎": 3, "抖音": 3,
    "百度新闻": 2, "搜狗新闻": 2, "新浪新闻": 2, "搜狐新闻": 2,
    "新京报": 2, "澎湃新闻": 2, "今日头条": 2,
    "百度": 1, "搜狗": 1, "360搜索": 1, "必应": 1,
    "微信": 2, "领英": 1,
    "智联招聘": 1, "职Q": 1, "脉脉": 1, "看准网": 1, "爱企查": 1,
    "金融界": 2, "医麦客": 2, "智慧芽": 2,
}

# 高权威媒体
HIGH_AUTHORITY = ["新京报", "澎湃新闻", "人民日报", "新华社", "央视", "经济观察报"]

# 严重负面关键词（橙色预警）
SEVERE_NEGATIVE_KEYWORDS = [
    "处罚", "行政处罚", "违法", "欺诈", "造假", "败诉",
    "监管", "介入", "调查", "立案", "冻结", "查封",
    "产品缺陷", "质量事故", "医疗事故", "不良反应",
]

# 红色预警关键词
RED_ALERT_KEYWORDS = [
    "热搜", "封杀", "停业", "吊销", "刑拘", "逮捕",
]

# SnowNLP 情感阈值
POSITIVE_THRESHOLD = 0.70  # > 0.70 判为正面
NEGATIVE_THRESHOLD = 0.30  # < 0.30 判为负面
# 0.30 ~ 0.70 不确定，需要 LLM 精判


def load_config(config_path):
    """加载监控配置文件"""
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    # 合并默认值
    for k, v in DEFAULT_CONFIG.items():
        if k not in cfg:
            cfg[k] = v
    # 合并 keywords 子字段
    for k, v in DEFAULT_CONFIG["keywords"].items():
        if k not in cfg["keywords"]:
            cfg["keywords"][k] = v
    return cfg


def get_all_keywords(cfg):
    """获取所有关键词列表"""
    kws = cfg["keywords"]
    return kws["core"] + kws["products"] + kws["tech"] + kws["people"] + kws["variants"]


def get_keyword_count(cfg):
    """获取各类关键词数量"""
    kws = cfg["keywords"]
    return {
        "core": len(kws["core"]),
        "products": len(kws["products"]),
        "tech": len(kws["tech"]),
        "people": len(kws["people"]),
        "variants": len(kws["variants"]),
        "total": sum(len(v) for v in kws.values()),
    }


def get_data_dir(cfg):
    """获取数据目录，自动创建"""
    d = cfg.get("data_dir", "")
    if not d:
        d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(config_path))), "sentiment_data")
    os.makedirs(d, exist_ok=True)
    return d


def get_history_file(cfg, data_dir=None):
    """获取历史文件路径"""
    if data_dir is None:
        data_dir = get_data_dir(cfg)
    return cfg.get("history_file", "") or os.path.join(data_dir, "history.json")


def get_trends_file(cfg, data_dir=None):
    """获取趋势文件路径"""
    if data_dir is None:
        data_dir = get_data_dir(cfg)
    return cfg.get("trends_file", "") or os.path.join(data_dir, "trends.json")


# ============================================================
# SnowNLP 本地情感分析（零 token 消耗）
# ============================================================

def snownlp_classify(text):
    """
    用 SnowNLP 对文本做情感分类。

    返回: (sentiment, confidence, needs_llm)
      sentiment: "positive" / "negative" / "neutral"
      confidence: 0.0-1.0
      needs_llm: True = SnowNLP 不确定，需 LLM 精判
    """
    try:
        from snownlp import SnowNLP
        s = SnowNLP(text)
        score = s.sentiments

        if score > POSITIVE_THRESHOLD:
            return ("positive", round(score, 3), False)
        elif score < NEGATIVE_THRESHOLD:
            return ("negative", round(score, 3), False)
        else:
            return ("neutral", round(abs(score - 0.5) * 2, 3), True)
    except ImportError:
        return ("neutral", 0.0, True)


def batch_snow_classify(items):
    """
    批量 SnowNLP 分类。

    items: [{"title": "...", "summary": "..."}, ...]
    返回: (results, uncertain_indices)
    """
    results = []
    uncertain_indices = []

    for i, item in enumerate(items):
        text = f"{item.get('title', '')} {item.get('summary', '')}".strip()
        sentiment, confidence, needs_llm = snownlp_classify(text)
        results.append({
            "sentiment": sentiment,
            "confidence": confidence,
            "needs_llm": needs_llm,
            "method": "snownlp" if not needs_llm else "pending_llm",
        })
        if needs_llm:
            uncertain_indices.append(i)

    return results, uncertain_indices


# ============================================================
# 工具函数
# ============================================================

def load_json(filepath, default=None):
    if default is None:
        default = {}
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def content_fingerprint(title, summary="", url=""):
    """内容指纹"""
    text = f"{title}|{(summary or '')[:30]}|{url}".strip().lower()
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]


def levenshtein_distance(s1, s2):
    """编辑距离"""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = range(len(s2) + 1)
    for c1 in s1:
        curr_row = [prev_row[0] + 1]
        for j, c2 in enumerate(s2):
            curr_row.append(min(
                curr_row[j] + 1,
                prev_row[j + 1] + 1,
                prev_row[j] + (c1 != c2),
            ))
        prev_row = curr_row
    return prev_row[-1]


def is_similar_title(t1, t2, threshold=0.8):
    """标题相似度判断"""
    if not t1 or not t2:
        return False
    t1, t2 = t1.strip(), t2.strip()
    if t1 == t2:
        return True
    max_len = max(len(t1), len(t2))
    if max_len == 0:
        return False
    return 1 - levenshtein_distance(t1, t2) / max_len >= threshold


def deduplicate_items(items):
    """智能去重：指纹 + 编辑距离"""
    if not items:
        return items
    seen_fp = set()
    unique = []
    for item in items:
        fp = content_fingerprint(item.get("title", ""), item.get("summary", ""), item.get("url", ""))
        if fp not in seen_fp:
            seen_fp.add(fp)
            unique.append(item)
    result = []
    for item in unique:
        if not any(is_similar_title(e.get("title", ""), item.get("title", ""), 0.8) for e in result):
            result.append(item)
    return result


def calc_heat_score(platform, rank, publish_date_str=""):
    """热度评分"""
    pw = 1
    for key, weight in PLATFORM_WEIGHT.items():
        if key in (platform or ""):
            pw = weight
            break
    try:
        r = int(rank) if rank else 5
    except (ValueError, TypeError):
        r = 5
    rank_score = 3 if r <= 3 else (2 if r <= 6 else 1)
    freshness = 0.5
    if publish_date_str:
        try:
            for fmt in ["%Y-%m-%d", "%Y年%m月%d日", "%Y/%m/%d"]:
                try:
                    pub_date = datetime.strptime(publish_date_str[:10], fmt)
                    days_ago = (datetime.now() - pub_date).days
                    freshness = 3 if days_ago <= 1 else (2 if days_ago <= 3 else (1 if days_ago <= 7 else 0.5))
                    break
                except ValueError:
                    continue
        except Exception:
            pass
    return round(pw * rank_score * freshness, 1)


def assess_alert_level(item, all_items):
    """评估单条舆情的预警等级"""
    if item.get("sentiment") != "negative":
        return "none"
    title = item.get("title", "")
    summary = item.get("summary", "")
    source = item.get("source", "")
    text = f"{title} {summary}".lower()
    heat = item.get("heat_score", 0)

    for kw in RED_ALERT_KEYWORDS:
        if kw in text:
            return ALERT_RED
    for kw in SEVERE_NEGATIVE_KEYWORDS:
        if kw in text:
            return ALERT_ORANGE
    for auth in HIGH_AUTHORITY:
        if auth in source:
            return ALERT_ORANGE

    same_topic = sum(
        1 for it in all_items
        if it.get("sentiment") == "negative" and is_similar_title(it.get("title", ""), title, 0.6)
    )
    if same_topic >= 2 or heat >= 6:
        return ALERT_YELLOW
    return ALERT_BLUE


def get_highest_alert(alert_levels):
    """获取最高预警等级"""
    priority = {"red": 4, "orange": 3, "yellow": 2, "blue": 1, "none": 0}
    highest = "none"
    for level in alert_levels:
        if priority.get(level, 0) > priority.get(highest, 0):
            highest = level
    return highest


def get_run_label():
    """根据当前时间返回早报/午报/晚报"""
    h = datetime.now().hour
    if 7 <= h < 10:
        return "早报"
    elif 11 <= h < 14:
        return "午报"
    elif 16 <= h < 18:
        return "晚报"
    return "临时报告"


def time_ago_str(dt_str):
    """时间差描述"""
    if not dt_str:
        return "首次监控"
    try:
        dt = datetime.fromisoformat(dt_str)
        delta = datetime.now() - dt
        d, h, m = delta.days, delta.seconds // 3600, (delta.seconds % 3600) // 60
        if d > 0:
            return f"{d}天{h}小时前"
        elif h > 0:
            return f"{h}小时{m}分钟前"
        return f"{m}分钟前"
    except Exception:
        return "未知"


# ============================================================
# 趋势追踪
# ============================================================

def record_trend(cfg, pos_count, neg_count, neu_count, alert_level, run_label):
    """记录趋势"""
    trends = load_json(get_trends_file(cfg), {"reports": []})
    trends["reports"].append({
        "time": datetime.now().isoformat(),
        "label": run_label,
        "positive": pos_count,
        "negative": neg_count,
        "neutral": neu_count,
        "alert_level": alert_level,
    })
    if len(trends["reports"]) > 30:
        trends["reports"] = trends["reports"][-30:]
    save_json(get_trends_file(cfg), trends)
    return trends


def get_trend_summary(cfg):
    """趋势对比"""
    trends = load_json(get_trends_file(cfg), {"reports": []})
    reports = trends.get("reports", [])
    if len(reports) < 2:
        return None
    curr, prev = reports[-1], reports[-2]
    return {
        "prev_time": prev["time"],
        "curr_time": curr["time"],
        "pos_delta": curr["positive"] - prev["positive"],
        "neg_delta": curr["negative"] - prev["negative"],
        "neu_delta": curr["neutral"] - prev["neutral"],
        "prev_alert": prev["alert_level"],
        "curr_alert": curr["alert_level"],
        "consecutive_neg_rise": _check_consecutive_neg_rise(reports),
    }


def _check_consecutive_neg_rise(reports, window=3):
    if len(reports) < window + 1:
        return False
    recent = reports[-(window + 1):]
    return all(recent[i]["negative"] > recent[i - 1]["negative"] for i in range(1, len(recent)))


# ============================================================
# 配置生成
# ============================================================

def generate_config(target_name, target_aliases=None, keywords=None, email_to="",
                    data_dir="", platforms=None):
    """
    生成监控配置文件内容。

    Args:
        target_name: 监控目标名称（如"小米科技"）
        target_aliases: 别名列表（如["Xiaomi", "MI"]）
        keywords: 关键词字典，可包含 core/products/tech/people/variants
        email_to: 报告接收邮箱
        data_dir: 数据存储目录
        platforms: 指定搜索平台（空=全网）
    """
    if target_aliases is None:
        target_aliases = []
    if keywords is None:
        keywords = {}
    if platforms is None:
        platforms = []

    cfg = {
        "target_name": target_name,
        "target_aliases": target_aliases,
        "keywords": {
            "core": keywords.get("core", [target_name]),
            "products": keywords.get("products", []),
            "tech": keywords.get("tech", []),
            "people": keywords.get("people", []),
            "variants": keywords.get("variants", []),
        },
        "email_to": email_to,
        "platforms": platforms if platforms else [],
        "data_dir": data_dir,
        "created_at": datetime.now().isoformat(),
    }
    return cfg


# ============================================================
# CLI
# ============================================================

def main():
    if len(sys.argv) < 2:
        print("Sentiment Monitor Engine v4 (Universal)")
        print()
        print("Usage:")
        print(f"  python {os.path.basename(__file__)} <config.json> keywords       - List all keywords")
        print(f"  python {os.path.basename(__file__)} <config.json> alerts         - Show alert levels")
        print(f"  python {os.path.basename(__file__)} <config.json> trends         - Show trends")
        print(f"  python {os.path.basename(__file__)} <config.json> history        - Show history")
        print(f"  python {os.path.basename(__file__)} <config.json> dedup test     - Test dedup")
        print(f"  python {os.path.basename(__file__)} <config.json> classify <text> - Test SnowNLP")
        print(f"  python {os.path.basename(__file__)} <config.json> benchmark      - Run benchmark")
        sys.exit(1)

    config_path = sys.argv[1]
    if not os.path.exists(config_path):
        print(f"Error: config not found: {config_path}")
        sys.exit(1)

    cfg = load_config(config_path)
    action = sys.argv[2] if len(sys.argv) > 2 else ""

    if action == "keywords":
        groups = [
            ("Core", cfg["keywords"]["core"]),
            ("Products", cfg["keywords"]["products"]),
            ("Tech", cfg["keywords"]["tech"]),
            ("People", cfg["keywords"]["people"]),
            ("Variants", cfg["keywords"]["variants"]),
        ]
        total = 0
        for name, kws in groups:
            if kws:
                print(f"\n=== {name} ({len(kws)}) ===")
                for kw in kws:
                    print(f"  {kw}")
                total += len(kws)
        print(f"\nTotal: {total} keywords")
        print(f"Target: {cfg['target_name']}")

    elif action == "alerts":
        print("=== Alert Levels ===")
        for level, c in ALERT_CONFIG.items():
            if level != "none":
                print(f"  {c['label']} ({level}): {c['color']}")
        print("\n=== Rules ===")
        print("  Blue   -> Yellow: same-topic negative 2+ or heat>=6")
        print("  Yellow -> Orange: authority media / severe keywords")
        print("  Orange -> Red:    hot-search / shutdown / arrest")

    elif action == "trends":
        trends = load_json(get_trends_file(cfg), {"reports": []})
        reports = trends.get("reports", [])
        print(f"Trend records: {len(reports)}")
        for r in reports[-10:]:
            ac = ALERT_CONFIG.get(r.get("alert_level", "none"), {})
            print(f"  {r['time'][:16]} [{r.get('label','?')}] "
                  f"+:{r['positive']} -:{r['negative']} =:{r['neutral']} "
                  f"alert:{ac.get('label','-')}")

    elif action == "history":
        history = load_json(get_history_file(cfg), {"items": []})
        items = history.get("items", [])
        print(f"Total: {len(items)} items")
        last = history.get("last_report_time")
        print(f"Last report: {last or 'N/A'}")
        for item in items[-5:]:
            s = item.get("sentiment", "neutral")
            tag = {"positive": "[+]", "negative": "[-]", "neutral": "[=]"}[s]
            print(f"  {tag} {item.get('title','')[:50]}")

    elif action == "dedup":
        test_titles = [
            f"{cfg['target_name']}获得国家发明专利授权",
            f"{cfg['target_name']}获国家发明专利授权",
            f"{cfg['target_name']}产品进入II期临床试验",
            f"{cfg['target_name']}产品进入II期临床",
        ]
        items = [{"title": t, "url": f"http://example.com/{i}"} for i, t in enumerate(test_titles)]
        deduped = deduplicate_items(items)
        print(f"Original: {len(items)}")
        print(f"Deduped:  {len(deduped)}")
        for item in deduped:
            print(f"  - {item['title']}")

    elif action == "classify":
        text = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
        if not text:
            print("Usage: python sentiment_engine.py <config> classify <text>")
            print("\nTest samples:")
            for t in [
                f"{cfg['target_name']}获得国家发明专利授权，技术突破行业领先",
                f"{cfg['target_name']}因虚假宣传被市场监管部门行政处罚",
                f"{cfg['target_name']}公司简介：专注于技术研发",
            ]:
                sentiment, confidence, needs_llm = snownlp_classify(t)
                tag = {"positive": "[+]", "negative": "[-]", "neutral": "[=]"}
                llm = " -> LLM" if needs_llm else " -> OK"
                print(f"  {tag[sentiment]} {confidence:.3f}{llm}  {t[:40]}")
        else:
            sentiment, confidence, needs_llm = snownlp_classify(text)
            tag = {"positive": "[+]", "negative": "[-]", "neutral": "[=]"}
            llm = " -> LLM" if needs_llm else " -> OK"
            print(f"  {tag[sentiment]} {confidence:.3f}{llm}  {text[:40]}")

    elif action == "benchmark":
        import time
        name = cfg["target_name"]
        tests = [
            ("positive", f"{name}获得国家发明专利授权，技术突破行业领先"),
            ("positive", f"{name}完成新一轮融资，估值突破10亿"),
            ("positive", f"{name}荣获中国生物医药创新奖"),
            ("positive", f"{name}产品获NMPA批准进入II期临床"),
            ("negative", f"{name}因虚假宣传被市场监管部门行政处罚"),
            ("negative", f"某患者家属投诉{name}治疗效果不达标"),
            ("negative", f"{name}涉嫌数据造假被调查"),
            ("negative", f"{name}产品出现严重质量问题，已被责令停产整改"),
            ("neutral", f"{name}公司简介：专注于技术研发"),
            ("neutral", f"{name}2026年招聘信息：现招聘研发工程师5名"),
            ("neutral", f"{name}参加第20届中国行业博览会"),
        ]
        correct = needs_llm_count = 0
        start = time.time()
        for expected, text in tests:
            sentiment, confidence, needs_llm = snownlp_classify(text)
            if sentiment == expected:
                correct += 1
            if needs_llm:
                needs_llm_count += 1
            tag = {"positive": "[+]", "negative": "[-]", "neutral": "[=]"}
            ok = "OK" if sentiment == expected or (needs_llm and sentiment == "neutral") else "FAIL"
            exp_tag = tag.get(expected, "[?]")
            sen_tag = tag.get(sentiment, "[?]")
            llm = " -> LLM" if needs_llm else ""
            print(f"  {ok} {sen_tag} want:{exp_tag} conf:{confidence:.3f}  {text[:40]}{llm}")
        elapsed = time.time() - start
        print(f"\n  Accuracy: {correct}/{len(tests)}")
        print(f"  Needs LLM: {needs_llm_count}/{len(tests)}")
        print(f"  Speed: {elapsed:.3f}s ({len(tests)/max(elapsed,0.001):.0f} items/s)")
        print(f"  Token saved: {len(tests)-needs_llm_count} items x ~350 = ~{(len(tests)-needs_llm_count)*350} tokens")

    else:
        print(f"Unknown action: {action}")
        print(f"Run without args for usage.")


if __name__ == "__main__":
    main()
