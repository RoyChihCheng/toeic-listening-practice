"""Playwright smoke tests for the static site (local or deployed). Uses isolated browser storage."""
import argparse
from pathlib import Path
import tempfile
from playwright.sync_api import sync_playwright, expect


def data(page):
    return page.locator('#testData').evaluate('(el)=>JSON.parse(el.textContent)')


def answer_part(page, number, wrong_id=None):
    page.evaluate('''({number,wrongId})=>{
      const part=JSON.parse(document.getElementById('testData').textContent).parts.find(p=>p.number===number);
      for(const q of part.questions){
        const value=q.id===wrongId?('ABCD'.split('').find(v=>v!==q.answer)):q.answer;
        const input=document.querySelector(`input[name="q${q.id}"][value="${value}"]`);
        input.checked=true;
        input.dispatchEvent(new Event('change',{bubbles:true}));
      }
    }''', {'number':number, 'wrongId':wrong_id})


def smoke(base_url):
    shots = Path(tempfile.mkdtemp(prefix='toeic-reading-smoke-'))
    errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        context=browser.new_context(viewport={'width':1440,'height':1000})
        page=context.new_page()
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(base_url,wait_until='networkidle')
        page.locator('[data-target="reading"]').click()
        expect(page.locator('.card-reading:visible')).to_have_count(10)
        expect(page.locator('.card-listening:visible')).to_have_count(0)
        page.screenshot(path=str(shots/'home-desktop.png'),full_page=True)
        for n in range(1,11):
            page.goto(base_url+f'reading{n}.html',wait_until='networkidle')
            assert [len(part['questions']) for part in data(page)['parts']]==[30,16,54]
            expect(page.locator('.question')).to_have_count(100)
            page.locator('[data-tab="7"]').click()
            panel=page.locator('[data-part="7"]')
            expect(panel).to_be_visible()
            expect(panel.locator('hr.doc-sep')).to_have_count(8)
            expect(panel.locator('[data-exp-box]').first).to_be_hidden()
            expect(panel.locator('[data-trans]').first).to_be_hidden()
            answer_part(page,7)
            expect(page.locator('[data-completion="7"]')).to_have_text('54 of 54 answered')
            page.reload(wait_until='networkidle')
            expect(page.locator('[data-tab="7"]')).to_have_attribute('aria-pressed','true')
            expect(panel.locator('input:checked')).to_have_count(54)
            page.locator('[data-submit-part="7"]').click()
            expect(page.locator('[data-result-part="7"]')).to_contain_text('54 / 54')
            expect(page.locator('[data-completion-summary]')).to_be_hidden()
            expect(panel.locator('[data-exp-box]').first).to_be_visible()
            expect(panel.locator('[data-trans]').first).to_be_visible()
            expect(panel.locator('input:disabled')).to_have_count(216)
            for part in [5,6]:
                page.locator(f'[data-tab="{part}"]').click()
                answer_part(page,part)
                page.locator(f'[data-submit-part="{part}"]').click()
            expect(page.locator('[data-final-score]')).to_have_text('100')
            expect(page.locator('[data-final-total]')).to_have_text('100')
            expect(page.locator('[data-final-percent]')).to_have_text('100%')
            expect(page.locator('[data-final-missed]')).to_have_text('0')
            page.reload(wait_until='networkidle')
            expect(page.locator('[data-completion-summary]')).to_be_visible()
            expect(page.locator('[data-final-score]')).to_have_text('100')
            page.locator('[data-tab="7"]').click()
            page.set_viewport_size({'width':320,'height':800})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1'),f'Test {n}: mobile page overflow'
            for box in panel.locator('.passage-text-panel').all():
                assert box.evaluate('(e)=>e.scrollWidth <= e.clientWidth+2'),f'Test {n}: passage overflow'
            if n==7:
                page.evaluate("window.scrollTo({top:0,behavior:'instant'})")
                page.screenshot(path=str(shots/'part7-mobile.png'))
            page.set_viewport_size({'width':1440,'height':1000})
            print(f'Test {n}: 54/54 Part 7, 100/100 full test, persisted/regraded, mobile layout PASS')
        context.close()

        # A previously completed 46-question test must gain an unsubmitted Part 7,
        # not lose old answers or show a premature 46/100 final result.
        context=browser.new_context()
        page=context.new_page()
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(base_url+'reading1.html',wait_until='networkidle')
        old_parts=data(page)['parts'][:2]
        saved={'activePart':6,'submittedParts':[5,6],
               'answers':{f'q{q["id"]}':q['answer'] for part in old_parts for q in part['questions']}}
        page.evaluate('(saved)=>localStorage.setItem("toeic_reading_test_1_v1",JSON.stringify(saved))',saved)
        page.reload(wait_until='networkidle')
        expect(page.locator('[data-result-part="5"]')).to_contain_text('30 / 30')
        expect(page.locator('[data-result-part="6"]')).to_contain_text('16 / 16')
        expect(page.locator('[data-completion-summary]')).to_be_hidden()
        page.locator('[data-tab="7"]').click()
        expect(page.locator('[data-part="7"] input:checked')).to_have_count(0)
        answer_part(page,7,wrong_id=147)
        page.locator('[data-submit-part="7"]').click()
        expect(page.locator('[data-final-score]')).to_have_text('99')
        expect(page.locator('[data-final-missed]')).to_have_text('1')
        page.locator('[data-review-question="147"]').click()
        expect(page.locator('[data-part="7"]')).to_be_visible()
        expect(page.locator('#question-147')).to_have_class('question p6-question review-wrong highlight-target')
        page.reload(wait_until='networkidle')
        expect(page.locator('[data-final-score]')).to_have_text('99')
        print('Legacy 46-question progress migration + wrong-answer jump/reload PASS')
        context.close()

        # Unanswered items remain wrong only when that part is actually submitted.
        context=browser.new_context(viewport={'width':375,'height':812})
        page=context.new_page()
        page.on('dialog',lambda dialog:dialog.accept())
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(base_url+'reading9.html',wait_until='networkidle')
        page.locator('[data-tab="7"]').click()
        page.locator('[data-submit-part="7"]').click()
        expect(page.locator('[data-result-part="7"]')).to_contain_text('0 / 54')
        expect(page.locator('[data-completion-summary]')).to_be_hidden()
        page.goto(base_url,wait_until='networkidle')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
        expect(page.locator('[data-target="reading"]')).to_be_visible()
        print('Unanswered submit confirmation + mobile homepage PASS')
        context.close()
        browser.close()
    assert not errors,errors
    print('No JavaScript page errors. Screenshots:',shots)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--base-url',default='http://127.0.0.1:8765/')
    args=parser.parse_args()
    smoke(args.base_url.rstrip('/')+'/')
