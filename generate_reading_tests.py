import zipfile
import json
import re
import html
import argparse
from pathlib import Path

THEMES = {
    1: {"name": "Executive Blue", "brand": "#143a5a", "accent": "#1976a8", "pale": "#eaf4f8"},
    2: {"name": "Emerald Finance", "brand": "#174b43", "accent": "#24866f", "pale": "#eaf6f2"},
    3: {"name": "Burgundy Legal", "brand": "#612d3d", "accent": "#a44c62", "pale": "#f8edf1"},
    4: {"name": "Copper Logistics", "brand": "#65402c", "accent": "#b26338", "pale": "#f8f0e9"},
    5: {"name": "Indigo Technology", "brand": "#303a70", "accent": "#5866b4", "pale": "#eef0fa"},
    6: {"name": "Teal Healthcare", "brand": "#15515a", "accent": "#168997", "pale": "#e9f6f7"},
    7: {"name": "Slate Aviation", "brand": "#334657", "accent": "#55758d", "pale": "#edf2f5"},
    8: {"name": "Plum Hospitality", "brand": "#55355f", "accent": "#8b5797", "pale": "#f5eef7"},
    9: {"name": "Cobalt Consulting", "brand": "#203f72", "accent": "#356fc0", "pale": "#edf3fb"},
    10: {"name": "Forest Sustainability", "brand": "#244c3a", "accent": "#4b7f60", "pale": "#edf5f0"}
}

def fmt_md(text):
    if not text:
        return ""
    # strip accidental trailing part headers from explanations
    text = re.sub(r'\s*\*\*(第二部分|第三部分)[^\*]*\*\*\s*$', '', text.strip())
    # Keep literal footnote asterisks out of the emphasis parser.
    text = text.replace('\\*', '\x00').replace('\\\n', '\n')
    text = re.sub(r'\\([_*\[\]().<>-])', r'\1', text)
    t = html.escape(text)
    t = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'\*([^*\n]+)\*', r'<em>\1</em>', t)
    t = t.replace('\x00', '*')
    return t.replace('\\n', '<br>').replace('\n', '<br>')

def render_passage_text(text):
    lines = text.split('\n')
    if lines and lines[0].strip().startswith("Questions "):
        lines = lines[1:]
    body = "\n".join(lines).strip()
    esc = html.escape(body)
    esc = re.sub(r'^―{10,}$', '<hr class="doc-sep">', esc, flags=re.MULTILINE)
    esc = re.sub(r'_{3,}\s*\[(\d+)\]', r'<span class="blank-chip" data-jump="\1">[\1]</span>', esc)
    return esc

