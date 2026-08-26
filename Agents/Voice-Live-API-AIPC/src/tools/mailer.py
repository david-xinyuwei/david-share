"""邮件发送。默认走 Microsoft Graph（Outlook.com 的 SMTP Basic Auth 已于 2026-04-30 退役），
可切回 SMTP 供仍支持授权码的邮箱使用。收件人受白名单约束，避免语音指令被诱导发往任意地址。"""

from __future__ import annotations

import re
import smtplib
import ssl
from email.message import EmailMessage

from .. import config, graph_mail
from . import tool
from .briefing import last_briefing

_ADDRESS_RE = re.compile(r"^[^@\s,;:<>\"\\]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_SPOKEN_AT_RE = re.compile(r"\s*(?:@|＠|\bat\b|艳符|圈一)\s*", re.IGNORECASE)
_SPOKEN_DOT_RE = re.compile(r"\s*(?:点|\bdot\b)\s*", re.IGNORECASE)
_MAX_ADDRESS_CHARS = 320
_MAX_SUBJECT_CHARS = 200
_MAX_CONTENT_CHARS = 100_000
_MAX_CONTENT_BYTES = 256 * 1024


def _allowed_recipients() -> set[str]:
    return {addr.lower() for addr in config.get_list("MAIL_ALLOWED_RECIPIENTS")}


def _default_recipient() -> str | None:
    """用户说「发到我邮箱」时不必口述地址；白名单只有一个地址时它就是本人邮箱。"""
    configured = config.get("MAIL_DEFAULT_RECIPIENT")
    if configured:
        return configured
    allowed = config.get_list("MAIL_ALLOWED_RECIPIENTS")
    return allowed[0] if len(allowed) == 1 else None


def _normalize_spoken(raw: str) -> str:
    """语音转写会把 @ 听成 at、把 . 听成「点」，并插入空格。"""
    text = _SPOKEN_AT_RE.sub("@", raw.strip(), count=1)
    local, sep, domain = text.partition("@")
    if sep:
        domain = _SPOKEN_DOT_RE.sub(".", domain)
        text = f"{local}@{domain}"
    return "".join(text.split())


def _canonical(address: str) -> str:
    """去掉本地部分的分隔符，用于容忍语音多识别出的点号。"""
    local, _, domain = address.lower().partition("@")
    return re.sub(r"[.\-_]", "", local) + "@" + domain


def _validate(address: str) -> str:
    candidate = _normalize_spoken(address)
    if len(candidate) > _MAX_ADDRESS_CHARS:
        raise ValueError("收件人地址过长")
    if "\r" in candidate or "\n" in candidate:
        raise ValueError("收件人地址包含非法换行符")
    if not _ADDRESS_RE.match(candidate):
        raise ValueError(f"不是合法的邮箱地址: {address}")

    allowed = _allowed_recipients()
    if not allowed:
        raise PermissionError("未配置 MAIL_ALLOWED_RECIPIENTS，出于安全考虑拒绝发送")
    if candidate.lower() in allowed:
        return candidate

    # 容错命中时仍然发往白名单里登记的真实地址，不使用识别结果。
    canon = _canonical(candidate)
    matches = [addr for addr in allowed if _canonical(addr) == canon]
    if len(matches) == 1:
        return matches[0]
    raise PermissionError(f"{candidate} 不在允许投递的白名单内")


@tool(
    name="send_email",
    description="Send content by email. Omit 'to' when the user asks to send to their own configured address. Code-enforced confirmation is required before delivery.",
    parameters={
        "type": "object",
        "properties": {
            "to": {
                "type": "string",
                "maxLength": _MAX_ADDRESS_CHARS,
                "description": "Recipient address. Omit when sending to the user's configured default; provide it only for another explicitly named recipient.",
            },
            "subject": {
                "type": "string",
                "minLength": 1,
                "maxLength": _MAX_SUBJECT_CHARS,
                "description": "Email subject.",
            },
            "body": {
                "type": "string",
                "maxLength": _MAX_CONTENT_CHARS,
                "description": "Email body. It may be omitted when sending only the latest generated news briefing.",
            },
            "include_last_briefing": {
                "type": "boolean",
                "description": "When true, append the complete briefing from the latest create_news_briefing result.",
            },
        },
        "required": ["subject"],
    },
)
def send_email(
    subject: str,
    to: str | None = None,
    body: str | None = None,
    include_last_briefing: bool = False,
) -> dict:
    target = to or _default_recipient()
    if not target:
        raise ValueError("未指定收件人，且未配置 MAIL_DEFAULT_RECIPIENT")
    recipient = _validate(target)
    subject = subject.strip()
    if not subject:
        raise ValueError("邮件主题为空")
    if len(subject) > _MAX_SUBJECT_CHARS:
        raise ValueError(f"邮件主题超过 {_MAX_SUBJECT_CHARS} 个字符")
    if "\r" in subject or "\n" in subject:
        raise ValueError("邮件主题包含非法换行符")

    sections: list[str] = []
    if body:
        sections.append(body)
    if include_last_briefing:
        briefing = last_briefing()
        if briefing is None:
            raise ValueError("尚未生成新闻简报，请先调用 create_news_briefing")
        sections.append(f"# {briefing.topic}新闻简报\n生成时间：{briefing.generated_at}\n\n{briefing.markdown}")
    if not sections:
        raise ValueError("邮件正文为空")
    content = "\n\n".join(sections)
    if len(content) > _MAX_CONTENT_CHARS:
        raise ValueError(f"邮件正文超过 {_MAX_CONTENT_CHARS} 个字符")
    if len(content.encode("utf-8")) > _MAX_CONTENT_BYTES:
        raise ValueError("邮件正文 UTF-8 大小超过 256 KiB")

    transport = (config.get("MAIL_TRANSPORT", "graph") or "graph").lower()
    if transport == "graph":
        result = graph_mail.send_mail(recipient, subject, content)
        sender = graph_mail.signed_in_user() or ""
    else:
        result = _send_via_smtp(recipient, subject, content)
        sender = result.pop("from", "")

    return {
        "to": recipient,
        "from": sender,
        "subject": subject,
        "included_briefing": bool(include_last_briefing),
        "message": "邮件已投递",
        **result,
    }


def _send_via_smtp(recipient: str, subject: str, content: str) -> dict:
    host = config.require("SMTP_HOST")
    port = int(config.get("SMTP_PORT", "587"))
    username = config.require("SMTP_USERNAME")
    password = config.require("SMTP_PASSWORD")
    sender = config.get("SMTP_FROM") or username

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(content)

    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
        smtp.login(username, password)
        smtp.send_message(message)

    return {"transport": "smtp", "smtp_host": host, "from": sender}
