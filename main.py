import ssl
import imaplib
import time
import email
import logging
from logging.handlers import RotatingFileHandler
from notion_client import Client
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import (
    IMAP_SERVER,
    IMAP_PORT,
    EMAIL,
    EMAIL_PASSWORD,
    NOTION_API_KEY,
)
from email_processor import process_email
from utils import extract_email_received_date, connect_imap

logger = logging.getLogger()
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

file_handler = RotatingFileHandler('app.log', maxBytes=5*1024*1024, backupCount=5)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('playwright').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)

notion = Client(auth=NOTION_API_KEY)

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type(imaplib.IMAP4.error)
)
def check_for_new_emails():
    try:
        mail = connect_imap(IMAP_SERVER, IMAP_PORT, EMAIL, EMAIL_PASSWORD)
        logger.info(f"Logged in to email: {EMAIL}")
        while True:
            try:
                mail.select("INBOX")
                status, messages = mail.search(None, "UNSEEN")
                if status != 'OK':
                    logger.error(f"Failed to search emails: {status}")
                    time.sleep(60)
                    continue
                email_ids = messages[0].split()
                for e_id in email_ids:
                    try:
                        res, msg_data = mail.fetch(e_id, "(RFC822)")
                        if res != 'OK':
                            logger.error(f"Failed to fetch email {e_id.decode()}: {res}")
                            continue
                        for response in msg_data:
                            if isinstance(response, tuple):
                                msg = email.message_from_bytes(response[1])
                                email_received_date = extract_email_received_date(msg)
                                process_email(e_id, msg, email_received_date)
                                mark_email_as_processed(mail, e_id)
                                move_email_to_archive(mail, e_id)
                    except Exception as e:
                        logger.error(f"Error processing email {e_id.decode()}: {e}")
                time.sleep(60)
            except imaplib.IMAP4.error as e:
                logger.error(f"IMAP error during email processing: {e}")
                raise e
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                time.sleep(60)
    except imaplib.IMAP4.error as e:
        logger.error(f"Failed to connect/login to IMAP: {e}")
        raise e
    except Exception as e:
        logger.error(f"Error in check_for_new_emails: {e}")
        raise e

def mark_email_as_processed(mail, email_id):
    try:
        mail.store(email_id, '+FLAGS', '\\Seen')
        logger.info(f"Marked email {email_id.decode()} as Seen.")
    except Exception as e:
        logger.error(f"Error marking email {email_id} as processed: {e}")

def move_email_to_archive(mail, email_id):
    try:
        archive_folder = 'Archive'
        result = mail.copy(email_id, archive_folder)
        if result[0] == 'OK':
            mail.store(email_id, '+FLAGS', '\\Deleted')
            mail.expunge()
            logger.info(f"Email {email_id.decode()} moved to {archive_folder}.")
        else:
            logger.error(f"Failed to copy email {email_id.decode()} to {archive_folder}: {result}")
    except Exception as e:
        logger.error(f"Error moving email {email_id.decode()} to {archive_folder}: {e}")

if __name__ == "__main__":
    try:
        check_for_new_emails()
    except Exception as e:
        logger.error(f"Critical error in main loop: {e}. Restarting in 60 seconds.")
        time.sleep(60)
