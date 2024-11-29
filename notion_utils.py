# notion_utils.py

import logging
import re
import requests
import unicodedata
from bs4 import BeautifulSoup
from datetime import datetime
from playwright.sync_api import sync_playwright
from notion_client import Client
from email_notification import send_error_email, send_success_email
from config import (
    NOTION_API_KEY,
    PEOPLE_DATABASE_ID,
    RELATED_DATABASE_ID,
    DATABASE_RESPONSIBLES,
    DEFAULT_RECIPIENTS,
    SERVICE_CONFIG,
    MAIN_DATABASE_ID,
)

# Initialize Notion client
notion = Client(auth=NOTION_API_KEY)

def normalize_text(text):
    return unicodedata.normalize('NFC', text)

def normalize_company_name(name):
    processed_name = name.strip()
    prefix_regex = re.compile(r'^(AS|OÜ|SAS|MTÜ)[\s\.-]*', re.IGNORECASE)
    patterns = [
        {'regex': re.compile(r'\baktsiaselts\b', re.IGNORECASE), 'replacement': 'AS'},
        {'regex': re.compile(r'\bosaühing\b', re.IGNORECASE), 'replacement': 'OÜ'},
        {'regex': re.compile(r'\bsihtasutus\b', re.IGNORECASE), 'replacement': 'SAS'},
        {'regex': re.compile(r'\bmittetulundusühing\b', re.IGNORECASE), 'replacement': 'MTÜ'},
        # Ensure abbreviations are uppercase
        {'regex': re.compile(r'\bAS\b', re.IGNORECASE), 'replacement': 'AS'},
        {'regex': re.compile(r'\bOÜ\b', re.IGNORECASE), 'replacement': 'OÜ'},
        {'regex': re.compile(r'\bSAS\b', re.IGNORECASE), 'replacement': 'SAS'},
        {'regex': re.compile(r'\bMTÜ\b', re.IGNORECASE), 'replacement': 'MTÜ'},
    ]

    suffix = ''
    prefix_match = prefix_regex.match(processed_name)
    if prefix_match:
        processed_name = prefix_regex.sub('', processed_name).strip()
        suffix = prefix_match.group(0).strip().upper()  

    for pattern in patterns:
        if pattern['regex'].search(processed_name):
            processed_name = pattern['regex'].sub('', processed_name).strip()
            suffix = pattern['replacement'].upper()  

    if suffix:
        processed_name = f"{processed_name} {suffix}"

    processed_name = processed_name.replace(',', '')
    return processed_name.strip()

# Function to get the database name
def get_database_name(database_id):
    try:
        response = notion.databases.retrieve(database_id=database_id)
        title = response.get('title', [])
        if title:
            database_name = ''.join([t['plain_text'] for t in title])
            return database_name
        else:
            return "Unnamed Database"
    except Exception as e:
        logging.error(f"Error retrieving database name: {e}")
        return "Unknown Database"

# Fetch all entries from a Notion database
def get_database_entries(database_id):
    try:
        entries = []
        next_cursor = None
        while True:
            logging.info(f"Fetching entries from database {database_id} with start_cursor={next_cursor}")
            response = notion.databases.query(database_id=database_id, start_cursor=next_cursor)
            results = response.get('results', [])
            entries.extend(results)
            logging.info(f"Fetched {len(results)} entries in this batch. Total entries so far: {len(entries)}")
            if not response.get('has_more'):
                logging.info("No more pages to fetch.")
                break
            next_cursor = response.get('next_cursor')
            logging.info(f"Next cursor set to: {next_cursor}")
        logging.info(f"Total entries fetched from database {database_id}: {len(entries)}")
        return entries
    except Exception as e:
        logging.error(f"Error fetching database entries: {e}", exc_info=True)
        return []

# Get database properties
def get_database_properties(database_id):
    try:
        response = notion.databases.retrieve(database_id=database_id)
        properties = response.get('properties', {})
        logging.info(f"Properties of database {database_id}: {list(properties.keys())}")
        return properties
    except Exception as e:
        logging.error(f"Error retrieving database properties: {e}", exc_info=True)
        return {}


