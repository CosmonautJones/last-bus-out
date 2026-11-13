"""Record the one-minute demo video with captions (optional dev tool, not needed to run the app).

    pip install playwright && python -m playwright install chromium
    python scripts/record_demo.py            # app must be running on http://localhost:8000

Drives the real UI with Playwright, overlays captions built from the numbers on screen,
and writes demo/last-bus-out-demo.mp4 (needs ffmpeg on PATH; otherwise leaves a .webm).
"""
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
OUT = Path(__file__).resolve().parent.parent / "demo"
W, H = 1280, 720

OVERLAY = r"""
(() => {
  const css = document.createElement('style');
  css.textContent = `
    #lboCap { position: fixed; left: 524px; right: 24px; bottom: 26px; z-index: 99998; background: rgba(15,27,42,.94);
      color: #fff; font: 600 25px/1.35 Inter, system-ui, "Segoe UI", sans-serif; padding: 16px 22px; border-radius: 16px;
      box-shadow: 0 10px 30px rgba(0,0,0,.35); opacity: 0; transition: opacity .35s; }
    #lboCap small { display: block; font: 700 13px/1 system-ui; letter-spacing: .12em; text-transform: uppercase; color: #7fb2ff; margin-bottom: 8px; }
    #lboCard { position: fixed; inset: 0; z-index: 99999; background: #0f1b2a; color: #fff; display: none; flex-direction: column;
      align-items: center; justify-content: center; text-align: center; padding: 0 110px; font-family: Inter, system-ui, "Segoe UI", sans-serif; }
    #lboCard h1 { font-size: 68px; margin: 0 0 18px; letter-spacing: -0.03em; }
    #lboCard h1::before { display: none; }
    #lboCard p { font-size: 31px; line-height: 1.4; margin: 8px 0; color: #dbe6f3; }
    #lboCard p.s { font-size: 22px; color: #8fa3ba; margin-top: 22px; }
    #lboCard b { color: #ffc34d; }
    .lboHi { outline: 4px solid #0f62fe !important; outline-offset: 4px; border-radius: 12px; transition: outline-color .3s; }
  `;
  document.head.appendChild(css);
  const cap = document.createElement('div'); cap.id = 'lboCap'; document.body.appendChild(cap);
  const card = document.createElement('div'); card.id = 'lboCard'; document.body.appendChild(card);
  window.__cap = (step, text) => { cap.innerHTML = (step ? `<small>${step}</small>` : '') + text; cap.style.opacity = text ? 1 : 0; };
  window.__card = (html) => { card.innerHTML = html || ''; card.style.display = html ? 'flex' : 'none'; };
  window.__hi = (sel) => { document.querySelectorAll('.lboHi').forEach((e) => e.classList.remove('lboHi'));
    if (sel) { const e = document.querySelector(sel); if (e) { e.classList.add('lboHi'); e.scrollIntoView({ behavior: 'smooth', block: 'center' }); } } };
  window.__setEnd = (v, done) => { const e = document.getElementById('end'); e.value = v;
    e.dispatchEvent(new Event('input', { bubbles: true })); if (done) e.dispatchEvent(new Event('change', { bubbles: true })); };
})();
"""

MEMO_READY = "() => { const m = document.getElementById('memo').textContent; return m && !/writing the memo/.test(m); }"


