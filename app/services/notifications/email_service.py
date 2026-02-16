"""
Email Service for Notifications
===============================

Dummy email service that simulates sending emails when notifications are created.
In production, this would integrate with actual email providers (SendGrid, SES, etc.).

Features:
    - Sends email notifications to users
    - Supports HTML and plain text emails
    - Logs email sending (dummy implementation)
    - Can be extended to use real email providers

Usage:
    from app.services.notifications.email_service import email_service
    
    await email_service.send_notification_email(
        recipient="user@example.com",
        subject="New Notification",
        body="You have a new notification"
    )
"""

import os
import asyncio
from typing import Optional, Dict, Any, Union
from datetime import datetime

from app.core.logger import get_logger

logger = get_logger(__name__)


def _notification_get(n: Any, key: str, default: Any = None) -> Any:
    """Get attribute from notification (dict or object). SQL-only path uses dict."""
    if n is None:
        return default
    if isinstance(n, dict):
        return n.get(key, default)
    return getattr(n, key, default)


class EmailService:
    """
    Dummy email service for sending notification emails.
    
    In production, replace with actual email provider integration:
    - AWS SES
    - SendGrid
    - Mailgun
    - SMTP server
    """
    
    def __init__(self):
        """Initialize email service"""
        logger.info("Initializing EmailService")
        self.enabled = os.getenv('EMAIL_SERVICE_ENABLED', 'true').lower() == 'true'
        self.provider = os.getenv('EMAIL_PROVIDER', 'dummy')  # dummy, ses, sendgrid, smtp
        self.from_email = os.getenv('EMAIL_FROM', 'notifications@xcloud.ai')
        self.from_name = os.getenv('EMAIL_FROM_NAME', 'XCloud Notifications')
        
    async def send_notification_email(
        self,
        recipient: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        notification: Optional[Union[Dict[str, Any], Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send a notification email to a recipient.
        
        Args:
            recipient: Email address of the recipient
            subject: Email subject line
            body: Plain text email body
            html_body: Optional HTML email body
            notification: Optional dict or object for context (dict from outbox/SQL path)
            metadata: Optional metadata dictionary
            
        Returns:
            bool: True if email was sent (or queued), False otherwise
        """
        logger.info(f"send_notification_email called: recipient={recipient}, subject={subject}, provider={self.provider}")
        if not self.enabled:
            logger.debug(f"Email service disabled, skipping email to {recipient}")
            return False

        try:
            # Validate email address
            if not recipient or '@' not in recipient:
                logger.warning(f"Invalid email address: {recipient}")
                return False
            
            # Use provider-specific implementation
            if self.provider == 'dummy':
                return await self._send_dummy_email(recipient, subject, body, html_body, notification)
            elif self.provider == 'ses':
                return await self._send_ses_email(recipient, subject, body, html_body)
            elif self.provider == 'sendgrid':
                return await self._send_sendgrid_email(recipient, subject, body, html_body)
            elif self.provider == 'smtp':
                return await self._send_smtp_email(recipient, subject, body, html_body)
            else:
                logger.warning(f"Unknown email provider: {self.provider}, using dummy")
                return await self._send_dummy_email(recipient, subject, body, html_body, notification)
                
        except Exception as e:
            logger.error(f"Failed to send email to {recipient}: {e}", exc_info=True)
            return False
    
    async def _send_dummy_email(
        self,
        recipient: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        notification: Optional[Union[Dict[str, Any], Any]] = None
    ) -> bool:
        """
        Dummy email implementation - just logs the email.
        
        In production, replace this with actual email sending.
        """
        logger.info("=" * 80)
        logger.info("📧 EMAIL NOTIFICATION (DUMMY)")
        logger.info("=" * 80)
        logger.info(f"From: {self.from_name} <{self.from_email}>")
        logger.info(f"To: {recipient}")
        logger.info(f"Subject: {subject}")
        logger.info("-" * 80)
        logger.info(f"Body:\n{body}")
        if html_body:
            logger.info(f"HTML Body:\n{html_body}")
        if notification:
            logger.info(f"Notification ID: {_notification_get(notification, 'id')}")
            logger.info(f"Notification Type: {_notification_get(notification, 'type')}")
            logger.info(f"Priority: {_notification_get(notification, 'priority')}")
        logger.info("=" * 80)
        logger.info(f"✅ Email would be sent to {recipient} at {datetime.utcnow().isoformat()}")
        logger.info("=" * 80)
        
        # Simulate async email sending delay
        await asyncio.sleep(0.1)
        
        return True
    
    async def _send_ses_email(
        self,
        recipient: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None
    ) -> bool:
        """
        Send email using AWS SES.

        Requires: boto3
        """
        try:
            logger.info(f"Sending email via AWS SES to {recipient}")
            import boto3
            from botocore.exceptions import ClientError
            
            ses_client = boto3.client('ses', region_name=os.getenv('AWS_REGION', 'us-east-1'))
            
            email_params = {
                'Source': f'{self.from_name} <{self.from_email}>',
                'Destination': {'ToAddresses': [recipient]},
                'Message': {
                    'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                    'Body': {
                        'Text': {'Data': body, 'Charset': 'UTF-8'}
                    }
                }
            }
            
            if html_body:
                email_params['Message']['Body']['Html'] = {
                    'Data': html_body,
                    'Charset': 'UTF-8'
                }
            
            response = ses_client.send_email(**email_params)
            logger.info(f"Email sent via SES to {recipient}, MessageId: {response['MessageId']}")
            return True
            
        except ImportError:
            logger.error("boto3 not installed. Install with: pip install boto3")
            return False
        except ClientError as e:
            logger.error(f"AWS SES error: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send email via SES: {e}")
            return False
    
    async def _send_sendgrid_email(
        self,
        recipient: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None
    ) -> bool:
        """
        Send email using SendGrid.

        Requires: sendgrid
        """
        try:
            logger.info(f"Sending email via SendGrid to {recipient}")
            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, Content
            
            api_key = os.getenv('SENDGRID_API_KEY')
            if not api_key:
                logger.error("SENDGRID_API_KEY not set")
                return False
            
            sg = sendgrid.SendGridAPIClient(api_key=api_key)
            
            from_email = Email(self.from_email, self.from_name)
            to_email = Email(recipient)
            content = Content("text/plain", body)
            
            message = Mail(from_email, to_email, subject, content)
            
            if html_body:
                message.add_content(Content("text/html", html_body))
            
            response = sg.client.mail.send.post(request_body=message.get())
            logger.info(f"Email sent via SendGrid to {recipient}, Status: {response.status_code}")
            return response.status_code in [200, 201, 202]
            
        except ImportError:
            logger.error("sendgrid not installed. Install with: pip install sendgrid")
            return False
        except Exception as e:
            logger.error(f"Failed to send email via SendGrid: {e}")
            return False
    
    async def _send_smtp_email(
        self,
        recipient: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None
    ) -> bool:
        """
        Send email using SMTP.

        Requires: aiosmtplib
        """
        try:
            logger.info(f"Sending email via SMTP to {recipient}")
            import aiosmtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            smtp_host = os.getenv('SMTP_HOST', 'localhost')
            smtp_port = int(os.getenv('SMTP_PORT', '587'))
            smtp_user = os.getenv('SMTP_USER', '')
            smtp_password = os.getenv('SMTP_PASSWORD', '')
            smtp_use_tls = os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'
            
            message = MIMEMultipart('alternative')
            message['From'] = f'{self.from_name} <{self.from_email}>'
            message['To'] = recipient
            message['Subject'] = subject
            
            message.attach(MIMEText(body, 'plain'))
            if html_body:
                message.attach(MIMEText(html_body, 'html'))
            
            await aiosmtplib.send(
                message,
                hostname=smtp_host,
                port=smtp_port,
                username=smtp_user if smtp_user else None,
                password=smtp_password if smtp_password else None,
                use_tls=smtp_use_tls
            )
            
            logger.info(f"Email sent via SMTP to {recipient}")
            return True
            
        except ImportError:
            logger.error("aiosmtplib not installed. Install with: pip install aiosmtplib")
            return False
        except Exception as e:
            logger.error(f"Failed to send email via SMTP: {e}")
            return False
    
    def format_notification_email(
        self,
        notification: Union[Dict[str, Any], Any],
        include_html: bool = True
    ) -> Dict[str, str]:
        """
        Format a notification as an email. Accepts dict (SQL/outbox path) or object.

        Args:
            notification: Dict or object with id, title, body, message, type, priority, created_at, metadata
            include_html: Whether to include HTML version

        Returns:
            Dict with 'subject', 'body', and optionally 'html_body'
        """
        nid = _notification_get(notification, "id")
        logger.info(f"Formatting notification email: id={nid}, include_html={include_html}")
        priority = (_notification_get(notification, "priority") or "normal").lower()
        priority_emoji = {
            "urgent": "🔴",
            "high": "🟠",
            "normal": "🔵",
            "low": "⚪",
        }.get(priority, "📢")
        title = _notification_get(notification, "title") or "New Notification"
        subject = f"{priority_emoji} {title}"
        body_text = _notification_get(notification, "body") or _notification_get(notification, "message") or ""
        created_at = _notification_get(notification, "created_at")
        created_str = (
            created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
            if hasattr(created_at, "strftime")
            else str(created_at) if created_at else ""
        )
        body_lines = [
            title,
            "",
            body_text,
            "",
            f"Type: {_notification_get(notification, 'type', 'info')}",
            f"Priority: {_notification_get(notification, 'priority', 'normal')}",
            f"Created: {created_str}",
        ]
        metadata = _notification_get(notification, "metadata")
        if metadata:
            body_lines.append("")
            body_lines.append("Additional Information:")
            for key, value in (metadata.items() if isinstance(metadata, dict) else []):
                body_lines.append(f"  {key}: {value}")
        body = "\n".join(body_lines)
        
        result = {
            'subject': subject,
            'body': body
        }
        
        # Build HTML body if requested
        if include_html:
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #4CAF50; color: white; padding: 20px; border-radius: 5px 5px 0 0; }}
                    .content {{ background-color: #f9f9f9; padding: 20px; border-radius: 0 0 5px 5px; }}
                    .priority {{ display: inline-block; padding: 5px 10px; border-radius: 3px; font-size: 12px; }}
                    .priority.urgent {{ background-color: #f44336; color: white; }}
                    .priority.high {{ background-color: #ff9800; color: white; }}
                    .priority.normal {{ background-color: #2196F3; color: white; }}
                    .priority.low {{ background-color: #9e9e9e; color: white; }}
                    .footer {{ margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>{title}</h1>
                    </div>
                    <div class="content">
                        <p>{body_text}</p>
                        <p>
                            <strong>Type:</strong> {_notification_get(notification, 'type', 'info')}<br>
                            <span class="priority {priority}">
                                Priority: {_notification_get(notification, 'priority', 'normal')}
                            </span><br>
                            <strong>Created:</strong> {created_str}
                        </p>
            """
            if metadata:
                html_body += """
                        <div style="margin-top: 20px; padding: 15px; background-color: #fff; border-left: 4px solid #4CAF50;">
                            <strong>Additional Information:</strong>
                            <ul>
                """
                for key, value in (metadata.items() if isinstance(metadata, dict) else []):
                    html_body += f"<li><strong>{key}:</strong> {value}</li>"
                html_body += """
                            </ul>
                        </div>
                """
            
            html_body += """
                    </div>
                    <div class="footer">
                        <p>This is an automated notification from XCloud.</p>
                        <p>You are receiving this because you have notifications enabled.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            result['html_body'] = html_body
        
        return result


# Global email service instance
email_service = EmailService()
