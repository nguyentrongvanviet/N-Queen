import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Keep import-time app data out of the repository and each test isolated.
_import_temp = tempfile.TemporaryDirectory()
os.environ['DATABASE_PATH'] = str(Path(_import_temp.name) / 'import.db')
from app import create_app
from queens import evaluate, parse_input, validate_positions


def solve(n=12):
    def visit(rows):
        if len(rows) == n:
            return [[x+1, y+1] for y,x in enumerate(rows)]
        for x in range(n):
            if all(x != a and abs(x-a) != len(rows)-y for y,a in enumerate(rows)):
                result = visit(rows+[x])
                if result:
                    return result
    return visit([])


PERFECT = solve()
DIAGONAL = [[i,i] for i in range(1,13)]


class RulesTests(unittest.TestCase):
    def test_perfect(self):
        self.assertEqual(evaluate(PERFECT)['score'], 12)
        self.assertEqual(evaluate(PERFECT)['conflicts'], 0)

    def test_diagonal(self):
        self.assertEqual(evaluate(DIAGONAL)['score'], 0)
        self.assertEqual(evaluate(DIAGONAL)['conflicts'], 66)

    def test_partial_score_counts_queens_not_pairs(self):
        result = evaluate([[1,1],[2,2],[5,4]])
        self.assertEqual(result['score'], 1)
        self.assertEqual(result['conflicts'], 1)

    def test_rows_and_columns(self):
        self.assertEqual(evaluate([[1,1],[1,4],[6,4]])['score'], 0)

    def test_empty(self):
        self.assertEqual(evaluate([])['score'], 0)

    def test_parser_formats(self):
        for separator in [' ', '\n', ', ', '\t']:
            text = '\ufeff' + separator.join(str(v) for p in PERFECT for v in p)
            self.assertEqual(evaluate(parse_input(text))['score'], 12)

    def test_bad_inputs(self):
        for text in ['', '1 1 '*8, '1 1 '*12, '0 1 '*12, '13 1 '*12,
                     '1.2 3 '*12, '-1 2 '*12, 'a '*24, '1'*4097, None, '9'*500+' 1 '*23]:
            with self.subTest(text=str(text)[:40]), self.assertRaises(ValueError):
                parse_input(text)

    def test_json_validation(self):
        for positions in [None, {}, 'bad', [[True,1]]*12, [[1.0,1]]*12, [[1]]*12,
                          [[1,1]]*13, [[0,2]]*12, [[1,1]]*12, []]:
            with self.subTest(positions=positions), self.assertRaises(ValueError):
                validate_positions(positions)


class APITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name)/'test.db')
        self.app = create_app(self.path)
        self.app.testing = True
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def submit(self, positions=PERFECT, client=None, **extra):
        return (client or self.client).post('/api/submissions', json={
            'author':'Người chơi', 'title':'Lời giải thử', 'positions':positions, **extra})

    def test_health_and_assets(self):
        for path in ['/', '/healthz', '/static/app.js', '/static/style.css', '/static/crown.svg']:
            with self.client.get(path) as response:
                self.assertEqual(response.status_code, 200)
        with self.client.get('/') as response:
            self.assertIn("script-src 'self'", response.headers['Content-Security-Policy'])

    def test_score_is_recomputed(self):
        response = self.submit(DIAGONAL, score=12, conflicts=0)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['score'], 0)
        self.assertEqual(response.json['conflicts'], 66)

    def test_persistence_and_detail(self):
        response = self.submit()
        self.assertEqual(response.status_code, 201)
        reopened = create_app(self.path).test_client()
        detail = reopened.get('/api/submissions/'+response.json['id'])
        self.assertEqual(detail.json['author'], 'Người chơi')
        self.assertEqual(detail.json['score'], 12)
        self.assertEqual(detail.json['rank'], 1)

    def test_invalid_submission(self):
        for body in [None, [], {}, {'author':'A', 'title':'B', 'positions':PERFECT},
                     {'author':'AB', 'title':'CD', 'positions':DIAGONAL[:-1]},
                     {'author':'A\nB', 'title':'CD', 'positions':PERFECT}]:
            self.assertIn(self.client.post('/api/submissions', json=body).status_code, [400,415])
        self.assertEqual(self.client.get('/api/submissions').json['total'], 0)

    def test_file_import_and_submit(self):
        text = ' '.join(str(v) for p in PERFECT for v in p)
        result = self.client.post('/api/parse', json={'text':text})
        self.assertEqual(result.json['score'], 12)
        self.assertEqual(self.submit(text=text).json['score'], 12)

    def test_rate_limit(self):
        self.assertEqual(self.submit().status_code, 201)
        self.assertEqual(self.submit().status_code, 429)

    def test_concurrent_rate_limit(self):
        def send(_):
            with self.app.test_client() as client:
                return self.submit(client=client).status_code
        with ThreadPoolExecutor(max_workers=4) as pool:
            codes = list(pool.map(send, range(4)))
        self.assertEqual(codes.count(201), 1)
        self.assertEqual(codes.count(429), 3)

    def test_ranking_search_and_pagination(self):
        for i in range(14):
            self.client.post('/api/submissions', json={
                'author':f'Player {i}', 'title':f'Board {i}',
                'positions':PERFECT if i else DIAGONAL},
                environ_overrides={'REMOTE_ADDR':f'10.0.0.{i}'})
        first = self.client.get('/api/submissions').json
        self.assertEqual(first['total'], 14)
        self.assertEqual(len(first['items']), 12)
        self.assertEqual(first['stats']['perfect'], 13)
        self.assertEqual(first['items'][0]['author'], 'Player 1')
        second = self.client.get('/api/submissions?page=2').json
        self.assertEqual(second['items'][-1]['score'], 0)
        filtered = self.client.get('/api/submissions?q=Player%200').json
        self.assertEqual(filtered['items'][0]['rank'], 14)
        self.assertEqual(self.client.get('/api/submissions?q=%25').json['total'], 0)
        self.assertEqual(self.client.get('/api/submissions?page=no').status_code, 400)

    def test_missing_and_large(self):
        self.assertEqual(self.client.get('/api/submissions/missing').status_code, 404)
        self.assertEqual(self.client.post('/api/parse', json={'text':'a'*20000}).status_code, 413)

    def test_names_stored_as_data(self):
        name='<script>alert(1)</script>'
        self.assertEqual(self.submit(author=name).json['author'], name)
        # Frontend renders user fields with textContent, never innerHTML.
        source=Path('static/app.js').read_text()
        self.assertNotIn('innerHTML',source)


if __name__ == '__main__':
    unittest.main()
