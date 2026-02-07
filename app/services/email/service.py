"""
Email Service

Send emails using SMTP with template support.
"""

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Optional, List

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings
from app.core.logger import get_logger


logger = get_logger(__name__)

# Template directory
TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates" / "emails"


class EmailService:
    """Email service for sending emails."""

    def __init__(self):
        self._smtp = None
        self._jinja_env = Environment(
            loader=FileSystemLoader(TEMPLATE_DIR),
            autoescape=select_autoescape(["html", "xml"]),
        )

    async def _get_smtp_client(self):
        """Get SMTP client."""
        try:
            import aiosmtplib
        except ImportError:
            raise RuntimeError("aiosmtplib package not installed")

        return aiosmtplib.SMTP(
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            use_tls=settings.SMTP_TLS,
            start_tls=not settings.SMTP_TLS and settings.SMTP_PORT == 587,
        )

    def _render_template(self, template_name: str, context: dict) -> str:
        """Render email template."""
        try:
            template = self._jinja_env.get_template(template_name)
            return template.render(**context)
        except Exception as e:
            logger.error(f"Failed to render template {template_name}: {e}")
            raise

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> bool:
        """
        Send email.

        Args:
            to: Recipient email address
            subject: Email subject
            body: Plain text body
            html_body: Optional HTML body
            cc: Optional CC recipients
            bcc: Optional BCC recipients

        Returns:
            True if email sent successfully
        """
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            logger.warning("SMTP not configured, skipping email")
            return False

        # Create message
        if html_body:
            msg = MIMEMultipart("alternative")
            msg.attach(MIMEText(body, "plain"))
            msg.attach(MIMEText(html_body, "html"))
        else:
            msg = MIMEText(body, "plain")

        msg["Subject"] = subject
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg["To"] = to

        if cc:
            msg["Cc"] = ", ".join(cc)

        recipients = [to]
        if cc:
            recipients.extend(cc)
        if bcc:
            recipients.extend(bcc)

        try:
            smtp = await self._get_smtp_client()
            await smtp.connect()
            await smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            await smtp.send_message(msg, recipients=recipients)
            await smtp.quit()

            logger.info(f"Email sent to {to}: {subject}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}")
            return False

    async def send_template_email(
        self,
        to: str,
        subject: str,
        template_name: str,
        context: dict,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> bool:
        """
        Send email using template.

        Args:
            to: Recipient email address
            subject: Email subject
            template_name: Template file name
            context: Template context variables
            cc: Optional CC recipients
            bcc: Optional BCC recipients

        Returns:
            True if email sent successfully
        """
        # Add common context
        context.update({
            "app_name": settings.APP_NAME,
            "support_email": settings.SMTP_FROM_EMAIL,
        })

        html_body = self._render_template(template_name, context)

        # Create plain text version
        body = f"""
{settings.APP_NAME}

{subject}

If you have any questions, please contact {settings.SMTP_FROM_EMAIL}
        """.strip()

        return await self.send_email(
            to=to,
            subject=subject,
            body=body,
            html_body=html_body,
            cc=cc,
            bcc=bcc,
        )

    async def send_welcome_email(self, to: str, name: str) -> bool:
        """Send welcome email to new user."""
        return await self.send_template_email(
            to=to,
            subject=f"Welcome to {settings.APP_NAME}!",
            template_name="welcome.html",
            context={"name": name},
        )

    async def send_password_reset_email(
        self,
        to: str,
        name: str,
        reset_link: str,
    ) -> bool:
        """Send password reset email."""
        return await self.send_template_email(
            to=to,
            subject=f"Reset your {settings.APP_NAME} password",
            template_name="password_reset.html",
            context={"name": name, "reset_link": reset_link},
        )

    async def send_email_verification(
        self,
        to: str,
        name: str,
        verification_link: str,
    ) -> bool:
        """Send email verification email."""
        return await self.send_template_email(
            to=to,
            subject=f"Verify your {settings.APP_NAME} email",
            template_name="email_verification.html",
            context={"name": name, "verification_link": verification_link},
        )


# Global email service instance
email_service = EmailService()