# Find an entry in the database by registration code
def find_matching_entry_by_registry_code(registration_code, database_id, registry_code_property_name):
    logging.info(f"Searching for entry with {registry_code_property_name} = {registration_code} in database {database_id}")
    try:
        response = notion.databases.query(
            database_id=database_id,
            filter={
                "property": registry_code_property_name,
                "number": {
                    "equals": int(registration_code)
                }
            }
        )
        results = response.get('results', [])
        logging.info(f"Number of entries found: {len(results)}")
        if results:
            entry = results[0]
            logging.info(f"Found matching entry with ID: {entry['id']}")
            return entry
        else:
            logging.info(f"No matching entry found for {registry_code_property_name}: {registration_code}")
            return None
    except Exception as e:
        logging.error(f"Error querying database with filter: {e}", exc_info=True)
        return None


def create_new_entry_in_related_database(company_name, registration_code, related_database_id):
    logging.info(f"Creating new entry in related database for company: {company_name} with Registrikood: {registration_code}")
    try:
        properties = {
            "Company Name": {
                "title": [
                    {
                        "text": {
                            "content": company_name
                        }
                    }
                ]
            },
            "Registrikood": {
                "number": int(registration_code)
            },
        }
        response = notion.pages.create(
            parent={"database_id": related_database_id},
            properties=properties,
        )
        new_entry_id = response["id"]
        logging.info(f"Successfully created new entry with ID: {new_entry_id} in related database.")
        return new_entry_id
    except Exception as e:
        logging.error(f"Error creating new entry in related database: {e}", exc_info=True)
        return None




# Get the maximum value of 'Jrk' from the database (number field version)
def get_max_jrk_number(database_id):
    logging.info(f"Getting max Jrk number from database {database_id}")
    try:
        response = notion.databases.query(
            database_id=database_id,
            sorts=[{
                "property": "Jrk",
                "direction": "descending"
            }],
            page_size=1
        )
        results = response.get('results', [])
        if results:
            max_jrk = results[0]['properties']['Jrk']['number']
            logging.info(f"Max Jrk number value found: {max_jrk}")
            return max_jrk
        else:
            logging.info("No entries found in the database.")
            return 0
    except Exception as e:
        logging.error(f"Error getting max Jrk number: {e}", exc_info=True)
        return 0


# Add company information to the main database
def add_company_to_main_database(
    email_data, email_received_date, related_entry_id,
    service_counts, language, include_jrk=False
):
    database_id = MAIN_DATABASE_ID
    try:
        logging.info(f"Starting to add company '{email_data['company_name']}' to the main database.")
        logging.info(f"Email data received: {email_data}")
        logging.info(f"Related entry ID: {related_entry_id}")

        normalized_company_name = normalize_company_name(email_data['company_name'])
        logging.info(f"Normalized company name: {normalized_company_name}")

        location = get_location_from_registry_playwright(email_data["registration_code"])
        logging.info(f"Retrieved location: {location}")

        if location is None:
            raise ValueError("Invalid registry code or scraping error")

        max_jrk = get_max_jrk_number(database_id)
        logging.info(f"Max Jrk value in database: {max_jrk}")
        next_jrk = max_jrk + 1

        vta_result = check_vta_remnant(email_data["registration_code"])
        logging.info(f"VTA check result: {vta_result}")

        contact_name = email_data.get("participant_name", "")
        related_contact_id = None

        if contact_name:
            logging.info(f"Looking for contact name: {contact_name}")
            related_contact = find_matching_contact_by_name(contact_name, PEOPLE_DATABASE_ID)
            if related_contact:
                related_contact_id = related_contact["id"]
                logging.info(f"Found related contact ID: {related_contact_id}")
            else:
                logging.info(f"Creating new contact for name: {contact_name}")
                related_contact_id = create_new_contact_in_people_database(
                    name=contact_name,
                    email_address=email_data.get("email_address", ""),
                    phone_number=email_data.get("phone_number", ""),
                    organisation_id=related_entry_id,
                    people_database_id=PEOPLE_DATABASE_ID
                )
                logging.info(f"New contact created with ID: {related_contact_id}")

        existing_entry = find_matching_entry_by_registry_code(
            email_data["registration_code"], database_id, "Registrikood"
        )
        if existing_entry:
            logging.info(f"Company {normalized_company_name} already exists in the main database. Skipping creation.")
            return

        properties = {
            "Projekt": {
                "title": [
                    {
                        "text": {
                            "content": f"{normalized_company_name} DMA T0"
                        }
                    }
                ]
            },
            "Registrikood": {
                "number": int(email_data["registration_code"]) if email_data["registration_code"].isdigit() else None
            },
            "Tööstusharu": {
                "rich_text": [
                    {
                        "text": {
                            "content": email_data["industry"]
                        }
                    }
                ]
            },
            "Teenusele reg kpv": {
                "date": {
                    "start": email_received_date
                }
            },
            "Company Name": {
                "relation": [
                    {
                        "id": related_entry_id
                    }
                ]
            },
            "Property": {
                "select": {
                    "name": "T0"
                }
            },
            "Location": {
                "select": {
                    "name": location
                }
            },
            "VTA kontroll": {
                "rich_text": [
                    {
                        "text": {
                            "content": vta_result
                        }
                    }
                ]
            },
        }

        if related_contact_id:
            properties["Kontakt"] = {
                "relation": [
                    {
                        "id": related_contact_id
                    }
                ]
            }

        if include_jrk:
            properties["Jrk"] = {
                "number": next_jrk
            }

        logging.info(f"Final properties for new entry: {properties}")

        new_page = notion.pages.create(parent={"database_id": database_id}, properties=properties)
        logging.info(f"Successfully added company: {normalized_company_name} to the main database. Entry ID: {new_page['id']}")

        item_url = new_page.get('url', '')
        database_name = get_database_name(database_id)
        recipients = DATABASE_RESPONSIBLES.get(database_id, DEFAULT_RECIPIENTS)
        send_success_email(email_data["registration_code"], email_data, recipients, item_url, database_name)

    except Exception as e:
        error_message = f"Failed to add company {email_data['company_name']} to main database: {str(e)}"
        recipients = DATABASE_RESPONSIBLES.get(database_id, DEFAULT_RECIPIENTS)
        send_error_email(email_data["registration_code"], error_message, email_data, recipients)
        logging.error(f"Skipping company {email_data['company_name']} due to error: {error_message}")


