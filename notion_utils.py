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

# ----------------------------------------------------------------------
# INIT
# ----------------------------------------------------------------------
notion = Client(auth=NOTION_API_KEY)

def query_all_pages(database_id: str, **kwargs):
    """
    Fetches ALL pages from a Notion database using automatic pagination.
    Keeps fetching until 'has_more' is False.
    Example:
        results = query_all_pages(database_id, filter=my_filter)
    """
    all_results = []
    has_more = True
    next_cursor = None

    while has_more:
        if next_cursor:
            kwargs["start_cursor"] = next_cursor

        try:
            response = notion.databases.query(database_id=database_id, **kwargs)
        except Exception as e:
            logging.error(f"Pagination query failed for DB {database_id}: {e}", exc_info=True)
            break

        results = response.get("results", [])
        all_results.extend(results)

        has_more = response.get("has_more", False)
        next_cursor = response.get("next_cursor")

        logging.info(f"📄 Retrieved {len(results)} entries (total: {len(all_results)}) from DB {database_id}")

    logging.info(f"✅ Pagination finished. Total records fetched: {len(all_results)} from DB {database_id}")
    return all_results
# ----------------------------------------------------------------------
# BASIC HELPERS
# ----------------------------------------------------------------------
def normalize_text(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")


def normalize_company_name(name: str) -> str:
    """Normalizing the company name: move prefix/suffix like AS/OÜ/... to the end, clean spaces and symbols."""
    if not name:
        return ""
    name = name.strip()
    prefix_regex = re.compile(r"^(AS|OÜ|SAS|MTÜ)[\s\.-]*", re.IGNORECASE)
    patterns = [
        {"regex": re.compile(r"\baktsiaselts\b", re.IGNORECASE), "replacement": "AS"},
        {"regex": re.compile(r"\bosaühing\b", re.IGNORECASE), "replacement": "OÜ"},
        {"regex": re.compile(r"\bsihtasutus\b", re.IGNORECASE), "replacement": "SAS"},
        {"regex": re.compile(r"\bmittetulundusühing\b", re.IGNORECASE), "replacement": "MTÜ"},
    ]
    suffix = ""
    prefix_match = prefix_regex.match(name)
    if prefix_match:
        name = prefix_regex.sub("", name).strip()
        suffix = prefix_match.group(0).strip().upper()

    for pattern in patterns:
        if pattern["regex"].search(name):
            name = pattern["regex"].sub("", name).strip()
            suffix = pattern["replacement"].upper()

    if suffix:
        name = f"{name} {suffix}"
    return name.replace(",", "").strip()


def get_database_name(database_id: str) -> str:
    try:
        r = notion.databases.retrieve(database_id=database_id)
        return "".join([t["plain_text"] for t in r.get("title", [])]) or "Unnamed"
    except Exception as e:
        logging.error(f"Error retrieving database name: {e}")
        return "Unknown"


def get_database_properties(database_id: str) -> dict:
    try:
        r = notion.databases.retrieve(database_id=database_id)
        props = r.get("properties", {})
        logging.info(f"Properties of database {database_id}: {list(props.keys())}")
        return props
    except Exception as e:
        logging.error(f"Error retrieving DB properties: {e}")
        return {}


def get_recipients_for_db(database_id: str):
    """Returns a list of email addresses for notifications (supports both string and list formats in config)."""
    recipients = DATABASE_RESPONSIBLES.get(database_id, DEFAULT_RECIPIENTS)
    if isinstance(recipients, str):
        recipients = [r.strip() for r in recipients.split(",") if r.strip()]
    return recipients


def is_estonian_company(email_data: dict) -> bool:
    origin = (email_data.get("company_origin") or "") + " " + (email_data.get("industry") or "")
    return "eesti" in origin.strip().lower() or "estonian" in origin.strip().lower()


# ----------------------------------------------------------------------
# VALIDATION (Äriregister)
# ----------------------------------------------------------------------
def validate_estonian_company(email_data: dict) -> bool:
    """
    For Estonian companies:
      - Check if the Äriregister page exists.
      - If not, send an error email and stop further processing.
    For foreign companies: return True.
    """
    if not is_estonian_company(email_data):
        logging.info("🌍 Foreign company — skipping Äriregister/VTA checks.")
        return True

    reg_code = (email_data.get("registration_code") or "").strip()
    company_name = email_data.get("company_name") or ""

    # --- Missing Registrikood ---
    if not reg_code or not reg_code.isdigit():
        msg = f"❌ Invalid or missing Registrikood for '{company_name}'. Got: '{reg_code}'"
        logging.error(msg)
        recipients = get_recipients_for_db(MAIN_DATABASE_ID)
        send_error_email(reg_code, msg, email_data, recipients)
        raise ValueError(msg)  

    try:
        url = f"https://ariregister.rik.ee/est/company/{reg_code}"
        resp = requests.get(url, timeout=12)

        if resp.status_code == 404 or any(x in resp.text for x in ["Vabandame", "Ei leitud", "not found"]):
            msg = f"❌ Registration code {reg_code} not found in Äriregister for '{company_name}'."
            logging.error(msg)
            recipients = get_recipients_for_db(MAIN_DATABASE_ID)
            send_error_email(reg_code, msg, email_data, recipients)
            raise ValueError(msg)

        logging.info(f"✅ Äriregister check passed for {company_name} ({reg_code})")
        return True

    except Exception as e:
        msg = f"⚠️ Äriregister validation failed for {reg_code}: {e}"
        logging.error(msg)
        recipients = get_recipients_for_db(MAIN_DATABASE_ID)
        send_error_email(reg_code, msg, email_data, recipients)
        raise ValueError(msg)



# ----------------------------------------------------------------------
# SEARCH
# ----------------------------------------------------------------------
def find_matching_entry_by_registry_code(registration_code: str, database_id: str, property_name: str):
    """Smart search by registration code; supports both rollup and number property types"""
    logging.info(f"Searching for entry with {property_name} = {registration_code} in DB {database_id}")
    try:
        db = notion.databases.retrieve(database_id=database_id)
        props = db.get("properties", {})
        if property_name not in props:
            raise ValueError(f"Property '{property_name}' not found in DB {database_id}")
        p_type = props[property_name].get("type")

        if p_type == "number":
            notion_filter = {"property": property_name, "number": {"equals": int(registration_code)}}
        elif p_type == "rollup":
            notion_filter = {"property": property_name, "rollup": {"any": {"number": {"equals": int(registration_code)}}}}
        else:
            notion_filter = {"property": property_name, "rich_text": {"equals": str(registration_code)}}

        results = query_all_pages(database_id, filter=notion_filter)
        logging.info(f"Found {len(results)} entries in {database_id}")
        return results[0] if results else None
    except Exception as e:
        logging.error(f"Error querying DB: {e}", exc_info=True)
        return None


def find_matching_contact_by_name(name: str, db_id: str):
    if not name:
        return None
    try:
        r = notion.databases.query(
            database_id=db_id,
            filter={"property": "Name", "title": {"equals": name}},
        )
        res = r.get("results", [])
        return res[0] if res else None
    except Exception as e:
        logging.error(f"Error finding contact: {e}")
        return None


# ----------------------------------------------------------------------
# UTILS
# ----------------------------------------------------------------------
def get_actual_property_name(db_id: str, candidates) -> str | None:
    """Finds the actual property name while ignoring case, spaces, and similar variations"""
    props = get_database_properties(db_id)
    normalized = {k.strip().lower(): k for k in props.keys()}
    for c in candidates:
        if c.strip().lower() in normalized:
            return normalized[c.strip().lower()]
    return None


def get_max_jrk_number(db_id: str) -> int:
    """Global maximum Jrk value in the database (used as a fallback)"""
    try:
        r = notion.databases.query(
            database_id=db_id,
            sorts=[{"property": "Jrk", "direction": "descending"}],
            page_size=1,
        )
        res = r.get("results", [])
        if not res:
            return 0
        val = res[0]["properties"].get("Jrk", {}).get("number")
        return val or 0
    except Exception as e:
        logging.error(f"Error getting Jrk: {e}")
        return 0


def get_company_local_jrk_start(database_id: str, related_company_id: str) -> int:
    """
    Finds the next Jrk value within the database for a specific company (local maximum),
    so that numbering remains sequential for each company, not globally.
    """
    try:
        results = query_all_pages(
            database_id,
            filter={"property": "Company Name", "relation": {"contains": related_company_id}},
            sorts=[{"property": "Jrk", "direction": "descending"}],
        )
        if not results:
            return get_max_jrk_number(database_id) + 1
        last = results[0]["properties"].get("Jrk", {}).get("number") or 0
        return int(last) + 1
    except Exception as e:
        logging.error(f"Error getting local Jrk for company {related_company_id}: {e}")
        return get_max_jrk_number(database_id) + 1


def get_next_project_index_for_company(database_id: str, related_company_id: str, service_name: str, company_clean: str) -> int:
    """
    Determines the next sequential number for the “Project” field (in the title),
    considering already created projects for THIS company in THIS service database.
    Projects are counted using the pattern: "{company_clean} {service_name} {N}".
    """
    try:
        results = query_all_pages(
            database_id,
            filter={"property": "Company Name", "relation": {"contains": related_company_id}},
        )

        prefix = f"{company_clean} {service_name}".strip()
        max_n = 0
        for page in results:
            title_fragments = page["properties"]["Project"]["title"]
            title = "".join([t["plain_text"] for t in title_fragments]) if title_fragments else ""
            if title.startswith(prefix):
                m = re.search(rf"^{re.escape(prefix)}\s+(\d+)\s*$", title)
                if m:
                    try:
                        n = int(m.group(1))
                        max_n = max(max_n, n)
                    except:
                        pass
        return max_n + 1
    except Exception as e:
        logging.error(f"Error computing next Project index: {e}")
        return 1


# ----------------------------------------------------------------------
# CONTACTS
# ----------------------------------------------------------------------
def link_contact_to_company(contact_id: str, company_page_id: str):
    try:
        c = notion.pages.retrieve(contact_id)
        rel = c["properties"].get("Organisation", {}).get("relation", [])
        if any(r.get("id") == company_page_id for r in rel):
            return
        rel += [{"id": company_page_id}]
        notion.pages.update(page_id=contact_id, properties={"Organisation": {"relation": rel}})
        logging.info(f"Linked contact {contact_id} to company {company_page_id}")
    except Exception as e:
        logging.error(f"Error linking contact: {e}")


def create_new_contact_in_people_database(name: str, email: str, phone: str, org_id: str | None, db_id: str) -> str | None:
    """Creates a contact and, if org_id is provided, links it to the corresponding company."""
    try:
        logging.info(f"👤 Creating new contact: {name}")
        props = {
            "Name": {"title": [{"text": {"content": name or ""}}]},
            "Email": {"email": email or ""},
            "Phone": {"phone_number": phone or ""},
        }
        if org_id:
            props["Organisation"] = {"relation": [{"id": org_id}]}
            logging.info(f"✅ Added Organisation relation → {org_id}")

        res = notion.pages.create(parent={"database_id": db_id}, properties=props)
        new_contact_id = res["id"]
        logging.info(f"✅ Created new contact '{name}' with ID: {new_contact_id}")

        if org_id:
            try:
                link_contact_to_company(new_contact_id, org_id)
                logging.info(f"🔗 Linked contact {new_contact_id} <-> company {org_id}")
            except Exception as link_err:
                logging.warning(f"⚠️ Could not double-link contact {new_contact_id} to company {org_id}: {link_err}")

        return new_contact_id
    except Exception as e:
        logging.error(f"❌ Error creating contact '{name}': {e}", exc_info=True)
        return None


# ----------------------------------------------------------------------
# LOCATION + VTA (scraping/matching)
# ----------------------------------------------------------------------
def get_location_from_registry_playwright(registry_code: str) -> str | None:
    url = f"https://ariregister.rik.ee/est/company/{registry_code}"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url)
            page.wait_for_selector('div.col-md-4.text-muted:has-text("Aadress")', timeout=8000)
            addr = page.query_selector('div.col-md-4.text-muted:has-text("Aadress")')
            if addr:
                addr_val = page.evaluate("(e)=>e.nextElementSibling.innerText", addr)
                if addr_val:
                    clean = addr_val.split(" Ava kaart")[0]
                    return match_location(clean)
        return None
    except Exception as e:
        logging.error(f"Scrape location fail {registry_code}: {e}")
        return None


