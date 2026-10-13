"""Queens Twelve — Flask + SQLite. Start production with gunicorn app:app."""
import json
from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
import time
from uuid import uuid4

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException
from queens import evaluate, parse_input, validate_positions


def create_app(database_path=None):
    app = Flask(__name__, static_folder='static', static_url_path='/static')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024
    path = Path(database_path or os.environ.get('DATABASE_PATH', 'data/queens.db'))
    path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect():
        db = sqlite3.connect(path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''
            CREATE TABLE IF NOT EXISTS submissions (
                id TEXT PRIMARY KEY, author TEXT NOT NULL, title TEXT NOT NULL,
                positions TEXT NOT NULL, score INTEGER NOT NULL CHECK(score BETWEEN 0 AND 12),
                conflicts INTEGER NOT NULL, created_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ranking ON submissions(score DESC, created_at ASC, id ASC);
            CREATE TABLE IF NOT EXISTS submit_limits (client TEXT PRIMARY KEY, last_at REAL NOT NULL);
        ''')

    def output(row):
        result = dict(row)
        result['positions'] = json.loads(result['positions'])
        return result

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(ValueError)
    def validation_error(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(HTTPException)
    def http_error(error):
        messages = {413: 'Dữ liệu quá lớn. File tối đa 4 KB.',
                    400: 'Dữ liệu gửi lên không hợp lệ.', 415: 'Hãy gửi dữ liệu JSON.',
                    404: 'Không tìm thấy nội dung này.'}
        return jsonify(error=messages.get(error.code, error.description)), error.code

    @app.errorhandler(sqlite3.Error)
    def database_error(error):
        app.logger.exception('Database error')
        return jsonify(error='Máy chủ đang bận. Vui lòng thử lại sau.'), 503

    @app.get('/')
    def home():
        return app.send_static_file('index.html')

    @app.get('/healthz')
    def health():
        with connect() as db:
            db.execute('SELECT 1 FROM submissions LIMIT 1').fetchone()
        return jsonify(status='ok')

    @app.post('/api/parse')
    def parse():
        body = request.get_json()
        if not isinstance(body, dict):
            raise ValueError('Dữ liệu phải là một đối tượng JSON.')
        return jsonify(evaluate(parse_input(body.get('text'))))

    @app.get('/api/submissions')
    def listing():
        try:
            page = int(request.args.get('page', '1'))
            if not 1 <= page <= 1000000:
                raise ValueError()
        except ValueError:
            raise ValueError('Trang không hợp lệ.')
        q = request.args.get('q', '').strip()[:80]
        # Escape LIKE wildcards. Rank remains global even when searching.
        needle = '%' + q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        where = "WHERE author LIKE ? ESCAPE '\\' OR title LIKE ? ESCAPE '\\'"
        with connect() as db:
            stats = dict(db.execute('SELECT COUNT(*) AS total, COALESCE(MAX(score),0) AS best, '
                                    'COALESCE(SUM(score=12),0) AS perfect FROM submissions').fetchone())
            count = db.execute('SELECT COUNT(*) FROM submissions ' + where, (needle, needle)).fetchone()[0]
            rows = db.execute('WITH ranked AS (SELECT *, ROW_NUMBER() OVER '
                              '(ORDER BY score DESC, created_at ASC, id ASC) AS rank FROM submissions) '
                              'SELECT * FROM ranked ' + where + ' ORDER BY rank LIMIT 12 OFFSET ?',
                              (needle, needle, (page - 1) * 12)).fetchall()
        return jsonify(items=[output(r) for r in rows], page=page, total=count, stats=stats)

    @app.get('/api/submissions/<submission_id>')
    def detail(submission_id):
        with connect() as db:
            row = db.execute('WITH ranked AS (SELECT *, ROW_NUMBER() OVER '
                             '(ORDER BY score DESC, created_at ASC, id ASC) AS rank FROM submissions) '
                             'SELECT * FROM ranked WHERE id=?', (submission_id,)).fetchone()
        if row is None:
            return jsonify(error='Không tìm thấy bài nộp.'), 404
        return jsonify(output(row))

    @app.post('/api/submissions')
    def submit():
        body = request.get_json()
        if not isinstance(body, dict):
            raise ValueError('Dữ liệu phải là một đối tượng JSON.')
        author, title = body.get('author'), body.get('title')
        for value, label, limit in ((author, 'Tên người nộp', 40), (title, 'Tên lời giải', 80)):
            if not isinstance(value, str) or not 2 <= len(value.strip()) <= limit:
                raise ValueError(f'{label} cần từ 2 đến {limit} ký tự.')
            if any(ord(c) < 32 for c in value):
                raise ValueError(f'{label} không được chứa ký tự điều khiển.')
        positions = (parse_input(body['text']) if 'text' in body
                     else validate_positions(body.get('positions')))
        result = evaluate(positions)  # Never trust a client-supplied score.
        now = time.time()
        # Render runs behind a reverse proxy. Its rightmost forwarded address is the connecting client.
        # Enable ONLY behind Render's managed proxy (set in render.yaml).
        client = request.remote_addr or 'unknown'
        if os.environ.get('TRUST_RENDER_PROXY') == '1':
            client = request.headers.get('X-Forwarded-For', client).split(',')[-1].strip()[:128]
        item = dict(id=uuid4().hex, author=author.strip(), title=title.strip(),
                    positions=positions, score=result['score'], conflicts=result['conflicts'],
                    created_at=time.time_ns() // 1_000_000)
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            last = db.execute('SELECT last_at FROM submit_limits WHERE client=?', (client,)).fetchone()
            if last and now - last['last_at'] < 10:
                return jsonify(error='Vui lòng đợi 10 giây giữa hai lần nộp bài.'), 429, {'Retry-After': '10'}
            db.execute('DELETE FROM submit_limits WHERE last_at < ?', (now - 3600,))
            db.execute('INSERT OR REPLACE INTO submit_limits VALUES (?,?)', (client, now))
            db.execute('INSERT INTO submissions VALUES (?,?,?,?,?,?,?)',
                       (item['id'], item['author'], item['title'], json.dumps(positions),
                        item['score'], item['conflicts'], item['created_at']))
        return jsonify(item), 201

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', '8000')))
