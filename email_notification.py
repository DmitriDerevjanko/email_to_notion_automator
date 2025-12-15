# email_notification.py

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import CC_EMAIL, EMAIL_PASSWORD  

def send_error_email(reg_code, error_message, email_data, recipients, database_name=None):
    import json
    import os
    import time
    from tempfile import NamedTemporaryFile

    sender_email = "aire-technical@aire-edih.eu"

    STORE_PATH = "/tmp/aire_notified.json"
    TTL_SECONDS = 180  

    client_email = email_data.get("email_address") if isinstance(email_data, dict) else None

    internal_recipients = recipients or []
    if isinstance(internal_recipients, str):
        internal_recipients = [internal_recipients]

    store = {}
    try:
        if os.path.exists(STORE_PATH):
            with open(STORE_PATH, "r", encoding="utf-8") as f:
                store = json.load(f) or {}
    except Exception:
        store = {}

    now = int(time.time())
    key = f"{reg_code}:{client_email}" if client_email else None

    store = {
        k: ts for k, ts in store.items()
        if isinstance(ts, int) and (now - ts) < TTL_SECONDS
    }

    client_can_receive = False
    if client_email:
        if key not in store:
            client_can_receive = True
            store[key] = now  

    subject = "Registreerimine ei õnnestunud / Registration failed"
    body = f"""
Tere,

Registreerimine ei õnnestunud, kuna sisestatud registrikood ({reg_code}) ei olnud õige.
Palun kontrollige andmeid ja registreerige uuesti.

Registrikoodi saab kontrollida Äriregistri veebilehel:
https://ariregister.rik.ee/est

---

Hello,

Registration failed because the provided registration code ({reg_code}) was incorrect.
Please review the information and register again.

You can verify the registration code on the Estonian Business Register website:
https://ariregister.rik.ee/est

Parimate soovidega / Kind regards,
AIRE Technical Support
"""

    recipients_all = []

    if client_can_receive and client_email:
        recipients_all.append(client_email)

    recipients_all.extend(internal_recipients)

    if CC_EMAIL:
        recipients_all.append(CC_EMAIL)

    seen = set()
    final_recipients = []
    for r in recipients_all:
        if r and r not in seen:
            seen.add(r)
            final_recipients.append(r)

    if not final_recipients:
        return

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = ", ".join(final_recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(body.strip(), "plain"))

    try:
        with smtplib.SMTP("smtp.zone.eu", 587) as server:
            server.starttls()
            server.login(sender_email, EMAIL_PASSWORD)
            server.sendmail(sender_email, final_recipients, msg.as_string())

        print(f"Unified error email sent to: {', '.join(final_recipients)}")

        with NamedTemporaryFile("w", delete=False, dir="/tmp", encoding="utf-8") as tf:
            json.dump(store, tf)
            tmp = tf.name
        os.replace(tmp, STORE_PATH)

    except Exception as e:
        print(f"Failed to send unified error email: {e}")


def send_success_email(reg_code, email_data, recipients, item_url, database_name):
    sender_email = "aire-technical@aire-edih.eu"
    recipient_emails = recipients 
    subject = f"Edu: Ettevõte {email_data['company_name']} edukalt lisatud andmebaasi {database_name}"

    body = f"""Tere,

Ettevõtte andmed on edukalt töödeldud ja lisatud andmebaasi Teenusele registreerimine – {database_name}.

Ettevõte: {email_data['company_name']}

Saate vaadata lisatud kirjet siin:
{item_url}

Parimate soovidega,
Tehniline tugi
AIRE"""

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = ", ".join(recipient_emails)
    msg["Cc"] = CC_EMAIL
    msg["Subject"] = subject

    msg.attach(MIMEText(body.strip(), "plain"))

    try:
        with smtplib.SMTP("smtp.zone.eu", 587) as server:
            server.starttls()
            server.login(sender_email, EMAIL_PASSWORD)  
            server.sendmail(sender_email, recipient_emails + [CC_EMAIL], msg.as_string())
        print(f"Success email sent to {', '.join(recipient_emails)} with CC to {CC_EMAIL}")
    except Exception as e:
        print(f"Failed to send success email: {e}")
