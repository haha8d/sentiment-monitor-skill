# -*- coding: utf-8 -*-
"""
舆情报告生成器 — 通用版
======================
生成 HTML + 纯文本双格式报告，配置驱动，适配任意监控目标。

依赖：无额外依赖（纯 Python 标准库）
"""

import os
from datetime import datetime

# 四色预警显示配置
ALERT_CFG = {
    "blue":   {"label": "蓝色预警", "color": "#3498db", "bg": "#eaf2f8", "tag": "关注"},
    "yellow": {"label": "黄色预警", "color": "#f39c12", "bg": "#fef9e7", "tag": "注意"},
    "orange": {"label": "橙色预警", "color": "#e67e22", "bg": "#fdf2e9", "tag": "警告"},
    "red":    {"label": "红色预警", "color": "#c0392b", "bg": "#fdedec", "tag": "紧急"},
    "none":   {"label": "无预警",   "color": "#95a5a6", "bg": "#f8f9fa", "tag": "-"},
}


def _render_item(item, highlight=False):
    """渲染单条舆情 HTML 行"""
    title = item.get("title", "无标题")
    source = item.get("source", "未知")
    summary = item.get("summary", "无摘要")
    url = item.get("url", "")
    time_text = item.get("time", "")
    heat = item.get("heat_score", 0)
    alert = item.get("alert_level", "none")
    acfg = ALERT_CFG.get(alert, ALERT_CFG["none"])

    summary_html = (
        f'<span style="color:#c0392b;font-weight:bold;">{summary}</span>'
        if highlight else summary
    )

    alert_badge = ""
    if alert != "none":
        alert_badge = (
            f'<span style="display:inline-block;padding:2px 8px;border-radius:3px;'
            f'font-size:11px;font-weight:bold;color:#fff;background:{acfg["color"]};'
            f'margin-left:6px;">{acfg["tag"]}</span>'
        )

    heat_color = "#c0392b" if heat >= 6 else ("#e67e22" if heat >= 4 else "#95a5a6")
    heat_badge = (
        f'<span style="display:inline-block;padding:2px 6px;border-radius:3px;'
        f'font-size:11px;color:{heat_color};border:1px solid {heat_color};'
        f'margin-left:4px;">热度 {heat}</span>'
    )

    link_html = ""
    if url:
        short = url[:50] + ("..." if len(url) > 50 else "")
        link_html = f'<a href="{url}" style="color:#2980b9;font-size:12px;">{short}</a>'

    return f'''<tr>
  <td style="padding:10px 12px;border-bottom:1px solid #ecf0f1;vertical-align:top;width:38%;">
    <strong>{title}</strong>{alert_badge}{heat_badge}<br>
    <span style="font-size:11px;color:#7f8c8d;">{source} {time_text}</span>
  </td>
  <td style="padding:10px 12px;border-bottom:1px solid #ecf0f1;vertical-align:top;width:32%;">
    {summary_html}
  </td>
  <td style="padding:10px 12px;border-bottom:1px solid #ecf0f1;vertical-align:top;width:30%;">
    {link_html}
  </td>
</tr>'''


