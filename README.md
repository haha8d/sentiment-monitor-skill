# sentiment-monitor

通用中文舆情监控系统 | Universal Chinese Public Opinion Monitoring System

[![Skill](https://img.shields.io/badge/WorkBuddy-Skill-blue)](https://www.codebuddy.cn/work/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-v1.0.0-orange)](https://github.com/haha8d/sentiment-monitor-skill/releases)

---

## 简介

**sentiment-monitor** 是一个专为企业品牌公关团队设计的自动化舆情监控工具。通过配置目标关键词，系统自动在全网搜索相关资讯，运用 SnowNLP + LLM 双层情感分析引擎进行智能分类，生成包含热度评分、情感倾向、预警等级的专业报告，并自动推送到指定邮箱。

## 核心特性

- **全网监控**：支持百度、新闻站点等多渠道信息采集
- **智能去重**：基于内容指纹的语义去重，避免重复信息干扰
- **双层情感分析**：SnowNLP 本地初筛（省 60-80% Token）+ LLM 精判不确定条目
- **四色预警体系**：
  - 🔴 红色：严重负面（危机级）
  - 🟠 橙色：中度负面（关注级）
  - 🟡 黄色：轻度负面/中性偏负（提醒级）
  - 🟢 绿色：正面/中性（正常级）
- **热度算法**：综合来源权重、情感强度、时效性计算文章热度
- **趋势追踪**：对比历史数据，识别舆情走势变化
- **自动报告**：支持早报/午报/晚报定时推送，HTML + 纯文本双格式

## 适用场景

- 企业品牌声誉监控
- 产品口碑追踪
- 竞品动态监测
- 行业舆情预警
- 危机公关响应

## 快速开始

### 安装

```bash
# 方式1：通过 WorkBuddy SkillHub 一键安装
# 打开 WorkBuddy → 技能市场 → 搜索 "sentiment-monitor" → 安装

# 方式2：手动安装
git clone https://github.com/haha8d/sentiment-monitor-skill.git
cp -r sentiment-monitor ~/.workbuddy/skills/
```

### 首次配置

在 WorkBuddy 中触发 Skill，按提示填写：

1. **监控目标名称**（如：小米科技）
2. **关键词配置**：
   - 核心关键词（5-10 个）
   - 产品关键词
   - 技术关键词
   - 关联关键词
   - 预警关键词
3. **收件邮箱列表**
4. **报告频率**（早报/午报/晚报/自定义）

配置完成后自动生成 `monitor_config.json`，并创建定时自动化任务。

### 日常使用

- **手动触发**："帮我查一下今天的舆情"
- **自动运行**：按配置频率自动执行搜索→分析→预警→发邮件

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                    sentiment-monitor                        │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   搜索引擎    │  │  情感分析引擎 │  │  报告生成器   │      │
│  │  (DuckDuckGo)│  │ (SnowNLP+LLM)│  │ (HTML/Text)  │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                 │              │
│         └─────────────────┼─────────────────┘              │
│                           ▼                                │
│                  ┌─────────────────┐                       │
│                  │  monitor_config.json                   │
│                  │  (配置驱动)      │                       │
│                  └─────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

## 文件结构

```
sentiment-monitor/
├── SKILL.md                    # 技能入口指南
├── scripts/
│   ├── sentiment_engine.py     # 核心引擎（搜索/分析/预警/趋势）
│   ├── report_generator.py     # 报告生成（HTML+纯文本）
│   └── report_sender.py        # 邮件发送
└── references/
    └── architecture.md         # 架构文档
```

## 依赖

- Python 3.8+
- `snownlp` - 中文情感分析
- `agentmail` - 邮件发送
- `duckduckgo-search` - 搜索引擎

## 安全说明

- ✅ 无 `exec`/`eval`/`subprocess`/`os.system` 等危险调用
- ✅ 配置文件与代码分离，敏感信息不硬编码
- ✅ 通过 Skill Creator 安全审计（P2 级别）

## 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| [v1.0.0](https://github.com/haha8d/sentiment-monitor-skill-skill/releases/tag/v1.0.0) | 2026-04-18 | 初始发布，通用中文舆情监控系统 |

## 致谢

感谢所有提供反馈和建议的用户。

## License

[MIT](LICENSE) © 虾哥（全利科技）
