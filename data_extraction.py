# data_extraction.py

import re
import logging
from bs4 import BeautifulSoup

from utils import decode_part

# Extract the email body
def extract_email_body(msg):
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

# Extract required data from the email body
def extract_email_data(body):
    email_data = {
        "company_name": "",
        "email_address": "",
        "phone_number": "",
        "registration_code": "",
        "industry": "",
        "participant_name": "",
    }

    email_pattern = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
    lines = body.split("\n")

    for index, line in enumerate(lines):
        line = line.strip()
        if re.search(
            r"^(Ettevõtte või organisatsiooni nimi|Company or organization name):",
            line,
            re.IGNORECASE,
        ):
            email_data["company_name"] = extract_value(line, lines, index)
        elif re.search(r"^(E-post|E-mail):", line, re.IGNORECASE):
            email_data["email_address"] = extract_value(
                line, lines, index, pattern=email_pattern
            )
        elif re.search(r"^(Telefoni number|Phone number):", line, re.IGNORECASE):
            email_data["phone_number"] = extract_value(line, lines, index)
        elif re.search(r"^(Registrikood|Registration code):", line, re.IGNORECASE):
            email_data["registration_code"] = extract_value(line, lines, index)
        elif re.search(r"^(Tööstusharu|Industry):", line, re.IGNORECASE):
            email_data["industry"] = extract_value(line, lines, index)
        elif re.search(
            r"^(Osaleja nimi|Participant name|Name of contact person):",
            line,
            re.IGNORECASE,
        ):
            email_data["participant_name"] = extract_value(line, lines, index)

    logging.info(f"Extracted email data: {email_data}")
    return email_data

# Extract the value from a line or from the next line if the current one is empty
def extract_value(line, lines, index, pattern=None):
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

