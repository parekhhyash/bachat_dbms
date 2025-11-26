from flask import Flask, render_template, request, redirect, url_for, session, g, flash, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

DB_PATH = 'bachat.db'

app = Flask(__name__)
app.secret_key = 'replace-with-a-strong-random-secret'  # CHANGE THIS before deploying

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        conn = get_db_connection()
        g.user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        if not username or not password:
            flash('Fill both fields')
            return redirect(url_for('signup'))
        pw_hash = generate_password_hash(password)
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, pw_hash))
            conn.commit()
            conn.close()
            return render_template('signup_success.html')
        except sqlite3.IntegrityError:
            conn.close()
            flash('Username already taken')
            return redirect(url_for('signup'))
    return render_template('signup.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password_hash'], password):
            session.clear()
            session['user_id'] = user['id']
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# Dashboard
@app.route('/app/dashboard')
def dashboard():
    if g.user is None:
        return redirect(url_for('login'))
    uid = g.user['id']
    conn = get_db_connection()

    month_prefix = datetime.now().strftime('%Y-%m')
    monthly_spent_row = conn.execute(
        "SELECT COALESCE(SUM(amount),0) as total FROM expenses WHERE user_id = ? AND substr(date,1,7) = ?",
        (uid, month_prefix)
    ).fetchone()
    monthly_spent = monthly_spent_row['total'] if monthly_spent_row else 0

    budget = g.user['budget'] if g.user['budget'] is not None else None
    remaining = budget - monthly_spent if budget is not None else None

    row = conn.execute("SELECT date, SUM(amount) as total FROM expenses WHERE user_id = ? GROUP BY date ORDER BY total DESC LIMIT 1", (uid,)).fetchone()
    highest_day = (row['date'], row['total']) if row else (None, 0)

    row2 = conn.execute("SELECT category, SUM(amount) as total FROM expenses WHERE user_id = ? GROUP BY category ORDER BY total DESC LIMIT 1", (uid,)).fetchone()
    highest_cat = (row2['category'], row2['total']) if row2 else (None, 0)

    conn.close()
    return render_template('dashboard.html', monthly_spent=monthly_spent, budget=budget, remaining=remaining, highest_day=highest_day, highest_cat=highest_cat)

@app.route('/app/set_budget', methods=['POST'])
def set_budget():
    if g.user is None:
        return jsonify({'error':'not logged in'}), 401
    try:
        new_budget = float(request.form['budget'])
    except Exception:
        return jsonify({'error':'invalid budget'}), 400
    conn = get_db_connection()
    conn.execute('UPDATE users SET budget = ? WHERE id = ?', (new_budget, g.user['id']))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/app/add_transaction', methods=['POST'])
def add_transaction():
    if g.user is None:
        return redirect(url_for('login'))
    category = request.form['category']
    amount = float(request.form['amount'])
    date = request.form['date']
    note = request.form.get('note','')
    conn = get_db_connection()
    conn.execute('INSERT INTO expenses (user_id, category, amount, date, note) VALUES (?, ?, ?, ?, ?)', (g.user['id'], category, amount, date, note))
    conn.commit()
    conn.close()
    return redirect(url_for('transactions'))

# Transactions page with filtering, edit, delete
@app.route('/app/transactions', methods=['GET'])
def transactions():
    if g.user is None:
        return redirect(url_for('login'))
    uid = g.user['id']
    category = request.args.get('category', type=str)
    month = request.args.get('month', type=str)  # YYYY-MM
    params = [uid]
    query = 'SELECT * FROM expenses WHERE user_id = ?'
    if category:
        query += ' AND category = ?'
        params.append(category)
    if month:
        query += ' AND substr(date,1,7) = ?'
        params.append(month)
    query += ' ORDER BY date DESC'
    conn = get_db_connection()
    rows = conn.execute(query, tuple(params)).fetchall()
    # total
    total_q = 'SELECT COALESCE(SUM(amount),0) as total FROM expenses WHERE user_id = ?'
    total_params = [uid]
    if category:
        total_q += ' AND category = ?'
        total_params.append(category)
    if month:
        total_q += ' AND substr(date,1,7) = ?'
        total_params.append(month)
    total = conn.execute(total_q, tuple(total_params)).fetchone()['total']
    conn.close()
    return render_template('transactions.html', rows=rows, total=total, filter_category=category or '', filter_month=month or '')

@app.route('/app/transactions/delete/<int:tx_id>', methods=['POST'])
def delete_transaction(tx_id):
    if g.user is None:
        return redirect(url_for('login'))
    conn = get_db_connection()
    conn.execute('DELETE FROM expenses WHERE id = ? AND user_id = ?', (tx_id, g.user['id']))
    conn.commit()
    conn.close()
    flash('Transaction deleted')
    return redirect(url_for('transactions'))

@app.route('/app/transactions/edit/<int:tx_id>', methods=['GET','POST'])
def edit_transaction(tx_id):
    if g.user is None:
        return redirect(url_for('login'))
    conn = get_db_connection()
    tx = conn.execute('SELECT * FROM expenses WHERE id = ? AND user_id = ?', (tx_id, g.user['id'])).fetchone()
    if not tx:
        conn.close()
        flash('Transaction not found')
        return redirect(url_for('transactions'))
    if request.method == 'POST':
        category = request.form['category']
        amount = float(request.form['amount'])
        date = request.form['date']
        note = request.form.get('note','')
        conn.execute('UPDATE expenses SET category = ?, amount = ?, date = ?, note = ? WHERE id = ? AND user_id = ?',
                     (category, amount, date, note, tx_id, g.user['id']))
        conn.commit()
        conn.close()
        flash('Transaction updated')
        return redirect(url_for('transactions'))
    conn.close()
    return render_template('edit_transaction.html', tx=tx)

# Analytics & APIs
@app.route('/app/analytics')
def analytics():
    if g.user is None:
        return redirect(url_for('login'))
    return render_template('analytics.html')

@app.route('/api/analytics/category_pie')
def category_pie():
    if g.user is None:
        return jsonify({'labels':[], 'data':[]})
    conn = get_db_connection()
    rows = conn.execute('SELECT category, SUM(amount) as total FROM expenses WHERE user_id = ? GROUP BY category', (g.user['id'],)).fetchall()
    conn.close()
    labels = [r['category'] for r in rows]
    data = [r['total'] for r in rows]
    return jsonify({'labels': labels, 'data': data})

@app.route('/api/analytics/monthly_bar')
def monthly_bar():
    if g.user is None:
        return jsonify({'labels':[], 'data':[]})
    conn = get_db_connection()
    rows = conn.execute("SELECT substr(date,1,7) as month, SUM(amount) as total FROM expenses WHERE user_id = ? GROUP BY month ORDER BY month", (g.user['id'],)).fetchall()
    conn.close()
    labels = [r['month'] for r in rows]
    data = [r['total'] for r in rows]
    return jsonify({'labels': labels, 'data': data})

@app.route('/api/transactions')
def api_transactions():
    if g.user is None:
        return jsonify([])
    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC', (g.user['id'],)).fetchall()
    conn.close()
    out = [dict(r) for r in rows]
    return jsonify(out)

if __name__ == '__main__':
    app.run(debug=True)
