import imaplib
import email
from email.header import decode_header
import json
import os

SAFE_LIST_FILE = "safe_list.json"

def load_safe_list():
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
        print(f"Warning Failed to load safe list: {e}")
        return []

def save_safe_list(safe_list):
    with open(SAFE_LIST_FILE, "w") as f:
        json.dump(sorted(list(set(safe_list))), f, indent=2)

def fetch_unapproved_senders(email_user, email_pass, safe_list, scan_limit='500'):
    imap_server = "imap.gmail.com" # Can be changed to fit other email services
    unapproved_senders = set()

    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email_user, email_pass)
        mail.select("inbox")

        result, data = mail.search(None, "ALL")
        if result != "OK":
            return []
        email_ids = data[0].split()
        email_ids = [e.decode() for e in email_ids]

        if scan_limit != 'all':
            try:
                limit = int(scan_limit)
                email_ids = email_ids[-limit:]
            except ValueError:
                pass # Use full list if conversion fails

        for i, num in enumerate(email_ids):
            if i % 100 == 0:
                print(f"Processed {i} emails...")

            result, msg_data = mail.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM)])")
            if result != "OK":
                continue

            msg = email.message_from_bytes(msg_data[0][1])
            sender = msg.get("From", "")
            if sender:
                decoded_sender, _ = decode_header(sender)[0]
                if isinstance(decoded_sender, bytes):
                    decoded_sender = decoded_sender.decode(errors="ignore")

                # extract email only
                if "<" in decoded_sender:
                    decoded_sender = decoded_sender.split("<")[-1].rstrip(">")

                if decoded_sender not in safe_list:
                    unapproved_senders.add(decoded_sender)
        mail.logout()

    except Exception as e:
        print("Error: ", e)

    return list(unapproved_senders)