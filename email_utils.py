import imaplib
import email
import re
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

def fetch_unapproved_senders(email_user, email_pass, safe_list, scan_limit='100'):
    imap_server = "imap.gmail.com" # Can be changed to fit other email services
    unapproved_senders = set()
    try:
        print("Fetching unapproved senders...")
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email_user, email_pass)
        mail.select("inbox")

        result, data = mail.search(None, "ALL")
        print("mail.search ran")
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
            if i % 10 == 0:
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
                    print(f"Found unapproved sender: {decoded_sender}")

        mail.logout()

    except Exception as e:
        print("Error: ", e)
    print(f"Total unapproved senders: {len(unapproved_senders)}")
    return list(unapproved_senders)

def delete_unapproved_emails_debug(email_user, email_pass, safe_list, scan_limit='500'):
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(email_user, email_pass)
    mail.select("inbox")

    result, data = mail.search(None, "ALL")
    if result != "OK":
        mail.logout()
        return 0

    email_ids = data[0].split()
    email_ids = [e.decode() for e in email_ids]

    print(f"DEBUG: Total emails in inbox: {len(email_ids)}")
    print(f"DEBUG: Scan limit: {scan_limit}")

    if scan_limit != 'all':
        try:
            limit = int(scan_limit)
            original_count = len(email_ids)
            email_ids = email_ids[-limit:]
            print(f"DEBUG: Limited from {original_count} to {len(email_ids)} emails")
        except ValueError:
            pass

    print(f"DEBUG: Processing {len(email_ids)} emails")
    print(f"DEBUG: Email ID range: {email_ids[0]} to {email_ids[-1]}")

    deleted_count = 0
    processed_count = 0
    failed_fetch_count = 0

    for i, num in enumerate(email_ids):
        processed_count += 1
        print(f"DEBUG: Processing {processed_count}/{len(email_ids)} - Email ID: {num}")

        try:
            # Check connection health
            try:
                mail.noop()  # Keep connection alive
            except:
                print("DEBUG: Connection lost, reconnecting...")
                mail.logout()
                mail = imaplib.IMAP4_SSL("imap.gmail.com")
                mail.login(email_user, email_pass)
                mail.select("inbox")

            result, msg_data = mail.fetch(num, '(BODY.PEEK[HEADER.FIELDS (FROM)])')
            print(f"DEBUG: Fetch result: {result}")

            if result != "OK":
                print(f"DEBUG: Fetch failed for email {num} - Result: {result}")
                failed_fetch_count += 1
                continue

            if not msg_data:
                print(f"DEBUG: No data returned for email {num}")
                failed_fetch_count += 1
                continue

            print(f"DEBUG: msg_data type: {type(msg_data)}, length: {len(msg_data)}")

            sender_found = False
            for response_part in msg_data:
                print(f"DEBUG: Processing response part: {type(response_part)}")

                # Handle None response parts
                if response_part is None:
                    print(f"DEBUG: Response part is None, skipping")
                    continue

                if isinstance(response_part, tuple):
                    if len(response_part) < 2 or response_part[1] is None:
                        print(f"DEBUG: Tuple response part has no data: {response_part}")
                        continue

                    raw = response_part[1].decode(errors='ignore')
                    print(f"DEBUG: Raw header (first 200 chars): {raw[:200]}")

                    # Extract sender email
                    sender = None
                    match = re.search(r"<([^>]+)>", raw)
                    if match:
                        sender = match.group(1).strip()
                        print(f"DEBUG: Found sender in brackets: {sender}")
                    else:
                        match = re.search(r"From:\s*([^\r\n]+)", raw, re.IGNORECASE)
                        if match:
                            from_line = match.group(1).strip()
                            email_match = re.search(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", from_line)
                            if email_match:
                                sender = email_match.group(1)
                                print(f"DEBUG: Found sender without brackets: {sender}")

                    if sender:
                        sender_found = True
                        print(f"DEBUG: Checking if '{sender}' is safe...")

                        is_safe = any(safe.lower() in sender.lower() for safe in safe_list)
                        print(f"DEBUG: Is safe: {is_safe}")

                        if not is_safe:
                            print(f"DEBUG: Moving email {num} from {sender} to trash")
                            try:
                                mail.copy(num, '[Gmail]/Trash')
                                mail.store(num, '+FLAGS', '\\Deleted')
                                deleted_count += 1
                                print(f"DEBUG: Successfully moved email {deleted_count}")
                            except Exception as move_error:
                                print(f"DEBUG: Error moving email {num}: {move_error}")
                        else:
                            print(f"DEBUG: Email from {sender} is safe, skipping")
                        break
                else:
                    print(f"DEBUG: Unexpected response type: {type(response_part)}")

            if not sender_found:
                print(f"DEBUG: No sender found in email {num} - trying alternative fetch method")
                # Try fetching the entire header as fallback
                try:
                    result2, msg_data2 = mail.fetch(num, '(BODY.PEEK[HEADER])')
                    if result2 == "OK" and msg_data2:
                        for part in msg_data2:
                            if isinstance(part, tuple) and part[1]:
                                full_header = part[1].decode(errors='ignore')
                                match = re.search(r"^From:\s*(.+)$", full_header, re.MULTILINE | re.IGNORECASE)
                                if match:
                                    from_line = match.group(1).strip()
                                    email_match = re.search(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
                                                            from_line)
                                    if email_match:
                                        sender = email_match.group(1)
                                        print(f"DEBUG: Found sender via full header: {sender}")
                                        sender_found = True

                                        is_safe = any(safe.lower() in sender.lower() for safe in safe_list)
                                        if not is_safe:
                                            mail.copy(num, '[Gmail]/Trash')
                                            mail.store(num, '+FLAGS', '\\Deleted')
                                            deleted_count += 1
                                            print(f"DEBUG: Moved email via fallback method")
                                        break
                except Exception as fallback_error:
                    print(f"DEBUG: Fallback method failed: {fallback_error}")

            if not sender_found:
                print(f"DEBUG: Still no sender found for email {num} - email may be corrupted or deleted")

        except Exception as e:
            print(f"DEBUG: Exception processing email {num}: {e}")
            import traceback
            traceback.print_exc()
            continue

    print(f"DEBUG: Final stats:")
    print(f"  - Processed: {processed_count}")
    print(f"  - Failed fetches: {failed_fetch_count}")
    print(f"  - Moved to trash: {deleted_count}")

    try:
        print("DEBUG: Running expunge...")
        mail.expunge()
        print("DEBUG: Expunge completed")
    except Exception as e:
        print(f"DEBUG: Error during expunge: {e}")

    mail.logout()
    return deleted_count


def delete_unapproved_emails_dry_run(email_user, email_pass, safe_list, scan_limit='500'):
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(email_user, email_pass)
    mail.select("inbox")

    result, data = mail.search(None, "ALL")
    if result != "OK":
        mail.logout()
        return 0

    email_ids = data[0].split()
    email_ids = [e.decode() for e in email_ids]

    if scan_limit != 'all':
        try:
            limit = int(scan_limit)
            email_ids = email_ids[-limit:]
        except ValueError:
            pass

    print(f"DRY RUN: Would process {len(email_ids)} emails")

    would_delete_count = 0
    processed_count = 0

    for i, num in enumerate(email_ids):
        processed_count += 1
        print(f"DRY RUN: Processing {processed_count}/{len(email_ids)} - Email ID: {num}")

        try:
            result, msg_data = mail.fetch(num, '(BODY.PEEK[HEADER.FIELDS (FROM)])')

            if result != "OK" or not msg_data:
                print(f"DRY RUN: Would skip email {num} - fetch failed")
                continue

            sender = None
            for response_part in msg_data:
                if response_part is None:
                    continue

                if isinstance(response_part, tuple) and len(response_part) > 1 and response_part[1]:
                    raw = response_part[1].decode(errors='ignore')

                    # Extract sender
                    match = re.search(r"<([^>]+)>", raw)
                    if match:
                        sender = match.group(1).strip()
                    else:
                        match = re.search(r"From:\s*([^\r\n]+)", raw, re.IGNORECASE)
                        if match:
                            from_line = match.group(1).strip()
                            email_match = re.search(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", from_line)
                            if email_match:
                                sender = email_match.group(1)
                    break

            if sender:
                is_safe = any(safe.lower() in sender.lower() for safe in safe_list)

                if not is_safe:
                    would_delete_count += 1
                    print(f"DRY RUN: WOULD DELETE email from {sender} (#{would_delete_count})")
                else:
                    print(f"DRY RUN: Would keep safe email from {sender}")
            else:
                print(f"DRY RUN: No sender found for email {num}")

        except Exception as e:
            print(f"DRY RUN: Error processing email {num}: {e}")
            continue

    print(f"DRY RUN SUMMARY: Would delete {would_delete_count} out of {processed_count} emails")
    mail.logout()
    return would_delete_count