"""Handles email notifications for the Inheco Incubator module.

This module provides functionality to send email notifications in case of errors or important
events related to the Inheco Incubator module. It uses the SMTP protocol to send emails through
a specified SMTP server.

Environment Variables:
- SMTP_SERVER: The SMTP server address.
- SMTP_PORT: The SMTP server port.
- SENDER_EMAIL: The email address of the sender.
- SENDER_PASSWORD: The password for the sender's email account.
- RECEIVER_EMAILS: A comma-separated list of recipient email addresses.
"""

import os
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv

# load environment variables from .env file
load_dotenv()

# Set up redis for exchange location lock
smtp_server = os.getenv("SMTP_SERVER")
smtp_port = os.getenv("SMTP_PORT")
sender_email = os.getenv("SENDER_EMAIL")
sender_password = os.getenv("SENDER_PASSWORD")
receiver_emails = os.getenv("RECEIVER_EMAILS").split(",")

# Note: Email list must be formatted as follows in the .env file:
# RECEIVER_EMAILS = "john_doe@example.com,jane_smith@example.com"  # noqa ERA001


def send_email(error_msg: str) -> None:
    """Send an email with the given error message to the specified recipients."""

    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender_email, sender_password)

            for email in receiver_emails:
                msg = EmailMessage()
                msg["Subject"] = "446 ERROR"
                msg["From"] = sender_email
                msg["To"] = email
                msg.set_content(error_msg)

                server.send_message(msg)
                print(f"Email sent to {email}")  # noqa T201

        print("Emails sent successfully!")  # noqa T201

    except Exception as e:
        print(f"Failed to send email: {e}")  # noqa T201