# Retrieve the location (county) by registry code using Playwright
def get_location_from_registry_playwright(registry_code):
    url = f"https://ariregister.rik.ee/est/company/{registry_code}"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url)
            page.wait_for_selector('div.col-md-4.text-muted:has-text("Aadress")', timeout=10000)
            address_label = page.query_selector('div.col-md-4.text-muted:has-text("Aadress")')
            if address_label:
                address_element = page.evaluate(
                    "(element) => element.nextElementSibling.innerText", address_label
                )
                if address_element:
                    cleaned_address = address_element.split(" Ava kaart")[0]
                    location = match_location(cleaned_address)
                    return location
                else:
                    logging.error(f"Address element not found for registry code {registry_code}")
            else:
                logging.error(f"Aadress label not found for registry code {registry_code}")
        return None
    except Exception as e:
        logging.error(f"Failed to scrape location for registry code {registry_code}: {str(e)}")
        return None

# Check VTA remnant and return formatted result string
def check_vta_remnant(reg_code):
    url = f"https://rar.fin.ee/rar/DMAremnantPage.action?regCode={reg_code}&name=&method:input=Kontrolli%2Bj%C3%A4%C3%A4ki&op=Kontrolli+j%C3%A4%C3%A4ki&antibot_key=7sGg3EvZfMwcaN_T3r2vjjczukTKLWUaUV6JuMTvf6k"
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        title_blocks = soup.find_all("div", class_="title")
        remnant_count = 0
        current_date = datetime.now().strftime("%d.%m.%Y")
        for block in title_blocks:
            h3_tag = block.find("h3")
            if h3_tag and "VTA vaba jääk" in h3_tag.text:
                remnant_element = block.find("div", class_="title-addon")
                if remnant_element:
                    remnant = remnant_element.text.strip()
                    remnant_value = float(re.sub(r"[^\d.]", "", remnant))
                    remnant_count += 1
                    if remnant_count == 2:
                        result = (
                            f"ok({current_date} - {remnant})"
                            if remnant_value > 5000
                            else f"vähe({current_date} - {remnant})"
                        )
                        logging.info(f"VTA check result: {result}")
                        return result
        logging.warning(f"No VTA remnant found for reg code {reg_code}")
        return "VTA informatsiooni ei leitud"
    logging.error(f"Error fetching VTA data for reg code {reg_code}")
    return "Viga VTA andmete hankimisel"

