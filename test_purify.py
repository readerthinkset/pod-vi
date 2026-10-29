"""Regression test: Vietnamese-field purification removes leaks from the script API.

Run with the standard library only:
    python test_purify.py        # exit 0 = pass, exit 1 = fail
"""
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import podcast_generator as pg

FAILURES = []


def check(name, got, must_have=(), must_missing=()):
    for s in must_have:
        if s not in got:
            FAILURES.append("%s: missing %r in %r" % (name, s, got))
    for s in must_missing:
        if s in got:
            FAILURES.append("%s: leaked %r in %r" % (name, s, got))


# 1. Leak mixed into target text is removed.
out = pg._purify_target('Xin chào các bạn 你好')
check("leak-plain", out, (), ('你好',))

# 2. Leak inside highlight markers is removed (empty markers go too).
out = pg._purify_target('Chào Minh, **hôm nay** chúng ta nói về thời tiết nhé. 你好')
check("leak-in-highlight", out, (), ('你好', '****'))

# 3. The brand name survives purification untouched.
brand = 'Velocity Vietnamese. Chào Minh, **hôm nay** chúng ta nói về thời tiết nhé.'
if pg._purify_target(brand) != brand:
    FAILURES.append("brand: damaged -> %r" % pg._purify_target(brand))

# 4. Clean input passes through unchanged.
clean = 'Chào Minh, **hôm nay** chúng ta nói về thời tiết nhé.'
if pg._purify_target(clean) != clean:
    FAILURES.append("clean-passthrough: changed -> %r" % pg._purify_target(clean))

# 5. Transliterator converts the test sample.
tr = pg.to_accurate_translit('Xin chào các bạn')
if tr != 'Xin chào các bạn':
    FAILURES.append('translit-passthrough: %r' % tr)

# 5b. Transliterator never returns empty on real content.
tr2 = pg.to_accurate_translit(clean)
if len(tr2) < 5:
    FAILURES.append('translit-empty: %r' % tr2)
# 6. End-to-end fragment of the generate_script guarantee loop.
turn = {"target": 'Chào Minh, **hôm nay** chúng ta nói về thời tiết nhé.', "translit": ""}
trg = pg._purify_target(turn.get("target", ""))
turn["target"] = trg
check("guarantee-writeback", turn["target"], (), ('你好', '****'))

# 7. Auto-highlight keeps existing markers or adds one.
hl = pg.auto_highlight_target(clean)
if "**" not in hl:
    FAILURES.append("highlight: no markers in %r" % hl)

# 8. Karaoke tokenizer yields tokens that rebuild the text.
toks = pg.karaoke_tokens_for_text(trg or clean)
if not toks:
    FAILURES.append("karaoke: no tokens")
elif "".join(toks).replace(" ", "") != (trg or clean).replace("**", "").replace(" ", ""):
    FAILURES.append("karaoke: rebuild mismatch %r" % toks)

# 9. Fallback turns address the OTHER host, never self (except self-introduction).
import json as _json
import re as _re
_fb = _json.loads((Path(__file__).resolve().parent.parent / "fleet_cache.json").read_text(encoding="utf-8"))["Vietnamese"]["fallback"]
_addr_bad = []
for _i, _t in enumerate(_fb):
    _en = _t.get("english", "") or ""
    _spk = _t.get("speaker", "")
    _own = "Linh" if _spk == "Host2" else "Minh"
    _other = "Minh" if _spk == "Host2" else "Linh"
    _el = _en.lower()
    if _re.search(r"%s" % _own.lower(), _el) and not _re.search(r"(i'm|i am|this is|my name is) %s" % _own.lower(), _el):
        _addr_bad.append((_i, _en))
    if _i < 2 and _other.lower() not in _el:
        _addr_bad.append((_i, "intro-missing-other: " + _en))
if _addr_bad:
    FAILURES.append('addressing: %r' % (_addr_bad,))

# 10. Karaoke marked lines preserve spacing exactly at every highlight step.
_mtoks = pg.karaoke_tokens_for_text(trg or clean)
_mplain = (trg or clean).replace("**", "").strip()
if not _mtoks:
    FAILURES.append("karaoke-marked: no tokens")
else:
    for _k in range(len(_mtoks)):
        _m = pg._karaoke_marked(_mtoks, _k)
        if _m.replace("**", "") != _mplain:
            FAILURES.append("karaoke-marked: spacing lost at step %d: %r" % (_k, _m))
            break

# 11. Tokenizer keeps spaces around highlight runs (exact round-trip).
class _StubDraw:
    def textbbox(self, xy, text, font=None):
        return (0, 0, 10 * len(text), 10)
if _mtoks:
    _mid = pg._karaoke_marked(_mtoks, len(_mtoks) // 2)
    _st = pg._script_tokens(_mid, None, _StubDraw())
    _rt = "".join(_t[0] for _t in _st)
    if _rt != _mid.replace("**", ""):
        FAILURES.append("tokenizer-space: %r became %r" % (_mid, _rt))

# 12. Wrapped subtitle lines never shift between highlight steps.
if _mtoks:
    _wraps = []
    for _k in range(len(_mtoks)):
        _mk = pg._karaoke_marked(_mtoks, _k)
        _tk = pg._script_tokens(_mk, None, _StubDraw())
        _w = pg._wrap_tokens(_tk, 150)
        _wraps.append([[_x[0] for _x in _line] for _line, _wd in _w])
    if any(_w != _wraps[0] for _w in _wraps):
        FAILURES.append("wrap-stable: lines shift between steps: %r" % (_wraps,))

if FAILURES:
    print("FAIL %d" % len(FAILURES))
    for f in FAILURES:
        print(" -", f)
    sys.exit(1)
print("PASS")
