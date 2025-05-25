import imaplib
import email
from email.header import decode_header


SERVER = "smtp.gmail.com"
#TODO: API input for email and password and mailbox(e.g. Inbox, Spam) to scan
USERNAME = "<EMAIL>"
PASSWORD = "<PASSWORD>"
MAILBOX = "<MAILBOX>"
#TODO: API input for individual senders to exclude from the purge
EXCLUDED_SENDERS = []

imap_server = imaplib.IMAP4_SSL(SERVER)
imap_server.login(USERNAME, PASSWORD)
imap_server.select(MAILBOX)


_, message_numbers = imap_server.search(None, "ALL")
message_numbers_list = message_numbers[0].split()

excluded_messages = []
for sender in EXCLUDED_SENDERS:
    _, search_result = imap_server.search(None, f'FROM {sender}')
    if search_result[0]:
        excluded_messages.extend(search_result[0].split())


not_from_excluded = [uid for uid in message_numbers_list if uid not in excluded_messages]
non_excluded_senders = []
#TODO: delete all emails not in the excluded list
if(not_from_excluded):
    for uid in not_from_excluded:
        _, data = imap_server.fetch(uid, "(RFC822)")  # Fetch email content
        email_content = data[0][1]  # Get the raw email content
        # Parse the raw email content
        msg = email.message_from_bytes(email_content)
        non_excluded_senders.extend(msg['From'])
        # TODO: Find a way to show all the non-excluded senders to ensure nothing desired it lost to the void


        imaplib.IMAP4.store(uid, "+FLAGS", "\\Deleted")



imap_server.close()
imap_server.logout()