def match_location(address: str) -> str:
    """
    Maps the raw 'Aadress' string to a known county name (maakond).
    Handles case differences, extra spaces, and punctuation.
    """
    if not address:
        return "Location not found"

    normalized = address.lower().replace(",", " ").replace("  ", " ").strip()

    valid_locations = {
        "harju maakond": "Harjumaa",
        "tartu maakond": "Tartumaa",
        "lääne-viru maakond": "Lääne-Virumaa",
        "võru maakond": "Võrumaa",
        "järva maakond": "Järvamaa",
        "viljandi maakond": "Viljandimaa",
        "saare maakond": "Saaremaa",
        "hiiu maakond": "Hiiumaa",
        "pärnu maakond": "Pärnumaa",
        "rapla maakond": "Raplamaa",
        "ida-viru maakond": "Ida-Virumaa",
        "jõgeva maakond": "Jõgevamaa",
        "põlva maakond": "Põlvamaa",
        "valga maakond": "Valgamaa",
        "lääne maakond": "Läänemaa",
    }

    for key, short in valid_locations.items():
        if key in normalized:
            return short

    return "Location not found"


def check_vta_remnant(reg_code: str) -> str:
    """
    Checks the VTA (de minimis) information on rar.fin.ee for the given registration code.
    Returns a string like "ok(DD.MM.YYYY - 205 544.07 EUR)" / "low(...)" / or an error message
    """
    url = f"https://rar.fin.ee/rar/DMAremnantPage.action?regCode={reg_code}&name=&method:input=Kontrolli%2Bj%C3%A4%C3%A4ki&op=Kontrolli+j%C3%A4%C3%A4ki&antibot_key=7sGg3EvZfMwcaN_T3r2vjjczukTKLWUaUV6JuMTvf6k"
    try:
        response = requests.get(url, timeout=12)
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
                        numeric = re.sub(r"[^\d.]", "", remnant)
                        try:
                            remnant_value = float(numeric)
                        except:
                            remnant_value = 0.0
                        remnant_count += 1
                        if remnant_count == 2:
                            result = (
                                f"ok({current_date} - {remnant})"
                                if remnant_value > 5000
                                else f"low({current_date} - {remnant})"
                            )
                            logging.info(f"VTA check result: {result}")
                            return result
            logging.warning(f"No VTA remnant found for reg code {reg_code}")
            return "No VTA information found"
        logging.error(f"Error fetching VTA data for reg code {reg_code}: HTTP {response.status_code}")
        return "Error retrieving VTA data"
    except Exception as e:
        logging.error(f"VTA check request failed: {e}")
        return "Error retrieving VTA data"


