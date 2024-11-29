import logging
import email
from langdetect import detect
from notion_utils import (
    get_location_from_registry_playwright,
    SERVICE_CONFIG,
    normalize_company_name
)
from email_notification import send_error_email

from config import (
    ESTONIAN_SUBJECT,
    ENGLISH_SUBJECT,
    MAIN_DATABASE_ID,
    RELATED_DATABASE_ID,
    PEOPLE_DATABASE_ID,
    DATABASE_RESPONSIBLES,
    DEFAULT_RECIPIENTS
)
from data_extraction import (
    extract_email_body,
    extract_email_data,
    extract_service_counts,
)
from notion_utils import (
    find_matching_entry_by_registry_code,
    create_new_entry_in_related_database,
    add_company_to_main_database,
    add_project_to_additional_databases,
    find_matching_contact_by_name,
    create_new_contact_in_people_database,
)
from utils import decode_subject

def process_email(e_id, msg, email_received_date):
    subject = decode_subject(msg["Subject"])

    body = extract_email_body(msg)

    try:
        language = detect(body)
        logging.info(f"Detected language: {language}")
    except Exception as e:
        logging.warning(f"Language detection failed: {e}")
        language = 'unknown'

    if language not in ['en', 'et']:
        logging.warning("Email language could not be determined. Skipping email.")
        return

    email_data = extract_email_data(body)

    if email_data["company_name"]:
        email_data["company_name"] = normalize_company_name(email_data["company_name"])


        service_counts = extract_service_counts(body, language)

        logging.info(f"Extracted service counts: {service_counts}")

        process_email_data(email_data, service_counts, email_received_date, language)
    else:
        logging.warning("Company name is missing in the email data. Skipping email.")
def process_email_data(email_data, service_counts, email_received_date, language):
    logging.info(f"Processing email data: {email_data}")
    try:
        logging.info("Searching for matching entry in related database.")
        related_entry = find_matching_entry_by_registry_code(
            email_data["registration_code"], RELATED_DATABASE_ID, "Registrikood"
        )
        if related_entry:
            related_entry_id = related_entry["id"]
            logging.info(f"Found related entry with ID: {related_entry_id}")
        else:
            logging.info("No related entry found. Creating a new one.")
            related_entry_id = create_new_entry_in_related_database(
                email_data["company_name"],
                email_data["registration_code"],
                RELATED_DATABASE_ID,
            )
            logging.info(f"Created new related entry with ID: {related_entry_id}")

        contact_name = email_data.get("participant_name", "")
        if contact_name:
            related_contact = find_matching_contact_by_name(contact_name, PEOPLE_DATABASE_ID)
            if not related_contact:
                create_new_contact_in_people_database(
                    name=contact_name,
                    email_address=email_data.get("email_address", ""),
                    phone_number=email_data.get("phone_number", ""),
                    organisation_id=related_entry_id,
                    people_database_id=PEOPLE_DATABASE_ID
                )

        include_jrk = any(count > 0 for count in service_counts.values())
        add_company_to_main_database(
            email_data,
            email_received_date,
            related_entry_id,
            service_counts,
            language,
            include_jrk=include_jrk
        )

        for service_name, count in service_counts.items():
            if count > 0 and service_name in SERVICE_CONFIG:
                recipients = DATABASE_RESPONSIBLES.get(
                    SERVICE_CONFIG[service_name]["database_id"],
                    DEFAULT_RECIPIENTS
                )
                add_project_to_additional_databases(
                    service_name, email_data, count, email_received_date, recipients
                )
    except Exception as e:
        error_message = f"An error occurred while processing the email: {str(e)}"
        recipients = DEFAULT_RECIPIENTS
        send_error_email(email_data.get("registration_code", ""), error_message, email_data, recipients)
        logging.error(f"Failed to process email for company {email_data.get('company_name', '')}: {error_message}", exc_info=True)