"""
Email Tasks

Celery tasks for async email sending.
"""

from app.core.celery_app import celery_app
from app.core.logger import get_logger
from app.services.email.service import email_service


logger = get_logger(__name__)


@celery_app.task(bind=True, max_retries=3)
def send_email_task(
    self,
    to: str,
    subject: str,
    body: str,
    html_body: str = None,
):
    """
    Celery task to send email asynchronously.

    Args:
        to: Recipient email address
        subject: Email subject
        body: Plain text body
        html_body: Optional HTML body
    """
    import asyncio

    async def send():
        return await email_service.send_email(
            to=to,
            subject=subject,
            body=body,
            html_body=html_body,
        )

    try:
        result = asyncio.run(send())
        if result:
            logger.info(f"Email sent to {to}")
        else:
            logger.warning(f"Email not sent to {to}")
        return result
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        raise self.retry(exc=e, countdown=300)


@celery_app.task(bind=True, max_retries=3)
def send_welcome_email_task(self, to: str, name: str):
    """Send welcome email task."""
    import asyncio

    try:
        asyncio.run(email_service.send_welcome_email(to, name))
        logger.info(f"Welcome email sent to {to}")
    except Exception as e:
        logger.error(f"Failed to send welcome email: {e}")
        raise self.retry(exc=e, countdown=300)


@celery_app.task(bind=True, max_retries=3)
def send_password_reset_email_task(self, to: str, name: str, reset_link: str):
    """Send password reset email task."""
    import asyncio

    try:
        asyncio.run(email_service.send_password_reset_email(to, name, reset_link))
        logger.info(f"Password reset email sent to {to}")
    except Exception as e:
        logger.error(f"Failed to send password reset email: {e}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def send_email_verification_task(self, to: str, name: str, verification_link: str):
    """Send email verification task."""
    import asyncio

    try:
        asyncio.run(email_service.send_email_verification(to, name, verification_link))
        logger.info(f"Verification email sent to {to}")
    except Exception as e:
        logger.error(f"Failed to send verification email: {e}")
        raise self.retry(exc=e, countdown=60)


def queue_welcome_email(to: str, name: str):
    """Queue welcome email for async sending."""
    return send_welcome_email_task.delay(to, name)


def queue_password_reset_email(to: str, name: str, reset_link: str):
    """Queue password reset email for async sending."""
    return send_password_reset_email_task.delay(to, name, reset_link)


def queue_email_verification(to: str, name: str, verification_link: str):
    """Queue email verification for async sending."""
    return send_email_verification_task.delay(to, name, verification_link)