def scrape_ariregister_data_sync(registry_code: str) -> dict:
    """
    Synchronously scrapes extended info from ariregister.rik.ee using Playwright.
    Returns:
        {
          'main_activity': str,
          'main_emtak_code': str,
          'employees_count': int | str | None,
          'address': str | None,
          'location': str | None
        }
    """
    url = f"https://ariregister.rik.ee/est/company/{registry_code}"
    data = {
        'main_activity': None,
        'main_emtak_code': None,
        'employees_count': None,
        'address': None,
        'location': None,
    }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=15000)

            # --- Main activity & EMTAK ---
            try:
                main_activity_row = page.locator('#areas-of-activity-table tbody tr').filter(has_text="Põhitegevusala")
                if main_activity_row.count() > 0:
                    try:
                        data['main_activity'] = main_activity_row.locator('td.activity-text a').inner_text().strip()
                    except:
                        pass
                    try:
                        data['main_emtak_code'] = main_activity_row.locator('td.text-nowrap.px-1').inner_text().strip()
                    except:
                        pass
                    if data['main_activity']:
                        logging.info(f"✅ Main activity found: {data['main_activity']}")
                    if data['main_emtak_code']:
                        logging.info(f"✅ EMTAK found: {data['main_emtak_code']}")
                else:
                    logging.warning("⚠️ No main activity row found.")
            except Exception as e:
                logging.warning(f"⚠️ Error while parsing main activity: {e}")

            # --- Employees count ---
            try:
                logging.info("🔍 Searching for 'Töötajate arv' block...")
                page.wait_for_selector('div.pt-3.mt-5', timeout=10000)

                employees_label = page.query_selector('div.pt-3.mt-5 div.text-muted:has-text("Töötajate arv")')
                if employees_label:
                    employees_value = page.evaluate('(el) => el.nextElementSibling?.innerText', employees_label)
                    if employees_value:
                        employees_value = employees_value.replace('\xa0', '').strip()
                        try:
                            data['employees_count'] = int(employees_value)
                        except ValueError:
                            data['employees_count'] = employees_value
                        logging.info(f"✅ Employees found: {data['employees_count']}")
                    else:
                        logging.warning("⚠️ Employees value not found next to label.")
                else:
                    logging.warning("⚠️ Employees label not found inside 'pt-3 mt-5' section.")
            except Exception as e:
                logging.warning(f"⚠️ Employees count not found: {e}")


            # --- Address ---
            try:
                address_label = page.query_selector('div.col-md-4.text-muted:has-text("Aadress")')
                if address_label:
                    address_value = page.evaluate('(el) => el.nextElementSibling?.innerText', address_label)
                    if address_value:
                        cleaned = address_value.split("Ava kaart")[0].strip()
                        data['address'] = cleaned
                        data['location'] = match_location(cleaned)
                        logging.info(f"✅ Address found: {cleaned}")
                    else:
                        logging.warning("⚠️ Address value not found next to label.")
                else:
                    logging.warning("⚠️ Aadress label not found.")
            except Exception as e:
                logging.error(f"Error extracting address for {registry_code}: {e}")

            browser.close()

    except Exception as e:
        logging.error(f"❌ scrape_ariregister_data_sync() failed for {registry_code}: {e}", exc_info=True)

    return data




