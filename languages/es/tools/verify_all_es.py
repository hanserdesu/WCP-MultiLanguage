# -*- coding: utf-8 -*-
"""Spanish wordbook full audit (verify_all_es.py).
Mirrors verify_all_ar.py checks. Usage: python tools/verify_all_es.py
"""
import hashlib, json, re, sqlite3, sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
OUT = ROOT / 'output'
IMPORT = OUT / 'import'
ES_WORD_AUDIO = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'es_word_audio'
ES_SENT_AUDIO = Path.home() / 'AppData' / 'LocalLow' / 'WCP' / 'wcp' / 'es_sentence_audio'
SPANISH_RE = re.compile(r'[a-z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1\u00fc]', re.I)
CHINESE_RE = re.compile(r'[\u4E00-\u9FA5]')

PASSES = 0
TOTAL = 0

def check(name, cond, detail=''):
    global PASSES, TOTAL
    TOTAL += 1
    status = 'OK' if cond else 'FAIL'
    if cond: PASSES += 1
    print(f'[{status:4s}] {name}' + (f': {detail}' if detail else ''))
    return cond

def main():
    print('=' * 70)
    print('    Spanish TEM-8 / CEFR Wordbook Full Audit')
    print('=' * 70)
    books_p = OUT / 'spanish_books.json'
    if not check('spanish_books.json exists', books_p.exists()):
        sys.exit(1)
    data = json.loads(books_p.read_text(encoding='utf-8'))
    levels = data.get('levels', {})
    all_words = []
    for lv in ('tem4_a1a2', 'tem4_b1', 'tem8_b2', 'tem8_c1'):
        all_words.extend(levels.get(lv, []))
    check('total 8600 words', len(all_words) == 8600, f'current {len(all_words)}')
    check('level distribution correct',
          {lv: len(levels.get(lv, [])) for lv in ('tem4_a1a2', 'tem4_b1', 'tem8_b2', 'tem8_c1')} ==
          {'tem4_a1a2': 2000, 'tem4_b1': 2500, 'tem8_b2': 3000, 'tem8_c1': 1100})
    check('unique words', len(set(w['word'] for w in all_words)) == len(all_words))
    # field completeness
    missing_ipa = [w['word'] for w in all_words if not w.get('ipa')]
    missing_zh = [w['word'] for w in all_words if not w.get('zh')]
    check('IPA coverage >= 95%', len(missing_ipa) / len(all_words) <= 0.05, f'missing {len(missing_ipa)}')
    check('Chinese meaning 100%', len(missing_zh) == 0, f'missing {len(missing_zh)}')
    check('POS 100%', all(w.get('pos') for w in all_words))
    # meaning format
    bad_meaning = [w['word'] for w in all_words if not CHINESE_RE.search(w.get('meaning', ''))]
    check('meaning contains Chinese', len(bad_meaning) == 0, f'bad {len(bad_meaning)}')
    # sentences master
    master_p = DATA / 'translations' / 'sentences_master.json'
    if check('sentences_master.json exists', master_p.exists()):
        master = json.loads(master_p.read_text(encoding='utf-8'))
        check('master covers all words', set(master.keys()) == set(w['word'] for w in all_words))
        ratio = sum(len(v) for v in master.values()) / max(len(master), 1)
        check('1:3 sentence ratio', ratio == 3.0, f'1:{ratio:.2f}')
    # import files
    for fn in ['西班牙语专四基础.xlsx', '西班牙语专四进阶.xlsx', '西班牙语专八高阶.xlsx',
               '西班牙语专八精通.xlsx', '西班牙语考级词库(猫条版).xlsx', 'wcp_spanish.db']:
        check(f'import file {fn}', (IMPORT / fn).exists())
    # db
    db_p = IMPORT / 'wcp_spanish.db'
    if db_p.exists():
        conn = sqlite3.connect(db_p)
        c = conn.cursor()
        c.execute('SELECT count(*) FROM pron')
        check('pron count', c.fetchone()[0] == 8600)
        c.execute('SELECT count(*) FROM spanish_all')
        check('spanish_all count', c.fetchone()[0] == 8600)
        c.execute('PRAGMA integrity_check')
        check('db integrity', c.fetchone()[0] == 'ok')
        conn.close()
    # audio
    if ES_WORD_AUDIO.exists():
        n_word_mp3 = len(list(ES_WORD_AUDIO.glob('*.mp3')))
        check('word audio 8600', n_word_mp3 == 8600, f'current {n_word_mp3}')
    if ES_SENT_AUDIO.exists():
        # Unique sentences only: duplicates share one md5-named file.
        # The generator md5-hashes the tag-stripped sentence; mirror that here.
        master2 = json.loads((DATA / 'translations' / 'sentences_master.json').read_text(encoding='utf-8'))
        def norm_es(raw): return re.sub(r'<[^>]+>', '', raw or '').strip()
        sent_uni = {norm_es(pair[0]) for v in master2.values() for pair in v
                    if len(pair) == 2 and len(norm_es(pair[0])) >= 2}
        missing_sent = [s for s in sent_uni
                        if not (ES_SENT_AUDIO / (hashlib.md5(s.encode('utf-8')).hexdigest() + '.mp3')).exists()]
        check('sentence audio coverage', not missing_sent,
              f'{len(sent_uni) - len(missing_sent)}/{len(sent_uni)} unique')
    # sha256 fingerprint of word set
    fp = hashlib.sha256(chr(10).join(sorted(set(w['word'] for w in all_words))).encode('utf-8')).hexdigest()
    print(f'  word set fingerprint: {fp}')
    # summary
    print()
    print('=' * 70)
    print(f'  {PASSES}/{TOTAL} checks passed' + (' - ALL PASS' if PASSES == TOTAL else ' - FAIL'))
    print('=' * 70)
    sys.exit(0 if PASSES == TOTAL else 1)

if __name__ == '__main__':
    main()