def make_html_report(
    target_name, pos_items, neg_items, neu_items,
    highest_alert, trend_data, summary_html,
    run_label, since_label, keyword_summary,
    snownlp_count=0, llm_count=0,
):
    """
    生成 HTML 格式舆情报告。

    Args:
        target_name: 监控目标名称
        pos_items/neg_items/neu_items: 分类后的舆情列表
        highest_alert: 最高预警等级
        trend_data: 趋势对比数据 (dict or None)
        summary_html: 总结 HTML
        run_label: 报告类型 (早报/午报/晚报)
        since_label: 距上次报告时间
        keyword_summary: 关键词统计字符串 (如 "7核心 + 21关联")
        snownlp_count: SnowNLP 本地分类条数
        llm_count: LLM 精判条数
    """
    now = datetime.now()
    date_str = now.strftime("%Y年%m月%d日")
    time_str = now.strftime("%H:%M")

    pos_count, neg_count, neu_count = len(pos_items), len(neg_items), len(neu_items)
    total = pos_count + neg_count + neu_count
    acfg = ALERT_CFG.get(highest_alert, ALERT_CFG["none"])

    # ---- 趋势区块 ----
    trend_section = ""
    if trend_data:
        def fmt_delta(d):
            if d > 0:
                return f'<span style="color:#c0392b;font-weight:bold;">+{d}</span>'
            elif d < 0:
                return f'<span style="color:#27ae60;font-weight:bold;">{d}</span>'
            return '<span style="color:#95a5a6;">0</span>'

        rise_warning = ""
        if trend_data.get("consecutive_neg_rise"):
            rise_warning = (
                '<div style="margin-top:8px;padding:8px 12px;background:#fdedec;'
                'border-radius:4px;border-left:4px solid #c0392b;font-size:13px;color:#c0392b;">'
                '<strong>!</strong> 负面舆情已连续3次报告呈上升趋势，请密切关注</div>'
            )

        trend_section = f'''
        <div style="padding:12px 28px 0;">
          <div style="background:#f5f6fa;padding:14px 16px;border-radius:8px;font-size:13px;">
            <div style="color:#7f8c8d;margin-bottom:8px;">相比上次报告（{trend_data["prev_time"][:16]}）</div>
            <div style="display:flex;gap:20px;">
              <span>正面: {fmt_delta(trend_data["pos_delta"])}</span>
              <span>负面: {fmt_delta(trend_data["neg_delta"])}</span>
              <span>一般: {fmt_delta(trend_data["neu_delta"])}</span>
            </div>
            {rise_warning}
          </div>
        </div>'''

    # ---- 预警区块 ----
    alert_section = ""
    if highest_alert != "none":
        msg = (
            "本轮发现严重负面舆情，建议及时跟进处理"
            if highest_alert in ("orange", "red")
            else "本轮发现部分负面舆情，建议关注"
        )
        alert_section = f'''
        <div style="padding:12px 28px 0;">
          <div style="background:{acfg["bg"]};padding:14px 16px;border-radius:8px;border-left:4px solid {acfg["color"]};">
            <div style="font-size:15px;font-weight:bold;color:{acfg["color"]};">{acfg["label"]}</div>
            <div style="font-size:12px;color:#7f8c8d;margin-top:4px;">{msg}</div>
          </div>
        </div>'''

    # ---- 三段内容 ----
    def rows(items, hl):
        return "".join(_render_item(i, hl) for i in items) if items else (
            '<tr><td colspan="3" style="padding:15px;text-align:center;color:#95a5a6;">本轮无新增</td></tr>'
        )

    pos_rows = rows(pos_items, True)
    neg_rows = rows(neg_items, True)
    neu_rows = rows(neu_items, False)
    neg_border = acfg["color"] if highest_alert != "none" else "#c0392b"

    # ---- Token 节省说明 ----
    token_line = ""
    if snownlp_count > 0 or llm_count > 0:
        saved = snownlp_count * 350
        token_line = (
            f'<div style="text-align:center;padding:8px;background:#eafaf1;border-radius:6px;'
            f'font-size:12px;color:#27ae60;margin-top:8px;">'
            f'SnowNLP 本地分类 {snownlp_count} 条，LLM 精判 {llm_count} 条，'
            f'节省约 {saved} token</div>'
        )

    html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:20px;background-color:#f8f9fa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;">
