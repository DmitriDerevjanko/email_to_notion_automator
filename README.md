# System Architecture

## Overview
This system automates the process of processing incoming emails and adding data to Notion databases. It consists of the following main components:

- **IMAP Server**: Responsible for retrieving incoming emails.
- **Python Script**:
  - **`data_extraction.py`**: Parses email content and extracts key information such as company name and registration code.
  - **`notion_utils.py`**: Interacts with Notion API to check, add, or update records in Notion databases.
  - **`email_notification.py`**: Sends email notifications about processing status (success or failure).
- **Notion API**: Provides access to Notion databases for data storage and retrieval.

---

## System Diagram

This diagram provides an overview of the system architecture:

![System Diagram](./assets/system-diagram.jpg)

## Architectural Levels

### Input Layer
- **Source**: Incoming emails retrieved from the IMAP server.
- **Functions**: 
  - Connect to the IMAP server.
  - Fetch and decode email content.

### Processing Layer
- **Modules**:
  - `data_extraction.py`: Extracts relevant data from emails (e.g., company name, registration code, participant details).
  - `utils.py`: Performs utility functions such as date formatting, text normalization, and IMAP connection retries.
- **Actions**:
  - Data validation and normalization.
  - Extracting relevant values for integration.

### Integration Layer
- **Module**: `notion_utils.py`.
- **Functionality**:
  - Creates or updates records in Notion databases.
  - Supports additional databases based on services (e.g., AI consultancy, public funding).
  
### Notification Layer
- **Module**: `email_notification.py`.
- **Functions**:
  - Sends success or error notifications to predefined recipients.
  - Provides detailed information on errors, including extracted data.

---

## Diagrams

### Component Diagram
```plaintext
+-------------------+       +-------------------+       +----------------------+
|     IMAP Server   |       |  Data Extraction  |       |  Notion Integration  |
| (Fetch Emails)    | ----> |  (Parse Emails)   | ----> |    (Work with API)   |
+-------------------+       +-------------------+       +----------------------+
                                                             |
                                                         +---v----+
                                                         |  Notion |
                                                         | Database|
                                                         +---------+



### Sequence Diagram


User                IMAP Server             Script                     Notion Database
 |                        |                      |                               |
 |------ Check emails --->|                      |                               |
 |                        |-- Fetch emails -->   |                               |
 |                        |                      |-- Parse email body ---------> |
 |                        |                      |-- Extract data -------------> |
 |                        |                      |-- Find existing record -----> |
 |                        |                      |-- Create/Update record -----> |
 |                        |                      |                               |

### Data Flow Diagram



+---------------------+
| Incoming Email      |
| (IMAP Server)       |
+---------------------+
           |
           v
+---------------------+        +--------------------+
| Data Extraction     | -----> | Notion Integration |
| (Parse Content)     |        | (Work with API)    |
+---------------------+        +--------------------+
           |
           v
+---------------------+
| Email Notification  |
| (Send Status)       |
+---------------------+


## Key Components and Technologies

| Component           | Technology               | Description                                                   |
|---------------------|--------------------------|---------------------------------------------------------------|
| IMAP Server         | IMAP Protocol            | Fetches incoming emails for processing.                      |
| Data Extraction     | Python, `re`, BeautifulSoup | Extracts and normalizes data from email content.             |
| Notion Integration  | Notion API, Python       | Adds or updates data in Notion databases based on email content. |
| Notifications       | SMTP, Python             | Sends notifications about success or errors in processing.   |




## How It Works

### 1. Retrieve Emails
- Connect to the IMAP server (`utils.py`).
- Fetch and decode incoming emails.

### 2. Parse and Extract Data
- Use `data_extraction.py` to process email content.
- Extract key details:
  - Company name.
  - Registration code.
  - Participant names.

### 3. Add to Notion
- Use `notion_utils.py` to:
  - Check existing records.
  - Create new entries if no match is found.
- Populate additional fields:
  - `Jrk`: A sequential number for sorting.
  - `Location`: Automatically determined based on the registration code.

### 4. Send Notifications
- **Success**: Notify recipients about successful data processing.
- **Failure**: Send detailed error messages (via `email_notification.py`) with extracted data for manual review.

---

## Logging

### Levels
- **INFO**: Logs successful operations (e.g., email processed, record created).
- **ERROR**: Logs issues during email processing or API interactions.

### Example Logs
```plaintext
2024-11-29 10:00:15 - INFO - Successfully added company: Example OÜ to the Notion database.
2024-11-29 10:01:20 - ERROR - Failed to process email: Invalid registry code.
