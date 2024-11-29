# email_notification.py

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import CC_EMAIL, EMAIL_PASSWORD  

def send_error_email(reg_code, error_message, email_data, recipients, database_name=None):
    sender_email = "aire-technical@aire-edih.eu"
    recipient_emails = recipients 
    subject = f"Viga Registrikoodiga: {reg_code}"

    if database_name:
        subject += f" andmebaasis {database_name}"

    body = f"""
    Tere,

    Kahjuks ilmnes viga ettevõtte andmete töötlemisel.

    Ettevõtte andmed:
    ----------------------------------------
    Ettevõtte nimi: {email_data['company_name']}
    E-posti aadress: {email_data['email_address']}
    Telefoni number: {email_data['phone_number']}
    Registrikood: {reg_code}
    Tööstusharu: {email_data['industry']}
    Osaleja nimi: {email_data['participant_name']}
    ----------------------------------------

    Viga:
    {error_message}

    Palun kontrollige andmeid ja sisestage need käsitsi Notion süsteemi.

    Lugupidamisega,
    Tehniline tugi
    AIRE
    """

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
        print(f"Error email sent to {', '.join(recipient_emails)} with CC to {CC_EMAIL}")
    except Exception as e:
        print(f"Failed to send error email: {e}")

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
