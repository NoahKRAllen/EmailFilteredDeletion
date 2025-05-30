from flask import Flask, render_template, request, redirect, url_for, session
from email_utils import fetch_unapproved_senders, load_safe_list, save_safe_list
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        session['email'] = request.form['email']
        session['password'] = request.form['password']
        stored_safe = load_safe_list()
        user_safe = request.form['safe_list'].splitlines()
        user_safe = [email.strip() for email in user_safe if email.strip()]
        merged_safe = list(set(stored_safe + user_safe))
        session['safe_list'] = merged_safe

        save_safe_list(merged_safe)

        scan_limit = request.form.get('scan_limit', '500')

        # Get unapproved senders
        unapproved = fetch_unapproved_senders(
            session['email'], session['password'], session['safe_list'], scan_limit
        )
        session['unapproved'] = unapproved
        return redirect(url_for('preview'))
    return render_template('index.html')

@app.route('/preview', methods=['GET', 'POST'])
def preview():
    if request.method == 'POST':
        # Optional: expand safe list from preview
        updated_safe_list = request.form.getlist('keep')
        session['safe_list'].extend(updated_safe_list)
        session['safe_list'] = list(set(session['safe_list'])) #Removes any duplicates

        save_safe_list(session['safe_list'])

        # Refresh preview
        unapproved = fetch_unapproved_senders(
            session['email'], session['password'], session['safe_list']
        )
        session['unapproved'] = unapproved
    return render_template(
        'preview.html',
        unapproved=session.get('unapproved', []),
        safe_list=session.get('safe_list', []),
    )

if __name__ == '__main__':
    app.run(debug=True)