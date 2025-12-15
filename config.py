# config.py

import os
from dotenv import load_dotenv

load_dotenv()


def parse_emails(env_var):
    emails = os.getenv(env_var, "")
    return [email.strip() for email in emails.split(",") if email.strip()]


# === BASE CONFIG ===
IMAP_SERVER = os.getenv("IMAP_SERVER")
IMAP_PORT = int(os.getenv("IMAP_PORT", 993))
EMAIL = os.getenv("EMAIL")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
NOTION_API_KEY = os.getenv("NOTION_API_KEY")

# === MAIN DATABASES ===
MAIN_DATABASE_ID = os.getenv("MAIN_DATABASE_ID")  # Tehisintellekti üldnõustamine / AI help desk
RELATED_DATABASE_ID = os.getenv("RELATED_DATABASE_ID")
PEOPLE_DATABASE_ID = os.getenv("PEOPLE_DATABASE_ID")

# === SERVICE DATABASES ===
AI_CONSULTANCY_DATABASE_ID = os.getenv("AI_CONSULTANCY_DATABASE_ID")  # Tehisintellekti otstarbekuse nõustamine
PRIVATE_FUNDING_DATABASE_ID = os.getenv("PRIVATE_FUNDING_DATABASE_ID")  # Finantseerimise nõustamine – Erakapitali kaasamine
PUBLIC_MEASURES_DATABASE_ID = os.getenv("PUBLIC_MEASURES_DATABASE_ID")  # Finantseerimise nõustamine – Avalikud meetmed
MATCHMAKING_DATABASE_ID = os.getenv("MATCHMAKING_DATABASE_ID")  # Koostööpartnerite leidmine
AI_ACT_AWARENESS_DATABASE_ID = os.getenv("AI_ACT_AWARENESS_DATABASE_ID")  # TI määruse nõustamine ja usaldusväärne TI
EU_AI_ACCESS_DATABASE_ID = os.getenv("EU_AI_ACCESS_DATABASE_ID")  # Ligipääs EL'i tehisintellekti taristule


# === EMAIL SUBJECTS ===
ESTONIAN_SUBJECT = os.getenv("ESTONIAN_SUBJECT")
ENGLISH_SUBJECT = os.getenv("ENGLISH_SUBJECT")

# === RESPONSIBLES ===
DATABASE_RESPONSIBLES = {
    MAIN_DATABASE_ID: parse_emails("DATABASE_RESPONSIBLES_MAIN"),
    AI_CONSULTANCY_DATABASE_ID: parse_emails("DATABASE_RESPONSIBLES_AI"),
    PRIVATE_FUNDING_DATABASE_ID: parse_emails("DATABASE_RESPONSIBLES_PRIVATE"),
    PUBLIC_MEASURES_DATABASE_ID: parse_emails("DATABASE_RESPONSIBLES_PUBLIC"),
    MATCHMAKING_DATABASE_ID: parse_emails("DATABASE_RESPONSIBLES_MATCHMAKING"),
    AI_ACT_AWARENESS_DATABASE_ID: parse_emails("DATABASE_RESPONSIBLES_AI_ACT"),
    EU_AI_ACCESS_DATABASE_ID: parse_emails("DATABASE_RESPONSIBLES_EU_ACCESS"),
}

# === DEFAULT EMAILS ===
CC_EMAIL = os.getenv("CC_EMAIL")
DEFAULT_RECIPIENTS = [
    email.strip()
    for email in os.getenv("DEFAULT_RECIPIENTS", "").split(",")
    if email.strip()
]

# === SERVICE CONFIGURATION ===
SERVICE_CONFIG = {
    # --- AI suitability assessment ---
    "Tehisintellekti otstarbekuse nõustamine": {
        "database_id": AI_CONSULTANCY_DATABASE_ID,
        "project_name_template": "{company_name} AI otstarbekuse nõustamine {project_count}",
        "property_name": "TI üldnõustamine",
    },
    # --- Public funding support ---
    "Finantseerimise nõustamine – Avalikud meetmed": {
        "database_id": PUBLIC_MEASURES_DATABASE_ID,
        "project_name_template": "{company_name} Avalikud meetmed {project_count}",
        "property_name": "TI üldnõustamine",
    },
    # --- Private capital support ---
    "Finantseerimise nõustamine – Erakapitali kaasamine": {
        "database_id": PRIVATE_FUNDING_DATABASE_ID,
        "project_name_template": "{company_name} Erakapitali kaasamine {project_count}",
        "property_name": "TI üldnõustamine",
    },
    # --- Matchmaking ---
    "Koostööpartnerite leidmine": {
        "database_id": MATCHMAKING_DATABASE_ID,
        "project_name_template": "{company_name} Koostööpartnerite leidmine {project_count}",
        "property_name": "TI üldnõustamine",
    },
    # --- 🆕 AI Act awareness and responsible AI ---
    "TI määruse nõustamine ja usaldusväärne TI": {
        "database_id": AI_ACT_AWARENESS_DATABASE_ID,
        "project_name_template": "{company_name} TI määruse nõustamine ja usaldusväärne TI {project_count}",
        "property_name": "TI üldnõustamine",
    },
    # --- 🆕 Access to EU AI infrastructure ---
    "Ligipääs EL'i tehisintellekti taristule": {
        "database_id": EU_AI_ACCESS_DATABASE_ID,
        "project_name_template": "{company_name} Ligipääs EL'i tehisintellekti taristule {project_count}",
        "property_name": "TI üldnõustamine",
    },
}
