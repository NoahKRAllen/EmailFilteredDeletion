import os
import json
import base64
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Gmail API scopes - we need modify scope to delete emails
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
SAFE_LIST_FILE = "safe_list.json"
TOKEN_FILE = "token.pickle"
CREDENTIALS_FILE = "credentials.json"


def load_safe_list():
    """Load the safe list from JSON file."""
    if not os.path.exists(SAFE_LIST_FILE):
        with open(SAFE_LIST_FILE, "w") as f:
            json.dump([], f)
        return []

    try:
        with open(SAFE_LIST_FILE, "r") as f:
            data = f.read().strip()
            if not data:
                return []
            return json.loads(data)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Failed to load safe list: {e}")
        return []


def save_safe_list(safe_list):
    """Save the safe list to JSON file."""
    with open(SAFE_LIST_FILE, "w") as f:
        json.dump(sorted(list(set(safe_list))), f, indent=2)


def authenticate_gmail():
    """Authenticate and return Gmail service object."""
    creds = None

    # Load existing token
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)

    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"Please download your OAuth 2.0 credentials from Google Cloud Console "
                    f"and save them as '{CREDENTIALS_FILE}'"
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)

    try:
        service = build('gmail', 'v1', credentials=creds)
        return service
    except HttpError as error:
        print(f'An error occurred: {error}')
        return None


def extract_email_from_header(header_value):
    """Extract email address from header value."""
    if not header_value:
        return None

    # Handle encoded headers
    try:
        decoded_parts = decode_header(header_value)
        decoded_header = ""
        for part in decoded_parts:
            if isinstance(part[0], bytes):
                decoded_header += part[0].decode(part[1] or 'utf-8', errors='ignore')
            else:
                decoded_header += part[0]
        header_value = decoded_header
    except:
        pass

    # Extract email from various formats
    email_pattern = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'

    # Try to find email in angle brackets first
    bracket_match = re.search(r'<([^>]+)>', header_value)
    if bracket_match:
        return bracket_match.group(1).strip()

    # Fall back to general email pattern
    email_match = re.search(email_pattern, header_value)
    if email_match:
        return email_match.group(1).strip()

    return None


def get_message_headers(service, message_id):
    """Get message headers including From field."""
    try:
        message = service.users().messages().get(
            userId='me',
            id=message_id,
            format='metadata',
            metadataHeaders=['From']
        ).execute()

        headers = message.get('payload', {}).get('headers', [])
        from_header = None

        for header in headers:
            if header['name'].lower() == 'from':
                from_header = header['value']
                break

        return extract_email_from_header(from_header)
    except HttpError as error:
        print(f'Error getting message headers: {error}')
        return None


def fetch_unapproved_senders(safe_list, scan_limit=500):
    """Fetch unapproved senders using Gmail API."""
    service = authenticate_gmail()
    if not service:
        return []

    unapproved_senders = set()

    try:
        print("Fetching unapproved senders using Gmail API...")

        # Get list of messages
        if scan_limit == 'all':
            max_results = None
        else:
            max_results = min(int(scan_limit), 500)  # Gmail API limits to 500 per request

        results = service.users().messages().list(
            userId='me',
            maxResults=max_results
        ).execute()

        messages = results.get('messages', [])
        print(f"Found {len(messages)} messages to process")

        # Process messages in batches for efficiency
        batch_size = 100
        for i in range(0, len(messages), batch_size):
            batch = messages[i:i + batch_size]
            print(f"Processing batch {i // batch_size + 1}/{(len(messages) + batch_size - 1) // batch_size}")

            for msg in batch:
                sender_email = get_message_headers(service, msg['id'])

                if sender_email:
                    # Check if sender is in safe list
                    is_safe = any(safe.lower() in sender_email.lower() for safe in safe_list)

                    if not is_safe:
                        unapproved_senders.add(sender_email)
                        print(f"Found unapproved sender: {sender_email}")

        print(f"Total unapproved senders: {len(unapproved_senders)}")
        return list(unapproved_senders)

    except HttpError as error:
        print(f'An error occurred: {error}')
        return []


