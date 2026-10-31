"""VELOCITY VIETNAMESE PODCAST
15-min bilingual Vietnamese/English podcast at A2 level with translit
2 hosts: Minh & Linh
"""
import os, sys, json, asyncio, subprocess, random, requests, re
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont, ImageFilter

load_dotenv()

# Target-script transliteration is implemented below (self-contained)
# no extra dependency needed.
POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL") or "openai"

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
FONTS_DIR = BASE_DIR / "fonts"

HOST1_VOICE = "vi-VN-NamMinhNeural"
HOST2_VOICE = "vi-VN-HoaiMyNeural"

VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
FPS = 30

TOPICS = [
    'Đi tàu hỏa - Taking a train'
    'Món ăn đường phố - Street food dishes'
    'Thói quen buổi sáng - Morning routine habits'
    'Lễ hội địa phương - Local festivals'
    'Thời tiết hôm nay - Today’s weather'
    'Gặp gỡ bạn bè - Meeting friends'
    'Nghe nhạc và xem phim - Listening to music and watching movies'
    'Tập thể dục hằng ngày - Exercising every day'
    'Thành phố lý tưởng - The ideal city'
    'Học tiếng mỗi ngày - Learning languages every day'
    'Kế hoạch cuối tuần - Plans for the weekend'
    'Mua sắm quần áo - Shopping for clothes'
    'Đi lại bằng xe buýt - Getting around by bus'
    'Nhà hàng và đồ ăn - At the restaurant'
    'Sức khỏe và chăm sóc - Health and wellness',
]

YELLOW = (247, 202, 0)
DARK_BG = (11, 14, 27)
WHITE = (255, 255, 255)
LIGHT_GRAY = (170, 180, 205)
DARK_LINE = (50, 55, 75)

def load_font(size, bold=False, italic=False):
    fonts_to_try = []
    if italic and bold:
        fonts_to_try.extend([
            "C:/Windows/Fonts/segoeuiz.ttf", "C:/Windows/Fonts/arialbi.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf",
            str(FONTS_DIR / "DejaVuSans-BoldOblique.ttf"),
        ])
    elif italic:
        fonts_to_try.extend([
            "C:/Windows/Fonts/segoeuii.ttf", "C:/Windows/Fonts/ariali.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
            str(FONTS_DIR / "DejaVuSans-Oblique.ttf"),
        ])
    elif bold:
        fonts_to_try.extend([
            "C:/Windows/Fonts/Inter-Bold-slnt=0.ttf", "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
            str(FONTS_DIR / "DejaVuSans-Bold.ttf"),
        ])
    else:
        fonts_to_try.extend([
            "C:/Windows/Fonts/Inter-Regular-slnt=0.ttf", "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            str(FONTS_DIR / "DejaVuSans.ttf"),
        ])

    for fp in fonts_to_try:
        if Path(fp).exists():
            try: return ImageFont.truetype(fp, size)
            except: continue
    return ImageFont.load_default()

def load_target_font(size, bold=False):
    """Load the target-script font from the bundled fonts dir."""
    p = FONTS_DIR / "DejaVuSans.ttf"
    if p.exists():
        try:
            f = ImageFont.truetype(str(p), size)
            try:
                names = [n.decode() if isinstance(n, bytes) else n for n in f.get_variation_names()]
                if bold and "Bold" in names:
                    f.set_variation_by_name("Bold")
                elif not bold and "Regular" in names:
                    f.set_variation_by_name("Regular")
            except Exception:
                pass
            return f
        except Exception:
            pass
    return load_font(size, bold=bold)