# ----------------------------------------------------------------------
# MAIN CREATION
# ----------------------------------------------------------------------
def add_company_to_main_database(email_data: dict, email_date: str, related_entry_id: str,
                                 service_counts: dict, language: str, include_jrk: bool = False):
    """
    Creates a main record (Main DB) only if:
        – the company is foreign (validation skipped), or
        – the company is Estonian and passed the Äriregister check.
    Sends a success email to the recipients responsible for MAIN_DATABASE_ID.
    """
    db_id = MAIN_DATABASE_ID
    main_entry_id = None
    try:
        if not validate_estonian_company(email_data):
            logging.warning("⛔ Main DB creation blocked by Äriregister validation.")
            return None

        cname = normalize_company_name(email_data.get("company_name") or "")
        max_jrk = get_max_jrk_number(db_id)
        next_jrk = (max_jrk or 0) + 1
        logging.info(f"Next Jrk: {next_jrk}")

        contact_id = None
        if email_data.get("participant_name"):
            existing = find_matching_contact_by_name(email_data["participant_name"], PEOPLE_DATABASE_ID)
            if existing:
                contact_id = existing["id"]
                if related_entry_id:
                    link_contact_to_company(contact_id, related_entry_id)
            else:
                contact_id = create_new_contact_in_people_database(
                    email_data["participant_name"],
                    email_data.get("email_address", ""),
                    email_data.get("phone_number", ""),
                    related_entry_id,
                    PEOPLE_DATABASE_ID,
                )

        existing = find_matching_entry_by_registry_code(
            email_data.get("registration_code", ""), db_id, "Registration number"
        )
        if existing:
            logging.info(f"{cname} already exists in Main DB, skipping.")
            return existing["id"]

        project_prop = get_actual_property_name(db_id, ["Project", "Projekt"])
        date_prop = get_actual_property_name(db_id, ["Teenusele reg kpv", "Registration date"])
        company_rel_prop = get_actual_property_name(db_id, ["Company Name"])
        vta_prop = get_actual_property_name(db_id, ["VTA kontroll"])
        contact_prop = get_actual_property_name(db_id, ["Contact"])
        jrk_prop = get_actual_property_name(db_id, ["Jrk"])
        service_desc_prop = get_actual_property_name(db_id, ["Service need desctiprion", "Service need description"])
        regnum_prop = get_actual_property_name(db_id, ["Registration number"])

        props = {}

        # --- ✅ ALWAYS Tehisintellekti esmanõustamine with numbering ---
        if project_prop:
            existing_related = find_matching_entry_by_registry_code(
                email_data.get("registration_code", ""), RELATED_DATABASE_ID, "Registrikood"
            )
            related_id = existing_related["id"] if existing_related else None

            next_project_index = get_next_project_index_for_company(
                MAIN_DATABASE_ID, related_id, "Tehisintellekti esmanõustamine", cname
            )

            project_title = f"{cname} Tehisintellekti esmanõustamine {next_project_index}"
            props[project_prop] = {"title": [{"text": {"content": project_title}}]}
            logging.info(f"🧩 Project name generated: {project_title}")

        if date_prop and email_date:
            props[date_prop] = {"date": {"start": email_date}}
        if company_rel_prop and related_entry_id:
            props[company_rel_prop] = {"relation": [{"id": related_entry_id}]}
        if regnum_prop and email_data.get("registration_code"):
            try:
                props[regnum_prop] = {"rich_text": [{"text": {"content": str(email_data['registration_code'])}}]}
            except Exception:
                pass

        if is_estonian_company(email_data):
            vta = check_vta_remnant(email_data.get("registration_code", ""))
            if vta_prop:
                props[vta_prop] = {"rich_text": [{"text": {"content": vta}}]}
        else:
            if vta_prop:
                props[vta_prop] = {"rich_text": [{"text": {"content": "N/A (foreign)"}}]}

        helpdesk_text = email_data.get("helpdesk_topics", "").strip()
        if service_desc_prop and helpdesk_text:
            # Skip if it's just confirmations / legal text
            if helpdesk_text.lower().startswith(("kinnitused", "confirmations", "olen teadlik", "i am aware")):
                logging.info("ℹ️ Skipping helpdesk_topics — detected confirmation text.")
            else:
                props[service_desc_prop] = {
                    "rich_text": [{"text": {"content": helpdesk_text[:2000]}}]
                }

        if include_jrk and jrk_prop:
            props[jrk_prop] = {"number": next_jrk}
        if contact_id and contact_prop:
            props[contact_prop] = {"relation": [{"id": contact_id}]}

        logging.info(f"Creating Main entry props: {props}")
        new_page = notion.pages.create(parent={"database_id": db_id}, properties=props)
        main_entry_id = new_page["id"]
        logging.info(f"✅ Created Main entry for {cname}: {main_entry_id}")

        try:
            item_url = new_page.get("url", "")
            db_name = get_database_name(db_id)
            recipients = get_recipients_for_db(db_id)
            send_success_email(email_data.get("registration_code", ""), email_data, recipients, item_url, db_name)
        except Exception as email_err:
            logging.error(f"Failed to send main DB success email: {email_err}")

        return main_entry_id

    except Exception as e:
        msg = f"Failed to add {email_data.get('company_name','(no name)')}: {e}"
        recipients = get_recipients_for_db(db_id)
        send_error_email(email_data.get("registration_code",""), msg, email_data, recipients)
        logging.error(msg, exc_info=True)
        return None



