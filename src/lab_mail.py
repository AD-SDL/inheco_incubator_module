import smtplib
from email.message import EmailMessage
import os

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
# RECEIVER_EMAILS = "john_doe@example.com,jane_smith@example.com"

def send_email(error_msg: str):

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
                print(f"Email sent to {email}")

        print("Emails sent successfully!")

    except Exception as e:
        print(f"Failed to send email: {e}")
