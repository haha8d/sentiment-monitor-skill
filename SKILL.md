---
name: sentiment-monitor
description: |
  Universal Chinese public opinion (sentiment) monitoring system. This skill should be used when the user wants to:
  - Monitor brand/company reputation, public opinion, or sentiment
  - Set up automated sentiment monitoring for a company, product, or person
  - Create scheduled public opinion reports (daily/weekly)
  - Search and analyze news, social media mentions, or online discussions about a target
  - Receive email alerts when negative sentiment is detected
  - Perform sentiment classification on Chinese text using local models
  Trigger phrases: 舆情监控, 舆情监测, 品牌监控, 口碑监控, 舆情报告, 舆情分析,
  负面预警, 舆情预警, 舆情跟踪, 声誉监控, 舆情系统, 情感分析, public opinion monitoring,
  sentiment monitoring, brand monitoring, reputation tracking
---

# Sentiment Monitor — 通用舆情监控系统

## Overview

A universal Chinese public opinion monitoring system. Supports any company, brand, or person as the monitoring target. Features four-level alert system, SnowNLP local sentiment classification (zero token), LLM precision judgment for uncertain items, semantic deduplication, heat scoring, and trend tracking.

All target-specific data (keywords, recipients, etc.) is driven by a JSON config file — no hardcoding.

## Quick Start

### Step 1: Initialize (First Time Only)

When the user triggers this skill for the first time, collect the following information:

1. **Target name** — What to monitor (e.g., "Apple中国", "华为", "小米")
2. **Target aliases** — English names, abbreviations (e.g., ["Apple", "Huawei", "Xiaomi"])
3. **Keywords** — Ask user to provide keywords in 5 categories:
   - **Core (核心)**: Main brand/company names (required, at least 1)
   - **Products (产品)**: Product or service names (optional)
   - **Tech (技术)**: Technical terms, patents, certifications (optional)
   - **People (人物)**: Key people, partnerships, related companies (optional)
   - **Variants (变体)**: Common misspellings, alternative names (optional)
4. **Email recipient** — Who receives the report
5. **Schedule** — Report frequency and times (default: daily 08:00, 12:00, 17:00)
6. **Platforms** — Search sources (default: all platforms)
7. **Data directory** — Where to store history/trends data (default: `sentiment_data/` under workspace)

### Step 2: Generate Config File

Generate a `monitor_config.json` in the user's workspace using this template:

```json
{
  "target_name": "目标名称",
  "target_aliases": ["别名1", "别名2"],
  "keywords": {
    "core": ["核心关键词1", "核心关键词2"],
    "products": [],
    "tech": [],
    "people": [],
    "variants": []
  },
  "email_to": "recipient@example.com",
  "platforms": [],
  "data_dir": "sentiment_data",
  "created_at": "2026-04-18T00:00:00"
}
```

Use the `generate_config()` function from `scripts/sentiment_engine.py` to create this programmatically, or write it directly.

### Step 3: Install Dependencies

```bash
pip install snownlp agentmail-sdk
```

SnowNLP (~7.7MB) provides local Chinese sentiment classification at 280 items/sec with zero token cost. AgentMail SDK is needed only if email delivery is required.

### Step 4: Create Automation

Use `automation_update` tool to create scheduled report tasks. Each task's prompt should follow the **Report Workflow** below.

## Report Workflow (for Automation Prompts)

Each scheduled report execution follows this workflow. Embed this in the automation prompt:

### Phase 1: Import Engine

```python
import sys
sys.path.insert(0, r"<SKILL_SCRIPTS_DIR>")
# <SKILL_SCRIPTS_DIR> is the absolute path to this skill's scripts/ directory
# On Windows: C:\Users\<USER>\.workbuddy\skills\sentiment-monitor\scripts
from sentiment_engine import *
from report_generator import make_html_report, make_text_report
```

### Phase 2: Load Config & History

```python
cfg = load_config("<WORKSPACE>/monitor_config.json")
history = load_json(get_history_file(cfg), {"items": []})
```

### Phase 3: Multi-Platform Search

Read keywords from config:
```python
keywords = get_all_keywords(cfg)
kw_counts = get_keyword_count(cfg)
```

Search all keywords across web, news, and social media platforms. Structure each result as:
```python
{
    "title": "标题",
    "summary": "摘要",
    "source": "来源平台/媒体",
    "url": "链接",
    "time": "发布时间",
}
```

### Phase 4: Deduplicate

```python
all_items = deduplicate_items(raw_items)
```

### Phase 5: Sentiment Classification (Token-Saving Strategy)

Apply the three-layer classification strategy:

**Layer 1 — SnowNLP Local Classification (zero token)**
```python
results, uncertain_indices = batch_snow_classify(all_items)
```
- `score > 0.70` → positive (confident, no LLM needed)
- `score < 0.30` → negative (confident, no LLM needed)
- `0.30 ~ 0.70` → uncertain, needs LLM

