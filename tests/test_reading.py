"""Standard-library checks for all generated reading pages; optional approved-source comparison."""
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from generate_reading_tests import fmt_md, render_passage_text, load_test


def page_data(page):
    return json.loads(re.search(r'<script id="testData" type="application/json">(.*?)</script>', page, re.S)[1])


class ReadingTests(unittest.TestCase):
    def test_markdown_preserves_literal_stars_and_escapes_html(self):
        rendered = fmt_md('**引文：***"marked (\\*)"*\\\n\\<test@example.com>\n<script>alert(1)</script>')
        self.assertIn('<strong>引文：</strong><em>&quot;marked (*)&quot;</em><br>', rendered)
        self.assertIn('&lt;test@example.com&gt;', rendered)
        self.assertNotIn('<script>', rendered)
        self.assertNotIn('\\', rendered)
        self.assertNotIn('\x00', rendered)

    def test_document_boundaries_and_insertion_markers(self):
        text = 'Questions 176-180 refer to the following texts.\n\nDoc one\n\n' + '―'*20 + '\n\nDoc two [1]'
        rendered = render_passage_text(text)
        self.assertNotIn('Questions 176', rendered)
        self.assertEqual(rendered.count('<hr class="doc-sep">'), 1)
        self.assertIn('Doc two [1]', rendered)
        self.assertNotIn('data-jump', rendered)
        self.assertIn('data-jump="131"', render_passage_text('Text ___ [131]'))

    def test_loader_rejects_incomplete_or_ambiguous_data(self):
        data = {'parts': []}
        for p, lo, hi in [(5,101,130), (6,131,146), (7,147,200)]:
            qs = [{'num': n, 'choices': [{'letter': L, 'correct': L == 'A'} for L in 'ABCD'],
                   'explanation': {'correct_letter': 'A'}} for n in range(lo,hi+1)]
            data['parts'].append({'id':f'part{p}', 'questions':qs})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'test.zip'
            def save():
                with ZipFile(path,'w') as z:
                    z.writestr('index.html', '<script>window.TOEIC_DATA = '+json.dumps(data)+';</script>')
            save()
            self.assertEqual(load_test(path), data)
            data['parts'][2]['questions'][0]['choices'][1]['correct'] = True
            save()
            with self.assertRaisesRegex(ValueError, 'invalid choices for 147'):
                load_test(path)
            data['parts'][2]['questions'].pop()
            save()
            with self.assertRaisesRegex(ValueError, 'incomplete part7'):
                load_test(path)

    def test_all_ten_pages_have_complete_unique_questions(self):
        for n in range(1,11):
            with self.subTest(test=n):
                page = (ROOT/f'reading{n}.html').read_text(encoding='utf-8')
                data = page_data(page)
                self.assertEqual([p['number'] for p in data['parts']], [5,6,7])
                self.assertEqual([len(p['questions']) for p in data['parts']], [30,16,54])
                qs = [q for p in data['parts'] for q in p['questions']]
                self.assertEqual([q['id'] for q in qs], list(range(101,201)))
                cards = re.findall(r'<article class="question[^\"]*" id="question-(\d+)".*?</article>', page, re.S)
                self.assertEqual(list(map(int,cards)), list(range(101,201)))
                ids = re.findall(r'\bid="([^"]+)"',page)
                self.assertEqual(len(ids),len(set(ids)))
                for q in qs:
                    self.assertIn(q['answer'], 'ABCD')
                    for L in 'ABCD':
                        self.assertEqual(page.count(f'id="q{q["id"]}_{L}"'),1)
                self.assertEqual(page.count('<hr class="doc-sep">'),8)
                self.assertEqual(page.count('data-trans hidden'),19)
                self.assertEqual(page.count('data-exp-box hidden'),100)
                self.assertNotIn('\ufffd',page)
                self.assertNotIn('\x00',page)
                self.assertNotIn('共 46 題',page)
                self.assertIn(f'toeic_reading_test_${{DATA.test}}_v1',page)

    def test_homepage_advertises_full_reading_tests(self):
        page = (ROOT/'index.html').read_text(encoding='utf-8')
        self.assertEqual(page.count('📝 100 題 (Q101–Q200)'),10)
        self.assertEqual(page.count('Part 7: 閱讀理解 (54 題)'),10)
        self.assertNotIn('📝 46 題',page)

    @unittest.skipUnless(os.environ.get('TOEIC_SOURCE_DIR'), 'set TOEIC_SOURCE_DIR for exact source comparison')
    def test_every_item_matches_approved_scorm(self):
        for n in range(1,11):
            page = (ROOT/f'reading{n}.html').read_text(encoding='utf-8')
            source = load_test(Path(os.environ['TOEIC_SOURCE_DIR'])/f'TOEIC_Reading_Mock_Test_{n:02d}.zip')
            client = {q['id']:q for p in page_data(page)['parts'] for q in p['questions']}
            cards = {int(qid): card for card,qid in re.findall(
                r'(<article class="question[^\"]*" id="question-(\d+)".*?</article>)',page,re.S)}
            for part in source['parts']:
                qs = part.get('questions', [q for pas in part.get('passages',[]) for q in pas['questions']])
                for q in qs:
                    with self.subTest(test=n, question=q['num']):
                        card = cards[q['num']]
                        self.assertEqual(client[q['num']]['answer'],next(c['letter'] for c in q['choices'] if c['correct']))
                        self.assertIn(fmt_md(q['explanation']['body']),card)
                        from html import escape
                        prompt = q.get('prompt') if part['id']=='part5' else (re.sub(rf'^{q["num"]}\.\s*','',q['stem']) if part['id']=='part7' else None)
                        if prompt is not None:
                            self.assertIn(escape(prompt),card)
                        for c in q['choices']:
                            self.assertIn(f'<b>{c["letter"]}</b>. {escape(c["text"])}',card)
                for pas in part.get('passages',[]):
                    self.assertIn(render_passage_text(pas['text']),page)
                    self.assertIn(fmt_md(pas['translation']),page)


if __name__ == '__main__':
    unittest.main()