# ----------------------------------------------------------------------
# RELATED (ORG) CREATION
# ----------------------------------------------------------------------
def create_new_entry_in_related_database(
    company_name: str,
    registration_code: str,
    related_database_id: str,
    email_data: dict | None = None
) -> str | None:
    """
    Creates an entry in the 'Related' (organizations) database.
    If Äriregister validation fails or returns empty data:
      - Sends an error email.
      - Stops the entire processing chain (no Notion entry creation).
    """
    logging.info(f"Creating new entry in Related DB for company: {company_name} ({registration_code})")

    try:
        # === 1. Äriregister validation ===
        if email_data:
            try:
                # Validate Estonian company before proceeding
                if not validate_estonian_company(email_data):
                    msg = f"⛔ Related DB creation blocked: invalid registration code ({registration_code})."
                    logging.warning(msg)
                    recipients = get_recipients_for_db(RELATED_DATABASE_ID)
                    send_error_email(registration_code, msg, email_data, recipients)
                    raise ValueError(msg)  # ❗ Stop chain execution
            except ValueError as e:
                recipients = get_recipients_for_db(RELATED_DATABASE_ID)
                send_error_email(registration_code, str(e), email_data, recipients)
                logging.error(f"Validation error: {e}")
                raise  # ❗ Raise again to stop execution

        # === 2. Base Notion properties ===
        properties = {
            "Company Name": {"title": [{"text": {"content": company_name}}]},
        }
        if registration_code and registration_code.isdigit():
            properties["Registrikood"] = {"number": int(registration_code)}

        if email_data:
            if email_data.get("company_origin"):
                properties["Company origin"] = {"select": {"name": email_data["company_origin"]}}
            if email_data.get("industry"):
                properties["Sektor"] = {"select": {"name": email_data["industry"]}}

        # === 3. Extended Äriregister data ===
        if email_data and is_estonian_company(email_data):
            ext = scrape_ariregister_data_sync(registration_code)

            # 🔴 If Äriregister returns nothing (timeout / invalid code / missing data)
            if not any(ext.values()):
                msg = f"⚠️ Äriregister returned empty data for {registration_code}"
                logging.error(f"{msg} — stopping execution.")
                recipients = get_recipients_for_db(RELATED_DATABASE_ID)
                send_error_email(registration_code, msg, email_data, recipients)
                raise ValueError(msg)  # ❗ Critical: stop execution completely

            # Otherwise, map the extracted data
            if ext.get("location"):
                properties["Location"] = {"select": {"name": ext["location"]}}
            if ext.get("main_activity"):
                properties["Main field of activity"] = {
                    "rich_text": [{"text": {"content": ext["main_activity"]}}]
                }
            if ext.get("main_emtak_code"):
                properties["EMTAK"] = {"multi_select": [{"name": ext["main_emtak_code"]}]}
            if ext.get("employees_count") is not None:
                try:
                    properties["Employees"] = {"number": int(ext["employees_count"])}
                except Exception:
                    pass

        # === 4. Create entry in Notion ===
        logging.info(f"Final Notion properties for Related DB: {properties}")
        response = notion.pages.create(
            parent={"database_id": related_database_id},
            properties=properties
        )
        new_entry_id = response["id"]
        logging.info(f"✅ Created new Related entry {company_name} ({registration_code}) → {new_entry_id}")
        return new_entry_id

    except Exception as e:
        # 🔴 Catch-all: send error email and stop
        logging.error(f"❌ Error creating new entry in Related DB: {e}", exc_info=True)
        recipients = get_recipients_for_db(RELATED_DATABASE_ID)
        send_error_email(
            registration_code,
            f"Related DB creation failed: {e}",
            email_data or {},
            recipients
        )
        return None



