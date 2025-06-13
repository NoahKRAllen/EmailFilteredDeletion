from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from gmail_utils import fetch_unapproved_senders,load_safe_list,save_safe_list, delete_unapproved_emails, delete_unapproved_emails_dry_run, setup_gmail_api
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)


@app.route('/')
def index():
    return render_template('gmail_index.html')


@app.route('/setup')
def setup():
    """Show setup instructions for Gmail API."""
    setup_gmail_api()
    return render_template('setup.html')


@app.route('/scan', methods=['POST'])
def scan_emails():
    """Scan emails and find unapproved senders."""
    try:
        # Load existing safe list
        stored_safe = load_safe_list()

        # Get user-provided safe list
        user_safe = request.form.get('safe_list', '').splitlines()
        user_safe = [email.strip() for email in user_safe if email.strip()]

        # Merge safe lists
        merged_safe = list(set(stored_safe + user_safe))
        session['safe_list'] = merged_safe
        save_safe_list(merged_safe)

        # Get scan limit
        scan_limit = request.form.get('scan_limit', '500')
        session['scan_limit'] = scan_limit

        # Fetch unapproved senders using Gmail API
        unapproved = fetch_unapproved_senders(merged_safe, scan_limit)
        session['unapproved'] = unapproved

        return redirect(url_for('preview'))

    except FileNotFoundError as e:
        return render_template('error.html',
                               error="Gmail API not set up",
                               message=str(e))
    except Exception as e:
        return render_template('error.html',
                               error="Scanning failed",
                               message=str(e))


@app.route('/preview', methods=['GET', 'POST'])
def preview():
    """Preview unapproved senders and allow safe list updates."""
    # Load values
    stored_safe = load_safe_list()
    unapproved_senders = session.get('unapproved', [])
    scan_limit = session.get('scan_limit', '500')

    # Handle new safe-list additions from the preview page
    if request.method == 'POST':
        newly_added_safe = request.form.getlist('keep')

        if newly_added_safe:
            # Add to stored safe list
            stored_safe.extend(newly_added_safe)
            stored_safe = list(set(stored_safe))  # Remove duplicates
            save_safe_list(stored_safe)

            # Filter out newly safe senders from unapproved list
            original_count = len(unapproved_senders)

            unapproved_senders = [
                sender for sender in unapproved_senders
                if not any(safe.lower() in sender.lower() for safe in newly_added_safe)
            ]

            session['unapproved'] = unapproved_senders

            print(f"Filtered unapproved list: {original_count} -> {len(unapproved_senders)} senders")
            print(f"Newly added safe senders: {newly_added_safe}")

    return render_template(
        "gmail_preview.html",
        unapproved=unapproved_senders,
        safe_list=stored_safe,
        scan_limit=scan_limit
    )


@app.route('/delete_emails', methods=['POST'])
def delete_emails():
    """Delete emails from unapproved senders."""
    try:
        scan_limit = session.get('scan_limit', '500')
        safe_list = load_safe_list()  # Pull fresh from file

        deleted_count = delete_unapproved_emails(safe_list, scan_limit)

        session.clear()

        return render_template('result.html',
                               action="Deleted",
                               count=deleted_count,
                               dry_run=False)

    except Exception as e:
        return render_template('error.html',
                               error="Deletion failed",
                               message=str(e))


@app.route('/delete_emails_dry_run', methods=['POST'])
def delete_emails_dry_run():
    """Dry run - count emails that would be deleted."""
    try:
        scan_limit = session.get('scan_limit', '500')
        safe_list = load_safe_list()  # Pull fresh from file

        would_delete_count = delete_unapproved_emails_dry_run(safe_list, scan_limit)

        return render_template('result.html',
                               action="Would delete",
                               count=would_delete_count,
                               dry_run=True)

    except Exception as e:
        return render_template('error.html',
                               error="Dry run failed",
                               message=str(e))


@app.route('/api/check_setup')
def check_setup():
    """API endpoint to check if Gmail API is set up."""
    credentials_exists = os.path.exists('credentials.json')
    return jsonify({
        'credentials_exists': credentials_exists,
        'setup_complete': credentials_exists
    })


if __name__ == '__main__':
    app.run(debug=True)