<div style="max-width:740px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#2c3e50,#34495e);padding:24px 28px;">
    <h1 style="margin:0;color:#fff;font-size:22px;font-weight:600;">{target_name} · 舆情监控{run_label}</h1>
    <p style="margin:8px 0 0;color:rgba(255,255,255,0.8);font-size:14px;">
      {date_str} {time_str} &nbsp;|&nbsp; {since_label} &nbsp;|&nbsp; 关键词: {keyword_summary}
    </p>
  </div>

  <!-- Summary Cards -->
  <div style="display:flex;padding:20px 28px 0;">
    <div style="flex:1;text-align:center;padding:14px;background:#eafaf1;border-radius:8px;margin-right:8px;">
      <div style="font-size:28px;font-weight:700;color:#27ae60;">{pos_count}</div>
      <div style="font-size:13px;color:#7f8c8d;margin-top:4px;">正面新增</div>
    </div>
    <div style="flex:1;text-align:center;padding:14px;background:#fdedec;border-radius:8px;margin-right:8px;">
      <div style="font-size:28px;font-weight:700;color:#c0392b;">{neg_count}</div>
      <div style="font-size:13px;color:#7f8c8d;margin-top:4px;">负面新增</div>
    </div>
    <div style="flex:1;text-align:center;padding:14px;background:#eaf2f8;border-radius:8px;">
      <div style="font-size:28px;font-weight:700;color:#2980b9;">{neu_count}</div>
      <div style="font-size:13px;color:#7f8c8d;margin-top:4px;">一般新增</div>
    </div>
  </div>

  <div style="padding:4px 28px 0;">
    <div style="text-align:center;padding:10px;background:#f5f6fa;border-radius:6px;font-size:13px;color:#7f8c8d;">
      本轮共发现 <strong>{total}</strong> 条新增舆情
      {"&nbsp;|&nbsp; 最高预警: <strong style='color:" + acfg["color"] + ";'>" + acfg["label"] + "</strong>"
       if highest_alert != "none" else "&nbsp;|&nbsp; 无预警"}
    </div>
    {token_line}
  </div>

  <!-- Alert Section -->
  {alert_section}

  <!-- Trend Section -->
  {trend_section}

  <!-- Positive -->
  <div style="padding:24px 28px 8px;">
    <h2 style="margin:0 0 12px;font-size:17px;color:#27ae60;">
      <span style="background:#27ae60;color:#fff;padding:2px 10px;border-radius:4px;font-size:13px;margin-right:8px;">正面</span>
      正面舆情（{pos_count}条）
    </h2>
    <table style="width:100%;border-collapse:collapse;font-size:14px;">
      <thead><tr style="background:#f8f9fa;">
        <th style="padding:8px 12px;text-align:left;border-bottom:2px solid #27ae60;color:#555;font-size:12px;font-weight:600;">标题 / 来源</th>
        <th style="padding:8px 12px;text-align:left;border-bottom:2px solid #27ae60;color:#555;font-size:12px;font-weight:600;">摘要</th>
        <th style="padding:8px 12px;text-align:left;border-bottom:2px solid #27ae60;color:#555;font-size:12px;font-weight:600;">链接</th>
      </tr></thead>
      <tbody>{pos_rows}</tbody>
    </table>
  </div>

  <!-- Negative -->
  <div style="padding:20px 28px 8px;">
    <h2 style="margin:0 0 12px;font-size:17px;color:#c0392b;">
      <span style="background:#c0392b;color:#fff;padding:2px 10px;border-radius:4px;font-size:13px;margin-right:8px;">负面</span>
      负面舆情（{neg_count}条）
    </h2>
    <table style="width:100%;border-collapse:collapse;font-size:14px;">
      <thead><tr style="background:#f8f9fa;">
        <th style="padding:8px 12px;text-align:left;border-bottom:2px solid {neg_border};color:#555;font-size:12px;font-weight:600;">标题 / 来源</th>
        <th style="padding:8px 12px;text-align:left;border-bottom:2px solid {neg_border};color:#555;font-size:12px;font-weight:600;">摘要</th>
        <th style="padding:8px 12px;text-align:left;border-bottom:2px solid {neg_border};color:#555;font-size:12px;font-weight:600;">链接</th>
      </tr></thead>
      <tbody>{neg_rows}</tbody>
    </table>
  </div>

  <!-- Neutral -->
  <div style="padding:20px 28px 8px;">
    <h2 style="margin:0 0 12px;font-size:17px;color:#2980b9;">
      <span style="background:#2980b9;color:#fff;padding:2px 10px;border-radius:4px;font-size:13px;margin-right:8px;">一般</span>
      一般舆情（{neu_count}条）
    </h2>
    <table style="width:100%;border-collapse:collapse;font-size:14px;">
      <thead><tr style="background:#f8f9fa;">
        <th style="padding:8px 12px;text-align:left;border-bottom:2px solid #2980b9;color:#555;font-size:12px;font-weight:600;">标题 / 来源</th>
        <th style="padding:8px 12px;text-align:left;border-bottom:2px solid #2980b9;color:#555;font-size:12px;font-weight:600;">摘要</th>
        <th style="padding:8px 12px;text-align:left;border-bottom:2px solid #2980b9;color:#555;font-size:12px;font-weight:600;">链接</th>
      </tr></thead>
      <tbody>{neu_rows}</tbody>
    </table>
  </div>

  <!-- Summary -->
  <div style="padding:20px 28px 24px;">
    <h2 style="margin:0 0 10px;font-size:17px;color:#2c3e50;">本期总结</h2>
    <div style="background:#f8f9fa;padding:16px 18px;border-radius:8px;font-size:14px;color:#34495e;line-height:1.8;">
      {summary_html}
    </div>
  </div>

  <!-- Footer -->
  <div style="background:#f8f9fa;padding:12px 28px;text-align:center;font-size:11px;color:#bdc3c7;border-top:1px solid #ecf0f1;">
    {target_name} 舆情监控系统 &nbsp;|&nbsp; 四色预警 + 热度评估 + 趋势追踪 + 语义去重
  </div>

