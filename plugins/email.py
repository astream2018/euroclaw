import os
import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from plugins.base import MessagingPlugin

class EmailPlugin(MessagingPlugin):
    def __init__(self):
        self.email_address = os.getenv("EUROCLAW_EMAIL")
        self.password = os.getenv("EUROCLAW_EMAIL_PASSWORD")
        self.imap_server = os.getenv("EUROCLAW_IMAP_SERVER")
        self.smtp_server = os.getenv("EUROCLAW_SMTP_SERVER")

    def connect(self):
        self.mail = imaplib.IMAP4_SSL(self.imap_server)
        self.mail.login(self.email_address, self.password)

    def receive_message(self, mailbox="inbox") -> list:
        parsed_messages = []
        self.mail.select(mailbox)
        status, messages = self.mail.search(None, '(UNSEEN)')
        for num in messages[0].split():
            status, data = self.mail.fetch(num, '(RFC822)')
            msg = email.message_from_bytes(data[0][1])
            body = msg.get_payload(decode=True).decode() if not msg.is_multipart() else ""
            parsed_messages.append({
                "source": "email", "user_id": msg.get("Reply-To", msg.get("From")), "text": body.strip()
            })
        return parsed_messages

    def send_message(self, user_id: str, text: str):
        msg = MIMEText(text)
        msg['Subject'] = "Re: EuroClaw Automated Architecture Execution Audit"
        msg['From'] = self.email_address
        msg['To'] = user_id
        with smtplib.SMTP_SSL(self.smtp_server) as server:
            server.login(self.email_address, self.password)
            server.send_message(msg)