# Extract the number of services based on the email body
def extract_service_counts(body, language="et"):
    body = body.replace("\n", " ").strip()
    body = body.replace("–", "-").replace("—", "-").replace("−", "-")

    logging.info(f"Processing email body: {body}")  

    service_counts = {
        "Digiküpsuse hindamine": 0,
        "Tehisintellekti otstarbekuse nõustamine": 0,
        "Finantseerimise nõustamine – Erakapitali kaasamine": 0,
        "Finantseerimise nõustamine – Avalikud meetmed": 0,
        "Robotiseerimise nõustamine": 0,
        "AIRE eelkiirendi": 0,
    }

    logging.info(f"Detected language: {language}")

    if language == "et":
        if re.search(r"Digik[uü]psuse hindamine", body, re.IGNORECASE):
            service_counts["Digiküpsuse hindamine"] = 1
            logging.info("Detected 'Digiküpsuse hindamine' in Estonian email.")

        if re.search(r"Tehisintellekti otstarbekuse nõustamine", body, re.IGNORECASE):
            ai_match = re.search(r"Projektipõhine AI nõustamine:\s*(\d+)\s*kordne", body)
            service_counts["Tehisintellekti otstarbekuse nõustamine"] = (
                int(ai_match.group(1)) if ai_match else 1
            )
            logging.info("Detected 'Tehisintellekti otstarbekuse nõustamine' in Estonian email.")

        if re.search(r"AIRE (eel)?kiirendi", body, re.IGNORECASE):
            service_counts["AIRE eelkiirendi"] = 1
            logging.info("Detected 'AIRE kiirendi' in Estonian email.")

        fin_match = re.search(r"Finantseerimise nõustamine:\s*(\d+)\s*kordne", body)
        if fin_match:
            fin_count = int(fin_match.group(1))
            logging.info(f"Found 'Finantseerimise nõustamine' with {fin_count} service units.")

            if re.search(r"Finantseerimise nõustamine.*Erakapitali kaasamine", body, re.IGNORECASE):
                service_counts["Finantseerimise nõustamine – Erakapitali kaasamine"] = fin_count
                logging.info("Detected 'Finantseerimise nõustamine – Erakapitali kaasamine' in Estonian email.")

            if re.search(r"Finantseerimise nõustamine.*Avalikud meetmed", body, re.IGNORECASE):
                service_counts["Finantseerimise nõustamine – Avalikud meetmed"] = fin_count
                logging.info("Detected 'Finantseerimise nõustamine – Avalikud meetmed' in Estonian email.")
        else:
            if "Finantseerimise nõustamine – Erakapitali kaasamine" in body:
                service_counts["Finantseerimise nõustamine – Erakapitali kaasamine"] = 1
                logging.info("Detected 'Finantseerimise nõustamine – Erakapitali kaasamine' in Estonian email.")

            if "Finantseerimise nõustamine – Avalikud meetmed" in body:
                service_counts["Finantseerimise nõustamine – Avalikud meetmed"] = 1
                logging.info("Detected 'Finantseerimise nõustamine – Avalikud meetmed' in Estonian email.")

        robot_match = re.search(r"Robotiseerimise nõustamine:\s*(\d+)\s*kordne", body, re.IGNORECASE)
        if robot_match:
            service_counts["Robotiseerimise nõustamine"] = int(robot_match.group(1))
            logging.info("Detected 'Robotiseerimise nõustamine' in Estonian email with count.")
        elif re.search(r"Robotiseerimise otstarbekuse nõustamine", body, re.IGNORECASE):
            service_counts["Robotiseerimise nõustamine"] = 1
            logging.info("Detected 'Robotiseerimise nõustamine' in Estonian email without explicit count.")

    elif language == "en":

        if re.search(r"Digital maturity assessment", body, re.IGNORECASE):
            service_counts["Digiküpsuse hindamine"] = 1
            logging.info("Detected 'Digital maturity assessment' in English email.")

        if re.search(r"AI suitability assessment", body, re.IGNORECASE):
            ai_match = re.search(r"Project-based AI consultancy:\s*(\d+)\s*service units", body, re.IGNORECASE)
            service_counts["Tehisintellekti otstarbekuse nõustamine"] = (
                int(ai_match.group(1)) if ai_match else 1
            )
            logging.info("Detected 'AI suitability assessment' in English email with count.")

        robotics_match = re.search(r"Robotics consultancy\s*(\d+)\s*service units", body, re.IGNORECASE)
        if robotics_match:
            service_counts["Robotiseerimise nõustamine"] = int(robotics_match.group(1))
            logging.info("Detected 'Robotics consultancy' in English email with count.")
        elif re.search(r"Robotics consultancy", body, re.IGNORECASE):
            service_counts["Robotiseerimise nõustamine"] = 1
            logging.info("Detected 'Robotics consultancy' in English email without explicit count.")

        if re.search(r"Finding Sources of funding\s*[-–—−]\s*Private capital", body, re.IGNORECASE):
            fin_private_match = re.search(r"Finding Sources of funding\s*[-–—−]\s*Private capital.*?(\d+)\s*service units", body, re.IGNORECASE)
            fin_private_count = int(fin_private_match.group(1)) if fin_private_match else 1
            service_counts["Finantseerimise nõustamine – Erakapitali kaasamine"] = fin_private_count
            logging.info("Detected 'Finding Sources of funding – Private capital' in English email with count.")

        if re.search(r"Finding Sources of funding\s*[-–—−]\s*Public measures", body, re.IGNORECASE):
            fin_public_match = re.search(r"Finding Sources of funding\s*[-–—−]\s*Public measures.*?(\d+)\s*service units", body, re.IGNORECASE)
            fin_public_count = int(fin_public_match.group(1)) if fin_public_match else 1
            service_counts["Finantseerimise nõustamine – Avalikud meetmed"] = fin_public_count
            logging.info("Detected 'Finding Sources of funding – Public measures' in English email with count.")

    else:
        logging.warning("Language not supported for service extraction.")

    logging.info(f"Extracted service counts: {service_counts}")
    return service_counts
