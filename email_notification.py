# email_notification.py

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import CC_EMAIL, EMAIL_PASSWORD  

def send_error_email(reg_code, error_message, email_data, recipients, database_name=None):
    sender_email = "aire-technical@aire-edih.eu"

    all_recipients = []

    client_email = email_data.get("email_address")
    if client_email:
        all_recipients.append(client_email)

    if isinstance(recipients, str):
        all_recipients.append(recipients)
    elif isinstance(recipients, list):
        all_recipients.extend(recipients)

    if CC_EMAIL:
        all_recipients.append(CC_EMAIL)

    all_recipients = list({email for email in all_recipients if email})

    if not all_recipients:
        print("No recipients for error email")
        return

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
    https://ariregister.rik.ee/eng

    Parimate soovidega / Kind regards,
    AIRE Technical Support
    """


    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = ", ".join(all_recipients)
    msg["Subject"] = subject

    msg.attach(MIMEText(body.strip(), "plain"))

    try:
        with smtplib.SMTP("smtp.zone.eu", 587) as server:
            server.starttls()
            server.login(sender_email, EMAIL_PASSWORD)
            server.sendmail(sender_email, all_recipients, msg.as_string())

        print(f"Unified error email sent to: {', '.join(all_recipients)}")

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