def main():
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": W, "height": H}, record_video_dir=str(OUT), record_video_size={"width": W, "height": H})
        page = ctx.new_page()
        page.goto(URL)
        page.wait_for_selector("#samples button")
        page.evaluate(OVERLAY)
        cap = lambda step, text: page.evaluate("([s,t]) => __cap(s,t)", [step, text])
        card = lambda html: page.evaluate("(h) => __card(h)", html)
        hi = lambda sel: page.evaluate("(s) => __hi(s)", sel)
        txt = lambda i: page.evaluate("(i) => document.getElementById(i).textContent.trim()", i)
        wait = page.wait_for_timeout

        card("<h1>Last Bus Out</h1><p>Can workers without a car get to this shift, and home again?</p>"
             "<p class='s'>For the HR or operations lead who sets shift times at a Southeast Michigan warehouse, hospital or auto supplier</p>")
        wait(5000)
        card("<p>About <b>1 in 3</b> Detroit residents don't own a car.</p>"
             "<p>Transit apps answer a rider's question about one trip.</p>"
             "<p>Nobody tells the employer: <b>if my shift ends at 11:30 PM, who can still get home?</b></p>")
        wait(6500)
        card(None)

        page.click("#samples button >> nth=0")
        hi("#posting")
        cap("Step 1 · Paste a job posting", "A real-looking warehouse posting. Note the last line: “Reliable transportation required.”")
        wait(4500)
        hi("#go")
        cap("Step 2 · IBM Granite on watsonx.ai", "Granite reads the address, shift times and days out of the messy text.")
        wait(1200)
        page.click("#go")
        page.wait_for_function("() => !document.getElementById('result').hidden", timeout=90000)
        hi("#parsed")
        wait(3500)

        hi(None)
        cap("Step 3 · Every scheduled bus is checked", "A deterministic engine checks every DDOT and SMART trip for each neighborhood. "
            "Green = bus there and home. Amber = you can get there, but no bus home.")
        wait(6000)
        amber, green, last = txt("nAmber"), txt("nGreen"), txt("lastBus")
        hi("#lastBus")
        cap("The result", f"{amber} car-free households can ride to this shift. {green} can ride home.<br>{last}.")
        page.screenshot(path=str(OUT / "shot-1-posted-shift.png"))
        wait(7000)

        hi("#end")
        cap("Step 4 · Try a different shift end", "Drag the shift end earlier. The map recolors live, no AI involved.")
        wait(1500)
        end = int(page.evaluate("() => Number(document.getElementById('end').value)"))
        target = 23 * 60
        for v in range(end - 15, target - 1, -15):
            page.evaluate("([v,d]) => __setEnd(v,d)", [v, v == target])
            wait(1100)
        green2, last2 = txt("nGreen"), txt("lastBus")
        hi("#lastBus")
        cap("30 minutes earlier", f"End at {txt('endLabel')} instead: {green2} car-free households can now make the round trip.<br>{last2}.")
        page.screenshot(path=str(OUT / "shot-2-earlier-end.png"))
        wait(6500)

        page.wait_for_function(MEMO_READY, timeout=60000)
        hi("#memoBox")
        cap("Step 5 · Memo for the employer", "Granite writes a short memo from the computed facts. Every number in it is checked "
            "against the schedule data; if Granite invents one, the memo is replaced by a template.")
        wait(1200)
        page.screenshot(path=str(OUT / "shot-3-memo.png"))
        wait(6800)

        hi(None)
        cap("", "")
        card("<h1>Last Bus Out</h1><p>Granite reads the posting. <b>The schedules decide.</b></p>"
             "<p class='s'>Built with IBM Bob IDE · IBM Granite on watsonx.ai · public DDOT and SMART schedules · U.S. Census data<br>"
             "Honest limits: scheduled times, not live · one-seat rides only · Census estimates<br><br>"
             "github.com/CosmonautJones/last-bus-out</p>")
        wait(6000)

        print("memo:", txt("memo").encode("ascii", "replace").decode())
        print("meta:", txt("memoMeta").encode("ascii", "replace").decode())
        print("numbers:", amber, green, "|", last.encode("ascii", "replace").decode(), "|", green2, "|", last2.encode("ascii", "replace").decode())
        video = page.video
        ctx.close()
        browser.close()
        webm = Path(video.path())

    final = OUT / "last-bus-out-demo.webm"
    if final.exists():
        final.unlink()
    webm.rename(final)
    if shutil.which("ffmpeg"):
        mp4 = OUT / "last-bus-out-demo.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "0.6", "-i", str(final), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-crf", "20", "-r", "30", "-movflags", "+faststart", str(mp4)], check=True)
        final = mp4
        if shutil.which("ffprobe"):
            d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)],
                               capture_output=True, text=True).stdout.strip()
            print("duration_s:", d)
    print("saved:", final)


if __name__ == "__main__":
    main()
