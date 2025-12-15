import re
import logging
from bs4 import BeautifulSoup
from utils import decode_part


# -------- Extract Email Body --------
def extract_email_body(msg):
    """Extracts and cleans text from HTML or plain-text emails."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if (
                part.get_content_type() in ["text/plain", "text/html"]
                and "attachment" not in str(part.get("Content-Disposition"))
            ):
                body = decode_part(part)
                if part.get_content_type() == "text/html":
                    body = BeautifulSoup(body, "html.parser").get_text(separator="\n")
        return body
    else:
        body = decode_part(msg)
        if msg.get_content_type() == "text/html":
            body = BeautifulSoup(body, "html.parser").get_text(separator="\n")
        return body


# -------- Extract Email Data (company info etc.) --------
def extract_email_data(body):
    """Parses structured company and participant data from the email body."""
    email_data = {
        "company_name": "",
        "email_address": "",
        "phone_number": "",
        "registration_code": "",
        "industry": "",
        "participant_name": "",
        "company_origin": "",
        "helpdesk_topics": "",  
    }

    email_pattern = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
    lines = body.split("\n")

    for index, line in enumerate(lines):
        line = line.strip()
        if re.search(
            r"^(Ettevõtte või organisatsiooni nimi|Company or organization name):",
            line, re.IGNORECASE,
        ):
            email_data["company_name"] = extract_value(line, lines, index)
        elif re.search(r"^(E-post|E-mail):", line, re.IGNORECASE):
            email_data["email_address"] = extract_value(line, lines, index, pattern=email_pattern)
        elif re.search(r"^(Telefoni number|Phone number):", line, re.IGNORECASE):
            email_data["phone_number"] = extract_value(line, lines, index)
        elif re.search(r"^(Registrikood|Registration code):", line, re.IGNORECASE):
            email_data["registration_code"] = extract_value(line, lines, index)
        elif re.search(r"^(Tööstusharu|Industry):", line, re.IGNORECASE):
            email_data["industry"] = extract_value(line, lines, index)
        elif re.search(
            r"^(Osaleja nimi|Participant name|Name of contact person):",
            line, re.IGNORECASE,
        ):
            email_data["participant_name"] = extract_value(line, lines, index)
        elif re.search(
            r"^(Ettevõtte päritolu|Company origin):",
            line, re.IGNORECASE,
        ):
            email_data["company_origin"] = extract_value(line, lines, index)
        elif re.search(
            r"(Mis on peamised teemad.*AI help desk|What are the main topics.*AI help desk)",
            line, re.IGNORECASE,
        ):
            email_data["helpdesk_topics"] = extract_value(line, lines, index)

    logging.info(f"Extracted email data: {email_data}")
    return email_data


def extract_value(line, lines, index, pattern=None):
    """Extracts value after ':' or from next line."""
    value = line.partition(":")[-1].strip()
    if not value and index + 1 < len(lines):
        next_line = lines[index + 1].strip()
        if pattern:
            match = pattern.search(next_line)
            return match.group() if match else ""
        return next_line
    if pattern:
        match = pattern.search(value)
        return match.group() if match else ""
    return value


# -------- Extract Service Counts --------
def extract_service_counts(body, language="et"):
    """Detects which of the 7 AIRE services were selected in the email."""
    body = body.replace("\n", " ").strip()
    body = body.replace("–", "-").replace("—", "-").replace("−", "-")

    logging.info(f"Processing email body: {body}")

    service_counts = {
        "Tehisintellekti otstarbekuse nõustamine": 0,
        "Finantseerimise nõustamine – Erakapitali kaasamine": 0,
        "Finantseerimise nõustamine – Avalikud meetmed": 0,
        "Koostööpartnerite leidmine": 0,
        "AI help desk": 0,
        "TI määruse nõustamine ja usaldusväärne TI": 0,
        "Ligipääs EL'i tehisintellekti taristule": 0,
    }

    logging.info(f"Detected language: {language}")

    # ----- Estonian -----
    if language == "et":
        # --- Tehisintellekti üldnõustamine (AI help desk) ---
        if re.search(r"Tehisintellekti\s+üldnõustamine", body, re.IGNORECASE):
            service_counts["AI help desk"] = 1
            logging.info("AI help desk (üldnõustamine) detected")

        # --- Tehisintellekti otstarbekuse nõustamine ---
        if re.search(r"Tehisintellekti\s+otstarbekuse\s+nõustamine", body, re.IGNORECASE):
            ai_match = re.search(r"AI nõustamine:\s*(\d+)\s*kordne", body)
            count = int(ai_match.group(1)) if ai_match else 1
            service_counts["Tehisintellekti otstarbekuse nõustamine"] = min(count, 2)
            logging.info(f"AI suitability (otstarbekuse nõustamine) detected: {count}x")

        # --- Finantseerimise nõustamine ---
        if re.search(r"Finantseerimise nõustamine", body, re.IGNORECASE):
            fin_match = re.search(r"Finantseerimise nõustamine:\s*(\d+)\s*kordne", body)
            count = int(fin_match.group(1)) if fin_match else 1
            count = min(count, 2)
            if re.search(r"Avalikud meetmed", body, re.IGNORECASE):
                service_counts["Finantseerimise nõustamine – Avalikud meetmed"] = count
            if re.search(r"Erakapitali kaasamine", body, re.IGNORECASE):
                service_counts["Finantseerimise nõustamine – Erakapitali kaasamine"] = count

        # --- Koostööpartnerite leidmine ---
        if re.search(r"Koostööpartnerite leidmine", body, re.IGNORECASE):
            service_counts["Koostööpartnerite leidmine"] = 1

        # --- 🆕 TI määruse nõustamine ja usaldusväärne TI ---
        if re.search(r"TI\s+m[äa]ruse\s+n[õo]ustamine.*usaldusv[äa]ärne\s+TI", body, re.IGNORECASE):
            ti_match = re.search(r"TI\s+m[äa]ruse.*?:\s*(\d+)\s*kordne", body)
            count = int(ti_match.group(1)) if ti_match else 1
            service_counts["TI määruse nõustamine ja usaldusväärne TI"] = min(count, 2)
            logging.info(f"TI määruse nõustamine ja usaldusväärne TI detected: {count}x")

        # --- 🆕 Ligipääs EL'i tehisintellekti taristule ---
        if re.search(r"Ligipääs\s+EL'?i\s+tehisintellekti\s+taristule", body, re.IGNORECASE):
            service_counts["Ligipääs EL'i tehisintellekti taristule"] = 1
            logging.info("Ligipääs EL'i tehisintellekti taristule detected")

    # ----- English -----
    elif language == "en":
        if re.search(r"AI help desk", body, re.IGNORECASE):
            service_counts["AI help desk"] = 1
            logging.info("AI help desk detected")

        if re.search(r"AI suitability assessment", body, re.IGNORECASE):
            ai_match = re.search(r"AI suitability assessment:\s*(two|[\d]+)", body, re.IGNORECASE)
            if ai_match:
                val = ai_match.group(1)
                count = 2 if val.lower() == "two" else int(val)
            else:
                count = 1
            service_counts["Tehisintellekti otstarbekuse nõustamine"] = min(count, 2)
            logging.info(f"AI suitability assessment detected: {count}x")

        if re.search(r"Support to find funding", body, re.IGNORECASE):
            fin_match = re.search(r"Support to find funding:\s*(two|[\d]+)", body, re.IGNORECASE)
            if fin_match:
                val = fin_match.group(1)
                count = 2 if val.lower() == "two" else int(val)
            else:
                count = 1
            count = min(count, 2)
            if re.search(r"public measures", body, re.IGNORECASE):
                service_counts["Finantseerimise nõustamine – Avalikud meetmed"] = count
            if re.search(r"private capital", body, re.IGNORECASE):
                service_counts["Finantseerimise nõustamine – Erakapitali kaasamine"] = count

        if re.search(r"(Matchmaking|international partnerships)", body, re.IGNORECASE):
            service_counts["Koostööpartnerite leidmine"] = 1
            logging.info("Matchmaking / international partnerships detected")

        # --- 🆕 AI Act awareness and responsible AI ---
        if re.search(r"AI\s*Act\s*awareness.*responsible\s*AI", body, re.IGNORECASE):
            act_match = re.search(r"AI\s*Act\s*awareness.*?:\s*(two|[\d]+)", body, re.IGNORECASE)
            if act_match:
                val = act_match.group(1)
                count = 2 if val.lower() == "two" else int(val)
            else:
                count = 1
            service_counts["TI määruse nõustamine ja usaldusväärne TI"] = min(count, 2)
            logging.info(f"AI Act awareness and responsible AI detected: {count}x")

        # --- 🆕 Access to EU AI infrastructure ---
        if re.search(r"Access\s+to\s+EU\s+AI\s+infrastructure", body, re.IGNORECASE):
            service_counts["Ligipääs EL'i tehisintellekti taristule"] = 1
            logging.info("Access to EU AI infrastructure detected")


    else:
        logging.warning("Language not supported for service extraction.")

    # enforce limits
    for k in service_counts:
        service_counts[k] = min(service_counts[k], 2 if "nõustamine" in k else 1)

    logging.info(f"Extracted service counts (final): {service_counts}")
    return service_counts
