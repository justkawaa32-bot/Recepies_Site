
from flask import Flask, g, request, jsonify, session, render_template, redirect
from flask_cors import CORS
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import json
import uuid
from datetime import timedelta
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from urllib.error import URLError, HTTPError
from functools import lru_cache

DB_PATH = 'recipes.db'
UPLOAD_DIR = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'}
ROLE_USER = 'user'
ROLE_MODERATOR = 'moderator'
ROLE_ADMIN = 'admin'
STAFF_ROLES = {ROLE_ADMIN, ROLE_MODERATOR}
ALL_ROLES = {ROLE_USER, ROLE_MODERATOR, ROLE_ADMIN}

MEALDB_BASE = "https://www.themealdb.com/api/json/v1/1"

def _fetch_json(url: str, timeout_s: int = 10):
    req = Request(url, headers={"User-Agent": "recipes-site/1.0"})
    with urlopen(req, timeout=timeout_s) as resp:
        data = resp.read().decode("utf-8")
        return json.loads(data)

@lru_cache(maxsize=6000)
def _translate_to_ru(text: str) -> str:
    source = (text or "").strip()
    if not source:
        return ""
    try:
        url = "https://translate.googleapis.com/translate_a/single?" + urlencode({
            "client": "gtx",
            "sl": "auto",
            "tl": "ru",
            "dt": "t",
            "q": source,
        })
        data = _fetch_json(url, timeout_s=12)
        if isinstance(data, list) and data and isinstance(data[0], list):
            translated = "".join(part[0] for part in data[0] if isinstance(part, list) and part and part[0])
            return translated.strip() or source
    except Exception:
        pass
    return source

@lru_cache(maxsize=2000)
def _translate_lines_to_ru(blob: str) -> str:
    source = (blob or "").strip()
    if not source:
        return ""
    return _translate_to_ru(source)

def _mealdb_to_recipe(meal):
    if not meal:
        return None
    meal_id = meal.get("idMeal")
    title = meal.get("strMeal") or ""
    category = meal.get("strCategory") or ""
    area = meal.get("strArea") or ""
    tags = meal.get("strTags") or ""
    img = meal.get("strMealThumb") or ""
    youtube = meal.get("strYoutube") or ""
    source = meal.get("strSource") or ""
    instructions = (meal.get("strInstructions") or "").strip()

    meta_blob = "\n".join([title, category, area, tags]).strip()
    meta_ru_blob = _translate_lines_to_ru(meta_blob) if meta_blob else ""
    meta_parts = meta_ru_blob.splitlines() if meta_ru_blob else []
    title_ru = (meta_parts[0] if len(meta_parts) > 0 else _translate_to_ru(title))
    category_ru = (meta_parts[1] if len(meta_parts) > 1 else (_translate_to_ru(category) if category else ""))
    area_ru = (meta_parts[2] if len(meta_parts) > 2 else (_translate_to_ru(area) if area else ""))
    tags_ru = (meta_parts[3] if len(meta_parts) > 3 else (_translate_to_ru(tags) if tags else ""))
    instructions_ru = _translate_to_ru(instructions) if instructions else ""

    ingredients_raw = []
    for i in range(1, 21):
        ing = (meal.get(f"strIngredient{i}") or "").strip()
        meas = (meal.get(f"strMeasure{i}") or "").strip()
        if ing:
            line = f"{ing}{(' — ' + meas) if meas else ''}"
            ingredients_raw.append(line)
    ingredients_blob = "\n".join(ingredients_raw)
    ingredients_ru_blob = _translate_lines_to_ru(ingredients_blob) if ingredients_blob else ""
    ingredients = [s.strip() for s in ingredients_ru_blob.splitlines() if s.strip()] if ingredients_ru_blob else []

    steps = [s.strip() for s in instructions_ru.splitlines() if s.strip()] if instructions_ru else []

    meta_bits = [b for b in [category_ru, area_ru, tags_ru] if b]
    subtitle = " • ".join(meta_bits) if meta_bits else None

    return {
        "id": f"mealdb:{meal_id}",
        "meal_id": meal_id,
        "title": title_ru,
        "category": category_ru or None,
        "area": area_ru or None,
        "tags": tags_ru or None,
        "subtitle": subtitle,
        "time_min": None,
        "level": None,
        "img": img,
        "ingredients": ingredients,
        "steps": steps,
        "instructions": instructions_ru,
        "youtube": youtube or None,
        "source": source or None,
        "provider": "TheMealDB",
    }