def load_test(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        raw_html = z.read('index.html').decode('utf-8')
    match = re.search(r'window\.TOEIC_DATA\s*=\s*(\{.*?\});\s*</script>', raw_html, re.DOTALL)
    if not match:
        raise ValueError(f'{zip_path}: missing TOEIC_DATA')
    data = json.loads(match.group(1))
    for part_id, start, end in [('part5', 101, 130), ('part6', 131, 146), ('part7', 147, 200)]:
        part = next(p for p in data['parts'] if p['id'] == part_id)
        questions = part.get('questions', [q for pas in part.get('passages', []) for q in pas['questions']])
        if [q['num'] for q in questions] != list(range(start, end + 1)):
            raise ValueError(f'{zip_path}: incomplete {part_id}')
        for q in questions:
            choices = q['choices']
            if [c['letter'] for c in choices] != list('ABCD') or sum(bool(c.get('correct')) for c in choices) != 1:
                raise ValueError(f'{zip_path}: invalid choices for {q["num"]}')
            if q['explanation']['correct_letter'] != next(c['letter'] for c in choices if c['correct']):
                raise ValueError(f'{zip_path}: explanation key mismatch for {q["num"]}')
    return data


def generate_test(test_num, source_dir, output_dir):
    data = load_test(Path(source_dir) / f'TOEIC_Reading_Mock_Test_{test_num:02d}.zip')

    theme = THEMES[test_num]
    p5 = next(p for p in data['parts'] if p['id'] == 'part5')
    p6 = next(p for p in data['parts'] if p['id'] == 'part6')
    p7 = next(p for p in data['parts'] if p['id'] == 'part7')

    client_data = {
        "test": test_num,
        "theme": theme["name"],
        "parts": [
            {
                "number": 5,
                "title": "Incomplete Sentences",
                "label": "單句填空",
                "questions": [
                    {
                        "id": q["num"],
                        "answer": next(c["letter"] for c in q["choices"] if c.get("correct")),
                        "tag": q.get("explanation", {}).get("tag", "")
                    }
                    for q in p5["questions"]
                ]
            },
            {
                "number": 6,
                "title": "Text Completion",
                "label": "短文填空",
                "questions": [
                    {
                        "id": q["num"],
                        "answer": next(c["letter"] for c in q["choices"] if c.get("correct")),
                        "tag": q.get("explanation", {}).get("tag", "")
                    }
                    for pas in p6["passages"] for q in pas["questions"]
                ]
            }
        ]
    }

    client_data['parts'].append({
        'number': 7, 'title': 'Reading Comprehension', 'label': '閱讀理解',
        'questions': [
            {'id': q['num'], 'answer': next(c['letter'] for c in q['choices'] if c['correct']),
             'tag': q['explanation'].get('tag', '')}
            for pas in p7['passages'] for q in pas['questions']
        ]
    })

    p5_html = []
    for q in p5["questions"]:
        qid = q["num"]
        choices_html = []
        for c in q["choices"]:
            let = c["letter"]
            cid = f"q{qid}_{let}"
            choices_html.append(
                f'<label class="choice" for="{cid}">'
                f'<input type="radio" id="{cid}" name="q{qid}" value="{let}">'
                f'<span><b>{let}</b>. {html.escape(c["text"])}</span>'
                f'</label>'
            )
        
        exp_tag = html.escape(q.get("explanation", {}).get("tag", ""))
        exp_body = fmt_md(q.get("explanation", {}).get("body", ""))

        p5_html.append(
            f'<article class="question" id="question-{qid}" tabindex="-1" data-question="{qid}">'
            f'<div class="qnum"><b>{qid}.</b></div>'
            f'<div class="qprompt">{html.escape(q["prompt"])}</div>'
            f'<div class="choices">{"".join(choices_html)}</div>'
            f'<div class="explanation-box" data-exp-box hidden>'
            f'<div class="exp-tag">{exp_tag}</div>'
            f'<div class="exp-body">{exp_body}</div>'
            f'</div>'
            f'</article>'
        )

    passage_html = {6: [], 7: []}
    passage_sets = [(number, index, passage)
                    for number, part in [(6, p6), (7, p7)]
                    for index, passage in enumerate(part['passages'])]
    for part_num, pi, pas in passage_sets:
        pas_header = html.escape(pas.get("header", f"Questions {pas['range'][0]}–{pas['range'][1]}"))
        pas_text_html = render_passage_text(pas["text"])
        trans_html = fmt_md(pas.get("translation", ""))

        pas_qs_html = []
        for q in pas["questions"]:
            qid = q["num"]
            choices_html = []
            for c in q["choices"]:
                let = c["letter"]
                cid = f"q{qid}_{let}"
                choices_html.append(
                    f'<label class="choice" for="{cid}">'
                    f'<input type="radio" id="{cid}" name="q{qid}" value="{let}">'
                    f'<span><b>{let}</b>. {html.escape(c["text"])}</span>'
                    f'</label>'
                )

            exp_tag = html.escape(q.get("explanation", {}).get("tag", ""))
            exp_body = fmt_md(q.get("explanation", {}).get("body", ""))

            stem = re.sub(rf'^{qid}\.\s*', '', q.get('stem', ''))
            prompt = (f'Select the best answer to complete blank [{qid}].' if part_num == 6 else stem)
            pas_qs_html.append(
                f'<article class="question p6-question" id="question-{qid}" tabindex="-1" data-question="{qid}">'
                f'<div class="qnum"><b>{qid}.</b></div><div class="qprompt">{html.escape(prompt)}</div>'
                f'<div class="choices">{"".join(choices_html)}</div>'
                f'<div class="explanation-box" data-exp-box hidden>'
                f'<div class="exp-tag">{exp_tag}</div>'
                f'<div class="exp-body">{exp_body}</div>'
                f'</div>'
                f'</article>'
            )

        passage_html[part_num].append(
            f'<div class="passage-block" id="passage-{part_num}-{pi+1}">'
            f'<div class="passage-header"><strong>{pas_header}</strong></div>'
            f'<div class="passage-layout">'
            f'<div class="passage-text-panel">'
            f'<div class="passage-text">{pas_text_html}</div>'
            f'<details class="passage-translation" data-trans hidden>'
            f'<summary>📖 查看本篇全文中譯 (View Translation)</summary>'
            f'<div class="trans-body">{trans_html}</div>'
            f'</details>'
            f'</div>'
            f'<div class="passage-questions-panel">'
            f'{"".join(pas_qs_html)}'
            f'</div>'
            f'</div>'
            f'</div>'
        )

    out_html = f"""<!doctype html>
<html lang="zh-TW">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<title>多益閱讀模擬測驗 Test {test_num} | TOEIC Reading Practice</title>
<style>
:root{{
  --brand:{theme['brand']};
  --accent:{theme['accent']};
  --pale:{theme['pale']};
  --line:#d5e5ec;
  --bg:#f3f7f9;
  --focus:#f2b544;
  --ink:#172433;
  --muted:#617080;
  --good:#13734a;
  --bad:#b73832;
  --paper:#fff;
  --shadow:0 12px 30px rgba(25,42,58,.09);
}}
*{{box-sizing:border-box}}
html{{scroll-behavior:smooth;min-width:0}}
body{{margin:0;min-width:0;background:radial-gradient(circle at 92% 0,var(--pale) 0,transparent 28rem),var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans TC",sans-serif;line-height:1.55;overflow-x:hidden}}
button,input,label{{font:inherit}}
button{{cursor:pointer;touch-action:manipulation}}

.top{{position:relative;overflow:hidden;background:linear-gradient(118deg,var(--brand),var(--accent));color:#fff;padding:1.25rem max(1rem,calc((100% - 1180px)/2));box-shadow:0 3px 14px #0003}}
.top:after{{content:"";position:absolute;width:18rem;height:18rem;border:4rem solid #fff1;border-radius:50%;right:-6rem;top:-10rem}}
.top-inner{{position:relative;z-index:1;display:flex;justify-content:space-between;align-items:center;gap:1rem;flex-wrap:wrap}}
.top-left{{display:flex;flex-direction:column;gap:.3rem}}
.back-btn{{display:inline-flex;align-items:center;gap:.4rem;color:#fff;text-decoration:none;font-size:.9rem;font-weight:700;opacity:.9;transition:opacity .15s}}
.back-btn:hover{{opacity:1;text-decoration:underline}}
.top h1{{font-size:clamp(1.35rem,3vw,2.05rem);line-height:1.2;margin:0}}
.top p{{margin:0;color:#fff;opacity:.85;font-size:.92rem}}
.top-right{{display:flex;align-items:center;gap:.65rem;flex-wrap:wrap}}
.switch-mode-btn{{display:inline-flex;align-items:center;gap:.35rem;padding:.38rem .85rem;border-radius:999px;background:rgba(255,255,255,0.2);color:#fff;text-decoration:none;font-size:.82rem;font-weight:700;border:1px solid rgba(255,255,255,0.4);transition:all .15s}}
.switch-mode-btn:hover{{background:rgba(255,255,255,0.35);transform:translateY(-1px)}}
.theme-badge{{flex:none;border:1px solid #ffffff55;background:#ffffff18;border-radius:999px;padding:.38rem .75rem;font-size:.8rem;font-weight:700;letter-spacing:.03em}}

.shell{{width:min(100%,1180px);margin:auto;padding:clamp(.7rem,2vw,1.35rem)}}
.summary{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.7rem;margin-bottom:1rem}}
.part-tab{{min-width:0;border:1px solid var(--line);border-top:4px solid transparent;background:#fff;border-radius:.85rem;padding:.85rem 1rem;text-align:left;color:var(--ink);box-shadow:0 4px 14px #1e344510;transition:transform .15s,box-shadow .15s,border-color .15s}}
.part-tab:not([disabled]):hover{{transform:translateY(-2px);box-shadow:0 8px 20px #1e34451c}}
.part-tab strong,.part-tab span{{display:block}}
.part-tab strong{{font-size:1.05rem}}
.part-tab span{{overflow:hidden;text-overflow:ellipsis;font-size:.84rem;color:var(--muted);margin-top:.2rem}}
.part-tab.active{{border-top-color:var(--accent);background:var(--pale);outline:2px solid color-mix(in srgb,var(--accent) 38%,transparent)}}

.panel{{display:none}}
.panel.active{{display:block}}
.part-head{{background:#fffc;border:1px solid var(--line);border-radius:1rem;padding:clamp(.85rem,2vw,1.15rem);margin-bottom:1.2rem;position:sticky;top:.35rem;z-index:4;box-shadow:var(--shadow);backdrop-filter:blur(12px)}}
.part-head h2{{margin:0;font-size:clamp(1.15rem,2.5vw,1.45rem);color:var(--brand)}}
.directions{{color:var(--muted);margin:.35rem 0 0;font-size:.9rem;line-height:1.5}}

.question{{min-width:0;background:#fff;border:1px solid var(--line);border-radius:.85rem;padding:clamp(.85rem,2vw,1.15rem);margin:0 0 1rem;box-shadow:0 3px 12px #20384d0b;transition:border-color .2s,box-shadow .2s}}
.question.highlight-target{{border-color:var(--accent);box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 35%,transparent);animation:pulse-highlight 1.5s ease-out}}
@keyframes pulse-highlight{{0%{{transform:scale(1.01)}}50%{{transform:scale(1)}}100%{{transform:scale(1)}}}}
.qnum{{font-size:1.05rem;margin:0 0 .5rem;color:var(--brand);font-weight:800}}
.qprompt{{font-size:1.02rem;line-height:1.6;margin-bottom:.85rem;color:#1e293b;font-weight:500;white-space:pre-line}}

.choices{{display:grid;gap:.5rem}}
.choice{{display:flex;min-width:0;align-items:flex-start;gap:.65rem;border:1px solid var(--line);border-radius:.65rem;padding:.7rem .85rem;cursor:pointer;transition:background .15s,border-color .15s,transform .15s}}
.choice:hover{{background:var(--pale);border-color:var(--accent)}}
.choice:has(input:checked){{background:var(--pale);border-color:var(--accent);box-shadow:inset 4px 0 0 var(--accent)}}
.choice:has(input:focus-visible){{outline:3px solid var(--focus);outline-offset:1px}}
.choice input{{flex:none;margin:.24rem 0 0;accent-color:var(--accent)}}
.choice span{{min-width:0;overflow-wrap:anywhere;font-size:.95rem}}

/* Part 6 Passage Layout */
.passage-block{{background:color-mix(in srgb,var(--pale) 60%,#fff);border:1px solid var(--line);border-radius:1rem;padding:clamp(.8rem,2vw,1.2rem);margin-bottom:1.5rem}}
.passage-header{{color:var(--brand);font-size:1.05rem;padding:.2rem .4rem .9rem;border-bottom:1px solid var(--line);margin-bottom:1rem}}
.passage-layout{{display:grid;grid-template-columns:1.15fr 1fr;gap:1.2rem;align-items:start}}
.passage-text-panel{{background:#fff;border:1px solid var(--line);border-radius:.85rem;padding:1.2rem;box-shadow:0 3px 12px #20384d0b;position:sticky;top:5.5rem;max-height:calc(100vh - 7rem);overflow-y:auto}}
.passage-text{{line-height:1.8;color:#2d3748;white-space:pre-line;font-size:.96rem;overflow-wrap:anywhere}}
.doc-sep{{border:0;border-top:3px solid var(--accent);margin:1.5rem 0;opacity:.65}}
.blank-chip{{display:inline-block;background:var(--brand);color:#fff;padding:.12rem .5rem;border-radius:6px;font-weight:700;font-size:.88rem;margin:0 .2rem;cursor:pointer;transition:transform .15s,background .15s}}
.blank-chip:hover{{background:var(--accent);transform:scale(1.08)}}
.blank-chip.answered{{background:var(--accent)}}
.passage-questions-panel{{display:flex;flex-direction:column;gap:.9rem}}
.p6-question{{margin:0}}

.passage-translation{{margin-top:1.1rem;border-top:1px dashed var(--line);padding-top:.85rem}}
.passage-translation summary{{cursor:pointer;font-weight:700;color:var(--brand);font-size:.9rem;padding:.3rem 0;user-select:none}}
.trans-body{{margin-top:.6rem;padding:.85rem;background:#f8fafc;border-radius:.6rem;font-size:.9rem;color:#475569;line-height:1.75;white-space:pre-line;border:1px solid #e2e8f0}}

/* Explanation & Review */
.explanation-box{{margin-top:.9rem;padding:.85rem 1rem;background:#f8fafc;border:1px solid #e2e8f0;border-left:4px solid var(--accent);border-radius:.6rem;font-size:.9rem;line-height:1.65}}
.exp-tag{{display:inline-block;background:#e2e8f0;color:#334155;font-weight:700;font-size:.78rem;padding:.2rem .6rem;border-radius:999px;margin-bottom:.55rem}}
.exp-body{{color:#1e293b}}

.review-correct{{border-color:#80c6a5;background:#f3fbf7}}
.review-wrong{{border-color:#e4a39e;background:#fff7f6}}
.review-note{{display:none;font-weight:700;margin:.6rem 0 0;font-size:.92rem}}
.submitted .review-note{{display:block}}
.submitted [data-exp-box]{{display:block !important}}
.submitted [data-trans]{{display:block !important}}
.good{{color:var(--good)}}
.bad{{color:var(--bad)}}

.submit-row{{background:#fff;border:1px solid var(--line);border-radius:.85rem;padding:1rem 1.25rem;display:flex;align-items:center;gap:1rem;justify-content:space-between;box-shadow:var(--shadow);margin-top:1.2rem}}
.submit{{min-height:44px;border:0;border-radius:.65rem;padding:.72rem 1.35rem;background:var(--brand);color:#fff;font-weight:800;transition:background .15s}}
.submit:hover:not(:disabled){{background:var(--accent)}}
.submit:disabled{{opacity:.45;cursor:not-allowed}}
.result{{display:none;background:#fff;border-left:5px solid var(--good);border-radius:.7rem;padding:1.15rem;margin:1.2rem 0;box-shadow:var(--shadow);line-height:1.7}}
.result.show{{display:block}}
.result strong{{font-size:1.2rem}}

/* Completion summary */
.completion-summary{{background:#fff;border:1px solid var(--line);border-top:6px solid var(--accent);border-radius:1rem;padding:clamp(.9rem,2.4vw,1.4rem);margin:1.5rem 0;box-shadow:var(--shadow);scroll-margin-top:1rem}}
.completion-summary:focus{{outline:3px solid var(--focus);outline-offset:3px}}
.completion-summary h2{{margin:0;color:var(--brand);font-size:clamp(1.3rem,3vw,1.8rem)}}
.summary-lead{{margin:.25rem 0 1rem;color:var(--muted)}}
.score-overview{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.65rem;margin-bottom:.8rem}}
.score-box{{min-width:0;background:var(--pale);border:1px solid var(--line);border-radius:.75rem;padding:.78rem;text-align:center}}
.score-box span{{display:block;color:var(--muted);font-size:.78rem;font-weight:800;text-transform:uppercase;letter-spacing:.03em}}
.score-box strong{{display:block;color:var(--brand);font-size:clamp(1.2rem,3vw,1.7rem);overflow-wrap:anywhere}}
.part-breakdown{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:.55rem;margin:.8rem 0 1.2rem}}
.part-score{{border:1px solid var(--line);border-radius:.7rem;padding:.68rem;background:#fff}}
.part-score b,.part-score span{{display:block}}
.part-score span{{color:var(--muted);font-size:.86rem}}
.missed-heading{{margin:1.2rem 0 .65rem;color:var(--brand);font-size:1.08rem}}
.missed-list{{display:grid;gap:.55rem}}
.missed-row{{display:grid;grid-template-columns:minmax(7rem,1.2fr) repeat(2,minmax(6rem,.8fr)) auto;gap:.65rem;align-items:center;border:1px solid #e9c6c2;background:#fff8f7;border-radius:.72rem;padding:.7rem}}
.missed-row span{{min-width:0;overflow-wrap:anywhere}}
.missed-label{{font-size:.75rem;color:var(--muted);display:block}}
.review-jump{{min-height:40px;border:1px solid var(--accent);border-radius:.55rem;background:#fff;color:var(--brand);font-weight:800;padding:.5rem .75rem;transition:all .15s}}
.review-jump:hover{{background:var(--pale)}}
.perfect-note{{border:1px solid #a7d7bf;background:#f3fbf7;color:var(--good);border-radius:.72rem;padding:.85rem;font-weight:800}}
.next-test-banner{{margin-top:1.5rem;padding:1rem 1.2rem;background:var(--pale);border:1px solid var(--line);border-radius:.85rem;display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap}}
.next-test-banner span{{font-weight:700;color:var(--brand)}}
.btn-next-action{{background:var(--brand);color:#fff;text-decoration:none;padding:.6rem 1.1rem;border-radius:.6rem;font-weight:700;font-size:.9rem;transition:background .15s}}
.btn-next-action:hover{{background:var(--accent)}}

.sr-only{{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}}
.foot{{text-align:center;color:var(--muted);font-size:.82rem;padding:2rem}}

@media(max-width:900px){{
  .passage-layout{{grid-template-columns:1fr}}
  .passage-text-panel{{position:static;max-height:none}}
}}
@media(max-width:760px){{
  .top{{padding:1rem}}
  .top-inner{{align-items:flex-start;flex-direction:column}}
  .shell{{padding:.65rem}}
  .summary{{grid-template-columns:1fr}}
  .part-head{{position:static}}
  .submit-row{{align-items:stretch;flex-direction:column}}
  .submit{{width:100%}}
  .missed-row{{grid-template-columns:repeat(2,minmax(0,1fr))}}
  .review-jump{{grid-column:1/-1;width:100%}}
}}
@media(max-width:520px){{
  .score-overview{{grid-template-columns:1fr}}
  .score-box{{display:flex;align-items:center;justify-content:space-between;text-align:left;gap:.7rem}}
  .score-box strong{{font-size:1.25rem}}
  .part-breakdown{{grid-template-columns:1fr}}
  .missed-row{{grid-template-columns:1fr}}
}}
</style>
</head>
<body>
<header class="top">
  <div class="top-inner">
    <div class="top-left">
      <a href="index.html" class="back-btn">← 回到測驗選單</a>
      <h1>多益閱讀模擬測驗 Test {test_num}</h1>
      <p>Part 5–7 · 共 100 題 (Q101–Q200) · 建議 75 分鐘 · 附完整解析與篇章中譯</p>
    </div>
    <div class="top-right">
      <a href="test{test_num}.html" class="switch-mode-btn">🎧 切換至聽力測驗 Test {test_num}</a>
      <span class="theme-badge">{theme['name']}</span>
    </div>
  </div>
</header>

<main class="shell" data-test-id="toeic-reading-test-{test_num}">
  <nav class="summary" aria-label="Reading test parts" id="partTabs">
    <button class="part-tab active" data-tab="5">
      <strong>Part 5: 單句填空</strong>
      <span>Incomplete Sentences · 30 題 (Q101–Q130)</span>
    </button>
    <button class="part-tab" data-tab="6">
      <strong>Part 6: 短文填空</strong>
      <span>Text Completion · 16 題 (Q131–Q146)</span>
    </button>
    <button class="part-tab" data-tab="7">
      <strong>Part 7: 閱讀理解</strong>
      <span>Reading Comprehension · 54 題 (Q147–Q200)</span>
    </button>
  </nav>

  <div id="parts">
    <!-- Part 5 Panel -->
    <section class="panel active" data-part="5" aria-labelledby="part-title-5">
      <div class="part-head">
        <h2 id="part-title-5">Part 5: Incomplete Sentences (單句填空)</h2>
        <p class="directions">Directions: A word or phrase is missing in each of the sentences below. Four answer choices are given below each sentence. Select the best answer to complete the sentence. (Questions 101–130)</p>
      </div>
      <div class="questions">
        {"".join(p5_html)}
      </div>
      <div class="submit-row">
        <span data-completion="5">0 of 30 answered</span>
        <button class="submit" data-submit-part="5">Submit Part 5</button>
      </div>
      <div class="result" data-result-part="5" role="status"></div>
    </section>

    <!-- Part 6 Panel -->
    <section class="panel" data-part="6" aria-labelledby="part-title-6">
      <div class="part-head">
        <h2 id="part-title-6">Part 6: Text Completion (短文填空)</h2>
        <p class="directions">Directions: Read the texts that follow. A word, phrase, or sentence is missing in parts of each text. Four answer choices for each empty space are given below the text. Select the best answer to complete the text. (Questions 131–146)</p>
      </div>
      <div class="questions">
        {"".join(passage_html[6])}
      </div>
      <div class="submit-row">
        <span data-completion="6">0 of 16 answered</span>
        <button class="submit" data-submit-part="6">Submit Part 6</button>
      </div>
      <div class="result" data-result-part="6" role="status"></div>
    </section>

    <section class="panel" data-part="7" aria-labelledby="part-title-7">
      <div class="part-head">
        <h2 id="part-title-7">Part 7: Reading Comprehension (閱讀理解)</h2>
        <p class="directions">Directions: Read the single- and multiple-document sets below. Select the best answer for each question. (Questions 147–200)</p>
      </div>
      <div class="questions">
        {"".join(passage_html[7])}
      </div>
      <div class="submit-row">
        <span data-completion="7">0 of 54 answered</span>
        <button class="submit" data-submit-part="7">Submit Part 7</button>
      </div>
      <div class="result" data-result-part="7" role="status"></div>
    </section>
  </div>

  <!-- Completion Summary -->
  <section class="completion-summary" data-completion-summary hidden tabindex="-1" aria-labelledby="completionTitle">
    <h2 id="completionTitle">測驗成果與錯題檢視 (Results & Review)</h2>
    <p class="summary-lead">恭喜完成練習！以下為本次閱讀作答成績統計與錯題分析：</p>
    <div class="score-overview">
      <div class="score-box"><span>總得分 (Total Score)</span><strong><span data-final-score>0</span> / <span data-final-total>0</span></strong></div>
      <div class="score-box"><span>正確率 (Percentage)</span><strong data-final-percent>0%</strong></div>
      <div class="score-box"><span>錯誤題數 (Incorrect)</span><strong data-final-missed>0</strong></div>
    </div>
    <div class="part-breakdown" data-part-breakdown></div>
    <h3 class="missed-heading">錯題檢討清單 (點擊可跳轉至該題)</h3>
    <div class="missed-list" data-missed-list></div>

    <div class="next-test-banner">
      <span>想要挑戰更多？立即進行本回聽力測驗或回到選單！</span>
      <div style="display:flex;gap:.6rem;flex-wrap:wrap">
        <a href="test{test_num}.html" class="btn-next-action">🎧 進行 Test {test_num} 聽力測驗</a>
        <a href="index.html" class="btn-next-action" style="background:#4a5568">回到測驗選單</a>
      </div>
    </div>
  </section>

  <p class="foot">可依 Part 分段練習，交卷後顯示該部分解析與中譯。作答紀錄自動儲存於目前瀏覽器，重新整理不會遺失；不同網站的紀錄分開保存。</p>
</main>

<script id="testData" type="application/json">{json.dumps(client_data, ensure_ascii=False).replace('<', chr(92) + 'u003c')}</script>
<script>
(()=>{{
'use strict';
const DATA=JSON.parse(document.getElementById('testData').textContent);
const byPart=Object.fromEntries(DATA.parts.map(part=>[part.number,part]));
const state={{active:5,answers:{{}},parts:Object.fromEntries(DATA.parts.map(p=>[p.number,{{submitted:false,score:0}}]))}};
const STORAGE_KEY=`toeic_reading_test_${{DATA.test}}_v1`;

const tabs=document.getElementById('partTabs');
const summary=document.querySelector('[data-completion-summary]');

function saveProgress(){{
  try{{
    const payload={{
      answers:state.answers,
      submittedParts:Object.entries(state.parts).filter(([_,v])=>v.submitted).map(([k])=>parseInt(k,10)),
      activePart:state.active
    }};
    localStorage.setItem(STORAGE_KEY,JSON.stringify(payload));
  }}catch(e){{}}
}}

function updateCompletion(partNum){{
  const part=byPart[partNum];
  if(!part)return;
  const count=part.questions.filter(q=>state.answers['q'+q.id]).length;
  const el=document.querySelector(`[data-completion="${{partNum}}"]`);
  if(el)el.textContent=`${{count}} of ${{part.questions.length}} answered`;
  
  if(partNum===6){{
    part.questions.forEach(q=>{{
      const chips=document.querySelectorAll(`.blank-chip[data-jump="${{q.id}}"]`);
      chips.forEach(c=>{{
        if(state.answers['q'+q.id])c.classList.add('answered');
        else c.classList.remove('answered');
      }});
    }});
  }}
}}

function showPart(n,scrollTop=true){{
  if(!byPart[n])return;
  state.active=n;
  tabs.querySelectorAll('[data-tab]').forEach(btn=>{{
    const match=parseInt(btn.dataset.tab,10)===n;
    btn.classList.toggle('active',match);
    btn.setAttribute('aria-pressed',match?'true':'false');
  }});
  document.querySelectorAll('.panel').forEach(p=>{{
    p.classList.toggle('active',parseInt(p.dataset.part,10)===n);
  }});
  if(scrollTop){{
    const panel=document.querySelector(`.panel[data-part="${{n}}"]`);
    if(panel)panel.scrollIntoView({{behavior:'smooth',block:'start'}});
  }}
  saveProgress();
}}

tabs.querySelectorAll('[data-tab]').forEach(btn=>{{
  btn.addEventListener('click',()=>showPart(parseInt(btn.dataset.tab,10)));
}});

document.querySelectorAll('.blank-chip').forEach(chip=>{{
  chip.addEventListener('click',()=>{{
    const qid=chip.dataset.jump;
    const card=document.getElementById(`question-${{qid}}`);
    if(card){{
      card.scrollIntoView({{behavior:'smooth',block:'center'}});
      card.classList.add('highlight-target');
      setTimeout(()=>card.classList.remove('highlight-target'),2000);
      card.focus({{preventScroll:true}});
    }}
  }});
}});

document.querySelectorAll('.panel input[type="radio"]').forEach(input=>{{
  input.addEventListener('change',e=>{{
    const qid=e.target.name.replace(/^q/,'');
    state.answers[e.target.name]=e.target.value;
    const partNum=parseInt(e.target.closest('.panel').dataset.part,10);
    updateCompletion(partNum);
    saveProgress();
  }});
}});

function currentPct(){{
  const score=Object.values(state.parts).reduce((a,p)=>a+p.score,0);
  const total=DATA.parts.reduce((sum,p)=>sum+p.questions.length,0);
  return total?Math.round(score/total*100):0;
}}

function renderCompletion(focus=false){{
  if(!DATA.parts.every(p=>state.parts[p.number].submitted)){{
    summary.hidden=true;
    return;
  }}
  const score=Object.values(state.parts).reduce((a,p)=>a+p.score,0);
  const total=DATA.parts.reduce((sum,p)=>sum+p.questions.length,0);
  const pct=total?Math.round(score/total*100):0;
  const missed=DATA.parts.flatMap(part=>part.questions.filter(q=>state.answers['q'+q.id]!==q.answer).map(q=>({{q,part:part.number,response:state.answers['q'+q.id]||''}})));

  summary.querySelector('[data-final-score]').textContent=score;
  summary.querySelector('[data-final-total]').textContent=total;
  summary.querySelector('[data-final-percent]').textContent=pct+'%';
  summary.querySelector('[data-final-missed]').textContent=missed.length;
  summary.querySelector('[data-part-breakdown]').innerHTML=DATA.parts.map(part=>`<div class="part-score"><b>Part ${{part.number}} (${{part.label}})</b><span><strong>${{state.parts[part.number].score}}</strong> / ${{part.questions.length}} 正確</span></div>`).join('');

  summary.querySelector('[data-missed-list]').innerHTML=missed.length?missed.map(item=>`
    <article class="missed-row" data-missed-question="${{item.q.id}}">
      <span><b>第 ${{item.q.id}} 題</b><small class="missed-label">Part ${{item.part}} · ${{item.q.tag}}</small></span>
      <span><small class="missed-label">您的作答</small><b data-student-answer>${{item.response||'未作答'}}</b></span>
      <span><small class="missed-label">正確解答</small><b data-correct-answer>${{item.q.answer}}</b></span>
      <button class="review-jump" type="button" data-review-question="${{item.q.id}}" data-review-part="${{item.part}}">檢視題目</button>
    </article>`).join(''):'<p class="perfect-note">🎉 全對！恭喜在本次閱讀模擬測驗獲得滿分！</p>';

  summary.querySelectorAll('[data-review-question]').forEach(btn=>{{
    btn.addEventListener('click',()=>{{
      const qid=btn.dataset.reviewQuestion;
      const partNum=parseInt(btn.dataset.reviewPart,10);
      showPart(partNum,false);
      setTimeout(()=>{{
        const card=document.getElementById(`question-${{qid}}`);
        if(card){{
          card.scrollIntoView({{behavior:'smooth',block:'center'}});
          card.classList.add('highlight-target');
          setTimeout(()=>card.classList.remove('highlight-target'),2000);
          card.focus({{preventScroll:true}});
        }}
      }},150);
    }});
  }});

  summary.hidden=false;
  if(focus){{
    summary.scrollIntoView({{behavior:'smooth',block:'start'}});
    setTimeout(()=>summary.focus({{preventScroll:true}}),250);
  }}
}}

function gradePart(n,report){{
  const ps=state.parts[n],part=byPart[n],panel=document.querySelector(`.panel[data-part="${{n}}"]`);
  let score=0;
  part.questions.forEach(q=>{{
    const picked=state.answers['q'+q.id],ok=picked===q.answer;
    if(ok)score++;
    const card=panel.querySelector(`[data-question="${{q.id}}"]`);
    if(card){{
      card.classList.add(ok?'review-correct':'review-wrong');
      const choices=card.querySelectorAll('.choice');
      choices.forEach(ch=>{{
        const inp=ch.querySelector('input');
        if(inp.value===q.answer)ch.style.borderColor='var(--good)';
        else if(inp.checked && !ok)ch.style.borderColor='var(--bad)';
      }});
      card.querySelectorAll('input').forEach(i=>i.disabled=true);
    }}
  }});
  ps.score=score;
  ps.submitted=true;
  panel.classList.add('submitted');
  panel.querySelector(`[data-submit-part="${{n}}"]`).disabled=true;

  panel.querySelectorAll('[data-trans]').forEach(t=>t.hidden=false);
  panel.querySelectorAll('[data-exp-box]').forEach(e=>e.hidden=false);

  const cumulative=Object.values(state.parts).reduce((a,p)=>a+p.score,0);
  const total=DATA.parts.reduce((sum,p)=>sum+p.questions.length,0);
  const submittedCount=Object.values(state.parts).filter(p=>p.submitted).length;
  const next=DATA.parts.find(p=>!state.parts[p.number].submitted);
  const isComplete=!next;
  const result=panel.querySelector(`[data-result-part="${{n}}"]`);

  result.innerHTML=`<strong>Part ${{n}} 得分：${{score}} / ${{part.questions.length}}</strong><br>${{isComplete?`全卷完成！總分：${{cumulative}} / ${{total}} (${{currentPct()}}%)`:`已完成 ${{submittedCount}} / ${{DATA.parts.length}} 個部分。提交所有 Part 後將顯示全卷成果。`}}`;
  result.classList.add('show');

  if(next){{
    result.insertAdjacentHTML('beforeend',`<br><button class="submit" style="margin-top:.8rem" data-next="${{next.number}}">前往 Part ${{next.number}} (${{next.label}})</button>`);
    result.querySelector('[data-next]').addEventListener('click',()=>showPart(next.number));
  }}else{{
    result.insertAdjacentHTML('beforeend','<br><b>測驗完成！請往下查看完整成績與錯題詳解。</b>');
  }}

  saveProgress();
  renderCompletion(isComplete&&report);
}}

document.querySelectorAll('[data-submit-part]').forEach(btn=>{{
  btn.addEventListener('click',()=>{{
    const n=parseInt(btn.dataset.submitPart,10);
    const part=byPart[n];
    const answered=part.questions.filter(q=>state.answers['q'+q.id]).length;
    if(answered<part.questions.length){{
      if(!confirm(`Part ${{n}} 尚有 ${{part.questions.length - answered}} 題未作答，確定現在交卷嗎？`))return;
    }}
    gradePart(n,true);
  }});
}});

function loadSaved(){{
  try{{
    const saved=JSON.parse(localStorage.getItem(STORAGE_KEY));
    if(!saved)return;
    for(const q of DATA.parts.flatMap(part=>part.questions)){{
      const name='q'+q.id,val=saved.answers?.[name];
      if(typeof val==='string' && /^[A-D]$/.test(val)){{
        state.answers[name]=val;
        document.querySelector(`input[name="${{name}}"][value="${{val}}"]`).checked=true;
      }}
    }}
    if(Array.isArray(saved.submittedParts)){{
      for(const part of DATA.parts){{
        if(saved.submittedParts.includes(part.number))gradePart(part.number,false);
      }}
    }}
    DATA.parts.forEach(part=>{{
      updateCompletion(part.number);
    }});
    if(Number.isInteger(saved.activePart)&&byPart[saved.activePart])showPart(saved.activePart,false);
  }}catch(e){{}}
}}

loadSaved();
showPart(state.active,false);
}})();
</script>
</body>
</html>
"""
    out_path = Path(output_dir) / f'reading{test_num}.html'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(out_html)
    print(f'Generated {out_path} ({len(out_html.encode("utf-8"))} bytes)')

def update_listening_tests(output_dir):
    for t in range(1, 11):
        path = Path(output_dir) / f'test{t}.html'
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        if '.switch-mode-btn' not in content:
            css_inject = """.switch-mode-btn{display:inline-flex;align-items:center;gap:.35rem;padding:.38rem .85rem;border-radius:999px;background:rgba(255,255,255,0.2);color:#fff;text-decoration:none;font-size:.82rem;font-weight:700;border:1px solid rgba(255,255,255,0.4);transition:all .15s}
.switch-mode-btn:hover{background:rgba(255,255,255,0.35);transform:translateY(-1px)}
"""
            content = content.replace('.top:after{', css_inject + '.top:after{')

        badge_pat = re.compile(r'(<span class=\"theme-badge\">[^<]+</span>)')
        if f'reading{t}.html' not in content:
            replacement = f'<div style="display:flex;align-items:center;gap:.65rem;flex-wrap:wrap"><a href="reading{t}.html" class="switch-mode-btn">📖 切換至閱讀測驗 Test {t}</a>\\1</div>'
            content = badge_pat.sub(replacement, content, count=1)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Updated test{t}.html with link to reading{t}.html')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate all 10 reading tests (Parts 5–7) from approved full SCORM ZIPs.')
    parser.add_argument('--source-dir', required=True, type=Path)
    parser.add_argument('--output-dir', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, 11):
        generate_test(i, args.source_dir, args.output_dir)