# ----------------------------------------------------------------------
# PROJECT DISTRIBUTION
# ----------------------------------------------------------------------
def add_project_to_additional_databases(service_name: str, email_data: dict, count: int,
                                        email_received_date: str, recipients, main_entry_id: str | None):
    """
    For the given service, creates entries in the corresponding databases (based on SERVICE_CONFIG).
    """
    try:
        logging.info(f"➡️ add_project_to_additional_databases() started for {service_name}")
        service_cfg = SERVICE_CONFIG.get(service_name)
        if not service_cfg:
            logging.error(f"❌ Service configuration not found for service: {service_name}")
            return

        property_name_key = normalize_text(service_cfg["property_name"])
        database_id = service_cfg["database_id"]
        project_name_template = service_cfg.get("project_name_template", "{company_name} {service_name} {project_count}")

        add_project(
            email_data=email_data,
            count=count,
            email_received_date=email_received_date,
            database_id=database_id,
            main_entry_id=main_entry_id,
            service_name=service_name,
            project_name_template=project_name_template,
            property_name_key=property_name_key,
            recipients=recipients,
        )

    except Exception as e:
        logging.error(f"❌ Error in add_project_to_additional_databases for {service_name}: {e}", exc_info=True)


def add_project(
    email_data: dict,
    count: int,
    email_received_date: str,
    database_id: str,
    main_entry_id: str | None,
    service_name: str,
    project_name_template: str,
    property_name_key: str,
    recipients,
):
    """
    Creates one or more projects in a specific service database.
    Logic:
        – if the company is Estonian and fails Äriregister validation → exit and send an error
        – “Project” titles are numbered sequentially per company in this database
        – Jrk is calculated locally per company (fallbacks to global if not available)
        – for foreign companies, skip VTA/location and set "N/A (foreign)"
        – after each successful creation, send a success email to the recipients of this database.
    """
    try:
        logging.info(f"🧩 add_project() started for {service_name}")
        logging.info(f"📎 main_entry_id = {main_entry_id}")
        logging.info(f"📦 Email data received: {email_data}")

        if not validate_estonian_company(email_data):
            msg = f"Project creation blocked: Äriregister validation failed for {email_data.get('company_name')}"
            logging.warning(msg)
            recipients = get_recipients_for_db(database_id)
            send_error_email(email_data.get("registration_code", ""), msg, email_data, recipients)
            return

        db_props = get_database_properties(database_id)
        normalized = {normalize_text(k): k for k in db_props.keys()}
        if property_name_key not in normalized:
            logging.error(f"❌ Property '{property_name_key}' not found in {service_name} DB.")
            return
        actual_property = normalized[property_name_key]
        logging.info(f"Using property '{actual_property}' for relation link.")

        foreign = not is_estonian_company(email_data)

        related_entry = find_matching_entry_by_registry_code(
            email_data.get("registration_code", ""), RELATED_DATABASE_ID, "Registrikood"
        )
        related_entry_id = related_entry["id"] if related_entry else None
        logging.info(f"🔗 Related entry ID: {related_entry_id}")

        contact_name = email_data.get("participant_name", "")
        contact_entry = find_matching_contact_by_name(contact_name, PEOPLE_DATABASE_ID)
        related_contact_id = contact_entry["id"] if contact_entry else None
        logging.info(f"👤 Related contact ID: {related_contact_id}")

        next_jrk = get_company_local_jrk_start(database_id, related_entry_id) if related_entry_id else (get_max_jrk_number(database_id) + 1)

        if foreign:
            location_text = "N/A (foreign)"
            vta_text = "N/A (foreign)"
        else:
            location_text = get_location_from_registry_playwright(email_data.get("registration_code", "")) or "Not found"
            vta_text = check_vta_remnant(email_data.get("registration_code", ""))

        company_clean = normalize_company_name(email_data.get("company_name") or "")

        project_number_start = count_company_entries_in_database(database_id, related_entry_id)


        for i in range(count):
            current_project_number = project_number_start + i + 1
            project_name = project_name_template.format(
                company_name=company_clean,
                project_count=current_project_number,
                service_name=service_name,
            )

            logging.info(f"🧠 Creating project {i+1}/{count}: {project_name}")

            props = {
                "Project": {"title": [{"text": {"content": project_name}}]},
                "Company Name": {"relation": [{"id": related_entry_id}]} if related_entry_id else {"relation": []},
                "Registration date": {"date": {"start": email_received_date}} if email_received_date else None,
                "Location": {"rich_text": [{"text": {"content": location_text}}]},
                "Company origin": {"select": {"name": "Foreign" if foreign else "Estonian"}},
                "VTA kontroll": {"rich_text": [{"text": {"content": vta_text}}]},
                "Jrk": {"number": next_jrk},
            }

            props = {k: v for k, v in props.items() if v is not None}

            if related_contact_id:
                props["Contact"] = {"relation": [{"id": related_contact_id}]}

            if main_entry_id:
                props[actual_property] = {"relation": [{"id": main_entry_id}]}
            else:
                logging.warning(f"⚠️ main_entry_id missing for {service_name}, skipping relation link")

            if service_name.lower().strip() in ["ai help desk", "ai helpdesk", "tehisintellekti esmanõustamine"]:
                helpdesk_text = email_data.get("helpdesk_topics", "")
                if helpdesk_text:
                    prop_name = None
                    for k in db_props.keys():
                        if "service need" in k.lower():
                            prop_name = k
                            break
                    if prop_name:
                        props[prop_name] = {"rich_text": [{"text": {"content": helpdesk_text[:2000]}}]}
                        logging.info(f"✅ Added helpdesk topics to '{prop_name}': {helpdesk_text}")

            logging.info(f"📝 Final props before create: {props}")
            new_page = notion.pages.create(parent={"database_id": database_id}, properties=props)
            logging.info(f"✅ Added {service_name} project: {project_name}")

            try:
                item_url = new_page.get("url", "")
                db_name = get_database_name(database_id)
                recips = get_recipients_for_db(database_id)
                send_success_email(email_data.get("registration_code", ""), email_data, recips, item_url, db_name)
                logging.info(f"📧 Success email sent for {service_name} → {recips}")
            except Exception as email_err:
                emsg = f"Error sending success email for {service_name}: {email_err}"
                recips = get_recipients_for_db(database_id)
                send_error_email(email_data.get("registration_code", ""), emsg, email_data, recips)
                logging.error(emsg, exc_info=True)

            next_jrk += 1

    except Exception as e:
        logging.error(f"❌ Error in add_project(): {e}", exc_info=True)
        recips = get_recipients_for_db(database_id)
        send_error_email(email_data.get("registration_code",""), f"Project create failed: {e}", email_data, recips)


