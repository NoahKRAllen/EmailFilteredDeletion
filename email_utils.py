import imaplib
import email
from email.header import decode_header

def fetch_unapproved_senders(email_user, email_pass, safe_list):
    imap_server = "imap.gmail.com" # Can be changed to fit other email services
    unapproved_senders = set()

    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email_user, email_pass)
        mail.select("inbox")

        result, data = mail.search(None, "ALL")
        if result != "OK":
            return []

        for num in data[0].split():
            result, msg_data = mail.fetch(num, "(RFC822)")
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