# Match the address to a valid county
def match_location(address):
    valid_locations = {
        "Harju maakond": "Harjumaa",
        "Tartu maakond": "Tartumaa",
        "Lääne-Viru maakond": "Lääne-Virumaa",
        "Võru maakond": "Võrumaa",
        "Järva maakond": "Järvamaa",
        "Viljandi maakond": "Viljandimaa",
        "Saare maakond": "Saaremaa",
        "Hiiu maakond": "Hiiumaa",
        "Pärnu maakond": "Pärnumaa",
        "Rapla maakond": "Raplamaa",
        "Ida-Viru maakond": "Ida-Virumaa",
        "Jõgeva maakond": "Jõgevamaa",
        "Põlva maakond": "Põlvamaa",
        "Valga maakond": "Valgamaa",
        "Lääne maakond": "Läänemaa",
        "Haju maakond": "Hajumaa",
    }
    for key in valid_locations:
        if key in address:
            return valid_locations[key]
    return "Asukohta ei leitud"

# Find a contact in the "People" database by name
def find_matching_contact_by_name(name, database_id):
    logging.info(f"Searching for contact with Name = {name} in database {database_id}")
    try:
        response = notion.databases.query(
            database_id=database_id,
            filter={
                "property": "Name",
                "title": {
                    "equals": name
                }
            }
        )
        results = response.get('results', [])
        logging.info(f"Number of contacts found: {len(results)}")
        if results:
            entry = results[0]
            logging.info(f"Found matching contact with ID: {entry['id']}")
            return entry
        else:
            logging.info(f"No matching contact found for Name: {name}")
            return None
    except Exception as e:
        logging.error(f"Error querying database with filter: {e}", exc_info=True)
        return None



# Create a new contact in the "People" database if no match is found
def create_new_contact_in_people_database(name, email_address, phone_number, organisation_id, people_database_id):
    logging.info(f"Creating new contact in people database for name: {name}")
    try:
        properties = {
            "Name": {
                "title": [
                    {
                        "text": {
                            "content": name
                        }
                    }
                ]
            },
            "Email": {
                "email": email_address
            },
            "Phone": {
                "phone_number": phone_number
            },
            "Organisation": {
                "relation": [
                    {
                        "id": organisation_id
                    }
                ]
            }
        }
        response = notion.pages.create(
            parent={"database_id": people_database_id},
            properties=properties
        )
        new_contact_id = response["id"]
        logging.info(f"Created new contact for name {name} with ID {new_contact_id}")
        return new_contact_id
    except Exception as e:
        logging.error(f"Error creating new contact in people database: {e}", exc_info=True)
        return None


# Add new entries to additional databases based on service name and count
def add_project_to_additional_databases(service_name, email_data, count, email_received_date, recipients):
    service_config = SERVICE_CONFIG.get(service_name)
    if service_config:
        property_name_key = normalize_text(service_config["property_name"])
        database_id = service_config["database_id"]

        add_project(
            email_data,
            count,
            email_received_date,
            database_id=database_id,
            main_database_id=MAIN_DATABASE_ID,
            service_name=service_name,
            project_name_template=service_config["project_name_template"],
            property_name_key=property_name_key,
            recipients=recipients
        )
    else:
        logging.error(f"Service configuration not found for service: {service_name}")