def count_company_entries_in_database(database_id, related_entry_id):
    """
    Counts how many entries in the specified database have a 'Company Name' relation
    that includes the given related_entry_id.
    """
    logging.info(f"Counting entries for related_entry_id {related_entry_id} in database {database_id}")
    try:
        filter_params = {
            "property": "Company Name",
            "relation": {
                "contains": related_entry_id
            }
        }
        results = query_all_pages(database_id, filter=filter_params)
        total_entries = len(results)

        logging.info(f"Total entries found: {total_entries}")
        return total_entries
    except Exception as e:
        logging.error(f"Error counting company entries in database: {e}", exc_info=True)
        return 0



def notify_error_for_relevant_databases(error_message: str, email_data: dict, service_counts: dict):
    """
    Sends an error email to all database responsibles depending on which services
    the company was trying to register for.
    """
    from email_notification import send_error_email
    from config import DATABASE_RESPONSIBLES, SERVICE_CONFIG, DEFAULT_RECIPIENTS

    reg_code = email_data.get("registration_code", "")
    notified = set()

    # 1️⃣ Loop through all services the user selected
    for service_name, count in service_counts.items():
        if count > 0 and service_name in SERVICE_CONFIG:
            db_id = SERVICE_CONFIG[service_name]["database_id"]
            recipients = DATABASE_RESPONSIBLES.get(db_id, DEFAULT_RECIPIENTS)
            send_error_email(reg_code, error_message, email_data, recipients)
            notified.update(recipients)
            logging.info(f"📧 Error notification sent for '{service_name}' → {recipients}")

    # 2️⃣ Always also notify main DB responsible
    from config import MAIN_DATABASE_ID
    main_recipients = DATABASE_RESPONSIBLES.get(MAIN_DATABASE_ID, DEFAULT_RECIPIENTS)
    if main_recipients:
        send_error_email(reg_code, error_message, email_data, main_recipients)
        notified.update(main_recipients)
        logging.info(f"📧 Error notification also sent to MAIN DB responsibles → {main_recipients}")

    # 3️⃣ Summary
    if not notified:
        send_error_email(reg_code, error_message, email_data, DEFAULT_RECIPIENTS)
        logging.warning(f"⚠️ No specific responsibles found — sent to default recipients.")
