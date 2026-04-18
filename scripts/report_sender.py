# -*- coding: utf-8 -*-
"""
舆情报告发送器 — 通用版
======================
通过 AgentMail 发送 HTML + 纯文本双格式舆情报告邮件。

依赖：pip install agentmail-sdk
前置：需要配置 ~/.agentmail/config.json
"""

import json
import os
import sys


CONFIG_PATH = os.path.expanduser("~/.agentmail/config.json")


def load_agentmail_config():
    """加载 AgentMail 配置"""
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(
            f"AgentMail config not found: {CONFIG_PATH}\n"
            "Please set up AgentMail first. See: https://agentmail.to"
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def send_report(subject, body_text, body_html=None, to_email=""):
    """
    发送舆情报告邮件。

    Args:
        subject: 邮件主题
        body_text: 纯文本正文
        body_html: HTML 正文（可选，建议同时提供）
        to_email: 收件人邮箱

    Returns:
        API response dict
    """
    if not to_email:
        raise ValueError("to_email is required")

    from agentmail import AgentMail

    config = load_agentmail_config()
    client = AgentMail(api_key=config["apiKey"])

    kwargs = {
        "inbox_id": config["email"],
        "to": to_email,
        "subject": subject,
        "text": body_text,
    }
    if body_html:
        kwargs["html"] = body_html

    result = client.inboxes.messages.send(**kwargs)
    return result


def send_sentiment_report(
    target_name, run_label, html_content, text_content, to_email
):
    """
    发送舆情报告（封装版，自动生成主题）。

    Args:
        target_name: 监控目标名称
        run_label: 报告类型（早报/午报/晚报/临时报告）
        html_content: HTML 格式报告
        text_content: 纯文本格式报告
        to_email: 收件人

    Returns:
        API response dict
    """
    from datetime import datetime
    date_str = datetime.now().strftime("%Y-%m-%d")
    subject = f"[舆情] {target_name} 监控{run_label} - {date_str}"

    result = send_report(subject, text_content, html_content, to_email)

    print(f"From: {load_agentmail_config()['email']}")
    print(f"To: {to_email}")
    print(f"Subject: {subject}")
    print(f"Text: {len(text_content)} chars")
    if html_content:
        print(f"HTML: {len(html_content)} chars")
    print(f"[OK] Email sent successfully!")

    return result


def main():
    """CLI: 快速发送测试报告"""
    if len(sys.argv) < 4:
        print("Usage:")
        print(f"  python {os.path.basename(__file__)} <subject> <body_text_or_file> <to_email>")
        print("  body: plain text, or file:<path> for file input")
        sys.exit(1)

    subject = sys.argv[1]
    body_arg = sys.argv[2]
    to_email = sys.argv[3]

    if body_arg.startswith("file:"):
        filepath = body_arg[5:]
        with open(filepath, "r", encoding="utf-8") as f:
            body = f.read()
    else:
        body = body_arg

    result = send_report(subject, body, to_email=to_email)
    print(f"Sent: {result}")


if __name__ == "__main__":
    main()