def delete_unapproved_emails_dry_run(safe_list, scan_limit=500):
    """Dry run - count emails that would be deleted."""
    service = authenticate_gmail()
    if not service:
        return 0

    try:
        print("DRY RUN: Counting emails that would be deleted...")

        # Get list of messages
        if scan_limit == 'all':
            max_results = None
        else:
            max_results = min(int(scan_limit), 500)

        results = service.users().messages().list(
            userId='me',
            maxResults=max_results
        ).execute()

        messages = results.get('messages', [])
        print(f"DRY RUN: Found {len(messages)} messages to check")

        would_delete_count = 0

        # Process messages in batches
        batch_size = 100
        for i in range(0, len(messages), batch_size):
            batch = messages[i:i + batch_size]
            print(f"DRY RUN: Checking batch {i // batch_size + 1}/{(len(messages) + batch_size - 1) // batch_size}")

            for msg in batch:
                sender_email = get_message_headers(service, msg['id'])

                if sender_email:
                    is_safe = any(safe.lower() in sender_email.lower() for safe in safe_list)

                    if not is_safe:
                        would_delete_count += 1
                        print(f"DRY RUN: WOULD DELETE email from {sender_email} (#{would_delete_count})")
                    else:
                        print(f"DRY RUN: Would keep safe email from {sender_email}")

        print(f"DRY RUN SUMMARY: Would delete {would_delete_count} out of {len(messages)} emails")
        return would_delete_count

    except HttpError as error:
        print(f'An error occurred: {error}')
        return 0


def delete_unapproved_emails(safe_list, scan_limit=500):
    """Delete emails from unapproved senders using Gmail API."""
    service = authenticate_gmail()
    if not service:
        return 0

    try:
        print("Deleting unapproved emails using Gmail API...")

        # Get list of messages
        if scan_limit == 'all':
            max_results = None
        else:
            max_results = min(int(scan_limit), 500)

        results = service.users().messages().list(
            userId='me',
            maxResults=max_results
        ).execute()

        messages = results.get('messages', [])
        print(f"Found {len(messages)} messages to process")

        messages_to_delete = []

        # First pass: identify messages to delete
        batch_size = 100
        for i in range(0, len(messages), batch_size):
            batch = messages[i:i + batch_size]
            print(f"Analyzing batch {i // batch_size + 1}/{(len(messages) + batch_size - 1) // batch_size}")

            for msg in batch:
                sender_email = get_message_headers(service, msg['id'])

                if sender_email:
                    is_safe = any(safe.lower() in sender_email.lower() for safe in safe_list)

                    if not is_safe:
                        messages_to_delete.append(msg['id'])
                        print(f"Marked for deletion: email from {sender_email}")

        print(f"Total messages marked for deletion: {len(messages_to_delete)}")

        # Second pass: delete messages in batches
        if messages_to_delete:
            deleted_count = 0
            delete_batch_size = 1000  # Gmail API allows up to 1000 messages per batch delete

            for i in range(0, len(messages_to_delete), delete_batch_size):
                batch_ids = messages_to_delete[i:i + delete_batch_size]

                try:
                    # Use batchDelete for efficiency
                    service.users().messages().batchDelete(
                        userId='me',
                        body={'ids': batch_ids}
                    ).execute()

                    deleted_count += len(batch_ids)
                    print(f"Deleted batch: {len(batch_ids)} messages (Total: {deleted_count})")

                except HttpError as error:
                    print(f"Error deleting batch: {error}")
                    # Fallback to individual deletion
                    for msg_id in batch_ids:
                        try:
                            service.users().messages().delete(userId='me', id=msg_id).execute()
                            deleted_count += 1
                        except HttpError as individual_error:
                            print(f"Error deleting individual message {msg_id}: {individual_error}")

            print(f"Successfully deleted {deleted_count} emails")
            return deleted_count
        else:
            print("No emails to delete")
            return 0

    except HttpError as error:
        print(f'An error occurred: {error}')
        return 0


def setup_gmail_api():
    """Setup instructions for Gmail API."""
    print("""
    GMAIL API SETUP INSTRUCTIONS:

    1. Go to Google Cloud Console (https://console.cloud.google.com/)
    2. Create a new project or select an existing one
    3. Enable the Gmail API:
       - Go to "APIs & Services" > "Library"
       - Search for "Gmail API" and enable it
    4. Configure OAuth consent screen:
       - Go to "APIs & Services" > "OAuth consent screen"
       - Choose "External" user type
       - Fill in required fields (Application name, User support email, etc.)
       - Add your email to test users
    5. Create credentials:
       - Go to "APIs & Services" > "Credentials"
       - Click "Create Credentials" > "OAuth client ID"
       - Choose "Desktop application"
       - Download the JSON file and save it as 'credentials.json' in this directory

    Required packages:
    pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client

    The first time you run the application, it will open a browser window for authentication.
    """)


if __name__ == "__main__":
    setup_gmail_api()