</div>
</body></html>'''

    return html


def make_text_report(
    target_name, pos_items, neg_items, neu_items,
    highest_alert, trend_data, summary_text,
    run_label, since_label, keyword_summary,
    snownlp_count=0, llm_count=0,
):
    """
    生成纯文本格式舆情报告。

    参数同 make_html_report，summary_text 为纯文本格式。
    """
    now = datetime.now()
    date_str = now.strftime("%Y年%m月%d日")
    time_str = now.strftime("%H:%M")

    pos_count, neg_count, neu_count = len(pos_items), len(neg_items), len(neu_items)
    total = pos_count + neg_count + neu_count
    acfg = ALERT_CFG.get(highest_alert, ALERT_CFG["none"])

    alert_line = f"  最高预警等级: {acfg['label']}" if highest_alert != "none" else "  预警等级: 无"

    sep = "=" * 60
    text = f"""{target_name} · 舆情监控{run_label}
{date_str} {time_str} | {since_label}
监控关键词: {keyword_summary} | 本轮新增: 正面{pos_count} 负面{neg_count} 一般{neu_count}
{alert_line}
{sep}"""

    if trend_data:
        pos_d = trend_data["pos_delta"]
        neg_d = trend_data["neg_delta"]
        neu_d = trend_data["neu_delta"]
        text += f"""
--- 趋势对比（vs 上次报告 {trend_data['prev_time'][:16]}）---
  正面变化: {'+' if pos_d > 0 else ''}{pos_d}
  负面变化: {'+' if neg_d > 0 else ''}{neg_d}
  一般变化: {'+' if neu_d > 0 else ''}{neu_d}"""
        if trend_data.get("consecutive_neg_rise"):
            text += "\n  [!] 负面舆情连续3次报告呈上升趋势，请密切关注"

    text += f"\n{sep}\n\n【正面舆情 - {pos_count}条】"
    for i, item in enumerate(pos_items, 1):
        text += f"""
{i}. {item.get('title', '无标题')}  [热度:{item.get('heat_score', 0)}]
   来源: {item.get('source', '未知')} {item.get('time', '')}
   摘要: {item.get('summary', '无摘要')}
   链接: {item.get('url', '')}"""

    text += f"\n\n【负面舆情 - {neg_count}条】"
    if neg_items:
        for i, item in enumerate(neg_items, 1):
            alert = item.get("alert_level", "none")
            atag = ALERT_CFG.get(alert, ALERT_CFG["none"])["tag"]
            text += f"""
{i}. [!!] {atag} {item.get('title', '无标题')}  [热度:{item.get('heat_score', 0)}]
   来源: {item.get('source', '未知')} {item.get('time', '')}
   摘要: {item.get('summary', '无摘要')}
   链接: {item.get('url', '')}"""
    else:
        text += "\n  本轮无新增负面舆情"

    text += f"\n\n【一般舆情 - {neu_count}条】"
    for i, item in enumerate(neu_items, 1):
        text += f"""
{i}. {item.get('title', '无标题')}
   来源: {item.get('source', '未知')} {item.get('time', '')}
   摘要: {item.get('summary', '无摘要')}
   链接: {item.get('url', '')}"""

    token_info = ""
    if snownlp_count > 0 or llm_count > 0:
        token_info = f"\n  分类统计: SnowNLP {snownlp_count} 条, LLM {llm_count} 条, 节省约 {snownlp_count * 350} token"

    text += f"""
{sep}
【本期总结】
{summary_text}
{sep}
{target_name} 舆情监控系统 | 四色预警 + 热度评估 + 趋势追踪{token_info}
"""
    return text
