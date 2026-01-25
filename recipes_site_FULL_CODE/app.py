
from flask import Flask, g, request, jsonify, session, send_from_directory, render_template
from flask_cors import CORS
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import timedelta

DB_PATH = 'recipes.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    if not os.path.exists(DB_PATH):
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.executescript('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );

            CREATE TABLE recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                category TEXT,
                time_min INTEGER,
                level TEXT,
                img TEXT,
                ingredients TEXT,
                steps TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            ''')
            cur.execute(
                "INSERT OR IGNORE INTO users (username, password_hash) VALUES (?,?)",
                ('user', generate_password_hash('1234'))
            )
            conn.commit()

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app, supports_credentials=True)
app.secret_key = 'secret_key'
app.permanent_session_lifetime = timedelta(days=7)

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/auth')
def auth():
    return render_template('auth.html')

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    # Добавляем проверку длины пароля
    if not username or not password:
        return jsonify({'ok': False, 'error': 'Поля username и password обязательны'}), 400
    if len(password) < 8:  # Ограничение на длину пароля
        return jsonify({'ok': False, 'error': 'Пароль должен быть не менее 8 символов'}), 400

    db = get_db()
    cur = db.cursor()
    try:
        cur.execute('INSERT INTO users (username, password_hash) VALUES (?,?)', (username, generate_password_hash(password)))
        db.commit()
        return jsonify({'ok': True})
    except sqlite3.IntegrityError:
        return jsonify({'ok': False, 'error': 'Пользователь уже существует'}), 400


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    db = get_db()
    user = db.execute(
        'SELECT * FROM users WHERE username=?', (data['username'],)
    ).fetchone()
    if user and check_password_hash(user['password_hash'], data['password']):
        session['user_id'] = user['id']
        session['username'] = user['username']
        return jsonify(ok=True)
    return jsonify(ok=False), 401

@app.route('/api/recipes')
def recipes():
    db = get_db()
    rows = db.execute(
        'SELECT r.*, u.username FROM recipes r JOIN users u ON r.user_id=u.id'
    ).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/recipes', methods=['POST'])
def add_recipe():
    if 'user_id' not in session:
        return jsonify(ok=False), 401
    data = request.get_json()
    db = get_db()
    db.execute(
        'INSERT INTO recipes (user_id,title,ingredients,steps) VALUES (?,?,?,?)',
        (session['user_id'], data['title'], data['ingredients'], data['steps'])
    )
    db.commit()
    return jsonify(ok=True)

@app.route('/api/whoami')
def whoami():
    if 'user_id' in session:
        return jsonify({'ok': True, 'user': {'username': session.get('username')}})
    return jsonify({'ok': False})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})


if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)
