"""Optional: sends the drafted email via your own Gmail account (free, using an
App Password — never your real Gmail password). If GMAIL_ADDRESS / GMAIL_APP_PASSWORD
aren't set, sending is simply skipped and emails stay as drafts, same as
WhatsApp/LinkedIn/Messenger.
"""
from __future__ import annotations
import smtplib
from email.mime.text import MIMEText


def send(to_email: str, subject: str, body: str, gmail_address: str, gmail_app_password: str) -> bool:
    if not gmail_address or not gmail_app_password:
        return False
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = to_email
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
        server.login(gmail_address, gmail_app_password)
        server.sendmail(gmail_address, [to_email], msg.as_string())
    return True
