"""Shared scoring rules: one point per queen attacked by no other queen."""
import re

N = 12


def validate_positions(positions, require_full=True):
    if not isinstance(positions, list) or len(positions) > N:
        raise ValueError('Bàn cờ chỉ được có tối đa 12 quân hậu.')
    if require_full and len(positions) != N:
        raise ValueError('Cần đúng 12 quân hậu để nộp bài.')
    seen = set()
    for pair in positions:
        if (not isinstance(pair, (list, tuple)) or len(pair) != 2
                or any(type(v) is not int or not 1 <= v <= N for v in pair)):
            raise ValueError('Mỗi tọa độ phải gồm hai số nguyên từ 1 đến 12.')
        if tuple(pair) in seen:
            raise ValueError('Hai quân hậu không thể nằm trên cùng một ô.')
        seen.add(tuple(pair))
    return sorted([list(p) for p in positions], key=lambda p: (p[1], p[0]))


def parse_input(text):
    if not isinstance(text, str) or len(text.encode('utf-8')) > 4096:
        raise ValueError('File input.txt phải nhỏ hơn hoặc bằng 4 KB.')
    text = text.lstrip('\ufeff').strip()
    if not text or re.search(r'[^0-9\s,]', text):
        raise ValueError('File chỉ chứa số nguyên, khoảng trắng, xuống dòng hoặc dấu phẩy.')
    tokens = re.split(r'[\s,]+', text)
    if len(tokens) != N * 2 or any(not t or len(t) > 2 for t in tokens):
        raise ValueError('File cần đúng 24 số: x1 y1 … x12 y12, mỗi số từ 1 đến 12.')
    values = [int(t) for t in tokens]
    return validate_positions([values[i:i + 2] for i in range(0, len(values), 2)])


def evaluate(positions):
    positions = validate_positions(positions, require_full=False)
    attacked = set()
    pairs = []
    for i, (x, y) in enumerate(positions):
        for j in range(i + 1, len(positions)):
            a, b = positions[j]
            if x == a or y == b or abs(x - a) == abs(y - b):
                attacked.update((i, j))
                pairs.append([i, j])
    return {'score': len(positions) - len(attacked), 'conflicts': len(pairs),
            'attacked': sorted(attacked), 'pairs': pairs, 'positions': positions}