def clean_text(text):
    text = re.sub(r'[\r\n]+', ' ', text)
    text = re.sub(r'\b(mm+|um+|uh+|ah+|äh+)\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _purify_target(text):
    """Remove leaked letters that do not belong in the target field. Keeps
    the target script, the **bold** markers and the 'Velocity Vietnamese' brand name."""
    if not text:
        return text
    text = clean_text(text)
    text = text.replace('**', chr(1))  # protect highlight markers
    text = text.replace('Velocity Vietnamese', chr(2))  # protect brand
    text = re.sub('[^' + chr(1) + chr(2) + chr(0x20) + '-' + chr(0x7E) + chr(0xA0) + '-' + chr(0x1EFF) + ']', '', text)

    text = text.replace(chr(1), '**')
    text = text.replace(chr(2), 'Velocity Vietnamese')
    text = _clean_empty_hl(text)
    text = " ".join(text.split())
    if not text:
        return ""
    return text


def _clean_empty_hl(text):
    """Drop highlight markers left empty after purification ('****')."""
    if not text or '**' not in text:
        return text
    text = re.sub(r'\*\*\s*\*\*', '', text)
    return re.sub(r'\s+', ' ', text).strip()


_LATIN_RANGES = [(0x20, 0x7E), (0xA0, 0xFF), (0x100, 0x17F), (0x1E00, 0x1EFF)]
_SCRIPT_RANGES = [[]]


def _in_ranges(o, ranges):
    for a, b in ranges:
        if a <= o <= b:
            return True
    return False


def _strip_hl(s):
    return s.replace(chr(42) + chr(42), "")


def _cap_sentences(s):
    out = []
    new_sent = True
    for ch in s:
        if new_sent and ch.isalpha():
            out.append(ch.upper())
            new_sent = False
        else:
            out.append(ch)
        if ch == "." or ch == "!" or ch == "?":
            new_sent = True
    return "".join(out).strip()


def _fix_punct(s):
    s = s.replace(chr(0xFF0C), ", ").replace(chr(0x3001), ", ")
    s = s.replace(chr(0x3002), ". ").replace(chr(0xFF0E), ". ")
    s = s.replace(chr(0xFF01), "! ").replace(chr(0xFF1F), "? ")
    s = s.replace(chr(0x061F), "? ").replace(chr(0x060C), ", ").replace(chr(0x061B), "; ")
    s = s.replace(chr(0x00AB), chr(34)).replace(chr(0x00BB), chr(34))
    s = s.replace(chr(0x2013), "-").replace(chr(0x2014), "-")
    s = s.replace(chr(0x2026), "...")
    s = s.replace(chr(0x0964), ". ").replace(chr(0x0965), ". ")
    while "  " in s:
        s = s.replace("  ", " ")
    for p in [",", ".", "?", "!"]:
        s = s.replace(" " + p, p)
    return s.strip()


def _clean_empty_hl(text):
    if not text or chr(42) + chr(42) not in text:
        return text
    while chr(42) * 4 in text:
        text = text.replace(chr(42) * 4, "")
    while (chr(42) * 2 + " " + chr(42) * 2) in text:
        text = text.replace(chr(42) * 2 + " " + chr(42) * 2, "")
    return " ".join(text.split())


def sanitize_english(text):
    if not text:
        return text
    text = text.replace(chr(42) * 2, "")
    text = text.replace(chr(0x2019), "'").replace(chr(0x2018), "'")
    text = text.replace(chr(0x201C), chr(34)).replace(chr(0x201D), chr(34))
    text = text.replace(chr(0x2026), "...")
    return " ".join(text.split())


def _is_ascii_word(s):
    return sum(1 for ch in s if "a" <= ch <= "z" or "A" <= ch <= "Z") >= 2


def _leftover(s):
    return any(ord(c) > 127 for c in s)


def _indic_translit(text, c_map, iv_map, s_map, virama, anusvara,
                    visarga, nukta, drop_final):
    if not text:
        return ""
    clean = _strip_hl(text)
    clean = clean.replace(chr(0x0901), chr(0x0902))
    clean = clean.replace(chr(0x0C01), chr(0x0C02))
    words_out = []
    for tok in clean.split(" "):
        if not tok:
            words_out.append("")
            continue
        res = []
        chars = list(tok)
        n = len(chars)
        i = 0
        while i < n:
            ch = chars[i]
            nxt = chars[i + 1] if i + 1 < n else ""
            if ch in c_map:
                base = c_map[ch]
                if nxt == virama or nxt == nukta:
                    res.append(base)
                    i += 2
                    continue
                if nxt in s_map:
                    res.append(base + s_map[nxt])
                    i += 2
                    continue
                if nxt == anusvara:
                    res.append(base)
                    i += 1
                    continue
                if nxt == "" or nxt == "-" or nxt == "'":
                    if drop_final:
                        res.append(base)
                    else:
                        res.append(base + "a")
                else:
                    res.append(base + "a")
                i += 1
            elif ch in iv_map:
                res.append(iv_map[ch])
                i += 1
            elif ch == anusvara:
                res.append("n")
                i += 1
            elif ch == visarga:
                res.append("h")
                i += 1
            elif ch == virama or ch == nukta:
                i += 1
            elif ch == chr(0x093D) or ch == chr(0x0C3D):
                res.append("'")
                i += 1
            else:
                res.append(ch)
                i += 1
        words_out.append("".join(res))
    out = _fix_punct(" ".join(words_out))
    if _leftover(out):
        return _translit_fallback(clean)
    out = _cap_sentences(out)
    if _is_ascii_word(out):
        return out.strip()
    return _translit_fallback(clean)



def to_accurate_translit(text):
    if not text:
        return ""
    clean = _strip_hl(text)
    out = _fix_punct(clean)
    if any(not _in_ranges(ord(c), _LATIN_RANGES) and c != " " for c in out):
        return _translit_fallback(clean)
    out = _cap_sentences(out)
    return out.strip()


def _translit_fallback(text):
    words = []
    cur = []
    for ch in text or "":
        if "a" <= ch <= "z" or "A" <= ch <= "Z":
            cur.append(ch)
        elif cur:
            words.append("".join(cur))
            cur = []
    if cur:
        words.append("".join(cur))
    return " ".join(words)



def sanitize_latin(text):
    """Convert leaked non-Latin characters to font-safe Latin equivalents so
    romaji/English never show tofu glyphs. Handles macrons, full-width forms
    and Vietnamese punctuation."""
    if not text:
        return text
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = text.replace('\u2019', "'").replace('\u2018', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2026', '...').replace('\u2014', ' - ').replace('\u2013', ' - ')
    text = text.replace('\u3001', ', ').replace('\u3002', '.').replace('\u30fb', ' ')
    text = text.replace('\uff0c', ',').replace('\uff0e', '.').replace('\uff01', '!')
    text = text.replace('\uff1f', '?').replace('\uff20', '@')
    _EXTRA_LATIN = {
        '\u00e6': 'ae', '\u00c6': 'AE',
        '\u00f8': 'o', '\u00d8': 'O',
        '\u0153': 'oe', '\u0152': 'OE',
        '\u00df': 'ss', '\u1e9e': 'SS',
        '\u0142': 'l', '\u0141': 'L',
        '\u0131': 'i',
        '\u0111': 'd', '\u0110': 'D',
        '\u00f0': 'd', '\u00d0': 'D',
        '\u00fe': 'th', '\u00de': 'TH',
    }
    def norm_letter(m):
        ch = m.group(0)
        if ch == '\u0101': return 'a'
        if ch == '\u014d': return 'o'
        if ch == '\u016b': return 'u'
        if ch == '\u012b': return 'i'
        if ch == '\u0113': return 'e'
        if ch == '\u0100': return 'A'
        if ch == '\u014c': return 'O'
        if ch == '\u016a': return 'U'
        if ch == '\u012a': return 'I'
        if ch == '\u0112': return 'E'
        if ch == '\u00e9': return 'e'
        if ch == '\u00e8': return 'e'
        if ch == '\u00ea': return 'e'
        if ch == '\u00ef': return 'i'
        if ch == '\u00f1': return 'n'
        if ch == '\u00fc': return 'u'
        if ch == '\u00f6': return 'o'
        if ch == '\u00e4': return 'a'
        if ch in _EXTRA_LATIN:
            return _EXTRA_LATIN[ch]
        import unicodedata as _ud
        _base = ''.join(
            c for c in _ud.normalize('NFKD', ch)
            if not _ud.combining(c))
        if _base and all(ord(c) < 128 for c in _base):
            return _base
        return ch
    text = re.sub(r'[\u00c0-\u024f\u0100-\u017f\u1e00-\u1eff]', norm_letter, text)
    text = re.sub(r'[\u3040-\u30ff\u4e00-\u9fff\uff00-\uffef\u3000-\u303f]', ' ', text)
    # final safety net: map remaining symbols to ASCII, else drop (prevents any tofu glyph)
    text = text.replace('\u2192', ' -> ').replace('\u2190', ' <- ').replace('\u2194', ' -- ')
    text = text.replace('\u2022', '-').replace('\u25cf', '-').replace('\u2605', '*').replace('\u2606', '*')
    out = []
    for ch in text:
        o = ord(ch)
        if 0x20 <= o <= 0x7E:
            out.append(ch)
        elif o in (0x0A, 0x0D):
            out.append(' ')
        else:
            out.append(' ')
    text = ''.join(out)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def sanitize_translit(text):
    """Transliteration (Revised Romanization) is plain Latin: same rules as sanitize_latin."""
    return sanitize_latin(text)

def auto_highlight_target(text):
    if '**' in text:
        return text
    stopwords = {'va', 'cua', 'la', 'co', 'trong', 'voi', 'mot', 'nhung', 'da', 'duoc', 'se', 'khong'}
    words = text.split()
    if len(words) < 2:
        return text
    candidates = []
    for idx, w in enumerate(words):
        clean_w = re.sub('[^A-Za-zÀ-ɏͰ-Ͽ]', '', w)
        if clean_w not in stopwords and len(clean_w) >= 2:
            candidates.append((len(clean_w), idx, w, clean_w))
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        best_idx = candidates[0][1]
        raw_w = words[best_idx]
        clean_w = candidates[0][3]
        highlighted = raw_w.replace(clean_w, "**" + clean_w + "**")
        words[best_idx] = highlighted
        return " ".join(words)
    return text


def draw_microphone_icon(draw, center_x, center_y, radius=24):
    draw.ellipse([center_x - radius, center_y - radius, center_x + radius, center_y + radius],
                 outline=YELLOW, width=3)
    w, h = 10, 18
    draw.rounded_rectangle([center_x - w//2, center_y - 12, center_x + w//2, center_y - 12 + h],
                           radius=4, fill=YELLOW)
    draw.arc([center_x - 10, center_y - 4, center_x + 10, center_y + 12],
             start=0, end=180, fill=YELLOW, width=3)
    draw.line([(center_x, center_y + 12), (center_x, center_y + 17)], fill=YELLOW, width=3)
    draw.line([(center_x - 7, center_y + 17), (center_x + 7, center_y + 17)], fill=YELLOW, width=3)

def draw_person_icon(draw, center_x, center_y):
    draw.ellipse([center_x - 6, center_y - 12, center_x + 6, center_y], fill=YELLOW)
    draw.chord([center_x - 12, center_y + 2, center_x + 12, center_y + 20],
               start=180, end=360, fill=YELLOW)

def draw_lang_badge(img, draw, center_x, center_y, radius=22, label="LG"):
    """Generic language badge: yellow ring with the 2-letter code."""
    draw.ellipse([center_x - radius, center_y - radius, center_x + radius, center_y + radius],
                 outline=YELLOW, width=3)
    try:
        bf = load_font(max(10, radius - 4), bold=True)
    except Exception:
        bf = ImageFont.load_default()
    draw.text((center_x, center_y), label, fill=YELLOW, font=bf, anchor="mm")


def draw_headphones_icon(draw, center_x, center_y):
    draw.arc([center_x - 14, center_y - 14, center_x + 14, center_y + 6],
             start=180, end=360, fill=YELLOW, width=3)
    draw.rounded_rectangle([center_x - 16, center_y - 3, center_x - 10, center_y + 11], radius=2, fill=YELLOW)
    draw.rounded_rectangle([center_x + 10, center_y - 3, center_x + 16, center_y + 11], radius=2, fill=YELLOW)

_SCRIPT_RANGES = []
_CJK_TRACKING_RATIO = 0.06


def _cjk_tracking(font):
    """Extra breathing room after each CJK glyph, scaled with font size."""
    try:
        size = font.size
    except Exception:
        size = 40
    return max(2, int(round(size * _CJK_TRACKING_RATIO)))


def _script_tokens(text, font, draw):
    """Word-level tokens; highlight runs stay single-span."""
    parts = re.split('(\\*\\*.*?\\*\\*)', text)
    tokens = []
    for part in parts:
        is_hl = False
        if part.startswith('**') and part.endswith('**') and len(part) > 4:
            is_hl = True
            part = part[2:-2]
            if not part:
                continue
        if not part:
            continue
        # Keep every space exactly (incl. around ** runs): split while
        # retaining separators so no gap is ever dropped or shifted.
        for w in re.split('( +)', part):
            if not w:
                continue
            if w.strip() == '':
                _sp = draw.textbbox((0, 0), ' ', font=font)[2]
                for _ch in w:
                    tokens.append((' ', False, _sp))
            else:
                bb = draw.textbbox((0, 0), w, font=font)
                tokens.append((w, is_hl, bb[2] - bb[0]))
    return tokens


def _vis_word(w):
    return w


def _vis_line(line):
    return line


def _wrap_tokens(tokens, max_w):
    """Greedy wrap tokens into visual lines that each fit max_w."""
    lines = []
    current_line = []
    current_line_width = 0

    for word, is_hl, w_width in tokens:
        if current_line_width + w_width <= max_w:
            current_line.append((word, is_hl, w_width))
            current_line_width += w_width
        else:
            if current_line:
                if current_line[-1][0] == ' ':
                    current_line_width -= current_line[-1][2]
                    current_line.pop()
                lines.append((current_line, current_line_width))
            if word == ' ':
                current_line = []
                current_line_width = 0
            else:
                current_line = [(word, is_hl, w_width)]
                current_line_width = w_width

    if current_line:
        if current_line[-1][0] == ' ':
            current_line_width -= current_line[-1][2]
            current_line.pop()
        lines.append((current_line, current_line_width))
    return lines

def _join_tokens(line, highlight=False):
    """Rebuild a wrapped line with its original spacing (never add spaces)."""
    return ''.join(f"**{w}**" if (highlight and hl and w != ' ') else w
                   for w, hl, _ww in line).strip()


def draw_lines_centered(draw, lines, center_y, font, line_height):
    """Draw pre-wrapped lines centered without re-wrapping, so karaoke
    highlighting can never shift the layout. Returns (ink_top, ink_bottom)."""
    ink_min_top = None
    ink_max = None
    total_height = len(lines) * line_height
    start_y = center_y - total_height // 2
    for idx, line in enumerate(lines):
        line = _vis_line(line)
        tokens = _script_tokens(line, font, draw)
        line_w = sum(tw for _tw, _th, tw in tokens)
        curr_x = (VIDEO_WIDTH - line_w) // 2
        curr_y = start_y + idx * line_height
        for word, is_yellow, w_w in tokens:
            if word == ' ':
                curr_x += w_w
                continue
            color = YELLOW if is_yellow else WHITE
            draw.text((curr_x, curr_y), word, fill=color, font=font)
            bb = draw.textbbox((curr_x, curr_y), word, font=font)
            if ink_min_top is None:
                ink_min_top, ink_max = bb[1], bb[3]
            else:
                ink_min_top = min(ink_min_top, bb[1])
                ink_max = max(ink_max, bb[3])
            curr_x += w_w
    if ink_min_top is None:
        ink_min_top = start_y
        ink_max = start_y + total_height
    return ink_min_top, ink_max

def _ro_ink_height(font, lines, max_w=1350):
    """Return the measured ink height of the given (already-wrapped) latin lines."""
    from PIL import Image, ImageDraw
    if not lines:
        return 0
    tmp = Image.new('RGB', (max_w, 200), (0, 0, 0))
    td = ImageDraw.Draw(tmp)
    probe = lines[0]
    bb = td.textbbox((0, 0), probe, font=font)
    h = bb[3] - bb[1]
    if len(lines) > 1:
        h += (len(lines) - 1) * int(font.size * 1.3)
    return h

def draw_english_translation(draw, text, center_y, font, max_w=1350, line_height=52):
    words = text.split()
    lines = []
    current_line = []
    
    for w in words:
        test_line = ' '.join(current_line + [w])
        bb = draw.textbbox((0, 0), test_line, font=font)
        if bb[2] - bb[0] <= max_w:
            current_line.append(w)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [w]
    if current_line:
        lines.append(' '.join(current_line))
        
    total_h = len(lines) * line_height
    start_y = center_y - total_h // 2

    ink_min_top = None
    ink_max = None
    for idx, line in enumerate(lines):
        lx = VIDEO_WIDTH // 2
        ly = start_y + idx * line_height + line_height // 2
        draw.text((lx, ly), line, fill=LIGHT_GRAY, font=font, anchor="mm")
        bb = draw.textbbox((lx, ly), line, font=font, anchor="mm")
        ink_min_top = bb[1] if ink_min_top is None else min(ink_min_top, bb[1])
        ink_max = bb[3] if ink_max is None else max(ink_max, bb[3])
    if ink_min_top is None:
        ink_min_top = start_y
        ink_max = start_y + total_h
    return ink_min_top, ink_max

_HB_TARGET = False


def _draw_target_block(cnv, lines, center_y, font, line_height):
    return draw_lines_centered(cnv, lines, center_y=center_y, font=font, line_height=line_height)


def _wrap_ro(text, font, max_w):
    tmp = Image.new("RGB", (8, 8))
    td = ImageDraw.Draw(tmp)
    tokens = _script_tokens(text, font, td)
    wrapped = _wrap_tokens(tokens, max_w)
    return [_join_tokens(line, highlight=True) for line, _wd in wrapped]


def create_frame(turn, output_path, frame_num=0, preserve_highlights=False):
    img = Image.new('RGB', (VIDEO_WIDTH, VIDEO_HEIGHT), DARK_BG)
    draw = ImageDraw.Draw(img)

    glow = Image.new('RGBA', (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse([(-200, VIDEO_HEIGHT-600), (600, VIDEO_HEIGHT+200)], fill=(30, 20, 60, 40))
    gdraw.ellipse([(VIDEO_WIDTH-500, -200), (VIDEO_WIDTH+300, 600)], fill=(30, 20, 60, 40))
    img.paste(glow, (0, 0), glow)

    f_title_white = load_font(36, bold=True)
    f_title_sub = load_font(18, bold=False)
    f_title_sub_muted = load_font(15, bold=False)
    f_ep = load_font(22, bold=True)
    f_speaker = load_font(26, bold=True)
    f_hablando = load_font(24, bold=False)
    f_target = load_target_font(64, bold=True)
    f_english = load_font(42, bold=False, italic=True)
    f_footer = load_font(22, bold=False)

    # === TOP HEADER ===
    header_y = 68
    draw_microphone_icon(draw, center_x=70, center_y=header_y, radius=24)

    draw.text((110, header_y), "VELOCITY", fill=WHITE, font=f_title_white, anchor="lm")
    v_bbox = draw.textbbox((110, header_y), "VELOCITY", font=f_title_white, anchor="lm")
    
    draw.text((v_bbox[2] + 8, header_y), "VIETNAMESE", fill=YELLOW, font=f_title_white, anchor="lm")
    s_bbox = draw.textbbox((v_bbox[2] + 8, header_y), "VIETNAMESE", font=f_title_white, anchor="lm")

    draw.text((s_bbox[2] + 8, header_y), "PODCAST", fill=WHITE, font=f_title_white, anchor="lm")
    p_bbox = draw.textbbox((s_bbox[2] + 8, header_y), "PODCAST", font=f_title_white, anchor="lm")

    draw.line([(p_bbox[2] + 20, 48), (p_bbox[2] + 20, 88)], fill=DARK_LINE, width=2)

    sub_x = p_bbox[2] + 35
    draw.text((sub_x, header_y - 12), "Vietnamese Podcast", fill=WHITE, font=f_title_sub, anchor="lm")
    draw.text((sub_x, header_y + 12), "Learn Through Conversations", fill=LIGHT_GRAY, font=f_title_sub_muted, anchor="lm")

    ep_num = (frame_num // 150) + 1 if isinstance(frame_num, int) else 1
    ep_str = f"EP {ep_num:02d}"
    draw.rounded_rectangle([(1640, 46), (1750, 90)], radius=8, fill=YELLOW)
    draw.text((1695, header_y), ep_str, fill=DARK_BG, font=f_ep, anchor="mm")

    draw_lang_badge(img, draw, center_x=1810, center_y=header_y, radius=22)

    draw.line([(0, 130), (VIDEO_WIDTH, 130)], fill=YELLOW, width=2)

    # === SPEAKER STATUS SECTION ===
    is_host1 = turn.get("speaker") == "Host1"
    speaker_name = "MINH" if is_host1 else "LINH"
    pill_x, pill_y = 120, 210
    pill_w, pill_h = 220, 52

    draw.rounded_rectangle([(pill_x, pill_y), (pill_x + pill_w, pill_y + pill_h)],
                           radius=26, outline=YELLOW, width=2)
    draw_person_icon(draw, center_x=pill_x + 36, center_y=pill_y + 26)
    draw.text((pill_x + 60, pill_y + 26), speaker_name, fill=YELLOW, font=f_speaker, anchor="lm")

    draw.text((pill_x + pill_w + 25, pill_y + 26), "dang noi", fill=LIGHT_GRAY, font=f_hablando, anchor="lm")

    # === MAIN TEXT ZONE: Vietnamese + Romaji, must BOTH fit above the center divider ===
    ZONE_TOP = 300
    DIV_Y = 615
    ZONE_BOTTOM = DIV_Y - 30
    ZONE_H = ZONE_BOTTOM - ZONE_TOP
    target_text = turn.get("target")
    if '**' not in target_text:
        target_text = auto_highlight_target(target_text)
    romaji_text = sanitize_translit(turn.get("translit", ""))
    if not re.search(r'[a-zA-Z]{2,}', romaji_text):
        romaji_text = to_accurate_translit(target_text)
    if not re.search(r'[a-zA-Z]{2,}', romaji_text):
        romaji_text = sanitize_latin(turn.get("english", ""))

    def _wrap(text, font, max_w):
        tokens = _script_tokens(text, font, draw)
        wrapped = _wrap_tokens(tokens, max_w)
        return [_join_tokens(line, highlight=True) for line, wd in wrapped]

    # 1) choose the largest Vietnamese font that wraps into <= 3 lines
    ja_font = None
    ja_size = 64
    final_lines = []
    for test_size in [64, 56, 48, 40, 34, 28, 24, 20]:
        tf = load_target_font(test_size, bold=True)
        tl = _wrap(target_text, tf, 1550)
        if len(tl) <= 3:
            ja_font, ja_size, final_lines = tf, test_size, tl
            break
    if ja_font is None:
        ja_font, ja_size = load_target_font(20, bold=True), 20
        all_lines = _wrap(target_text, ja_font, 1550)
        final_lines = all_lines[:3]
        if len(all_lines) > 3 and target_text:
            final_lines[-1] = final_lines[-1].rstrip() + "..."
    n_ja = len(final_lines)

    # 2) wrap romaji at the starting italic size
    ro_size = 40
    ro_font = load_font(ro_size, bold=True, italic=True)
    ro_lines = _wrap_ro(romaji_text, ro_font, 1350) if romaji_text else []
    n_ro = len(ro_lines)

    JA_RO_GAP = 72
    SAFE_BOTTOM = ZONE_BOTTOM - 6

    def _measure_block():
        """Render ja+ro to a temp canvas and return (ja_center, ro_center, ink_bottom).
        Mirrors the real draw path so measured ink is exactly what appears."""
        tmp = Image.new('RGB', (VIDEO_WIDTH, VIDEO_HEIGHT), DARK_BG)
        td = ImageDraw.Draw(tmp)
        ja_lh_ = int(ja_size * 1.4)
        ja_center = ZONE_TOP + len(final_lines) * ja_lh_ // 2
        _, ja_ib = _draw_target_block(td, final_lines, center_y=ja_center, font=ja_font, line_height=ja_lh_)
        if not n_ro:
            return ja_center, None, ja_ib
        ih = _ro_ink_height(ro_font, ro_lines)
        target_top = ja_ib + JA_RO_GAP
        ly0 = target_top + ih / 2
        ro_center = ly0 - ro_lh // 2 + (n_ro * ro_lh) // 2
        _, ro_ib = draw_english_translation(td, " ".join(ro_lines), center_y=ro_center,
                                            font=ro_font, max_w=1350, line_height=ro_lh)
        return ja_center, ro_center, ro_ib

    # 3) dynamically shrink BOTH fonts until the MEASURED ink block stays
    #    clear of the center divider (real ink, not just estimated line-h).
    ja_lh = int(ja_size * 1.4)
    ro_lh = int(ro_size * 1.3)
    while True:
        ja_center, ro_center, ink_bottom = _measure_block()
        if ink_bottom <= SAFE_BOTTOM or ja_size <= 20:
            break
        ja_size = max(20, ja_size - 2)
        ro_size = max(18, ro_size - 1)
        ja_font = load_target_font(ja_size, bold=True)
        ro_font = load_font(ro_size, bold=True, italic=True)
        final_lines = _wrap(target_text, ja_font, 1550)
        n_ja = len(final_lines)
        ro_lines = _wrap_ro(romaji_text, ro_font, 1350) if romaji_text else []
        n_ro = len(ro_lines)
        ja_lh = int(ja_size * 1.4)
        ro_lh = int(ro_size * 1.3)

    ja_center, ro_center, _ = _measure_block()
    _draw_target_block(draw, final_lines, center_y=ja_center, font=ja_font, line_height=ja_lh)
    if n_ro and ro_center is not None:
        draw_english_translation(draw, " ".join(ro_lines), center_y=ro_center,
                                 font=ro_font, max_w=1350, line_height=ro_lh)

    # === CENTER DIVIDER WITH DOT ===
    div_y = 615
    draw.line([(VIDEO_WIDTH//2 - 300, div_y), (VIDEO_WIDTH//2 + 300, div_y)], fill=YELLOW, width=2)
    draw.ellipse([(VIDEO_WIDTH//2 - 8, div_y - 8), (VIDEO_WIDTH//2 + 8, div_y + 8)], fill=YELLOW)

    # === ENGLISH TRANSLATION (ITALIC, WRAPPED) ===
    english_text = sanitize_latin(turn.get("english", ""))
    draw_english_translation(draw, english_text, center_y=715, font=f_english, max_w=1350, line_height=48)

    # === BOTTOM FOOTER ===
    draw.line([(0, 975), (VIDEO_WIDTH, 975)], fill=YELLOW, width=2)

    footer_y = 1025
    draw_headphones_icon(draw, center_x=VIDEO_WIDTH//2 - 270, center_y=footer_y)
    draw.text((VIDEO_WIDTH//2 - 240, footer_y), "Learn Vietnamese Naturally", fill=WHITE, font=f_footer, anchor="lm")
    
    fn_bbox = draw.textbbox((VIDEO_WIDTH//2 - 240, footer_y), "Learn Vietnamese Naturally", font=f_footer, anchor="lm")
    draw.line([(fn_bbox[2] + 20, footer_y - 12), (fn_bbox[2] + 20, footer_y + 12)], fill=DARK_LINE, width=2)
    
    draw.text((fn_bbox[2] + 40, footer_y), "velocityvietnamese.com", fill=WHITE, font=f_footer, anchor="lm")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, quality=92)


def parse_turns_json(content, target_key="target"):
    """Robustly parse JSON array of turns from LLM output, handling unescaped control chars, code fences, and partial json."""
    clean = content.strip()
    if "```json" in clean:
        clean = clean.split("```json")[1].split("```")[0].strip()
    elif "```" in clean:
        clean = clean.split("```")[1].split("```")[0].strip()

    try:
        obj = json.loads(clean, strict=False)
        if isinstance(obj, list):
            return obj
    except Exception:
        pass

    fixed = re.sub(r'(?<!\\)\n', r'\\n', clean)
    try:
        obj = json.loads(fixed, strict=False)
        if isinstance(obj, list):
            return obj
    except Exception:
        pass

    recovered = []
    start = None
    depth = 0
    for ci, ch in enumerate(clean):
        if ch == '{':
            if depth == 0:
                start = ci
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                chunk = clean[start:ci + 1]
                try:
                    t = json.loads(chunk, strict=False)
                    if isinstance(t, dict):
                        recovered.append(t)
                except Exception:
                    try:
                        chunk_fixed = re.sub(r'(?<!\\)\n', r'\\n', chunk)
                        t = json.loads(chunk_fixed, strict=False)
                        if isinstance(t, dict):
                            recovered.append(t)
                    except Exception:
                        pass
                start = None
    if recovered:
        return recovered

    regex = re.compile(
        r'\{\s*"speaker"\s*:\s*"(?P<speaker>[^"]+)"\s*,\s*'
        r'(?:"(?:' + target_key + r'|text|content|spanish)"\s*:\s*"(?P<tgt>.*?)"\s*,\s*)?'
        r'(?:"(?:romaji|translit|transliteration)"\s*:\s*"(?P<ro>.*?)"\s*,\s*)?'
        r'(?:"english"\s*:\s*"(?P<en>.*?)"\s*)?'
        r'\}', re.DOTALL
    )
    for m in regex.finditer(clean):
        spk = m.group("speaker") or "Host1"
        tgt = m.group("tgt") or ""
        ro = m.group("ro") or ""
        en = m.group("en") or ""
        if tgt:
            recovered.append({"speaker": spk, target_key: tgt, "translit": ro, "english": en})

    return recovered

def _format_history_block(history, max_turns=6):
    """Compact recent turns for the batch prompt (speaker + English + target text)."""
    lines = []
    for turn in (history or [])[-max_turns:]:
        if not isinstance(turn, dict):
            continue
        speaker = turn.get("speaker", "?")
        role = "Linh" if speaker == "Host2" else "Minh"
        en = clean_text(turn.get("english", ""))
        tx = clean_text(re.sub(r'\*\*(.*?)\*\*', r'\1', turn.get("target", "")))
        lines.append(f"{role} ({speaker}): EN: {en} / TX: {tx}")
    return "\n".join(lines)


def _fetch_turns_batch(topic, topic_tr, topic_en, start_turn, batch_size=10, history=None):
    """Fetch one small batch of turns with multi-model fallback and robust parsing."""
    current_host = "Host2" if start_turn % 2 == 0 else "Host1"
    next_host = "Host1" if current_host == "Host2" else "Host2"
    host_role = "Linh" if current_host == "Host2" else "Minh"

    history_block = _format_history_block(history)
    intro_instruction = ""
    if start_turn == 0:
        intro_instruction = ("IMPORTANT: This is the FIRST batch. Keep the introduction SHORT - just 2 lines total "
                             "(one from Linh/Host2, one from Minh/Host1), then immediately dive into the topic. "
                             "No long welcome speeches.\n")
    elif history_block:
        intro_instruction = ("IMPORTANT: This is a CONTINUATION. The conversation below is already in progress. "
                             "The first new turn MUST directly respond to the last line above: answer its question, "
                             "react with an opinion or feeling, then ask a follow-up question. "
                             "Do NOT greet, introduce yourself, welcome anyone, or restate the topic. "
                             "Keep ONE evolving thread: every turn answers or reacts to the previous turn, "
                             "never two disconnected monologues.\n")
    else:
        intro_instruction = "Continue naturally into the topic conversation. No new introductions.\n"

    history_section = ""
    if history_block:
        history_section = (f"Previous conversation (respond directly to the LAST line):\n{history_block}\n\n")

    prompt = f"""You are writing a Vietnamese/English learning podcast at A2 level with translit.
Topic: {topic}

{history_section}The dialogue so far is at turn {start_turn}. The current speaker is {host_role} ({current_host}).
Write the NEXT {batch_size} turns. Speakers STRICTLY alternate starting with {current_host}.

{intro_instruction}Each turn: 3-4 SHORT sentences (6-10 words each) with PERIODS for natural TTS pauses. 20-30 seconds spoken.
Simple present tense. A2 vocabulary. Natural Vietnamese. The translit field repeats the Vietnamese line exactly. NO filler sounds.
IMPORTANT: The "target" field MUST be written 100% in Vietnamese (Latin letters).
IMPORTANT: The "translit" field must repeat the "target" text exactly.
IMPORTANT: Highlight exactly 1 key A2 target vocabulary word in each turn using double asterisks, for example: "prefix **word** suffix."
IMPORTANT: Highlight exactly 1 key A2 target vocabulary word in each turn using double asterisks, for example: "prefix **word** suffix."
IMPORTANT: Format as a single compact JSON array without unescaped line breaks inside string values.

Return EXACTLY {batch_size} turns as a JSON array (no markdown):
[{{"speaker": "{current_host}", "target": "...", "translit": "...", "english": "..."}},
 {{"speaker": "{next_host}", "target": "...", "translit": "...", "english": "..."}}]"""

    candidate_models = [AI_MODEL, "openai", "mistral", "qwen"]
    models_to_try = []
    for mod in candidate_models:
        if mod and mod not in models_to_try:
            models_to_try.append(mod)

    for attempt, model_name in enumerate(models_to_try):
        try:
            resp = requests.post("https://gen.pollinations.ai/v1/chat/completions", json={
                "model": model_name,
                "messages": [
                    {"role": "system", "content": "You write natural A2-level Vietnamese podcast scripts with VERY clear punctuation. Every sentence must have at least 2 commas for natural TTS pauses. Minh and Linh strictly alternate. Highlight 1 key target word per turn in double asterisks. No filler sounds. CRITICAL: the target field must contain ONLY Vietnamese (Latin letters). Each host addresses the OTHER host by name: Linh greets Minh and Minh greets Linh. No host ever addresses themselves by their own name; the only exception is introducing yourself. The translit field must repeat the target text exactly. English belongs only in the english field. Output single compact JSON array without unescaped newlines inside strings."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.8
            }, headers={"Authorization": f"Bearer {POLLINATIONS_API_KEY}"} if POLLINATIONS_API_KEY else {}, timeout=45)
            if resp.status_code != 200:
                print(f"  Batch attempt {attempt+1} ({model_name}) returned HTTP {resp.status_code}", flush=True)
                continue
            content = resp.json()["choices"][0]["message"]["content"].strip()
            script = parse_turns_json(content, "target")
            valid = []
            for i, turn in enumerate(script):
                if not isinstance(turn, dict):
                    continue
                ja = turn.get("target") or turn.get("text") or turn.get("content") or turn.get("spanish") or ""
                en = turn.get("english") or turn.get("translation") or ""
                ro = sanitize_translit(turn.get("translit") or turn.get("translit") or turn.get("romanji") or "")
                ja = _purify_target(ja)
                if not ja:
                    continue
                if not re.search(r'[a-zA-Z]{2,}', ro):
                    ro = to_accurate_translit(ja)
                valid.append({
                    "speaker": current_host if i % 2 == 0 else next_host,
                    "target": clean_text(ja),
                    "translit": ro,
                    "english": clean_text(en) if en else "Translation unavailable"
                })
            if len(valid) >= 4:
                return valid
            else:
                print(f"  Batch attempt {attempt+1} ({model_name}) parsed only {len(valid)} turns, trying next model...", flush=True)
        except Exception as e:
            print(f"  Batch attempt {attempt+1} ({model_name}) failed: {e}", flush=True)
            import time
            time.sleep(1)
    return None


def _generate_topic():
    """Have the AI invent a brand-new random topic (unlimited variety).
    Returns '<topic - English>' or None on failure (caller falls back to TOPICS)."""
    seed = random.randint(100000, 999999)
    candidate_models = [AI_MODEL, "openai", "mistral"]
    for m in candidate_models:
        if not m:
            continue
        try:
            resp = requests.post("https://gen.pollinations.ai/v1/chat/completions", json={
                "model": m,
                "messages": [
                    {"role": "system", "content": "You invent fresh, interesting, everyday topics for a Vietnamese/English A2 learning podcast. Always pick something new and varied from all areas of daily life, as a SHORT noun phrase (2-5 words), NOT a full sentence."},
                    {"role": "user", "content": f"Create EXACTLY ONE brand-new topic (uniqueness seed {seed}) for a Vietnamese/English A2 podcast. Return ONLY one line in this exact format: <topic in Vietnamese> - <topic in English>. The first part must be a short noun phrase in Latin letters. No numbering, no bullets, no extra text."}
                ],
                "temperature": 1.1,
            }, headers={"Authorization": f"Bearer {POLLINATIONS_API_KEY}"} if POLLINATIONS_API_KEY else {}, timeout=45)
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"].strip().strip('"').strip()
                if content and " - " in content:
                    return content
        except Exception as e:
            print(f"  Topic gen ({m}) failed: {e}", flush=True)
    return None


def _fallback_script(topic_tr, topic_en, target=150):
    """Generate 150 unique, educational, progressive dialogue turns in Vietnamese
    with translit covering diverse conversation phases."""
    topic_translit = to_accurate_translit(topic_tr)
    phases = [
        [
            ('Host2', 'Chào Minh, **hôm nay** chúng ta nói về thời tiết nhé.', 'Hi Minh, today we will talk about the weather.'),
            ('Host1', 'Chào Linh, hôm nay trời **nắng** và ấm.', 'Hi Linh, today it is sunny and warm.'),
            ('Host2', 'Bạn có **thích** thời tiết như vậy không?', 'Do you like weather like this?'),
            ('Host1', 'Vâng, tôi **thích** lắm vì tôi có thể đi bộ.', 'Yes, I like it because I can walk.'),
            ('Host2', 'Tuy nhiên tối nay có thể **mưa**.', 'However, tonight it may rain.'),
            ('Host1', 'Đúng rồi, tôi sẽ mang **ô** đi làm.', 'That’s right, I will bring an umbrella to work.'),
            ('Host2', 'Mình hỏi thêm: bạn uống **nước** mỗi ngày không?', 'I ask more: do you drink water every day?'),
            ('Host1', 'Tôi uống **nước** buổi sáng và buổi tối.', 'I drink water in the morning and in the evening.'),
            ('Host2', 'Thật tốt! Bạn có ăn **trái cây** không?', 'That’s good! Do you eat fruit?'),
            ('Host1', 'Tôi ăn **chuối** và táo mỗi tuần.', 'I eat bananas and apples every week.'),
            ('Host2', 'Vậy chúng ta nhớ **giữ** sức khỏe nhé.', 'So let’s remember to stay healthy.'),
            ('Host1', 'Ok Linh, cảm ơn bạn. Tạm biệt!', 'Okay Linh, thank you. Goodbye!'),
        ],
    ]
    all_templates = []
    for ph in phases:
        all_templates.extend(ph)
    turns = []
    for i in range(target):
        _, t_tr, t_en = all_templates[i % len(all_templates)]
        spk = "Host2" if i % 2 == 0 else "Host1"
        turns.append({
            "speaker": spk,
            "target": t_tr,
            "translit": to_accurate_translit(t_tr),
            "english": t_en
        })
    return turns

def _extend_script(existing_turns, topic_tr, topic_en, target=150):
    fallback_pool = _fallback_script(topic_tr, topic_en, target)
    idx = 0
    cur_speaker = existing_turns[-1]["speaker"] if existing_turns else "Host1"
    while len(existing_turns) < target:
        cand = fallback_pool[idx % len(fallback_pool)]
        idx += 1
        needed_spk = "Host1" if cur_speaker == "Host2" else "Host2"
        existing_turns.append({
            "speaker": needed_spk,
            "target": cand["target"],
            "translit": cand["translit"],
            "english": cand["english"]
        })
        cur_speaker = needed_spk
    return existing_turns[:target]


def generate_script():
    topic = _generate_topic() or random.choice(TOPICS)
    topic_tr = topic.split(" - ")[0]
    topic_en = topic.split(" - ")[1]

    TARGET = int(os.getenv("SAMPLE_TURNS", "150") or 150)
    BATCH = 10
    all_turns = []
    consecutive_empty = 0
    import time as _time
    _deadline = _time.time() + 600  # generous 10 min cap

    while len(all_turns) < TARGET and consecutive_empty < 12 and _time.time() < _deadline:
        batch = _fetch_turns_batch(topic, topic_tr, topic_en, len(all_turns), BATCH, history=all_turns)
        if not batch:
            consecutive_empty += 1
            wait_s = min(15, 3 + consecutive_empty * 2)
            print(f"  API busy (consecutive fails: {consecutive_empty}) - waiting {wait_s}s before retrying...", flush=True)
            _time.sleep(wait_s)
            continue
        all_turns.extend(batch)
        consecutive_empty = 0
        print(f"  Script progress: {len(all_turns)}/{TARGET} turns", flush=True)
        if len(all_turns) < TARGET:
            _time.sleep(1)

    all_turns = all_turns[:TARGET]

    if not all_turns:
        print("  Using structured fallback script (150 unique turns)...", flush=True)
        all_turns = _fallback_script(topic_tr, topic_en, TARGET)
    elif len(all_turns) < TARGET:
        print(f"  Extending {len(all_turns)} turns to {TARGET} with topic conversation...", flush=True)
        all_turns = _extend_script(all_turns, topic_tr, topic_en, TARGET)

    # Short 2-line intro: FEMALE (Host2) first, then MALE (Host1)
    topic_translit = to_accurate_translit(topic_tr)
    all_turns[0]["speaker"] = "Host2"
    all_turns[0]["target"] = 'Chào Minh, **hôm nay** chúng ta nói về thời tiết nhé.'
    all_turns[0]["translit"] = to_accurate_translit('Chào Minh, **hôm nay** chúng ta nói về thời tiết nhé.')
    all_turns[0]["english"] = 'Hi Minh, today we will talk about the weather.'
    if len(all_turns) > 1:
        all_turns[1]["speaker"] = "Host1"
        all_turns[1]["target"] = 'Chào Linh, hôm nay trời **nắng** và ấm.'
        all_turns[1]["translit"] = to_accurate_translit('Chào Linh, hôm nay trời **nắng** và ấm.')
        all_turns[1]["english"] = 'Hi Linh, today it is sunny and warm.'
    # Final guarantee across ALL turns: ensure valid Latin romaji exists for every single turn
    for turn in all_turns:
        ja = turn.get("target", "")
        ja = _purify_target(ja)
        turn["target"] = ja
        ro = sanitize_translit(turn.get("translit", ""))
        if not re.search(r'[a-zA-Z]{2,}', ro):
            turn["translit"] = to_accurate_translit(ja)
        else:
            turn["translit"] = ro

    print(f"  Script: {len(all_turns)} turns, topic: {topic_tr}", flush=True)
    return all_turns, topic_tr, topic_en


def configure_edge_tts():
    """Stock edge-tts endpoint only: forcing api.msedgeservices.com breaks runners."""
    return None




async def generate_audio(turns, target_dir=None):
    configure_edge_tts()
    import edge_tts
    audio_files = []
    audio_dir = Path(target_dir) if target_dir else OUTPUT_DIR
    audio_dir.mkdir(parents=True, exist_ok=True)
    for i, turn in enumerate(turns):
        voice = HOST1_VOICE if turn["speaker"] == "Host1" else HOST2_VOICE
        filename = audio_dir / f"audio_{i:03d}.mp3"
        spoken_text = re.sub(r'\*\*(.*?)\*\*', r'\1', turn.get("target"))
        success = False
        word_boundaries = []
        engine = "edge"
        for attempt in range(5):
            try:
                configure_edge_tts()
                communicate = edge_tts.Communicate(spoken_text, voice, boundary="WordBoundary")
                _bounds = []
                _chunks = bytearray()
                async for _c in communicate.stream():
                    _t = _c.get("type")
                    if _t == "audio":
                        _chunks.extend(_c.get("data", b""))
                    elif _t == "WordBoundary":
                        _bounds.append({"offset": _c["offset"] / 10_000_000, "duration": _c["duration"] / 10_000_000, "text": _c.get("text", "")})
                if _chunks:
                    with open(str(filename), "wb") as _f:
                        _f.write(_chunks)
                word_boundaries = list(_bounds)
                if Path(filename).exists() and Path(filename).stat().st_size > 100:
                    success = True
                    break
                print(f"  Audio {i} attempt {attempt+1}/5: no audio received")
            except Exception as e:
                print(f"  Audio {i} attempt {attempt+1}/5 failed: {e}")
            if attempt < 4:
                _wait = [15.0, 45.0, 90.0, 180.0][attempt]
                print(f"  Audio {i} waiting {_wait:g}s before retry...")
                await asyncio.sleep(_wait)
        if not success:
            raise RuntimeError(f"Edge TTS failed for turn {i} after 5 attempts; no fallback allowed")
        try:
            r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(filename)], capture_output=True, text=True)
            duration = float(r.stdout.strip()) if r.stdout else 3.0
        except:
            duration = 3.0
        audio_files.append({"path": str(filename), "duration": duration, "speaker": turn["speaker"], "voice": voice, "engine": engine, "word_boundaries": word_boundaries})
        if (i + 1) % 25 == 0 or i == 0:
            print(f"  Audio {i} [{turn['speaker']}/{voice}] via {engine}: {duration:.1f}s, {len(word_boundaries)} bounds")
    return audio_files

_KARAOKE_SEP = " "
# Joiner that rebuilds the exact original spacing from karaoke tokens.
# Word languages use " "; char/cluster languages use "".


def _karaoke_marked(tokens, k):
    """Rebuild the karaoke line with token k highlighted, preserving spacing.

    The highlighted token keeps its exact position, so the wrapped subtitle
    lines are identical at every step: only the color changes, the layout
    never shifts. A pure-space step keeps the nearest real word highlighted
    (looking backward first), so no step is ever marker-free.
    """
    kk = k
    if 0 <= kk < len(tokens) and tokens[kk].strip() == "":
        j = kk
        while j >= 0 and tokens[j].strip() == "":
            j -= 1
        if j < 0:
            j = kk
            while j < len(tokens) and tokens[j].strip() == "":
                j += 1
        if j < len(tokens):
            kk = j
    return _KARAOKE_SEP.join(
        f"**{x}**" if (j == kk and x.strip() != "") else x
        for j, x in enumerate(tokens))


def _boundary_tokens_and_spans(clean, boundaries):
    """Align Edge TTS word boundaries to the text: (token texts, spans).

    Returns (None, None) when alignment fails. Skipped characters between
    boundaries (punctuation or spaces the engine does not emit) attach to
    the preceding token, so joining the tokens rebuilds the text exactly.
    """
    items = [(b.get("text", ""), b) for b in (boundaries or []) if b.get("text")]
    if not items or not clean:
        return None, None
    out, spans, pos = [], [], 0
    for t, b in items:
        raw = t
        i = clean.find(raw, pos)
        if i < 0:
            return None, None
        if i > pos:
            gap = clean[pos:i]
            if out:
                out[-1] += gap
            else:
                t = gap + raw
        try:
            start = float(b.get("offset", 0))
            end = start + float(b.get("duration", 0))
        except (TypeError, ValueError):
            return None, None
        out.append(t)
        spans.append([start, end])
        pos = i + len(raw)
    if pos < len(clean):
        if not out:
            return None, None
        out[-1] += clean[pos:]
    return out, spans


def _spans_for_tokens(tokens, aligned, spans):
    """Map display tokens back onto aligned boundary spans.

    Matching tolerates whitespace attached to boundary pieces (spaces the
    engine skips attach to the neighboring piece); returns None on any
    surprise (caller falls back to even split).
    """
    res, j = [], 0
    for tok in tokens:
        rest, s, e = tok, None, None
        while rest:
            if j >= len(aligned):
                return None
            p, (ps, pe) = aligned[j], spans[j]
            pm = p.strip()
            if not pm:
                j += 1
                continue
            if rest == pm or rest.startswith(pm):
                s = ps if s is None else s
                e = pe
                rest = rest[len(pm):]
                j += 1
            else:
                return None
        res.append([s, e])
    return res


def karaoke_tokens_for_text(target_text, boundaries=None):
    """Split a line into per-word highlight tokens.

    Edge TTS word boundaries are preferred when they rebuild the text
    (the engine's own spoken words); otherwise plain word split.
    """
    clean = re.sub('\\*\\*(.*?)\\*\\*', '\\1', target_text or "").strip()
    if not clean:
        return []
    if boundaries:
        aligned, _spans = _boundary_tokens_and_spans(clean, boundaries)
        if aligned is not None and "".join(aligned) == clean:
            return [a.strip() for a in aligned if a.strip()]
    return clean.split()


def karaoke_step_durations(tokens, duration, boundaries, target_text=None):
    """Per-token seconds: exact Edge spans when they map to tokens, else split."""
    n = len(tokens)
    if n == 0:
        return []
    if boundaries and target_text:
        clean = re.sub(r'\*\*(.*?)\*\*', r'\1', target_text or "").strip()
        aligned, spans = _boundary_tokens_and_spans(clean, boundaries)
        if (aligned is not None and "".join(aligned) == clean
                and "".join(tokens).replace(" ", "") == clean.replace(" ", "")):
            mapped = _spans_for_tokens(tokens, aligned, spans)
            if mapped is not None:
                total = sum(e - s for s, e in mapped) or duration
                durs = [(e - s) * duration / total for s, e in mapped]
                durs = [max(0.12, d) for d in durs]
                scale = duration / sum(durs)
                return [d * scale for d in durs]
    if boundaries and len(boundaries) == n:
        total = sum(b["duration"] for b in boundaries) or duration
        durs = [b["duration"] * duration / total for b in boundaries]
    else:
        durs = [duration / n] * n
    durs = [max(0.12, d) for d in durs]
    scale = duration / sum(durs)
    return [d * scale for d in durs]


def _ass_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def write_karaoke_files(turns, audio_files, out_dir):
    """Write word_timings.json + karaoke ASS subtitle data for the episode."""
    out_dir = Path(out_dir)
    t = 0.0
    events = []
    timings = []
    for turn, audio in zip(turns, audio_files):
        dur = audio["duration"]
        bounds = audio.get("word_boundaries", [])
        tokens = karaoke_tokens_for_text(turn.get("target", ""), bounds)
        steps = karaoke_step_durations(tokens, dur, bounds, turn.get("target", ""))
        cursor = t
        cells = []
        for tok, d in zip(tokens, steps):
            cells.append({"token": tok, "start": round(cursor, 3), "end": round(cursor + d, 3)})
            cursor += d
        timings.append({"speaker": turn["speaker"], "tokens": cells})
        if tokens:
            k_line = _KARAOKE_SEP.join("{\\k%d}%s" % (max(1, int(round(d * 100))), tok) for tok, d in zip(tokens, steps))
            events.append(f"Dialogue: 0,{_ass_timestamp(t)},{_ass_timestamp(t + dur)},VI,,0,0,0,,{k_line}")
        romaji = sanitize_translit(turn.get("translit", ""))
        if romaji:
            events.append(f"Dialogue: 0,{_ass_timestamp(t)},{_ass_timestamp(t + dur)},Translit,,0,0,0,,{romaji}")
        t += dur
    with open(out_dir / "word_timings.json", "w", encoding="utf-8") as f:
        json.dump(timings, f, indent=1, ensure_ascii=False)
    header = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n\n"
              "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Alignment, MarginV\n"
              "Style: KR,DejaVu Sans,64,&H0000CAF7,&H80000000,&H80000000,1,8,180\n"
              "Style: Translit,Arial,40,&H00CDB4AA,&H80000000,&H80000000,0,8,120\n\n"
              "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    with open(out_dir / "podcast_karaoke.ass", "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events) + "\n")
    return out_dir / "podcast_karaoke.ass"


def render_karaoke_preview(turns, audio_files, out_dir, max_turns=3):
    """Burnt-in per-word highlight preview for the first turns (local check)."""
    out_dir = Path(out_dir)
    prev_dir = out_dir / "karaoke_preview"
    prev_dir.mkdir(parents=True, exist_ok=True)
    segments = []
    for ti in range(min(max_turns, len(turns))):
        turn = turns[ti]
        audio = audio_files[ti]
        bounds = audio.get("word_boundaries", [])
        tokens = karaoke_tokens_for_text(turn.get("target", ""), bounds)
        if not tokens:
            continue
        steps = karaoke_step_durations(tokens, audio["duration"], bounds, turn.get("target", ""))
        parts = []
        for k in range(len(tokens)):
            marked = _karaoke_marked(tokens, k)
            step_turn = dict(turn)
            step_turn["target"] = marked
            img = prev_dir / f"t{ti:02d}_w{k:03d}.png"
            create_frame(step_turn, str(img), ti, preserve_highlights=True)
            part = prev_dir / f"t{ti:02d}_w{k:03d}.mp4"
            subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", str(img),
                            "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT},fps={FPS}",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p",
                            "-t", f"{steps[k]:.3f}", str(part)],
                           check=True, capture_output=True)
            parts.append(part)
        seg = prev_dir / f"seg_{ti:02d}.mp4"
        lst = prev_dir / f"seg_{ti:02d}.txt"
        with open(lst, "w") as f:
            for p in parts:
                f.write(f"file '{p.resolve().as_posix()}'\n")
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-i", audio["path"], "-c:v", "copy", "-c:a", "aac",
                        "-shortest", str(seg)], check=True, capture_output=True)
        segments.append(seg)
    preview = out_dir / "karaoke_preview.mp4"
    lst = prev_dir / "all.txt"
    with open(lst, "w") as f:
        for s in segments:
            f.write(f"file '{s.resolve().as_posix()}'\n")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", str(preview)], check=True)
    return preview


def _render_turn_segment(turn, audio, video_dir, i):
    """One video segment per turn with burnt-in per-word karaoke highlight."""
    video_dir = Path(video_dir)
    bounds = audio.get("word_boundaries", [])
    tokens = karaoke_tokens_for_text(turn.get("target", ""), bounds)
    steps = karaoke_step_durations(tokens, audio["duration"], bounds, turn.get("target", ""))
    if not tokens:
        img = video_dir / f"f_{i:04d}.png"
        create_frame(turn, str(img), i)
        parts = [(img, audio["duration"])]
    else:
        parts = []
        for k in range(len(tokens)):
            marked = _karaoke_marked(tokens, k)
            step_turn = dict(turn)
            step_turn["target"] = marked
            img = video_dir / f"f_{i:04d}_w{k:03d}.png"
            create_frame(step_turn, str(img), i, preserve_highlights=True)
            parts.append((img, steps[k]))
    if len(parts) == 1:
        img, dur = parts[0]
        clip = video_dir / f"c_{i:04d}.mp4"
        fade_start = max(0.0, dur - 0.3)
        subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", str(img), "-i", audio["path"],
            "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT},fps={FPS}",
            "-c:v", "libx264", "-c:a", "aac", "-b:a", "128k",
            "-pix_fmt", "yuv420p", "-preset", "veryfast",
            "-t", str(dur), "-af", f"afade=t=out:st={fade_start:.2f}:d=0.3",
            str(clip)
        ], check=True, capture_output=True)
        return clip
    word_clips = []
    for j, (img, d) in enumerate(parts):
        part = video_dir / f"c_{i:04d}_w{j:03d}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", str(img),
            "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT},fps={FPS}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
            "-t", f"{d:.3f}", str(part)], check=True, capture_output=True)
        word_clips.append(part)
    lst = video_dir / f"seg_{i:04d}.txt"
    with open(lst, "w") as f:
        for p in word_clips:
            f.write(f"file '{p.resolve().as_posix()}'\n")
    clip = video_dir / f"c_{i:04d}.mp4"
    fade_start = max(0.0, audio["duration"] - 0.3)
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
        "-i", audio["path"], "-c:v", "libx264", "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p", "-preset", "veryfast",
        "-af", f"afade=t=out:st={fade_start:.2f}:d=0.3",
        "-shortest", str(clip)], check=True, capture_output=True)
    for p in word_clips:
        p.unlink(missing_ok=True)
    lst.unlink(missing_ok=True)
    return clip


def create_video(turns, audio_files, video_dir=None):
    if video_dir is None:
        video_dir = OUTPUT_DIR / f"podcast_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    video_dir = Path(video_dir)
    video_dir.mkdir(parents=True, exist_ok=True)

    clips = []
    total_dur = 0

    for i, (turn, audio) in enumerate(zip(turns, audio_files)):
        clip = _render_turn_segment(turn, audio, video_dir, i)
        clips.append(clip)

        total_dur += audio["duration"]
        if (i + 1) % 25 == 0:
            print(f"  Frame {i+1}/{len(turns)}")

    concat = video_dir / "list.txt"
    with open(concat, "w") as f:
        for c in clips:
            f.write(f"file '{c.resolve().as_posix()}'\n")

    out = video_dir / "podcast_final.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                    "-movflags", "+faststart", str(out)], check=True)

    for c in clips:
        c.unlink(missing_ok=True)
    for a in audio_files:
        try:
            Path(a["path"]).unlink(missing_ok=True)
        except Exception:
            pass
    if concat.exists():
        concat.unlink(missing_ok=True)

    return out, total_dur


async def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("=" * 60)
    print("  VELOCITY VIETNAMESE PODCAST")
    print("=" * 60)

    print("\n[1/4] Generating script...")
    turns, topic_tr, topic_en = generate_script()

    video_dir = OUTPUT_DIR / f"podcast_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    video_dir.mkdir(parents=True, exist_ok=True)

    with open(video_dir / "script.json", "w", encoding="utf-8") as f:
        json.dump({"topic": topic_tr, "topic_en": topic_en, "turns": turns}, f, indent=2, ensure_ascii=False)

    print(f"\n[2/4] Generating audio ({len(turns)} turns)...")
    audio_files = await generate_audio(turns, video_dir)
    total_audio = sum(a["duration"] for a in audio_files)
    print(f"  Total audio: {total_audio/60:.1f} min")

    print(f"\n[2b/4] Writing karaoke subtitle data...")
    write_karaoke_files(turns, audio_files, video_dir)
    if os.getenv("KARAOKE_PREVIEW_TURNS"):
        try:
            preview = render_karaoke_preview(turns, audio_files, video_dir, max_turns=int(os.getenv("KARAOKE_PREVIEW_TURNS", "3")))
            print(f"  Karaoke preview: {preview}")
        except Exception as e:
            print(f"  Karaoke preview warn: {e}")
    print(f"\n[3/4] Creating video...")
    video_path, duration = create_video(turns, audio_files, video_dir)

    print(f"\n[4/4] Saving...")
    first_frame = video_dir / "f_0000.png"
    thumbnail_path = video_dir / "thumbnail.jpg"
    try:
        from PIL import Image as _Img
        if first_frame.exists():
            _Img.open(str(first_frame)).convert("RGB").save(str(thumbnail_path), quality=92)
    except Exception as e:
        print(f"  Thumbnail warn: {e}")

    title = build_podcast_title(topic_tr, topic_en)
    description = build_podcast_description(topic_tr, topic_en, len(turns), round(duration / 60, 1))
    tags = ["Learn Vietnamese", "Vietnamese", "Vietnamese Podcast", "Learn Vietnamese Naturally", "Vietnamese for Beginners", "Bilingual", "Vietnamese Listening", "Vietnamese Conversation", "Velocity Vietnamese", topic_tr, topic_en]
    meta_out = {
        "title": title,
        "description": description,
        "tags": tags,
        "category_english": topic_tr,
        "language": "Vietnamese",
        "duration_minutes": round(duration / 60, 1),
        "turns_count": len(turns),
        "video_path": str(video_path),
        "thumbnail_path": str(thumbnail_path),
        "generated_at": datetime.now().isoformat(),
    }
    (OUTPUT_DIR).mkdir(exist_ok=True)
    with open(OUTPUT_DIR / "latest_video.json", "w", encoding="utf-8") as f:
        json.dump(meta_out, f, indent=2, ensure_ascii=False)
    with open(OUTPUT_DIR / "latest_upload_info.json", "w", encoding="utf-8") as f:
        json.dump({"title": title, "description": description,
                   "category": topic_tr, "turns_count": len(turns)}, f, indent=2, ensure_ascii=False)

    print("=" * 60)
    print("  PODCAST COMPLETE!")
    print(f"  Topic: {topic_tr}")
    print(f"  Duration: {duration/60:.1f} min ({len(turns)} turns)")
    print(f"  Video: {video_path.name}")
    print("=" * 60)


def build_podcast_title(topic_tr, topic_en):
    titles = [
        f"Learn Vietnamese: {topic_tr} ({topic_en}) | Bilingual Vietnamese Podcast | Velocity Vietnamese",
        f"Vietnamese Conversation for Beginners: {topic_tr} | Minh & Linh | Velocity Vietnamese",
        f"Vietnamese Podcast: {topic_tr} ({topic_en}) | A2 Listening Practice",
        f"{topic_tr} | Speak Vietnamese Naturally with Minh & Linh | Velocity Vietnamese",
    ]
    return random.choice(titles)


def build_podcast_description(topic_tr, topic_en, turns_count, duration_min):
    description = (
        f"Welcome to Velocity Vietnamese Podcast! Today: {topic_tr} ({topic_en})."
        f"\n\nFree Vietnamese Guides and Vocabulary Blog: https://velocityvietnamese.com/"
        f"\nRead our latest Vietnamese Articles: https://velocityvietnamese.com/blog/\n\n"
        f"This episode: Minh and Linh talk in Vietnamese: {topic_tr} ({topic_en})."
        f"\nA2-level bilingual conversation - every line has English translation."
        f"\n"
        f"WHAT IS INSIDE THIS EPISODE:\n"
        f"{turns_count} practical Vietnamese phrases\n"
        f"Everyday conversational vocabulary\n"
        f"Natural native pronunciation\n\n"
        f"HOW TO USE THIS PODCAST:\n"
        f"1. Listen to the Vietnamese, try to understand\n"
        f"2. Read the English translation\n"
        f"3. Repeat the phrases out loud\n"
        f"4. Practice daily!\n\n"
        f"OFFICIAL WEBSITE and BLOG:\n"
        f"Website: https://velocityvietnamese.com/\n"
        f"Blog: https://velocityvietnamese.com/blog/\n\n"
        f"New episodes every day!\n\n"
        f"#LearnVietnamese #VietnamesePodcast #Bilingual #LanguageLearning #VelocityVietnamese"
    )
    return description
    return description

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('  Cancelled.')