def add_project(
    email_data, count, email_received_date, database_id, main_database_id,
    service_name, project_name_template, property_name_key, recipients
):
    database_properties = get_database_properties(database_id)

    normalized_properties = {normalize_text(k): k for k in database_properties.keys()}

    logging.info(f"Available properties in {service_name} database (normalized): {list(normalized_properties.keys())}")

    try:
        if property_name_key not in normalized_properties:
            logging.error(f"Property '{property_name_key}' does not exist in the {service_name} database.")
            return

        actual_property_name = normalized_properties[property_name_key]

        location = get_location_from_registry_playwright(email_data["registration_code"])

        if location is None:
            raise ValueError("Invalid registry code or scraping error")

        vta_result = check_vta_remnant(email_data["registration_code"])

        contact_name = email_data.get("participant_name", "")
        related_contact_id = None

        if contact_name:
            related_contact = find_matching_contact_by_name(contact_name, PEOPLE_DATABASE_ID)
            if related_contact:
                related_contact_id = related_contact["id"]
            else:
                related_contact_id = create_new_contact_in_people_database(
                    name=contact_name,
                    email_address=email_data.get("email_address", ""),
                    phone_number=email_data.get("phone_number", ""),
                    organisation_id=None,  # Update if necessary
                    people_database_id=PEOPLE_DATABASE_ID
                )

        max_jrk = get_max_jrk_number(database_id)
        next_jrk = max_jrk + 1  

        related_entry = find_matching_entry_by_registry_code(
            email_data["registration_code"], RELATED_DATABASE_ID, "Registrikood"
        )
        if related_entry:
            related_entry_id = related_entry["id"]
        else:
            related_entry_id = create_new_entry_in_related_database(
                email_data["company_name"],
                email_data["registration_code"],
                RELATED_DATABASE_ID,
            )

        main_entry = find_matching_entry_by_registry_code(
            email_data["registration_code"], main_database_id, "Registrikood"
        )

        if main_entry:
            main_entry_id = main_entry["id"]
            logging.info(f"Company {email_data['company_name']} exists in the main database.")
        else:
            logging.info(f"Company {email_data['company_name']} does not exist in the main database. Creating new entry.")
            add_company_to_main_database(
                email_data,
                email_received_date,
                related_entry_id,
                service_counts={}, 
                language='et',  
                include_jrk=True  
            )
            main_entry = find_matching_entry_by_registry_code(
                email_data["registration_code"], main_database_id, "Registrikood"
            )
            main_entry_id = main_entry["id"] if main_entry else None

        if main_entry_id is None:
            logging.error("main_entry_id is None. Cannot establish relation.")
            return

        normalized_company_name = normalize_company_name(email_data['company_name'])

        project_count = count_company_entries_in_database(database_id, related_entry_id)

        item_urls = []  

        for _ in range(count):
            try:
                project_name = project_name_template.format(
                    company_name=normalized_company_name,
                    project_count=project_count + 1
                )

                properties = {
                    "Projekt": {
                        "title": [
                            {
                                "text": {
                                    "content": project_name
                                }
                            }
                        ]
                    },
                    "VTA kontroll": {
                        "rich_text": [
                            {
                                "text": {
                                    "content": vta_result
                                }
                            }
                        ]
                    },
                    "Teenusele reg kpv": {
                        "date": {
                            "start": email_received_date
                        }
                    },
                    "Jrk": {
                        "number": next_jrk
                    },
                    "Company Name": {
                        "relation": [
                            {
                                "id": related_entry_id
                            }
                        ]
                    },
                    actual_property_name: {
                        "relation": [
                            {
                                "id": main_entry_id
                            }
                        ]
                    },
                }

                if related_contact_id:
                    logging.info(f"Linking contact {contact_name} with ID {related_contact_id} to the project.")
                    properties["Kontakt"] = {
                        "relation": [
                            {
                                "id": related_contact_id
                            }
                        ]
                    }

                new_page = notion.pages.create(parent={"database_id": database_id}, properties=properties)
                logging.info(
                    f"Added '{service_name}' project for {normalized_company_name} with Jrk {next_jrk}."
                )

                item_url = new_page.get('url', '')
                item_urls.append(item_url)

                next_jrk += 1  
                project_count += 1 

            except Exception as e:
                logging.error(f"Error adding to '{service_name}' database: {e}")

        if item_urls:
            item_urls_text = '\n'.join(item_urls)
            database_name = get_database_name(database_id)
            send_success_email(email_data["registration_code"], email_data, recipients, item_urls_text, database_name)

    except Exception as e:
        error_message = f"Failed to process company {email_data['company_name']}: {str(e)}"
        if not recipients:
            recipients = DEFAULT_RECIPIENTS
        send_error_email(email_data["registration_code"], error_message, email_data, recipients)
        logging.error(f"Skipping project for company {email_data['company_name']} due to error: {error_message}")

# Count how many times this related_entry_id is present in the given database
def count_company_entries_in_database(database_id, related_entry_id):
    logging.info(f"Counting entries for related_entry_id {related_entry_id} in database {database_id}")
    try:
        filter_params = {
            "property": "Company Name",
            "relation": {
                "contains": related_entry_id
            }
        }
        response = notion.databases.query(
            database_id=database_id,
            filter=filter_params
        )
        total_entries = len(response.get('results', []))
        logging.info(f"Total entries found: {total_entries}")
        return total_entries
    except Exception as e:
        logging.error(f"Error counting company entries in database: {e}", exc_info=True)
        return 0