def _meal_has_ingredient(meal, ingredient_query: str) -> bool:
    q = (ingredient_query or "").strip().lower()
    if not q:
        return True
    for i in range(1, 21):
        ing = (meal.get(f"strIngredient{i}") or "").strip().lower()
        if ing and q in ing:
            return True
    return False

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    if not os.path.exists(DB_PATH):
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.executescript('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user'
            );

            CREATE TABLE recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                category TEXT,
                time_min INTEGER,
                level TEXT,
                img TEXT,
                is_public INTEGER NOT NULL DEFAULT 1,
                ingredients TEXT,
                steps TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            ''')
            cur.execute(
                "INSERT OR IGNORE INTO users (username, password_hash, role) VALUES (?,?,?)",
                ('user', generate_password_hash('12345678'), ROLE_ADMIN)
            )
            conn.commit()
    ensure_schema()

def ensure_schema():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(users)")
        columns = {row[1] for row in cur.fetchall()}
        if 'role' not in columns:
            cur.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
        cur.execute("UPDATE users SET role=? WHERE role IS NULL OR role=''", (ROLE_USER,))
        cur.execute("UPDATE users SET role=? WHERE username=? AND role=?", (ROLE_ADMIN, 'user', ROLE_USER))
        cur.execute("PRAGMA table_info(recipes)")
        columns = {row[1] for row in cur.fetchall()}
        if 'is_public' not in columns:
            cur.execute("ALTER TABLE recipes ADD COLUMN is_public INTEGER NOT NULL DEFAULT 1")
        cur.execute("UPDATE recipes SET is_public=1 WHERE is_public IS NULL")
        cur.execute("SELECT id FROM users WHERE username=?", ('admin',))
        if cur.fetchone() is None:
            cur.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
                ('admin', generate_password_hash('admin'), ROLE_ADMIN)
            )

        cur.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                rating INTEGER NOT NULL,
                text TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(recipe_id, user_id),
                FOREIGN KEY(recipe_id) REFERENCES recipes(id),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_reviews_recipe ON reviews(recipe_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_reviews_user ON reviews(user_id)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                recipe_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(user_id, recipe_id),
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(recipe_id) REFERENCES recipes(id)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_fav_user ON favorites(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_fav_recipe ON favorites(recipe_id)")

        # Trigram search (FTS5). Used for fast fuzzy-ish matching.
        # If FTS5 is unavailable in the build, routes will fall back to LIKE search.
        cur.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS recipes_fts
            USING fts5(
                title,
                category,
                level,
                ingredients,
                steps,
                content='recipes',
                content_rowid='id',
                tokenize='trigram'
            )
        """)
        cur.executescript("""
            CREATE TRIGGER IF NOT EXISTS recipes_ai AFTER INSERT ON recipes BEGIN
                INSERT INTO recipes_fts(rowid, title, category, level, ingredients, steps)
                VALUES (new.id, new.title, new.category, new.level, new.ingredients, new.steps);
            END;
            CREATE TRIGGER IF NOT EXISTS recipes_ad AFTER DELETE ON recipes BEGIN
                INSERT INTO recipes_fts(recipes_fts, rowid, title, category, level, ingredients, steps)
                VALUES('delete', old.id, old.title, old.category, old.level, old.ingredients, old.steps);
            END;
            CREATE TRIGGER IF NOT EXISTS recipes_au AFTER UPDATE ON recipes BEGIN
                INSERT INTO recipes_fts(recipes_fts, rowid, title, category, level, ingredients, steps)
                VALUES('delete', old.id, old.title, old.category, old.level, old.ingredients, old.steps);
                INSERT INTO recipes_fts(rowid, title, category, level, ingredients, steps)
                VALUES (new.id, new.title, new.category, new.level, new.ingredients, new.steps);
            END;
        """)
        # Ensure index is populated for existing DBs
        try:
            cur.execute("INSERT INTO recipes_fts(recipes_fts) VALUES('rebuild')")
        except sqlite3.OperationalError:
            # e.g. if fts5 is missing
            pass
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

def normalize_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            loaded = json.loads(stripped)
            if isinstance(loaded, list):
                return [str(v) for v in loaded if str(v).strip()]
        except json.JSONDecodeError:
            pass
        if '\n' in stripped:
            parts = stripped.splitlines()
        else:
            parts = stripped.split(',')
        return [p.strip() for p in parts if p.strip()]
    return [str(value)]

def coerce_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

def _fts_quote(value: str) -> str:
    # FTS query syntax is sensitive to special characters.
    # Quote the query to treat it as a literal term/phrase.
    cleaned = (value or '').replace('"', ' ').strip()
    return f"\"{cleaned}\"" if cleaned else ""

def _build_recipe_filters(args):
    q = (args.get('q') or '').strip()
    category = (args.get('category') or '').strip()
    level = (args.get('level') or '').strip()
    time_max = coerce_int(args.get('time_max'))

    clauses = []
    params = []

    if q:
        # Trigram FTS is great for 3+ chars; for 1-2 chars use LIKE so "по одной букве" works.
        if len(q) < 3:
            like = f"%{q.lower()}%"
            clauses.append(
                "(LOWER(r.title) LIKE ? OR LOWER(COALESCE(r.category,'')) LIKE ? OR LOWER(COALESCE(r.level,'')) LIKE ? OR LOWER(COALESCE(r.ingredients,'')) LIKE ? OR LOWER(COALESCE(r.steps,'')) LIKE ?)"
            )
            params.extend([like, like, like, like, like])
        else:
            fts_q = _fts_quote(q)
            if fts_q:
                clauses.append("EXISTS (SELECT 1 FROM recipes_fts fts WHERE fts.rowid = r.id AND recipes_fts MATCH ?)")
                params.append(fts_q)

    if category:
        clauses.append("LOWER(COALESCE(r.category,'')) = LOWER(?)")
        params.append(category)

    if level:
        clauses.append("LOWER(COALESCE(r.level,'')) = LOWER(?)")
        params.append(level)

    if time_max is not None:
        clauses.append("(r.time_min IS NOT NULL AND r.time_min <= ?)")
        params.append(time_max)

    return clauses, params

def allowed_file(filename):
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_EXTENSIONS

def get_current_role():
    role = session.get('role')
    if role:
        return role
    user_id = session.get('user_id')
    if not user_id:
        return None
    db = get_db()
    row = db.execute('SELECT role FROM users WHERE id=?', (user_id,)).fetchone()
    if row:
        session['role'] = row['role']
        return row['role']
    return None

def is_staff():
    role = get_current_role()
    return role in STAFF_ROLES

def is_admin():
    return get_current_role() == ROLE_ADMIN

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/auth')
def auth():
    return render_template('auth.html')

@app.route('/my-recipes')
def my_recipes_page():
    if 'user_id' not in session:
        return redirect('/auth')
    return render_template('my_recipes.html')

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
        cur.execute(
            'INSERT INTO users (username, password_hash, role) VALUES (?,?,?)',
            (username, generate_password_hash(password), ROLE_USER)
        )
        db.commit()
        return jsonify({'ok': True})
    except sqlite3.IntegrityError:
        return jsonify({'ok': False, 'error': 'Пользователь уже существует'}), 400


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        return jsonify(ok=False), 400
    db = get_db()
    user = db.execute(
        'SELECT * FROM users WHERE username=?', (username,)
    ).fetchone()
    if user and check_password_hash(user['password_hash'], password):
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
        return jsonify(ok=True)
    return jsonify(ok=False), 401

@app.route('/api/recipes')
def recipes():
    db = get_db()
    page = coerce_int(request.args.get('page')) or 1
    page_size = coerce_int(request.args.get('page_size')) or 15
    page = max(1, page)
    page_size = max(1, min(50, page_size))
    offset = (page - 1) * page_size
    clauses, params = _build_recipe_filters(request.args)
    where = ["r.is_public=1"]
    where.extend(clauses)
    user_id = session.get('user_id')
    where_sql = " AND ".join(where)
    sql = f"""
        SELECT
            r.*,
            u.username,
            ROUND(COALESCE(rv.avg_rating, 0), 2) AS avg_rating,
            COALESCE(rv.reviews_count, 0) AS reviews_count,
            CASE WHEN ? IS NOT NULL AND f.id IS NOT NULL THEN 1 ELSE 0 END AS is_favorite
        FROM recipes r
        JOIN users u ON r.user_id=u.id
        LEFT JOIN (
            SELECT recipe_id, AVG(rating) AS avg_rating, COUNT(*) AS reviews_count
            FROM reviews
            GROUP BY recipe_id
        ) rv ON rv.recipe_id = r.id
        LEFT JOIN favorites f ON f.recipe_id = r.id AND f.user_id = ?
        WHERE {where_sql}
        ORDER BY r.id DESC
        LIMIT ? OFFSET ?
    """
    count_sql = f"SELECT COUNT(*) AS total_count FROM recipes r WHERE {where_sql}"
    try:
        rows = db.execute(sql, (user_id, user_id, *params, page_size, offset)).fetchall()
        total_count = int(db.execute(count_sql, params).fetchone()["total_count"])
    except sqlite3.OperationalError:
        # Fallback if FTS5/trigram isn't available
        raw_q = (request.args.get('q') or '').strip()
        clauses2 = []
        params2 = []
        if raw_q:
            like = f"%{raw_q.lower()}%"
            clauses2.append("(LOWER(r.title) LIKE ? OR LOWER(COALESCE(r.category,'')) LIKE ? OR LOWER(COALESCE(r.level,'')) LIKE ? OR LOWER(COALESCE(r.ingredients,'')) LIKE ? OR LOWER(COALESCE(r.steps,'')) LIKE ?)")
            params2.extend([like, like, like, like, like])
        # keep other filters
        category = (request.args.get('category') or '').strip()
        level = (request.args.get('level') or '').strip()
        time_max = coerce_int(request.args.get('time_max'))
        if category:
            clauses2.append("LOWER(COALESCE(r.category,'')) = LOWER(?)")
            params2.append(category)
        if level:
            clauses2.append("LOWER(COALESCE(r.level,'')) = LOWER(?)")
            params2.append(level)
        if time_max is not None:
            clauses2.append("(r.time_min IS NOT NULL AND r.time_min <= ?)")
            params2.append(time_max)
        where2 = ["r.is_public=1", *clauses2]
        where2_sql = " AND ".join(where2)
        sql2 = sql.replace(f"WHERE {where_sql}", f"WHERE {where2_sql}")
        rows = db.execute(sql2, (user_id, user_id, *params2, page_size, offset)).fetchall()
        count_sql2 = f"SELECT COUNT(*) AS total_count FROM recipes r WHERE {where2_sql}"
        total_count = int(db.execute(count_sql2, params2).fetchone()["total_count"])
    result = []
    for row in rows:
        item = dict(row)
        item['ingredients'] = normalize_list(item.get('ingredients'))
        item['steps'] = normalize_list(item.get('steps'))
        result.append(item)
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    return jsonify(
        ok=True,
        items=result,
        page=page,
        page_size=page_size,
        total_count=total_count,
        total_pages=total_pages,
    )

@app.route('/api/my-recipes')
def my_recipes():
    if 'user_id' not in session:
        return jsonify(ok=False), 401
    db = get_db()
    clauses, params = _build_recipe_filters(request.args)
    where = ["r.user_id=?"]
    where.extend(clauses)
    user_id = session['user_id']
    sql = f"""
        SELECT
            r.*,
            u.username,
            ROUND(COALESCE(rv.avg_rating, 0), 2) AS avg_rating,
            COALESCE(rv.reviews_count, 0) AS reviews_count,
            CASE WHEN f.id IS NOT NULL THEN 1 ELSE 0 END AS is_favorite
        FROM recipes r
        JOIN users u ON r.user_id=u.id
        LEFT JOIN (
            SELECT recipe_id, AVG(rating) AS avg_rating, COUNT(*) AS reviews_count
            FROM reviews
            GROUP BY recipe_id
        ) rv ON rv.recipe_id = r.id
        LEFT JOIN favorites f ON f.recipe_id = r.id AND f.user_id = ?
        WHERE {' AND '.join(where)}
        ORDER BY r.id DESC
    """
    try:
        rows = db.execute(sql, (user_id, user_id, *params)).fetchall()
    except sqlite3.OperationalError:
        raw_q = (request.args.get('q') or '').strip()
        clauses2 = []
        params2 = []
        if raw_q:
            like = f"%{raw_q.lower()}%"
            clauses2.append("(LOWER(r.title) LIKE ? OR LOWER(COALESCE(r.category,'')) LIKE ? OR LOWER(COALESCE(r.level,'')) LIKE ? OR LOWER(COALESCE(r.ingredients,'')) LIKE ? OR LOWER(COALESCE(r.steps,'')) LIKE ?)")
            params2.extend([like, like, like, like, like])
        category = (request.args.get('category') or '').strip()
        level = (request.args.get('level') or '').strip()
        time_max = coerce_int(request.args.get('time_max'))
        if category:
            clauses2.append("LOWER(COALESCE(r.category,'')) = LOWER(?)")
            params2.append(category)
        if level:
            clauses2.append("LOWER(COALESCE(r.level,'')) = LOWER(?)")
            params2.append(level)
        if time_max is not None:
            clauses2.append("(r.time_min IS NOT NULL AND r.time_min <= ?)")
            params2.append(time_max)
        where2 = ["r.user_id=?", *clauses2]
        sql2 = sql.replace(f"WHERE {' AND '.join(where)}", f"WHERE {' AND '.join(where2)}")
        rows = db.execute(sql2, (user_id, user_id, *params2)).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item['ingredients'] = normalize_list(item.get('ingredients'))
        item['steps'] = normalize_list(item.get('steps'))
        result.append(item)
    return jsonify(result)

@app.route('/recipe/<int:recipe_id>')
def recipe_detail(recipe_id):
    db = get_db()
    row = db.execute(
        """
        SELECT
            r.*,
            u.username,
            ROUND(COALESCE(rv.avg_rating, 0), 2) AS avg_rating,
            COALESCE(rv.reviews_count, 0) AS reviews_count
        FROM recipes r
        JOIN users u ON r.user_id=u.id
        LEFT JOIN (
            SELECT recipe_id, AVG(rating) AS avg_rating, COUNT(*) AS reviews_count
            FROM reviews
            GROUP BY recipe_id
        ) rv ON rv.recipe_id = r.id
        WHERE r.id=?
        """,
        (recipe_id,)
    ).fetchone()
    if row is None:
        return render_template('recipe.html', recipe=None), 404
    recipe = dict(row)
    recipe['ingredients'] = normalize_list(recipe.get('ingredients'))
    recipe['steps'] = normalize_list(recipe.get('steps'))
    return render_template('recipe.html', recipe=recipe, is_staff=is_staff())

@app.route('/add')
def add_recipe_page():
    if 'user_id' not in session:
        return redirect('/auth')
    return render_template('add_recipe.html')

@app.route('/edit/<int:recipe_id>')
def edit_recipe_page(recipe_id):
    if not is_staff():
        return redirect('/')
    return render_template('edit_recipe.html', recipe_id=recipe_id)

@app.route('/admin/users')
def admin_users_page():
    if not is_admin():
        return redirect('/')
    return render_template('admin_users.html')

@app.route('/api/recipes/<int:recipe_id>')
def get_recipe(recipe_id):
    db = get_db()
    row = db.execute(
        """
        SELECT
            r.*,
            u.username,
            ROUND(COALESCE(rv.avg_rating, 0), 2) AS avg_rating,
            COALESCE(rv.reviews_count, 0) AS reviews_count
        FROM recipes r
        JOIN users u ON r.user_id=u.id
        LEFT JOIN (
            SELECT recipe_id, AVG(rating) AS avg_rating, COUNT(*) AS reviews_count
            FROM reviews
            GROUP BY recipe_id
        ) rv ON rv.recipe_id = r.id
        WHERE r.id=?
        """,
        (recipe_id,)
    ).fetchone()
    if row is None:
        return jsonify(ok=False), 404
    item = dict(row)
    item['ingredients'] = normalize_list(item.get('ingredients'))
    item['steps'] = normalize_list(item.get('steps'))
    return jsonify(item)

@app.route('/api/recipes', methods=['POST'])
def add_recipe():
    if 'user_id' not in session:
        return jsonify(ok=False), 401
    data = {}
    image = None
    if request.is_json:
        data = request.get_json() or {}
    else:
        data = request.form.to_dict()
        image = request.files.get('image')

    title = (data.get('title') or '').strip()
    if not title:
        return jsonify(ok=False, error='Название обязательно'), 400
    category = (data.get('category') or '').strip() or None
    time_min = coerce_int(data.get('time_min') or data.get('time'))
    level = (data.get('level') or '').strip() or None
    img = (data.get('img') or '').strip() or None
    ingredients = normalize_list(data.get('ingredients'))
    steps = normalize_list(data.get('steps'))

    if image and image.filename:
        if not allowed_file(image.filename):
            return jsonify(ok=False, error='Недопустимый формат изображения'), 400
        filename = f"{uuid.uuid4().hex}_{secure_filename(image.filename)}"
        image.save(os.path.join(UPLOAD_DIR, filename))
        img = f"/static/uploads/{filename}"

    db = get_db()
    db.execute(
        'INSERT INTO recipes (user_id,title,category,time_min,level,img,is_public,ingredients,steps) VALUES (?,?,?,?,?,?,?,?,?)',
        (
            session['user_id'],
            title,
            category,
            time_min,
            level,
            img,
            1 if is_staff() else 0,
            json.dumps(ingredients, ensure_ascii=True),
            json.dumps(steps, ensure_ascii=True),
        )
    )
    db.commit()
    return jsonify(ok=True)

@app.route('/api/recipes/<int:recipe_id>', methods=['POST', 'PUT', 'DELETE'])
def update_recipe(recipe_id):
    if not is_staff():
        return jsonify(ok=False), 403
    if request.method == 'DELETE':
        db = get_db()
        row = db.execute('SELECT id FROM recipes WHERE id=?', (recipe_id,)).fetchone()
        if row is None:
            return jsonify(ok=False), 404
        db.execute('DELETE FROM recipes WHERE id=?', (recipe_id,))
        db.commit()
        return jsonify(ok=True)

    data = {}
    image = None
    if request.is_json:
        data = request.get_json() or {}
    else:
        data = request.form.to_dict()
        image = request.files.get('image')

    title = (data.get('title') or '').strip()
    if not title:
        return jsonify(ok=False, error='Название обязательно'), 400
    category = (data.get('category') or '').strip() or None
    time_min = coerce_int(data.get('time_min') or data.get('time'))
    level = (data.get('level') or '').strip() or None
    img = (data.get('img') or '').strip() or None
    ingredients = normalize_list(data.get('ingredients'))
    steps = normalize_list(data.get('steps'))

    if image and image.filename:
        if not allowed_file(image.filename):
            return jsonify(ok=False, error='Недопустимый формат изображения'), 400
        filename = f"{uuid.uuid4().hex}_{secure_filename(image.filename)}"
        image.save(os.path.join(UPLOAD_DIR, filename))
        img = f"/static/uploads/{filename}"

    db = get_db()
    existing = db.execute('SELECT id, img FROM recipes WHERE id=?', (recipe_id,)).fetchone()
    if existing is None:
        return jsonify(ok=False), 404
    if not img:
        img = existing['img']

    db.execute(
        'UPDATE recipes SET title=?, category=?, time_min=?, level=?, img=?, ingredients=?, steps=? WHERE id=?',
        (
            title,
            category,
            time_min,
            level,
            img,
            json.dumps(ingredients, ensure_ascii=True),
            json.dumps(steps, ensure_ascii=True),
            recipe_id,
        )
    )
    db.commit()
    return jsonify(ok=True)

@app.route('/api/admin/users')
def admin_list_users():
    if not is_admin():
        return jsonify(ok=False), 403
    db = get_db()
    rows = db.execute('SELECT id, username, role FROM users ORDER BY username').fetchall()
    return jsonify(ok=True, users=[dict(r) for r in rows])

@app.route('/api/admin/users/<int:user_id>', methods=['POST'])
def admin_update_user(user_id):
    if not is_admin():
        return jsonify(ok=False), 403
    data = request.get_json() or {}
    role = (data.get('role') or '').strip()
    if role not in ALL_ROLES:
        return jsonify(ok=False, error='Недопустимая роль'), 400
    db = get_db()
    row = db.execute('SELECT id FROM users WHERE id=?', (user_id,)).fetchone()
    if row is None:
        return jsonify(ok=False), 404
    db.execute('UPDATE users SET role=? WHERE id=?', (role, user_id))
    db.commit()
    return jsonify(ok=True)

@app.route('/api/whoami')
def whoami():
    if 'user_id' in session:
        return jsonify({'ok': True, 'user': {'username': session.get('username'), 'role': get_current_role()}})
    return jsonify({'ok': False})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})


@app.route('/api/mealdb/search')
def mealdb_search():
    q = (request.args.get('q') or '').strip()
    category = (request.args.get('category') or '').strip()
    area = (request.args.get('area') or '').strip()
    ingredient = (request.args.get('ingredient') or '').strip()

    if not q and not category and not area and not ingredient:
        return jsonify(ok=True, recipes=[])

    def _fetch_ids(param_name, value):
        if not value:
            return None
        url = f"{MEALDB_BASE}/filter.php?{urlencode({param_name: value})}"
        data = _fetch_json(url)
        meals = data.get("meals") or []
        return {str(m.get("idMeal")) for m in meals if m.get("idMeal")}

    try:
        id_sets = []
        by_category = _fetch_ids('c', category)
        if by_category is not None:
            id_sets.append(by_category)
        by_area = _fetch_ids('a', area)
        if by_area is not None:
            id_sets.append(by_area)
        by_ingredient = _fetch_ids('i', ingredient)
        if by_ingredient is not None:
            id_sets.append(by_ingredient)

        candidate_ids = None
        if id_sets:
            candidate_ids = set.intersection(*id_sets) if len(id_sets) > 1 else id_sets[0]
            if not candidate_ids:
                return jsonify(ok=True, recipes=[])

        meals = []
        if q:
            search_url = f"{MEALDB_BASE}/search.php?{urlencode({'s': q})}"
            data = _fetch_json(search_url)
            meals = data.get("meals") or []
            if candidate_ids is not None:
                meals = [m for m in meals if str(m.get("idMeal")) in candidate_ids]
        else:
            ids = list(candidate_ids or [])
            ids = ids[:60]
            for meal_id in ids:
                lookup_url = f"{MEALDB_BASE}/lookup.php?{urlencode({'i': meal_id})}"
                data = _fetch_json(lookup_url)
                found = data.get("meals") or []
                if found:
                    meals.append(found[0])

        if category:
            meals = [m for m in meals if (m.get("strCategory") or "").strip().lower() == category.lower()]
        if area:
            meals = [m for m in meals if (m.get("strArea") or "").strip().lower() == area.lower()]
        if ingredient:
            meals = [m for m in meals if _meal_has_ingredient(m, ingredient)]

        recipes = []
        for m in meals:
            r = _mealdb_to_recipe(m)
            if r:
                recipes.append(r)
        return jsonify(ok=True, recipes=recipes)
    except (URLError, HTTPError, TimeoutError, json.JSONDecodeError):
        return jsonify(ok=False, error="TheMealDB недоступен"), 502


@app.route('/api/mealdb/random')
def mealdb_random():
    url = f"{MEALDB_BASE}/random.php"
    try:
        data = _fetch_json(url)
    except (URLError, HTTPError, TimeoutError, json.JSONDecodeError):
        return jsonify(ok=False, error="TheMealDB недоступен"), 502
    meals = data.get("meals") or []
    recipes = []
    for m in meals:
        r = _mealdb_to_recipe(m)
        if r:
            recipes.append(r)
    return jsonify(ok=True, recipes=recipes)


@app.route('/api/mealdb/<meal_id>')
def mealdb_detail(meal_id):
    meal_id = (meal_id or '').strip()
    if not meal_id.isdigit():
        return jsonify(ok=False, error="Bad id"), 400
    url = f"{MEALDB_BASE}/lookup.php?{urlencode({'i': meal_id})}"
    try:
        data = _fetch_json(url)
    except (URLError, HTTPError, TimeoutError, json.JSONDecodeError):
        return jsonify(ok=False, error="TheMealDB недоступен"), 502
    meals = data.get("meals") or []
    if not meals:
        return jsonify(ok=False), 404
    recipe = _mealdb_to_recipe(meals[0])
    return jsonify(ok=True, recipe=recipe)


@app.route('/mealdb/<meal_id>')
def mealdb_page(meal_id):
    return render_template('mealdb_recipe.html', meal_id=meal_id)


@app.route('/api/recipes/<int:recipe_id>/reviews')
def list_reviews(recipe_id):
    db = get_db()
    row = db.execute('SELECT id FROM recipes WHERE id=?', (recipe_id,)).fetchone()
    if row is None:
        return jsonify(ok=False), 404

    reviews = db.execute(
        """
        SELECT
            rv.id,
            rv.recipe_id,
            rv.user_id,
            u.username,
            rv.rating,
            rv.text,
            rv.created_at,
            rv.updated_at
        FROM reviews rv
        JOIN users u ON u.id = rv.user_id
        WHERE rv.recipe_id=?
        ORDER BY rv.updated_at DESC
        """,
        (recipe_id,)
    ).fetchall()

    stats = db.execute(
        "SELECT ROUND(COALESCE(AVG(rating),0),2) AS avg_rating, COUNT(*) AS reviews_count FROM reviews WHERE recipe_id=?",
        (recipe_id,)
    ).fetchone()

    my = None
    if 'user_id' in session:
        my_row = db.execute(
            """
            SELECT id, recipe_id, user_id, rating, text, created_at, updated_at
            FROM reviews
            WHERE recipe_id=? AND user_id=?
            """,
            (recipe_id, session['user_id'])
        ).fetchone()
        if my_row is not None:
            my = dict(my_row)

    return jsonify(
        ok=True,
        avg_rating=float(stats['avg_rating'] or 0),
        reviews_count=int(stats['reviews_count'] or 0),
        reviews=[dict(r) for r in reviews],
        my_review=my
    )


@app.route('/api/recipes/<int:recipe_id>/reviews', methods=['POST', 'PUT', 'DELETE'])
def upsert_review(recipe_id):
    if 'user_id' not in session:
        return jsonify(ok=False), 401

    db = get_db()
    row = db.execute('SELECT id FROM recipes WHERE id=?', (recipe_id,)).fetchone()
    if row is None:
        return jsonify(ok=False), 404

    if request.method == 'DELETE':
        db.execute('DELETE FROM reviews WHERE recipe_id=? AND user_id=?', (recipe_id, session['user_id']))
        db.commit()
        return jsonify(ok=True)

    data = request.get_json(silent=True) or {}
    rating = coerce_int(data.get('rating'))
    text = (data.get('text') or '').strip()

    if rating is None or rating < 1 or rating > 5:
        return jsonify(ok=False, error='Оценка должна быть от 1 до 5'), 400
    if len(text) > 2000:
        return jsonify(ok=False, error='Отзыв слишком длинный'), 400

    now = datetime.now(timezone.utc).isoformat()

    existing = db.execute(
        'SELECT id FROM reviews WHERE recipe_id=? AND user_id=?',
        (recipe_id, session['user_id'])
    ).fetchone()

    if existing is None:
        db.execute(
            """
            INSERT INTO reviews (recipe_id, user_id, rating, text, created_at, updated_at)
            VALUES (?,?,?,?,?,?)
            """,
            (recipe_id, session['user_id'], rating, text or None, now, now)
        )
    else:
        db.execute(
            """
            UPDATE reviews
            SET rating=?, text=?, updated_at=?
            WHERE recipe_id=? AND user_id=?
            """,
            (rating, text or None, now, recipe_id, session['user_id'])
        )
    db.commit()
    return jsonify(ok=True)


@app.route('/api/favorites')
def list_favorites():
    if 'user_id' not in session:
        return jsonify(ok=False), 401
    db = get_db()
    user_id = session['user_id']
    rows = db.execute(
        """
        SELECT
            r.*,
            u.username,
            ROUND(COALESCE(rv.avg_rating, 0), 2) AS avg_rating,
            COALESCE(rv.reviews_count, 0) AS reviews_count,
            1 AS is_favorite
        FROM favorites f
        JOIN recipes r ON r.id = f.recipe_id
        JOIN users u ON u.id = r.user_id
        LEFT JOIN (
            SELECT recipe_id, AVG(rating) AS avg_rating, COUNT(*) AS reviews_count
            FROM reviews
            GROUP BY recipe_id
        ) rv ON rv.recipe_id = r.id
        WHERE f.user_id=?
        ORDER BY f.created_at DESC
        """,
        (user_id,)
    ).fetchall()

    result = []
    for row in rows:
        item = dict(row)
        item['ingredients'] = normalize_list(item.get('ingredients'))
        item['steps'] = normalize_list(item.get('steps'))
        result.append(item)
    return jsonify(ok=True, recipes=result)


@app.route('/api/favorites/<int:recipe_id>', methods=['POST', 'DELETE'])
def toggle_favorite(recipe_id):
    if 'user_id' not in session:
        return jsonify(ok=False), 401

    db = get_db()
    user_id = session['user_id']
    row = db.execute('SELECT id FROM recipes WHERE id=?', (recipe_id,)).fetchone()
    if row is None:
        return jsonify(ok=False), 404

    if request.method == 'DELETE':
        db.execute('DELETE FROM favorites WHERE user_id=? AND recipe_id=?', (user_id, recipe_id))
        db.commit()
        return jsonify(ok=True, is_favorite=False)

    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        'INSERT OR IGNORE INTO favorites (user_id, recipe_id, created_at) VALUES (?,?,?)',
        (user_id, recipe_id, now)
    )
    db.commit()
    return jsonify(ok=True, is_favorite=True)


if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)