**Layer 2 — LLM Precision Judgment (only for uncertain items)**
Send only items at `uncertain_indices` to LLM for classification. This typically covers 20-40% of total items, saving 60-80% of tokens.

**Layer 3 — Alert Keyword Check (zero token, pure keyword matching)**
For all items classified as negative, run `assess_alert_level()` to determine alert level:
- Red: 热搜/封杀/停业/吊销/刑拘/逮捕
- Orange: 处罚/违法/欺诈/造假/败诉/监管/调查/立案
- Yellow: 2+ same-topic negatives or heat >= 6
- Blue: default for other negatives

### Phase 6: Heat Scoring

```python
for i, item in enumerate(all_items):
    item["heat_score"] = calc_heat_score(item.get("source"), i // len(all_items) * 10 + 1, item.get("time"))
    item["sentiment"] = results[i]["sentiment"]
    item["alert_level"] = assess_alert_level(item, all_items)
```

### Phase 7: Incremental Comparison

Compare with history.json to find new items. Get trend data:
```python
trend = get_trend_summary(cfg)
since_label = time_ago_str(history.get("last_report_time"))
```

### Phase 8: Generate Report

```python
kw_summary = f"{kw_counts['core']}核心 + {kw_counts['total'] - kw_counts['core']}关联"
highest = get_highest_alert([i.get("alert_level") for i in new_items])

html = make_html_report(
    target_name=cfg["target_name"],
    pos_items=positive_items,
    neg_items=negative_items,
    neu_items=neutral_items,
    highest_alert=highest,
    trend_data=trend,
    summary_html=summary_html,
    run_label=get_run_label(),
    since_label=since_label,
    keyword_summary=kw_summary,
    snownlp_count=snownlp_classified_count,
    llm_count=llm_classified_count,
)

text = make_text_report(
    target_name=cfg["target_name"],
    # ... same args ...
    summary_text=summary_text,
)
```

### Phase 9: Send Email

```python
from report_sender import send_sentiment_report
send_sentiment_report(
    target_name=cfg["target_name"],
    run_label=get_run_label(),
    html_content=html,
    text_content=text,
    to_email=cfg["email_to"],
)
```

### Phase 10: Update Data Files

```python
record_trend(cfg, pos_count, neg_count, neu_count, highest, get_run_label())
# Also update history.json with new items and last_report_time
```

## Automation Prompt Template

Copy and customize this template for each scheduled report:

```
执行 {target_name} 舆情监控任务（{早报/午报/晚报}），按以下步骤执行：

## 0. 导入引擎
import sys; sys.path.insert(0, r"C:\Users\{USER}\.workbuddy\skills\sentiment-monitor\scripts")
from sentiment_engine import *
from report_generator import make_html_report, make_text_report

## 1. 加载配置
读取 {WORKSPACE}/monitor_config.json 和历史数据

## 2. 全网搜索（{keyword_count}个关键词）
核心：{列出核心关键词}
产品：{列出产品关键词}
技术：{列出技术关键词}
关联：{列出关联关键词}
变体：{列出变体关键词}

## 3. 智能去重
使用 deduplicate_items() 去重

## 4. 情感分类（省token策略）
第一步：SnowNLP 本地初筛（零token）
第二步：仅不确定条目调 LLM 精判
第三步：预警关键词兜底（零token）

## 5. 增量对比 + 热度评分 + 预警评估

## 6. 生成 HTML+纯文本 报告

## 7. 发送邮件至 {email_to}

## 8. 更新数据文件（history.json + trends.json）
```

## Manual Operations

### Single Classification Test
```python
from sentiment_engine import snownlp_classify
sentiment, confidence, needs_llm = snownlp_classify("文本内容")
```

### CLI Commands
```bash
python sentiment_engine.py <config.json> keywords       # 列出关键词
python sentiment_engine.py <config.json> alerts         # 查看预警配置
python sentiment_engine.py <config.json> trends         # 查看趋势
python sentiment_engine.py <config.json> classify <文本>  # 测试分类
python sentiment_engine.py <config.json> benchmark      # 基准测试
```

## Architecture

For detailed architecture and design decisions, read `references/architecture.md`.

## Scripts

| File | Purpose |
|------|---------|
| `scripts/sentiment_engine.py` | Core engine: config, dedup, SnowNLP classification, heat score, alert level, trends |
| `scripts/report_generator.py` | HTML + text report generation |
| `scripts/report_sender.py` | Email delivery via AgentMail |

## Dependencies

| Package | Size | Purpose | Required |
|---------|------|---------|----------|
| `snownlp` | ~7.7MB | Local Chinese sentiment classification | Yes |
| `agentmail-sdk` | ~1MB | Email delivery | Only if sending reports |
