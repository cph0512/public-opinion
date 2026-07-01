"""透過 SMTP 寄送每日摘要 Email。"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from ..config import Config

log = logging.getLogger(__name__)


def _missing(smtp: dict[str, str]) -> list[str]:
    required = ["host", "user", "password", "from", "to"]
    return [k for k in required if not smtp.get(k)]


def send_email(subject: str, markdown_body: str, config: Config) -> bool:
    smtp = config.smtp
    missing = _missing(smtp)
    if missing:
        log.warning("[email] 缺少 SMTP 設定:%s,略過寄信。", ", ".join(missing))
        return False

    recipients = [addr.strip() for addr in smtp["to"].split(",") if addr.strip()]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp["from"]
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(markdown_body, "plain", "utf-8"))
    msg.attach(MIMEText(_to_html(markdown_body), "html", "utf-8"))

    try:
        port = int(smtp.get("port", "587") or 587)
        if port == 465:
            server = smtplib.SMTP_SSL(smtp["host"], port, timeout=30)
        else:
            server = smtplib.SMTP(smtp["host"], port, timeout=30)
            server.starttls()
        with server:
            server.login(smtp["user"], smtp["password"])
            server.sendmail(smtp["from"], recipients, msg.as_string())
    except Exception as exc:  # noqa: BLE001
        log.warning("[email] 寄信失敗:%s", exc)
        return False

    log.info("[email] 已寄送給 %s", ", ".join(recipients))
    return True


def _to_html(markdown_body: str) -> str:
    """極簡 Markdown → HTML(避免額外相依套件)。"""
    body = (
        markdown_body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    return (
        '<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;'
        'white-space:pre-wrap;line-height:1.5">'
        f"{body}"
        "</div>"
    )
