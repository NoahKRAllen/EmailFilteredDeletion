from flask import Flask, render_template, request, redirect, url_for, session
from email_utils import fetch_unapproved_senders
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        session['email'] = request.form['email']
        session['password'] = request.form['password']
        safe_list = request.form['safe_list'].splitlines()
        session['safe_list'] = [email.strip() for email in safe_list if email.strip()]

        # Get unapproved senders
        unapproved = fetch_unapproved_senders(
            session['email'], session['password'], session['safe_list']
        )
        session['unapproved'] = unapproved
        return redirect('preview.html')
    return render_template('index.html')

@app.route('/preview', methods=['GET', 'POST'])
def preview():
    if request.method == 'POST':
        # Optional: expand safe list from preview
        updated_safe_list = request.form.getlist('keep')
        session['safe_list'].extend(updated_safe_list)
        session['safe_list'] = list(set(session['safe_list'])) #Removes any duplicates

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