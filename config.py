# config.py

import os
from dotenv import load_dotenv

load_dotenv()

def parse_emails(env_var):
    emails = os.getenv(env_var, "")
    return [email.strip() for email in emails.split(",") if email.strip()]

# Load sensitive data from environment variables without default values
IMAP_SERVER = os.getenv("IMAP_SERVER")
IMAP_PORT = int(os.getenv("IMAP_PORT", 993))  
EMAIL = os.getenv("EMAIL")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
NOTION_API_KEY = os.getenv("NOTION_API_KEY")

# Main Database ID
MAIN_DATABASE_ID = os.getenv("MAIN_DATABASE_ID")
RELATED_DATABASE_ID = os.getenv("RELATED_DATABASE_ID")
PEOPLE_DATABASE_ID = os.getenv("PEOPLE_DATABASE_ID")

# Service-specific Database IDs
AI_CONSULTANCY_DATABASE_ID = os.getenv("AI_CONSULTANCY_DATABASE_ID")
PRIVATE_FUNDING_DATABASE_ID = os.getenv("PRIVATE_FUNDING_DATABASE_ID")
PUBLIC_MEASURES_DATABASE_ID = os.getenv("PUBLIC_MEASURES_DATABASE_ID")
ROBOTICS_CONSULTANCY_DATABASE_ID = os.getenv("ROBOTICS_CONSULTANCY_DATABASE_ID")
AIRE_PRE_ACCELERATOR_DATABASE_ID = os.getenv("AIRE_PRE_ACCELERATOR_DATABASE_ID")

# Keywords for filtering emails by subject
ESTONIAN_SUBJECT = os.getenv("ESTONIAN_SUBJECT")
ENGLISH_SUBJECT = os.getenv("ENGLISH_SUBJECT")

# Mapping of database IDs to responsible persons
DATABASE_RESPONSIBLES = {
    MAIN_DATABASE_ID: parse_emails("DATABASE_RESPONSIBLES_MAIN"),
    AI_CONSULTANCY_DATABASE_ID: parse_emails("DATABASE_RESPONSIBLES_AI"),
    PRIVATE_FUNDING_DATABASE_ID: parse_emails("DATABASE_RESPONSIBLES_PRIVATE"),
    PUBLIC_MEASURES_DATABASE_ID: parse_emails("DATABASE_RESPONSIBLES_PUBLIC"),
    ROBOTICS_CONSULTANCY_DATABASE_ID: parse_emails("DATABASE_RESPONSIBLES_ROBOTICS"),
    AIRE_PRE_ACCELERATOR_DATABASE_ID: parse_emails("DATABASE_RESPONSIBLES_PRE_ACCELERATOR"),
}

# Email address to always include in CC
CC_EMAIL = os.getenv("CC_EMAIL")

# Default recipients if no responsible persons are found
DEFAULT_RECIPIENTS = [email.strip() for email in os.getenv("DEFAULT_RECIPIENTS", "").split(',') if email.strip()]

# Service Configurations
SERVICE_CONFIG = {
    "Tehisintellekti otstarbekuse nõustamine": {
        "database_id": AI_CONSULTANCY_DATABASE_ID,
        "project_name_template": "{company_name} AI nõustamine {project_count}",
        "property_name": "Digiküpsuse hindamine"
    },
    "Finantseerimise nõustamine – Erakapitali kaasamine": {
        "database_id": PRIVATE_FUNDING_DATABASE_ID,
        "project_name_template": "{company_name} Erakapitali kaasamine {project_count}",
        "property_name": "Digiküpsuse hindamine"
    },
    "Finantseerimise nõustamine – Avalikud meetmed": {
        "database_id": PUBLIC_MEASURES_DATABASE_ID,
        "project_name_template": "{company_name} Avalikud meetmed {project_count}",
        "property_name": "Digiküpsuse hindamine"
    },
    "Robotiseerimise nõustamine": {
        "database_id": ROBOTICS_CONSULTANCY_DATABASE_ID,
        "project_name_template": "{company_name} Robotiseerimise nõustamine {project_count}",
        "property_name": "Digiküpsuse hindamine"
    },
    "AIRE eelkiirendi": {
        "database_id": AIRE_PRE_ACCELERATOR_DATABASE_ID,
        "project_name_template": "{company_name} AIRE eelkiirendi {project_count}",
        "property_name": "Digiküpsuse hindamine"
    },
}
