from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Union

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from starlette.datastructures import UploadFile


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _as_list(value: Union[str, Iterable[str]]) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


class EmailSendService:
    """
    Thin wrapper around FastMail to send text, HTML, and template-based emails.
    """

    def __init__(self, config: ConnectionConfig):
        self._fm = FastMail(config)

    @classmethod
    def from_env(cls) -> "EmailSendService":
        """
        Build the service from environment variables. Supports both new and legacy flags.

        Required:
          - MAIL_USERNAME
          - MAIL_PASSWORD
          - MAIL_FROM
          - MAIL_SERVER
        Optional:
          - MAIL_PORT (default 587)
          - MAIL_FROM_NAME
          - MAIL_STARTTLS / MAIL_TLS (default True)
          - MAIL_SSL_TLS / MAIL_SSL (default False)
          - MAIL_USE_CREDENTIALS / USE_CREDENTIALS (default True)
          - MAIL_VALIDATE_CERTS / VALIDATE_CERTS (default True)
          - MAIL_SUPPRESS_SEND (default False)
          - MAIL_TEMPLATE_FOLDER (default "templates")
        """
        template_folder = os.getenv("MAIL_TEMPLATE_FOLDER", "templates")
        template_path = Path(template_folder).resolve()

        conf = ConnectionConfig(
            MAIL_USERNAME=os.getenv("MAIL_USERNAME", ""),
            MAIL_PASSWORD=os.getenv("MAIL_PASSWORD", ""),
            MAIL_FROM=os.getenv("MAIL_FROM", ""),
            MAIL_PORT=int(os.getenv("MAIL_PORT", "587")),
            MAIL_SERVER=os.getenv("MAIL_SERVER", ""),
            MAIL_FROM_NAME=os.getenv("MAIL_FROM_NAME"),
            MAIL_STARTTLS=_get_bool(
                "MAIL_STARTTLS", _get_bool("MAIL_TLS", True)),
            MAIL_SSL_TLS=_get_bool(
                "MAIL_SSL_TLS", _get_bool("MAIL_SSL", False)),
            USE_CREDENTIALS=_get_bool(
                "MAIL_USE_CREDENTIALS", _get_bool("USE_CREDENTIALS", True)
            ),
            VALIDATE_CERTS=_get_bool(
                "MAIL_VALIDATE_CERTS", _get_bool("VALIDATE_CERTS", True)
            ),
            SUPPRESS_SEND=_get_bool("MAIL_SUPPRESS_SEND", False),
            TEMPLATE_FOLDER=template_path if template_path.exists() else None,
        )
        return cls(conf)

    async def send_text(
        self,
        subject: str,
        recipients: Union[str, Sequence[str]],
        body: str,
        *,
        reply_to: Optional[str] = None,
        cc: Optional[Sequence[str]] = None,
        bcc: Optional[Sequence[str]] = None,
        attachments: Optional[Sequence[Union[UploadFile,
                                             str, Path, bytes]]] = None,
    ) -> None:
        """
        Send a plain-text email.
        """
        msg = MessageSchema(
            subject=subject,
            recipients=_as_list(recipients),
            body=body,
            subtype=MessageType.plain,
            reply_to=reply_to if reply_to else [],
            cc=_as_list(cc) if cc else [],
            bcc=_as_list(bcc) if bcc else [],
            attachments=list(attachments) if attachments else [],
        )
        await self._fm.send_message(msg)

    async def send_html(
        self,
        subject: str,
        recipients: Union[str, Sequence[str]],
        html: str,
        *,
        reply_to: Optional[str] = None,
        cc: Optional[Sequence[str]] = None,
        bcc: Optional[Sequence[str]] = None,
        attachments: Optional[Sequence[Union[UploadFile,
                                             str, Path, bytes]]] = None,
    ) -> None:
        """
        Send a raw HTML email.
        """
        msg = MessageSchema(
            subject=subject,
            recipients=_as_list(recipients),
            body=html,
            subtype=MessageType.html,
            reply_to=reply_to,
            cc=_as_list(cc) if cc else None,
            bcc=_as_list(bcc) if bcc else None,
            attachments=list(attachments) if attachments else None,
        )
        await self._fm.send_message(msg)

    async def send_template(
        self,
        subject: str,
        recipients: Union[str, Sequence[str]],
        template_name: str,
        context: dict,
        *,
        reply_to: Optional[str] = None,
        cc: Optional[Sequence[str]] = None,
        bcc: Optional[Sequence[str]] = None,
        attachments: Optional[Sequence[Union[UploadFile,
                                             str, Path, bytes]]] = None,
    ) -> None:
        """
        Send an email rendered from a Jinja2 template.

        Requirements:
          - Set MAIL_TEMPLATE_FOLDER to a directory containing your templates.
          - Provide context dict used to render the template.
        """
        msg = MessageSchema(
            subject=subject,
            recipients=_as_list(recipients),
            body=context,  # dict required when using template rendering
            subtype=MessageType.html,
            reply_to=reply_to,
            cc=_as_list(cc) if cc else None,
            bcc=_as_list(bcc) if bcc else None,
            attachments=list(attachments) if attachments else None,
        )
        await self._fm.send_message(msg, template_name=template_name)


if __name__ == "__main__":

    config = ConnectionConfig(
        MAIL_USERNAME="*******",
        MAIL_PASSWORD="*******",
        MAIL_SERVER="smtp.gmx.com",
        MAIL_PORT="587",
        MAIL_FROM="*******",
        MAIL_STARTTLS=True,
        MAIL_SSL_TLS=False,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True,
        SUPPRESS_SEND=False,
    )

    email_service = EmailSendService(config)

    # test sending a simple email
    import asyncio

    async def main():
        await email_service.send_text(
            subject="Test Email",
            recipients=["orth-sebastian@gmx.de"],
            body="This is a test email.",
            reply_to=None,
            cc=None,
            bcc=None,
            attachments=None,
        )

    asyncio.run(main())
