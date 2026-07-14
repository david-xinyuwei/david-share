"""Build and optionally open a draft-only EML in New Outlook."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
from collections.abc import Iterable
from email import policy
from email.headerregistry import Address
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses
from pathlib import Path
from uuid import uuid4

from .models import MeetingAnalysis


def build_eml(
    analysis: MeetingAnalysis,
    attachments: Iterable[Path],
    output_path: Path,
    recipients: Iterable[str] = (),
) -> dict[str, object]:
    """Create an unsent MIME message and return validated evidence."""
    attachment_paths = [Path(path) for path in attachments]
    for attachment in attachment_paths:
        if not attachment.is_file():
            raise FileNotFoundError(attachment)

    message = EmailMessage()
    message["Subject"] = _subject(analysis.title)
    message["X-Unsent"] = "1"
    recipient_list = _recipient_list(recipients)
    if recipient_list:
        message["To"] = ", ".join(recipient_list)
    message.set_content(_plain_body(analysis))
    message.add_alternative(_html_body(analysis), subtype="html")

    for attachment in attachment_paths:
        maintype, subtype = _mime_type(attachment)
        message.add_attachment(
            attachment.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            filename=attachment.name,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(output_path)
    try:
        temporary.write_bytes(message.as_bytes(policy=policy.default))
        temporary.replace(output_path)
    finally:
        temporary.unlink(missing_ok=True)
    evidence = validate_eml(output_path)
    evidence["sha256"] = file_sha256(output_path)
    return evidence


def validate_eml(path: Path) -> dict[str, object]:
    message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    recipient_headers = [
        str(value)
        for header in ("To", "Cc", "Bcc")
        for value in message.get_all(header, [])
    ]
    recipients = [address for _, address in getaddresses(recipient_headers) if address]
    attachments = [part.get_filename() for part in message.iter_attachments()]
    subject = str(message.get("Subject") or "").strip()
    if message.get("X-Unsent") != "1":
        raise ValueError("EML is missing X-Unsent: 1")
    if not attachments:
        raise ValueError("EML has no attachments")
    return {
        "x_unsent": message.get("X-Unsent"),
        "recipient_count": len(recipients),
        "attachment_count": len(attachments),
        "attachment_names": attachments,
        "subject": subject,
    }


def open_in_new_outlook(path: Path) -> subprocess.Popen[bytes]:
    """Open an EML with New Outlook. This function never sends the message."""
    if platform.system() != "Windows":
        raise RuntimeError("New Outlook handoff is available only on Windows")
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        return subprocess.Popen(
            ["olk.exe", str(path.resolve())],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except FileNotFoundError as error:
        raise RuntimeError(
            "New Outlook executable olk.exe was not found; install New Outlook "
            "and ensure olk.exe is available on PATH"
        ) from error


def write_evidence(path: Path, evidence: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(path)
    try:
        temporary.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _plain_body(analysis: MeetingAnalysis) -> str:
    lines = [analysis.summary, "", "Decisions:"]
    lines.extend(f"- {item}" for item in analysis.decisions or ["None recorded"])
    lines.extend(["", "Action items:"])
    lines.extend(f"- {item.description}" for item in analysis.action_items)
    lines.extend(["", "Review this draft and its attachments before sending manually."])
    return "\n".join(lines)


def _html_body(analysis: MeetingAnalysis) -> str:
    decisions = "".join(f"<li>{_escape(item)}</li>" for item in analysis.decisions)
    actions = "".join(
        f"<li>{_escape(item.description)}</li>" for item in analysis.action_items
    )
    return (
        f"<p>{_escape(analysis.summary)}</p>"
        f"<h3>Decisions</h3><ul>{decisions or '<li>None recorded</li>'}</ul>"
        f"<h3>Action items</h3><ul>{actions or '<li>None recorded</li>'}</ul>"
        "<p><strong>Review this draft and its attachments before sending manually.</strong></p>"
    )


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _subject(value: str) -> str:
    subject = " ".join(value.split())[:160].strip()
    if not subject:
        raise ValueError("email subject cannot be empty")
    return subject


def _recipient_list(values: Iterable[str]) -> list[str]:
    recipients: list[str] = []
    for raw_value in values:
        value = raw_value.strip()
        if not value:
            continue
        if "\r" in value or "\n" in value:
            raise ValueError("recipient addresses cannot contain newlines")
        try:
            address = Address(addr_spec=value)
        except ValueError as error:
            raise ValueError(f"invalid recipient address: {value!r}") from error
        if not address.domain:
            raise ValueError(f"invalid recipient address: {value!r}")
        recipients.append(str(address))
    return recipients


def _mime_type(path: Path) -> tuple[str, str]:
    suffix = path.suffix.casefold()
    if suffix == ".png":
        return "image", "png"
    if suffix == ".svg":
        return "image", "svg+xml"
    if suffix == ".pptx":
        return (
            "application",
            "vnd.openxmlformats-officedocument.presentationml.presentation",
        )
    return "application", "octet-stream"


def _temporary_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.{uuid4().hex}.tmp")