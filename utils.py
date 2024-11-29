# utils.py

import imaplib
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import logging
from email.header import decode_header
from email.utils import parsedate_to_datetime

# Get the logger for this module
logger = logging.getLogger(__name__)

# Decode the email subject
def decode_subject(subject):
    decoded_subject, encoding = decode_header(subject)[0]
    if isinstance(decoded_subject, bytes):
        return decoded_subject.decode(encoding or "utf-8")
    return decoded_subject

# Extract the received date of the email
def extract_email_received_date(msg):
    email_date = msg["Date"]
    email_datetime = parsedate_to_datetime(email_date)
    return email_datetime.strftime("%Y-%m-%d")

# Decode the email part
def decode_part(part):
    try:
        return part.get_payload(decode=True).decode()
    except UnicodeDecodeError:
        return part.get_payload(decode=True).decode("iso-8859-1")

# Connect to IMAP with retry logic
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(imaplib.IMAP4.error)
)
def connect_imap(server, port, email, password):
    try:
        mail = imaplib.IMAP4_SSL(server, port)
        mail.login(email, password)
        logger.info(f"Successfully connected to IMAP server: {server}")
        return mail
    except imaplib.IMAP4.error as e:
        logger.error(f"IMAP connection error: {e}")
        raise e  # Trigger retry
