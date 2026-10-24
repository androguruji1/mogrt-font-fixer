#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mogrt Font Fixer
Installed .mogrt files ke fonts padhta hai, jo system me missing hain unhe
free sites se dhundh ke install karta hai, baaki ke liye links wali report banata hai.

Mac aur Windows dono pe chalta hai.

Commands:
  scan [--force] [--open-report]   saare watch folders scan karo
  watch                            background me nazar rakho (auto-start isi ko chalata hai)
  gui [path ...]                   shortcut / app ke liye: path diya toh wo file, warna full scan
  file <path> [...]                ek .mogrt / .prproj / .aep file check karo
  add-folder <dir>                 ek aur folder watch list me jodo
  cleanup                          purane log / cache / kachra saaf karo
  remove-standins                  stand-in fonts hatao aur aage ke liye band karo
  status                           abhi ki haalat dikhao
  setup-windows / unsetup-windows  Windows: auto-start aur shortcut lagana / hatana
Sirf Python standard library use hoti hai (Mac pe download ke liye system ka curl).
"""
import base64
import gc
import gzip
import html
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import traceback
import urllib.parse
import zipfile

APP = os.environ.get("MFF_HOME") or os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")
VERSION = "2.0"
IS_MAC = sys.platform == "darwin"
IS_WIN = os.name == "nt"
if IS_WIN:
    _LOCAL = os.environ.get("LOCALAPPDATA") or os.path.join(HOME, "AppData", "Local")
    _ROAM = os.environ.get("APPDATA") or os.path.join(HOME, "AppData", "Roaming")
    _DEF_FONT_DIR = os.path.join(_LOCAL, "Microsoft", "Windows", "Fonts")      # sirf is user ke fonts, admin nahi chahiye
    _DEF_WATCH = os.path.join(_ROAM, "Adobe", "Common", "Motion Graphics Templates")
else:
    _DEF_FONT_DIR = os.path.join(HOME, "Library", "Fonts")
    _DEF_WATCH = os.path.join(HOME, "Library", "Application Support", "Adobe", "Common", "Motion Graphics Templates")
FONT_DIR = os.environ.get("MFF_FONT_DIR") or _DEF_FONT_DIR
DEFAULT_WATCH = [_DEF_WATCH]
NOWIN = {"creationflags": 0x08000000} if IS_WIN else {}     # Windows pe kaali window na khule
USE_URLLIB = IS_WIN or os.environ.get("MFF_HTTP") == "urllib"
HEARTBEAT_F = os.path.join(APP, "watch.alive")
WIN_FONT_KEY = r"Software\Microsoft\Windows NT\CurrentVersion\Fonts"
WIN_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
CONFIG_F = os.path.join(APP, "config.json")
STATE_F = os.path.join(APP, "state.json")
LOG_F = os.path.join(APP, "log.txt")
REPORT_F = os.path.join(APP, "report.html")
LASTSCAN_F = os.path.join(APP, "last_scan.json")
DEBUG_DIR = os.path.join(APP, "debug")
CACHE_DIR = os.path.join(APP, "cache")
UA_BROWSER = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
RETRY_NOTFOUND_SECS = 3 * 24 * 3600
POLL_SECS = 15
LOG_MAX = 1_000_000                 # log isse bada hua toh purana hissa hat jata hai
DEBUG_MAX_AGE = 7 * 86400
FONT_EXT = (".ttf", ".otf", ".ttc")
IGNORE = {"adobeinvisfont", "lastresort"}
# After Effects ke purane default fonts: project file me naam pada rehta hai, asal me use nahi hote
AE_DEFAULTS = {"myriadroman", "timesroman", "timesbold", "timesitalic", "timesbolditalic"}

STYLE_WORDS = ["Regular", "Bold", "Italic", "Light", "Medium", "Black", "Thin", "Heavy", "Book",
               "Roman", "Oblique", "SemiBold", "Semibold", "DemiBold", "Demibold", "ExtraBold",
               "Extrabold", "UltraBold", "ExtraLight", "Extralight", "UltraLight", "Condensed",
               "Cond", "Demi", "Hairline", "Display", "It", "Normal", "Narrow", "Extended",
               "Expanded", "Semi", "Extra", "Ultra"]


# ----------------------------------------------------------------- helpers
def log(msg):
    line = "%s  %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        if os.path.exists(LOG_F) and os.path.getsize(LOG_F) > LOG_MAX:
            os.replace(LOG_F, LOG_F + ".old")          # sirf ek purani file rehti hai
        with open(LOG_F, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    try:
        if sys.stdout and sys.stdout.isatty():
            print(msg, flush=True)
    except Exception:
        pass


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def load_config():
    cfg = load_json(CONFIG_F, {})
    cfg.setdefault("watch_dirs", DEFAULT_WATCH)
    cfg.setdefault("sources", ["google", "fontsquirrel", "dafont", "1001fonts"])
    if "befonts" not in cfg["sources"] and not cfg.get("sources_v2"):
        cfg["sources"].append("befonts")          # naya source purane config me bhi jodo
        cfg["sources_v2"] = True
        if os.path.exists(CONFIG_F):
            save_json(CONFIG_F, cfg)
    cfg.setdefault("notifications", True)
    cfg.setdefault("auto_open_report", True)
    cfg.setdefault("standins", True)              # paid font ki jagah milta-julta free font usi naam se
    cfg.setdefault("standin_default", "Montserrat")
    cfg.setdefault("standin_map", {})             # jaise {"Gilroy": "Poppins"}
    if not os.path.exists(CONFIG_F):
        save_json(CONFIG_F, cfg)
    return cfg


def norm(name):
    """Font naam compare karne ke liye: lowercase, sirf letters/digits, end ka 'regular' hata ke."""
    n = re.sub(r"[^a-z0-9]", "", (name or "").lower())
    if n.endswith("regular") and len(n) > 7:
        n = n[:-7]
    return n


def _http_urllib(url, ua, timeout, referer):
    import urllib.error
    import urllib.request
    headers = {"User-Agent": ua, "Accept-Encoding": "gzip", "Accept": "*/*"}
    if referer:
        headers["Referer"] = referer
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
            data = r.read()
            if (r.headers.get("Content-Encoding") or "").lower() == "gzip":
                data = gzip.decompress(data)
            return data
    except urllib.error.HTTPError as e:
        log("   http %s %s" % (e.code, url))
    except Exception as e:
        log("   http error %s: %s" % (url, e))
    return None


def http_get(url, ua=UA_BROWSER, timeout=40, referer=None):
    """Download. Mac pe system ka curl, Windows pe Python khud. bytes ya None."""
    if USE_URLLIB:
        return _http_urllib(url, ua, timeout, referer)
    cmd = ["curl", "-sS", "-L", "--compressed", "--max-time", str(timeout), "-A", ua,
           "-w", "\n%{http_code}", url]
    if referer:
        cmd[1:1] = ["-e", referer]
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout + 10)
    except Exception as e:
        log("   http error %s: %s" % (url, e))
        return None
    body, _, code = p.stdout.rpartition(b"\n")
    if p.returncode != 0 or not code.strip().startswith(b"2"):
        log("   http %s rc=%s %s" % (code.decode("ascii", "replace").strip(), p.returncode, url))
        return None
    return body


def notify(title, text):
    try:
        if IS_MAC:
            script = 'display notification %s with title %s' % (json.dumps(text), json.dumps(title))
            subprocess.run(["osascript", "-e", script], timeout=10,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif IS_WIN:
            ps = ("Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; "
                  "$n = New-Object System.Windows.Forms.NotifyIcon; $n.Icon = [System.Drawing.SystemIcons]::Information; "
                  "$n.Visible = $true; $n.ShowBalloonTip(8000, $env:MFF_NT, $env:MFF_NB, 'Info'); "
                  "Start-Sleep -Seconds 9; $n.Dispose()")
            env = dict(os.environ, MFF_NT=title, MFF_NB=text)
            subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps], env=env,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, **NOWIN)
    except Exception:
        pass


def open_path(path):
    try:
        if IS_WIN:
            os.startfile(path)                       # noqa: default browser me khulta hai
        elif IS_MAC:
            subprocess.run(["open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


# ------------------------------------------------------- font file parsing
def _name_table(read, off):
    """Ek sfnt font ke name table se {nameID: text}, aur variable instances ke PS naam.
    `read(offset, length)` bytes deta hai, taaki poori file memory me na aaye."""
    names, inst = {}, []
    try:
        num = struct.unpack(">H", read(off + 4, 2))[0]
        if num > 200:
            return names, inst
        directory = read(off + 12, num * 16)
        tables = {}
        for i in range(num):
            tag, _, toff, tlen = struct.unpack(">4sIII", directory[i * 16: i * 16 + 16])
            tables[tag] = (toff, tlen)
        if b"name" not in tables:
            return names, inst
        noff, nlen = tables[b"name"]
        nt = read(noff, min(nlen, 2_000_000))
        _, count, soff = struct.unpack(">HHH", nt[:6])
        for i in range(count):
            pid, eid, lid, nid, ln, so = struct.unpack(">HHHHHH", nt[6 + i * 12: 18 + i * 12])
            if nid > 25 and nid < 256:
                continue
            raw = nt[soff + so: soff + so + ln]
            try:
                txt = raw.decode("utf-16-be") if pid in (0, 3) else raw.decode("mac_roman")
            except Exception:
                continue
            txt = txt.replace("\x00", "").strip()
            if not txt:
                continue
            # English Windows naam ko priority
            if nid not in names or (pid == 3 and lid == 0x409):
                names[nid] = txt
        if b"fvar" in tables:
            foff, flen = tables[b"fvar"]
            fv = read(foff, min(flen, 200_000))
            _, _, axoff, _, axcount, axsize, icount, isize = struct.unpack(">HHHHHHHH", fv[:16])
            fam = names.get(16) or names.get(1) or ""
            p = axoff + axcount * axsize
            for i in range(icount):
                rec = fv[p + i * isize: p + (i + 1) * isize]
                sub_id = struct.unpack(">H", rec[0:2])[0]
                ps = None
                if isize >= axcount * 4 + 6:
                    ps_id = struct.unpack(">H", rec[axcount * 4 + 4: axcount * 4 + 6])[0]
                    ps = names.get(ps_id)
                if ps:
                    inst.append(ps)
                if names.get(sub_id):
                    prefix = names.get(25) or fam
                    inst.append(re.sub(r"[^A-Za-z0-9]", "", prefix) + "-" + re.sub(r"[^A-Za-z0-9]", "", names[sub_id]))
    except Exception:
        pass
    return names, inst


def _font_info(read):
    head = read(0, 12)
    offs = [0]
    if head[:4] == b"ttcf":
        n = min(struct.unpack(">I", head[8:12])[0], 64)
        offs = list(struct.unpack(">%dI" % n, read(12, 4 * n)))
    elif head[:4] not in (b"\x00\x01\x00\x00", b"OTTO", b"true", b"typ1"):
        return None
    ps, fam, variable = [], "", False
    for o in offs:
        names, inst = _name_table(read, o)
        if names.get(6):
            ps.append(names[6])
        if names.get(4):
            ps.append(names[4])           # full name bhi match ke liye
        if inst:
            variable = True
            ps.extend(inst)
        fam = fam or names.get(16) or names.get(1) or ""
    return {"ps": ps, "family": fam, "variable": variable} if ps else None


def font_info(buf):
    """Font ke bytes -> {'ps': [PostScript naam...], 'family': str, 'variable': bool}"""
    try:
        return _font_info(lambda off, ln: buf[off: off + ln])
    except Exception:
        return None


def font_info_file(path):
    """Wahi cheez file se, par sirf header aur name table padh ke (badi font files ke liye halka)."""
    try:
        with open(path, "rb") as f:
            def read(off, ln):
                f.seek(off)
                return f.read(ln)
            return _font_info(read)
    except Exception:
        return None


def _font_dirs():
    if IS_MAC:
        return [(FONT_DIR, True), ("/Library/Fonts", True), ("/System/Library/Fonts", True)]
    if IS_WIN:
        roam = os.environ.get("APPDATA") or ""
        return [(os.path.join(os.environ.get("WINDIR") or r"C:\Windows", "Fonts"), True), (FONT_DIR, True),
                # Adobe Fonts (Creative Cloud) ke activate hue fonts: bina extension ki files
                (os.path.join(roam, "Adobe", "CoreSync", "plugins", "livetype"), False)]
    return [(FONT_DIR, True)]


def _scan_font_dirs(dirs):
    """Folders ke fonts ke naam. Har file ka result cache hota hai, toh agli baar sirf nayi files padhi jati hain."""
    cache_f = os.path.join(CACHE_DIR, "fontlist.json")
    old = load_json(cache_f, {})
    new, have = {}, set()
    for d, need_ext in dirs:
        if not d or not os.path.isdir(d):
            continue
        for root, _, files in os.walk(d):
            for fn in files:
                if need_ext and not fn.lower().endswith(FONT_EXT):
                    continue
                p = os.path.join(root, fn)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                sig = [int(st.st_mtime), st.st_size]
                hit = old.get(p)
                if hit and hit[0] == sig:
                    names = hit[1]
                else:
                    info = font_info_file(p)
                    names = sorted({norm(n) for n in (info or {}).get("ps", [])})
                new[p] = [sig, names]
                have.update(names)
    if new != old:
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(cache_f + ".tmp", "w", encoding="utf-8") as f:
                json.dump(new, f)
            os.replace(cache_f + ".tmp", cache_f)
        except Exception:
            pass
    return have


def system_fonts():
    """System me jo fonts abhi available hain unke normalized naam."""
    have = set()
    if IS_MAC:
        js = ('ObjC.import("AppKit"); $.NSFontManager.sharedFontManager.availableFonts.js'
              '.map(function(x){return x.js}).join("\\n")')
        try:
            p = subprocess.run(["osascript", "-l", "JavaScript", "-e", js], timeout=60,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for line in p.stdout.decode("utf-8", "replace").splitlines():
                if line.strip():
                    have.add(norm(line))
        except Exception as e:
            log("font list (osascript) fail: %s" % e)
        if len(have) >= 20:
            # Mac ne list de di: bas apna Fonts folder aur dekh lo (abhi-abhi install hue fonts)
            return have | _scan_font_dirs([(FONT_DIR, True)])
    return have | _scan_font_dirs(_font_dirs())


# --------------------------------------------------- fonts nikalna (mogrt)
_STYLE_ALT = "|".join(sorted(set(STYLE_WORDS), key=len, reverse=True))
GUESS_RE = re.compile((r"(?<![A-Za-z0-9_\-])([A-Z][A-Za-z0-9_]{1,40}-(?:%s)(?:%s){0,3})(?![A-Za-z0-9_\-])"
                       % (_STYLE_ALT, _STYLE_ALT)).encode("ascii"))
COOLTYPE_RE = re.compile(rb"CoolTypeFont[\s\S]{0,48}?\(\xfe\xff((?:\x00[\x20-\x27\x2a-\x5b\x5d-\x7e]){1,80})\)")
B64_RE = re.compile(rb"[A-Za-z0-9+/]{80,}={0,2}")
FONT_KEYS = {"fonteditvalue", "postscriptname", "fontname", "fontpostscriptname"}


def fonts_from_definition(data):
    out = set()
    try:
        j = json.loads(data.decode("utf-8-sig", "replace"))
    except Exception:
        return out

    def walk(o, key=""):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, k)
        elif isinstance(o, list):
            for v in o:
                walk(v, key)
        elif isinstance(o, str) and key.lower() in FONT_KEYS:
            s = o.strip()
            if 1 < len(s) < 80:
                out.add(s)
    walk(j)
    return out


def fonts_from_aep(data):
    out = set()
    for m in COOLTYPE_RE.finditer(data):
        try:
            out.add(m.group(1).decode("utf-16-be").strip())
        except Exception:
            pass
    return {x for x in out if x}


def guess_fonts(data):
    """Binary / XML me 'Family-Style' jaise naam dhundhna (andaza, 100% pakka nahi)."""
    out = set()

    def grab(buf):
        for m in GUESS_RE.finditer(buf):
            out.add(m.group(1).decode("ascii"))
        if b"\x00" in buf[:4096] or b"\x00" in buf[-4096:]:
            # UTF-16 text: beech ke zero hata ke dobara
            for start in (0, 1):
                sl = buf[start::2]
                for m in GUESS_RE.finditer(sl):
                    out.add(m.group(1).decode("ascii"))
    grab(data)
    for m in B64_RE.finditer(data):
        chunk = m.group(0)
        try:
            dec = base64.b64decode(chunk + b"=" * (-len(chunk) % 4))
        except Exception:
            continue
        grab(dec)
    return out


def maybe_gunzip(data):
    if data[:2] == b"\x1f\x8b":
        try:
            return gzip.decompress(data)
        except Exception:
            pass
    return data


def scan_mogrt(path):
    res = {"definition": [], "aep": [], "guess": [], "members": [], "error": None}
    d, a, g = set(), set(), set()
    try:
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                n = info.filename
                low = n.lower()
                res["members"].append(n)
                if info.file_size > 150_000_000:
                    continue
                if low.endswith("definition.json"):
                    raw = z.read(n)
                    d |= fonts_from_definition(raw)
                    res["_definition_raw"] = raw
                elif low.endswith(".aegraphic"):
                    try:
                        with zipfile.ZipFile(io.BytesIO(z.read(n))) as z2:
                            for n2 in z2.namelist():
                                res["members"].append(n + " > " + n2)
                                if n2.lower().endswith((".aep", ".aepx")):
                                    a |= fonts_from_aep(z2.read(n2))
                    except zipfile.BadZipFile:
                        a |= fonts_from_aep(z.read(n))
                elif low.endswith((".aep", ".aepx")):
                    a |= fonts_from_aep(z.read(n))
                elif low.endswith((".prgraphic", ".prproj")):
                    g |= guess_fonts(maybe_gunzip(z.read(n)))
    except Exception as e:
        res["error"] = "%s: %s" % (type(e).__name__, e)
    res["definition"], res["aep"] = sorted(d), sorted(a)
    res["guess"] = sorted(x for x in g if norm(x) not in {norm(y) for y in d | a})
    return res


def scan_loose_file(path):
    """.prproj ya .aep seedha check karna."""
    with open(path, "rb") as f:
        data = maybe_gunzip(f.read())
    if path.lower().endswith((".aep", ".aepx")):
        return {"definition": [], "aep": sorted(fonts_from_aep(data)), "guess": [], "members": [], "error": None}
    found = fonts_from_aep(data)
    return {"definition": [], "aep": sorted(found), "guess": sorted(guess_fonts(data) - found),
            "members": [], "error": None}


# ------------------------------------------------------- family ka andaza
def family_candidates(ps):
    base = ps.split("-")[0] if "-" in ps else ps
    base = base.replace("_", " ")
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z0-9])|(?<=[A-Z])(?=[A-Z][a-z])|(?<=[0-9])(?=[A-Za-z])", " ", base)
    spaced = re.sub(r"\s+", " ", spaced).strip()
    cands = [spaced]
    words = spaced.split(" ")
    style_l = {w.lower() for w in STYLE_WORDS} | {"mt", "ps", "std", "pro", "lt"}
    while len(words) > 1 and words[-1].lower() in style_l:
        words = words[:-1]
        cands.append(" ".join(words))
    junk = {"personal", "personaluse", "personaluseonly", "demo", "trial", "free", "w00", "w01", "w02", "w05",
            "ot", "dot", "itc", "std", "pro", "lt", "mt", "ps", "com"}
    words = [w for w in spaced.split(" ") if w.lower() not in junk and w.lower() not in style_l]
    if words:
        cands.append(" ".join(words))
    if base != spaced:
        cands.append(base)
    seen, out = set(), []
    for c in cands:
        if c and c.lower() not in seen:
            seen.add(c.lower())
            out.append(c)
    return out


# ------------------------------------------------------------- resolver
class Resolver:
    def __init__(self, needed, cfg):
        self.needed = dict(needed)        # norm -> PostScript naam (jo abhi bhi chahiye)
        self.cfg = cfg
        self.done = {}                    # norm -> {source, file, variable}
        self.seen_urls = set()
        self._gf_index = None

    # --- package ke andar se sahi font uthana
    def harvest(self, name, data, source):
        hit = False
        if data[:2] == b"PK":
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    for info in z.infolist():
                        if info.filename.startswith("__MACOSX") or info.file_size > 40_000_000:
                            continue
                        if info.filename.lower().endswith(FONT_EXT):
                            hit |= self.harvest(os.path.basename(info.filename), z.read(info), source)
            except Exception as e:
                log("   zip kharab (%s): %s" % (source, e))
            return hit
        info = font_info(data)
        if not info:
            return False
        hits = [n for n in {norm(x) for x in info["ps"]} if n in self.needed]
        if not hits:
            return False
        dest = install_font(name, data)
        for n in hits:
            self.done[n] = {"ps": self.needed.pop(n), "source": source, "file": os.path.basename(dest),
                            "variable": info["variable"]}
            log("   INSTALL %s  <- %s  (%s)%s" % (self.done[n]["ps"], source, os.path.basename(dest),
                                                   "  [variable font]" if info["variable"] else ""))
        return True

    def fetch(self, url, source, **kw):
        if url in self.seen_urls:
            return False
        self.seen_urls.add(url)
        data = http_get(url, **kw)
        if not data:
            return False
        fname = urllib.parse.unquote(url.split("?")[0].rstrip("/").split("/")[-1]) or "font"
        return self.harvest(fname, data, source)

    # --- Google Fonts
    def gf_index(self):
        if self._gf_index is not None:
            return self._gf_index
        os.makedirs(CACHE_DIR, exist_ok=True)
        cache = os.path.join(CACHE_DIR, "google_families.json")
        idx = {}
        if os.path.exists(cache) and time.time() - os.path.getmtime(cache) < 14 * 86400:
            idx = load_json(cache, {})
        if not idx:
            raw = http_get("https://fonts.google.com/metadata/fonts", timeout=60)
            if raw:
                try:
                    txt = raw.decode("utf-8", "replace")
                    j = json.loads(txt[txt.index("{"):])
                    idx = {norm(f["family"]): f["family"] for f in j.get("familyMetadataList", [])}
                    save_json(cache, idx)
                except Exception as e:
                    log("   google list parse fail: %s" % e)
        self._gf_index = idx
        return idx

    def try_google(self, ps):
        idx = self.gf_index()
        fams = []
        for c in family_candidates(ps):
            real = idx.get(norm(c)) if idx else c
            if real and real not in fams:
                fams.append(real)
        for fam in fams:
            key = norm(ps)
            # 1) Google ka CSS API: alag-alag weight ki static .ttf files
            variants = ",".join("%d,%di" % (w, w) for w in range(100, 1000, 100))
            css_url = "https://fonts.googleapis.com/css?family=%s:%s" % (urllib.parse.quote_plus(fam), variants)
            if css_url not in self.seen_urls:
                self.seen_urls.add(css_url)
                css = http_get(css_url, ua="curl/8.4.0")
                if css:
                    for u in sorted(set(re.findall(rb"url\((https://[^)]+?\.(?:ttf|otf))\)", css))):
                        self.fetch(u.decode(), "Google Fonts")
            if key not in self.needed:
                return True
            # 2) Google Fonts ka GitHub repo (fallback)
            slug = re.sub(r"[^a-z0-9]", "", fam.lower())
            for lic in ("ofl", "apache", "ufl"):
                base = "https://raw.githubusercontent.com/google/fonts/main/%s/%s/" % (lic, slug)
                if base in self.seen_urls:
                    continue
                self.seen_urls.add(base)
                meta = http_get(base + "METADATA.pb", timeout=20)
                if not meta:
                    continue
                for fn in sorted(set(re.findall(rb'filename:\s*"([^"]+)"', meta))):
                    self.fetch(base + urllib.parse.quote(fn.decode()), "Google Fonts (GitHub)")
                break
            if key not in self.needed:
                return True
        return False

    # --- Font Squirrel
    def try_fontsquirrel(self, ps):
        for c in family_candidates(ps):
            slug = re.sub(r"[^a-z0-9]+", "-", c.lower()).strip("-")
            self.fetch("https://www.fontsquirrel.com/fonts/download/" + slug, "Font Squirrel",
                       referer="https://www.fontsquirrel.com/fonts/" + slug)
            if norm(ps) not in self.needed:
                return True
        return False

    # --- DaFont
    def try_dafont(self, ps):
        for c in search_terms(ps):
            page_url = "https://www.dafont.com/search.php?q=" + urllib.parse.quote_plus(c)
            if page_url in self.seen_urls:
                continue
            self.seen_urls.add(page_url)
            page = http_get(page_url)
            if not page:
                continue
            slugs = []
            for s in re.findall(rb"dl\.dafont\.com/dl/\?f=([A-Za-z0-9_]+)", page):
                if s not in slugs:
                    slugs.append(s)
            log("   DaFont '%s': %d result" % (c, len(slugs)))
            for s in slugs[:5]:
                self.fetch("https://dl.dafont.com/dl/?f=" + s.decode(), "DaFont", referer=page_url)
                if norm(ps) not in self.needed:
                    return True
        return False

    # --- 1001 Fonts
    def try_1001fonts(self, ps):
        for c in search_terms(ps):
            page_url = "https://www.1001fonts.com/search.html?search=" + urllib.parse.quote_plus(c)
            if page_url in self.seen_urls:
                continue
            self.seen_urls.add(page_url)
            page = http_get(page_url)
            if not page:
                continue
            slugs = []
            for s in re.findall(rb"/download/([a-z0-9\-]+)\.zip", page):
                if s not in slugs:
                    slugs.append(s)
            log("   1001 Fonts '%s': %d result" % (c, len(slugs)))
            for s in slugs[:5]:
                self.fetch("https://www.1001fonts.com/download/%s.zip" % s.decode(), "1001 Fonts",
                           referer=page_url)
                if norm(ps) not in self.needed:
                    return True
        return False

    # --- Befonts
    def try_befonts(self, ps):
        for c in search_terms(ps, 2):
            page_url = "https://befonts.com/?s=" + urllib.parse.quote_plus(c)
            if page_url in self.seen_urls:
                continue
            self.seen_urls.add(page_url)
            page = http_get(page_url)
            if not page:
                continue
            words = [w for w in re.sub(r"[^a-z0-9 ]", "", c.lower()).split(" ") if w]
            pages = []
            for u in re.findall(rb'href="(https://befonts\.com/[a-z0-9\-]+\.html)"', page):
                u = u.decode()
                slug = u.rsplit("/", 1)[-1]
                if u not in pages and all(w in slug for w in words):
                    pages.append(u)
            log("   Befonts '%s': %d page" % (c, len(pages)))
            for u in pages[:3]:
                if u in self.seen_urls:
                    continue
                self.seen_urls.add(u)
                fp = http_get(u, referer=page_url)
                if not fp:
                    continue
                for d in list(dict.fromkeys(re.findall(rb"https://befonts\.com/downfile/[A-Za-z0-9.]+", fp)))[:2]:
                    self.fetch(d.decode(), "Befonts", referer=u)
                if norm(ps) not in self.needed:
                    return True
        return False

    def resolve_all(self):
        table = {"google": self.try_google, "fontsquirrel": self.try_fontsquirrel,
                 "dafont": self.try_dafont, "1001fonts": self.try_1001fonts,
                 "befonts": self.try_befonts}
        for key, ps in sorted(self.needed.items(), key=lambda kv: kv[1].lower()):
            if key not in self.needed:
                continue                  # kisi aur font ke package me mil chuka
            log(" dhundh raha hun: %s" % ps)
            _beat_if_watcher()
            for src in self.cfg.get("sources", []):
                fn = table.get(src)
                if not fn:
                    continue
                try:
                    if fn(ps):
                        break
                except Exception as e:
                    log("   %s error: %s" % (src, e))
            if key in self.needed:
                log("   nahi mila: %s" % ps)


def search_terms(ps, limit=3):
    """Sites pe search ke liye: space wale naam pehle, chhota saaf naam bhi."""
    c = family_candidates(ps)
    spaced = [x for x in c if not (" " not in x and len(c) > 1 and x.lower() == c[0].replace(" ", "").lower())]
    return (spaced or c)[:limit]


def _win_broadcast():
    try:
        import ctypes
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001D, 0, 0, 0x0002, 1000, None)   # WM_FONTCHANGE
    except Exception:
        pass


def register_font(dest, data):
    """Windows: font ko is user ke liye register karna (Mac pe file rakhna hi kaafi hai)."""
    if not IS_WIN:
        return
    try:
        import ctypes
        import winreg
        info = font_info(data) or {}
        label = (info.get("ps") or [os.path.splitext(os.path.basename(dest))[0]])[0]
        kind = "OpenType" if data[:4] == b"OTTO" else "TrueType"
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, WIN_FONT_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, "%s (%s)" % (label, kind), 0, winreg.REG_SZ, dest)
        ctypes.windll.gdi32.AddFontResourceW(dest)
        _win_broadcast()
    except Exception as e:
        log("   Windows font register fail (%s): %s" % (os.path.basename(dest), e))


def unregister_font(dest):
    if not IS_WIN:
        return
    try:
        import ctypes
        import winreg
        ctypes.windll.gdi32.RemoveFontResourceW(dest)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WIN_FONT_KEY, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
            names, i = [], 0
            while True:
                try:
                    name, val, _ = winreg.EnumValue(k, i)
                except OSError:
                    break
                if isinstance(val, str) and os.path.normcase(val) == os.path.normcase(dest):
                    names.append(name)
                i += 1
            for name in names:
                winreg.DeleteValue(k, name)
        _win_broadcast()
    except Exception:
        pass


def install_font(name, data):
    os.makedirs(FONT_DIR, exist_ok=True)
    name = re.sub(r"[^A-Za-z0-9._\-\[\] ]", "_", name) or "font.ttf"
    if not name.lower().endswith(FONT_EXT):
        name += ".otf" if data[:4] == b"OTTO" else ".ttf"
    dest = os.path.join(FONT_DIR, name)
    stem, ext = os.path.splitext(name)
    i = 1
    while os.path.exists(dest):
        if os.path.getsize(dest) == len(data):
            register_font(dest, data)
            return dest                   # yahi file pehle se hai
        dest = os.path.join(FONT_DIR, "%s_%d%s" % (stem, i, ext))
        i += 1
    with open(dest, "wb") as f:
        f.write(data)
    register_font(dest, data)
    return dest


# ------------------------------------------------------------- stand-in
# Jo font kahin free nahi milta (paid), uski jagah ek milta-julta open-license
# Google font usi PostScript naam se install hota hai, taaki Premiere me "missing" na aaye.
STANDIN_PREFIX = "STANDIN__"
STANDIN_MAP = {            # font family ke naam ki shuruaat -> Google Fonts family
    "gilroy": "Urbanist", "gotham": "Montserrat", "proximanova": "Montserrat", "avenir": "Nunito Sans",
    "futura": "Jost", "helveticaneue": "Inter", "helvetica": "Inter", "sfpro": "Inter", "din": "Barlow",
    "edwardianscript": "Pinyon Script", "nimbussans": "Archivo", "voga": "Bodoni Moda", "didot": "Bodoni Moda",
    "bodoni": "Bodoni Moda", "times": "Tinos", "garamond": "EB Garamond", "impact": "Anton",
    "bebas": "Bebas Neue", "myriad": "Source Sans 3", "circular": "Outfit", "brandon": "Josefin Sans",
}
STANDIN_KEYWORDS = [
    (("script", "signature", "callig", "handwrit", "brush"), "Dancing Script"),
    (("mono", "typewriter", "code"), "JetBrains Mono"),
    (("condensed", "compressed", "narrow"), "Barlow Condensed"),
    (("slab",), "Roboto Slab"),
    (("serif", "roman", "display"), "Playfair Display"),
]
RIBBI = ("Regular", "Bold", "Italic", "Bold Italic")


def parse_style(ps):
    """PostScript naam se weight / italic / chauda-patla ka andaza."""
    st = ps.split("-", 1)[1] if "-" in ps else ""
    if not st:
        words = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", ps).split(" ")
        st = "".join(w for w in words[1:] if w.lower() in {x.lower() for x in STYLE_WORDS})
    low = st.lower()
    weight = 400
    for keys, w in ((("extralight", "ultralight", "extralig", "ultralig", "xlight"), 200), (("thin", "hairline"), 100),
                    (("semibold", "demibold", "semibol", "demibol", "demi"), 600),
                    (("extrabold", "ultrabold", "extrabol", "ultrabol", "xbold"), 800),
                    (("black", "blac", "heavy", "heav", "ultra", "fat"), 900), (("bold", "bol"), 700),
                    (("medium", "med"), 500), (("light", "lig"), 300)):
        if any(k in low for k in keys):
            weight = w
            break
    italic = "ital" in low or "obli" in low or low.endswith("it")
    wide = any(k in low for k in ("exte", "expa", "wide"))
    label = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", st).strip() or "Regular"
    return {"weight": weight, "italic": italic, "wide": wide, "label": label}


def sfnt_tables(buf):
    num = struct.unpack(">H", buf[4:6])[0]
    out = {}
    for i in range(num):
        tag, _, off, ln = struct.unpack(">4sIII", buf[12 + i * 16: 28 + i * 16])
        out[tag] = (off, ln)
    return out


def font_weight_italic(buf):
    try:
        t = sfnt_tables(buf)
        off = t[b"OS/2"][0]
        w = struct.unpack(">H", buf[off + 4: off + 6])[0]
        fs = struct.unpack(">H", buf[off + 62: off + 64])[0]
        return w, bool(fs & 1)
    except Exception:
        return 400, False


def _checksum(data):
    data = data + b"\0" * (-len(data) % 4)
    return sum(struct.unpack(">%dI" % (len(data) // 4), data)) & 0xFFFFFFFF


def rename_font(buf, ps, family, style, note):
    """Font ki name table badal ke naya naam dena (sirf single .ttf/.otf)."""
    if buf[:4] not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
        return None
    tables = sfnt_tables(buf)
    old, _ = _name_table(lambda o, n: buf[o: o + n], 0)
    italic = "italic" in style.lower()
    if style in RIBBI:
        fam1, sub2 = family, style
    else:
        base_style = re.sub(r"\s*Italic\s*", " ", style).strip()
        fam1, sub2 = (family + " " + base_style).strip(), ("Italic" if italic else "Regular")
    strings = {0: old.get(0, ""), 1: fam1, 2: sub2, 3: "MogrtFontFixer stand-in: " + ps, 4: (family + " " + style).strip(),
               5: "Version 1.000", 6: ps, 10: note, 13: old.get(13, ""), 14: old.get(14, ""), 16: family, 17: style}
    recs, blob = [], b""
    for pid, eid, lid, enc in ((1, 0, 0, "mac_roman"), (3, 1, 0x409, "utf-16-be")):
        for nid in sorted(strings):
            txt = strings[nid]
            if not txt:
                continue
            raw = txt.encode(enc, "replace")
            recs.append(struct.pack(">HHHHHH", pid, eid, lid, nid, len(raw), len(blob)))
            blob += raw
    name_tab = struct.pack(">HHH", 0, len(recs), 6 + 12 * len(recs)) + b"".join(recs) + blob

    data = {}
    for tag, (off, ln) in tables.items():
        if tag in (b"DSIG", b"name"):
            continue
        data[tag] = buf[off: off + ln]
    data[b"name"] = name_tab
    if b"head" in data:
        h = data[b"head"]
        data[b"head"] = h[:8] + b"\0\0\0\0" + h[12:]
    tags = sorted(data)
    n = len(tags)
    es = max(0, n.bit_length() - 1)
    sr = (1 << es) * 16
    header = buf[:4] + struct.pack(">HHHH", n, sr, es, n * 16 - sr)
    offset = 12 + 16 * n
    directory, body, head_pos = b"", b"", None
    for tag in tags:
        d = data[tag]
        if tag == b"head":
            head_pos = offset
        directory += struct.pack(">4sIII", tag, _checksum(d), offset, len(d))
        pad = d + b"\0" * (-len(d) % 4)
        body += pad
        offset += len(pad)
    out = bytearray(header + directory + body)
    if head_pos is not None:
        adj = (0xB1B0AFBA - _checksum(bytes(out))) & 0xFFFFFFFF
        out[head_pos + 8: head_pos + 12] = struct.pack(">I", adj)
    return bytes(out)


def standin_family(ps, cfg):
    user = {norm(k): v for k, v in (cfg.get("standin_map") or {}).items()}
    keys = [norm(c) for c in family_candidates(ps)]
    for table in (user, STANDIN_MAP):
        for k in keys:
            for prefix in sorted(table, key=len, reverse=True):
                if k.startswith(prefix):
                    return table[prefix]
    low = ps.lower()
    for words, fam in STANDIN_KEYWORDS:
        if any(w in low for w in words) and "sansserif" not in low:
            return fam
    return cfg.get("standin_default") or "Montserrat"


def google_family_files(family, wide=False):
    """Google Fonts se family ki static files (cache ke saath). [(bytes, weight, italic)]"""
    slug = re.sub(r"[^a-z0-9]", "", family.lower()) + ("_wide" if wide else "")
    d = os.path.join(CACHE_DIR, "gf", slug)
    os.makedirs(d, exist_ok=True)
    if not any(f.lower().endswith(".ttf") for f in os.listdir(d)):
        q = urllib.parse.quote_plus(family)
        if wide:
            urls = ["https://fonts.googleapis.com/css2?family=%s:wdth,wght@125,%d&display=swap" % (q, w) for w in (400, 700, 900)]
        else:
            variants = ",".join("%d,%di" % (w, w) for w in range(100, 1000, 100))
            urls = ["https://fonts.googleapis.com/css?family=%s:%s" % (q, variants)]
        i = 0
        for cu in urls:
            css = http_get(cu, ua="curl/8.4.0")
            for u in sorted(set(re.findall(rb"url\((https://[^)]+?\.ttf)\)", css or b""))):
                data = http_get(u.decode())
                if data and font_info(data):
                    with open(os.path.join(d, "%02d.ttf" % i), "wb") as f:
                        f.write(data)
                    i += 1
        if i == 0 and not wide:                 # fallback: GitHub repo ki static files
            gslug = re.sub(r"[^a-z0-9]", "", family.lower())
            for lic in ("ofl", "apache", "ufl"):
                base = "https://raw.githubusercontent.com/google/fonts/main/%s/%s/" % (lic, gslug)
                meta = http_get(base + "METADATA.pb", timeout=20)
                if not meta:
                    continue
                for fn in sorted(set(re.findall(rb'filename:\s*"([^"]+)"', meta))):
                    if b"[" in fn:
                        continue                # variable file stand-in ke kaam ki nahi
                    data = http_get(base + urllib.parse.quote(fn.decode()))
                    if data and font_info(data):
                        with open(os.path.join(d, "%02d.ttf" % i), "wb") as f:
                            f.write(data)
                        i += 1
                break
    out = []
    for fn in sorted(os.listdir(d)):
        if fn.lower().endswith(".ttf"):
            with open(os.path.join(d, fn), "rb") as f:
                b = f.read()
            w, it = font_weight_italic(b)
            out.append((b, w, it))
    return out


def make_standin(ps, cfg):
    """Milta-julta free font `ps` naam se install karo. {'of':..., 'file':...} ya None."""
    st = parse_style(ps)
    fam = standin_family(ps, cfg)
    files = google_family_files(fam, wide=True) if st["wide"] else []
    if not files:
        files = google_family_files(fam)
    if not files and fam != "Montserrat":
        fam = "Montserrat"
        files = google_family_files(fam)
    if not files:
        log("   stand-in ke liye %s download nahi hua" % fam)
        return None
    pool = [f for f in files if f[2] == st["italic"]] or files
    data, w, it = min(pool, key=lambda f: abs(f[1] - st["weight"]))
    display = family_candidates(ps)[0] + " (Stand-in)"
    new = rename_font(data, ps, display, st["label"],
                      "Stand-in for %s, made from the open-license font %s by Mogrt Font Fixer. Not the original typeface." % (ps, fam))
    if not new:
        return None
    os.makedirs(FONT_DIR, exist_ok=True)
    dest = os.path.join(FONT_DIR, STANDIN_PREFIX + re.sub(r"[^A-Za-z0-9._\-]", "_", ps) + ".ttf")
    unregister_font(dest)                 # purana stand-in ho toh pehle chhodo
    with open(dest, "wb") as f:
        f.write(new)
    register_font(dest, new)
    of = "%s %d%s" % (fam, w, " Italic" if it else "")
    log("   STAND-IN %s  <- %s  (%s)" % (ps, of, os.path.basename(dest)))
    return {"of": of, "file": os.path.basename(dest)}


def remove_standin_file(fn):
    p = os.path.join(FONT_DIR, os.path.basename(fn))
    if not os.path.basename(p).startswith(STANDIN_PREFIX) or not os.path.exists(p):
        return False
    unregister_font(p)
    try:
        os.remove(p)
        return True
    except OSError as e:
        log("   stand-in file nahi hati (koi app use kar raha hoga): %s" % e)
        return False


def remove_standins():
    n = 0
    if os.path.isdir(FONT_DIR):
        for fn in os.listdir(FONT_DIR):
            if fn.startswith(STANDIN_PREFIX) and remove_standin_file(fn):
                n += 1
    return n


def cleanup():
    """Kachra saaf: purane log, cache, debug files, adhoori downloads. Storage bharne nahi deta."""
    now, freed = time.time(), 0

    def rm(path):
        nonlocal freed
        try:
            if os.path.isdir(path):
                size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(path) for f in fs)
                shutil.rmtree(path, ignore_errors=True)
            else:
                size = os.path.getsize(path)
                os.remove(path)
            freed += size
        except OSError:
            pass

    try:
        for fn in os.listdir(APP):
            p = os.path.join(APP, fn)
            if fn.endswith(".tmp") or fn in ("python.tar.gz", "python.zip"):
                if now - os.path.getmtime(p) > 3600:
                    rm(p)
            elif fn == "daemon.log" and os.path.getsize(p) > LOG_MAX // 2:
                open(p, "w").close()
            elif fn == "log.txt.old" and now - os.path.getmtime(p) > 30 * 86400:
                rm(p)
        gf = os.path.join(CACHE_DIR, "gf")                  # stand-in ke liye download hue source fonts
        if os.path.isdir(gf):
            for fn in os.listdir(gf):
                p = os.path.join(gf, fn)
                rm(p)                                       # har scan ke baad poora saaf
        if os.path.isdir(DEBUG_DIR):
            files = sorted((os.path.join(DEBUG_DIR, f) for f in os.listdir(DEBUG_DIR)), key=os.path.getmtime)
            for i, p in enumerate(files):
                if now - os.path.getmtime(p) > DEBUG_MAX_AGE or i < len(files) - 5:
                    rm(p)
        pyc = os.path.join(APP, "__pycache__")
        if os.path.isdir(pyc):
            rm(pyc)
    except Exception:
        log("cleanup error:\n" + traceback.format_exc())
    if freed > 100_000:
        log("Safai: %.1f MB khali hua" % (freed / 1e6))
    return freed


# ---------------------------------------------------------------- report
def search_links(ps):
    cands = family_candidates(ps)
    if len(cands) > 1 and " " not in cands[-1] and cands[-1].lower() == cands[0].replace(" ", "").lower():
        cands = cands[:-1]                 # bina space wala roop search ke liye bekaar hai
    q = cands[-1] if len(cands[-1]) >= 3 else cands[0]
    e = urllib.parse.quote_plus(q)
    return [
        ("DaFont", "https://www.dafont.com/search.php?q=" + e),
        ("1001 Fonts", "https://www.1001fonts.com/search.html?search=" + e),
        ("Font Squirrel", "https://www.fontsquirrel.com/fonts/list/find_fonts?q%5Bterm%5D=" + e
         + "&q%5Bsearch_check%5D=Y"),
        ("Google Fonts", "https://fonts.google.com/?query=" + e),
        ("Adobe Fonts", "https://fonts.adobe.com/search?query=" + e),
        ("Google search", "https://www.google.com/search?q=" + urllib.parse.quote_plus('"%s" font download' % q)),
    ]


def write_report(state):
    fonts = state.get("fonts", {})
    notfound = sorted((v for v in fonts.values() if v.get("status") == "notfound"), key=lambda v: v["ps"].lower())
    installed = sorted((v for v in fonts.values() if v.get("status") == "installed"), key=lambda v: v["ps"].lower())
    standins = sorted((v for v in fonts.values() if v.get("status") == "standin"), key=lambda v: v["ps"].lower())
    sure = [v for v in notfound if not v.get("guess")]
    maybe = [v for v in notfound if v.get("guess")]
    esc = html.escape

    def rows(items):
        out = []
        for v in items:
            links = " ".join('<a href="%s" target="_blank">%s</a>' % (esc(u), esc(t)) for t, u in search_links(v["ps"]))
            used = ", ".join(esc(os.path.basename(m)) for m in v.get("mogrts", [])[:4])
            more = len(v.get("mogrts", [])) - 4
            if more > 0:
                used += " +%d aur" % more
            out.append('<tr><td class="f">%s</td><td class="l">%s</td><td class="u">%s</td></tr>' % (esc(v["ps"]), links, used))
        return "\n".join(out)

    def standin_rows():
        out = []
        for v in standins:
            links = " ".join('<a href="%s" target="_blank">%s</a>' % (esc(u), esc(t)) for t, u in search_links(v["ps"])[-2:])
            used = ", ".join(esc(os.path.basename(m)) for m in v.get("mogrts", [])[:3])
            out.append('<tr><td class="f">%s</td><td>%s</td><td class="l">%s</td><td class="u">%s</td></tr>'
                       % (esc(v["ps"]), esc(v.get("standin_of", "")), links, used))
        return "\n".join(out)

    standin_html = ""
    if standins:
        standin_html = ("<h2>Stand-in lage hain (%d)</h2><p class='s'>Ye paid fonts kahin free nahi mile, isliye inki jagah "
                        "milta-julta free font usi naam se install hua hai. Premiere me missing nahi aayega, par ye asli font "
                        "nahi hai, look thoda alag ho sakta hai. Client ko exact font chahiye toh asli kharid ke install karo "
                        "aur Fonts folder se STANDIN__ wali file hata do.</p><table><tr><th>Font</th><th>Iski jagah laga</th>"
                        "<th>Asli yahan</th><th>Kis mogrt me</th></tr>%s</table>" % (len(standins), standin_rows()))

    inst_rows = "\n".join(
        "<tr><td class='f'>%s</td><td>%s%s</td><td class='u'>%s</td></tr>" % (
            esc(v["ps"]), esc(v.get("source", "")),
            " (variable font: Premiere me na dikhe toh batana)" if v.get("variable") else "",
            time.strftime("%d %b %Y", time.localtime(v.get("when", 0))))
        for v in installed)
    page = """<!doctype html><html><head><meta charset="utf-8"><title>Mogrt Font Fixer report</title>
<style>
body{font:15px -apple-system,Helvetica,Arial,sans-serif;margin:32px auto;max-width:1000px;padding:0 20px;color:#1c1c1e;background:#fafafa}
@media(prefers-color-scheme:dark){body{background:#1c1c1e;color:#eee}a{background:#333!important;color:#9cc7ff!important}td,th{border-color:#3a3a3c!important}}
h1{font-size:24px}h2{font-size:18px;margin-top:34px}.s{color:#888}
table{border-collapse:collapse;width:100%%}td,th{text-align:left;padding:9px 8px;border-bottom:1px solid #e3e3e6;vertical-align:top}
td.f{font-weight:600;white-space:nowrap}td.u{color:#888;font-size:13px}
td.l a{display:inline-block;margin:2px 4px 2px 0;padding:3px 9px;border-radius:12px;background:#e8f0fe;color:#0b57d0;text-decoration:none;font-size:13px}
</style></head><body>
<h1>Mogrt Font Fixer</h1>
<p class="s">Last scan: %s &nbsp;|&nbsp; Mogrt files: %d &nbsp;|&nbsp; Auto-install hue: %d &nbsp;|&nbsp; Stand-in: %d &nbsp;|&nbsp; Nahi mile: %d</p>
<h2>Ye fonts auto nahi mile (%d)</h2>
<p class="s">Link pe click karo, seedha us font ki search khulegi. Download karke double-click se install kar lo. Paid fonts free sites pe nahi milenge.</p>
<table><tr><th>Font</th><th>Yahan dhundho</th><th>Kis mogrt me</th></tr>
%s</table>
%s
%s
<h2>Auto-install ho chuke (%d)</h2>
<table><tr><th>Font</th><th>Kahan se</th><th>Kab</th></tr>
%s</table>
<p class="s">Font install hone ke baad agar Premiere me abhi bhi missing dikhe toh project band karke dobara kholo ya Premiere restart karo.</p>
</body></html>""" % (
        time.strftime("%d %b %Y, %I:%M %p"), len(state.get("mogrts", {})), len(installed), len(standins), len(notfound),
        len(sure), rows(sure) or "<tr><td colspan=3>Sab mil gaye.</td></tr>",
        ("<h2>Shayad ye bhi (andaze se nikale naam, %d)</h2><p class='s'>Ye naam Premiere-made mogrt / project file "
         "ke andar se andaze se nikle hain, kuch galat bhi ho sakte hain.</p><table>%s</table>" % (len(maybe), rows(maybe)))
        if maybe else "",
        standin_html,
        len(installed), inst_rows)
    with open(REPORT_F, "w", encoding="utf-8") as f:
        f.write(page)


# ------------------------------------------------------------------ scan
def list_mogrts(cfg):
    out = {}
    for d in cfg["watch_dirs"]:
        d = os.path.expanduser(d)
        if not os.path.isdir(d):
            continue
        for root, _, files in os.walk(d):
            for fn in files:
                if fn.lower().endswith(".mogrt") and not fn.startswith("."):
                    p = os.path.join(root, fn)
                    try:
                        st = os.stat(p)
                        out[p] = [int(st.st_mtime), st.st_size]
                    except OSError:
                        pass
    return out


LOCK_F = os.path.join(APP, "scan.lock")


def run_scan(force=False, open_report=False, extra_files=None, announce=True):
    """Ek time pe ek hi scan chale."""
    try:
        if os.path.exists(LOCK_F) and time.time() - os.path.getmtime(LOCK_F) > 45 * 60:
            os.remove(LOCK_F)              # purana atka hua lock
        fd = os.open(LOCK_F, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        log("Scan pehle se chal raha hai, ye wala chhod diya")
        return [], []
    try:
        return _run_scan(force, open_report, extra_files, announce)
    finally:
        try:
            os.remove(LOCK_F)
        except OSError:
            pass


def _run_scan(force, open_report, extra_files, announce):
    cfg = load_config()
    state = load_json(STATE_F, {})
    state.setdefault("mogrts", {})
    state.setdefault("fonts", {})
    first_run = not state.get("first_scan_done")
    files = list_mogrts(cfg)
    missing_dirs = [d for d in cfg["watch_dirs"] if not os.path.isdir(os.path.expanduser(d))]
    log("SCAN shuru: %d mogrt files%s%s" % (len(files), " (force)" if force else "",
                                             "  | folder nahi mila: %s" % missing_dirs if missing_dirs else ""))
    # 1) har mogrt ke fonts (jo badla nahi uska purana result)
    old = state["mogrts"]
    new = {}
    zero_dumped = len(os.listdir(DEBUG_DIR)) if os.path.isdir(DEBUG_DIR) else 0
    for p, sig in files.items():
        if p in old and old[p].get("sig") == sig and not old[p].get("error"):
            new[p] = old[p]
            if new[p].get("definition") or new[p].get("aep") or new[p].get("guess"):
                new[p].pop("members", None)
            continue
        res = scan_mogrt(p)
        raw = res.pop("_definition_raw", None)
        res["sig"] = sig
        new[p] = res
        total = len(res["definition"]) + len(res["aep"]) + len(res["guess"])
        if total and not res["error"]:
            res.pop("members", None)                 # file list sirf gadbad wale mogrt ki rakho
        log(" %s -> %d fonts%s" % (os.path.basename(p), total, "  ERROR " + res["error"] if res["error"] else ""))
        if total == 0 and raw and zero_dumped < 5:      # debugging ke liye: jisme kuch nahi mila
            os.makedirs(DEBUG_DIR, exist_ok=True)
            with open(os.path.join(DEBUG_DIR, os.path.basename(p) + ".definition.json"), "wb") as f:
                f.write(raw[:300_000])
            zero_dumped += 1
    for p in extra_files or []:
        try:
            res = scan_mogrt(p) if p.lower().endswith(".mogrt") else scan_loose_file(p)
            res.pop("_definition_raw", None)
            res.pop("members", None)
            res["sig"] = [0, 0]
            res["extra"] = True
            new[p] = res
            log(" %s -> %d fonts" % (os.path.basename(p), len(res["definition"]) + len(res["aep"]) + len(res["guess"])))
        except Exception as e:
            log(" %s padh nahi paya: %s" % (p, e))
    for p, v in old.items():                           # pehle check ki hui loose files yaad rakho
        if v.get("extra") and p not in new and os.path.exists(p):
            new[p] = v
    state["mogrts"] = new

    # 2) kaunsa font kahan use hua
    usage, guess_only = {}, {}
    for p, res in new.items():
        for kind in ("definition", "aep", "guess"):
            for ps in res.get(kind, []):
                n = norm(ps)
                if not n or n in IGNORE or ps.startswith("."):
                    continue
                if n in AE_DEFAULTS and kind != "definition":
                    continue
                usage.setdefault(n, {"ps": ps, "mogrts": []})
                if p not in usage[n]["mogrts"]:
                    usage[n]["mogrts"].append(p)
                guess_only[n] = guess_only.get(n, True) and kind == "guess"

    # 3) missing nikalo
    have = system_fonts()
    fonts = state["fonts"]
    now = time.time()
    todo = {}
    for n, u in usage.items():
        rec = fonts.get(n, {})
        rec.update({"ps": u["ps"], "mogrts": u["mogrts"], "guess": guess_only.get(n, False)})
        if n in have:
            if rec.get("status") not in ("installed", "standin"):
                rec["status"] = "present"
        else:
            if rec.get("status") == "notfound" and not force and now - rec.get("tried", 0) < RETRY_NOTFOUND_SECS:
                pass
            else:
                todo[n] = u["ps"]
        fonts[n] = rec
    for n in list(fonts):                               # jo ab kisi mogrt me nahi, hata do
        if n in usage:
            continue
        st = fonts[n].get("status")
        if st == "standin" and files:                   # mogrt hat gaya toh uska stand-in font bhi hatao
            if remove_standin_file(fonts[n].get("file", "")):
                log(" stand-in hataya (ab kisi mogrt me nahi): %s" % fonts[n].get("ps"))
            del fonts[n]
        elif st not in ("installed", "standin"):
            del fonts[n]
    log(" system me fonts: %d | mogrt me alag fonts: %d | missing jinhe dhundhna hai: %d" % (len(have), len(usage), len(todo)))

    # 4) dhundho aur install karo
    newly_installed, newly_notfound = [], []
    if todo:
        r = Resolver(todo, cfg)
        r.resolve_all()
        for n, info in r.done.items():
            fonts[n].update({"status": "installed", "source": info["source"], "file": info["file"],
                             "variable": info["variable"], "when": now})
            newly_installed.append(info["ps"])
        for n, ps in r.needed.items():
            if fonts[n].get("status") != "notfound":
                newly_notfound.append(ps)
            fonts[n].update({"status": "notfound", "tried": now})

    # 5) jo kahin nahi mile: milta-julta free font usi naam se (stand-in)
    newly_standin = []
    if cfg.get("standins"):
        for n, rec in fonts.items():
            if rec.get("status") != "notfound" or rec.get("guess") or n in have:
                continue
            if not force and now - rec.get("standin_tried", 0) < 6 * 3600:
                continue
            rec["standin_tried"] = now
            try:
                res = make_standin(rec["ps"], cfg)
            except Exception:
                log("   stand-in error %s:\n%s" % (rec["ps"], traceback.format_exc()))
                res = None
            if res:
                rec.update({"status": "standin", "standin_of": res["of"], "file": res["file"], "when": now})
                newly_standin.append(rec["ps"])
                if rec["ps"] in newly_notfound:
                    newly_notfound.remove(rec["ps"])

    state["first_scan_done"] = True
    state["last_scan"] = now
    save_json(STATE_F, state)
    save_json(LASTSCAN_F, {
        "when": time.strftime("%Y-%m-%d %H:%M:%S"), "mogrt_count": len(files), "system_fonts": len(have),
        "installed_now": newly_installed, "notfound_now": newly_notfound, "standin_now": newly_standin,
        "all_standin": {v["ps"]: v.get("standin_of") for v in fonts.values() if v.get("status") == "standin"},
        "all_notfound": sorted(v["ps"] for v in fonts.values() if v.get("status") == "notfound"),
        "mogrts": {p: {k: v.get(k) for k in ("definition", "aep", "guess", "error", "members")} for p, v in new.items()},
    })
    write_report(state)
    total_nf = sum(1 for v in fonts.values() if v.get("status") == "notfound")
    log("SCAN khatam: install %d, stand-in %d, nahi mile (naye) %d, total nahi mile %d"
        % (len(newly_installed), len(newly_standin), len(newly_notfound), total_nf))

    if announce and cfg.get("notifications") and (newly_installed or newly_notfound or newly_standin or first_run or force):
        parts = []
        if newly_installed:
            parts.append("%d font install hue" % len(newly_installed))
        if newly_standin:
            parts.append("%d paid font ki jagah stand-in laga" % len(newly_standin))
        if newly_notfound:
            parts.append("%d nahi mile (report dekho)" % len(newly_notfound))
        if not parts:
            parts.append("Sab fonts theek hain" if total_nf == 0 else "Kuch naya nahi, %d font abhi bhi baaki" % total_nf)
        notify("Mogrt Font Fixer", ", ".join(parts))
    if open_report or ((newly_notfound or newly_standin) and cfg.get("auto_open_report")):
        open_path(REPORT_F)
    cleanup()
    del new, usage, have
    gc.collect()                                        # scan ki memory turant chhodo
    return newly_installed, newly_notfound


_IS_WATCHER = False


def pid_alive(pid):
    try:
        if IS_WIN:
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
            if not h:
                return False
            code = ctypes.c_ulong()
            ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
            ctypes.windll.kernel32.CloseHandle(h)
            return bool(ok) and code.value == 259          # STILL_ACTIVE
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def other_watcher():
    """Koi aur watcher chal raha ho toh uski pid, warna None."""
    try:
        if time.time() - os.path.getmtime(HEARTBEAT_F) > 180:
            return None
        with open(HEARTBEAT_F) as f:
            pid = int(f.read().strip() or 0)
        return pid if pid and pid != os.getpid() and pid_alive(pid) else None
    except Exception:
        return None


def _beat():
    try:
        with open(HEARTBEAT_F, "w") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass


def _beat_if_watcher():
    if _IS_WATCHER:
        _beat()


def stop_watcher():
    pid = other_watcher()
    if pid and IS_WIN:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **NOWIN)
    try:
        os.remove(HEARTBEAT_F)
    except OSError:
        pass
    return pid


def start_watcher():
    """Windows: watcher ko background me (bina window) chalu karna."""
    stop_watcher()
    flags = (0x08000000 | 0x00000200) if IS_WIN else 0
    subprocess.Popen([_pythonw(), os.path.abspath(__file__), "watch"], cwd=APP, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)


def watch():
    global _IS_WATCHER
    if other_watcher():
        log("Watcher pehle se chal raha hai, ye wala band")
        return
    _IS_WATCHER = True
    _beat()
    log("WATCH chalu (pid %d, v%s)" % (os.getpid(), VERSION))
    last = None
    last_full = 0
    me = os.path.abspath(__file__)
    my_mtime = os.path.getmtime(me)
    while True:
        try:
            _beat()
            if os.path.getmtime(me) != my_mtime:
                log("Script update hua, watcher restart ho raha hai")
                try:
                    os.remove(HEARTBEAT_F)
                except OSError:
                    pass
                if IS_WIN:
                    start_watcher()                     # Windows: naya khud chalu karo
                sys.exit(0)                             # Mac: launchd naye code ke saath dobara chalayega
            cfg = load_config()
            snap = list_mogrts(cfg)
            if last is None or snap != last:
                time.sleep(4)                           # file copy poori hone do
                if list_mogrts(cfg) == snap:
                    run_scan()
                    last = snap
                    last_full = time.time()
            elif time.time() - last_full > 24 * 3600:   # din me ek baar: dobara koshish + safai
                run_scan(announce=False)
                last_full = time.time()
            del snap
        except SystemExit:
            raise
        except Exception:
            log("WATCH error:\n" + traceback.format_exc())
        time.sleep(POLL_SECS)


# ------------------------------------------------------- Windows setup
def _pythonw():
    w = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return w if IS_WIN and os.path.exists(w) else sys.executable


def _win_folder(csidl):
    import ctypes
    buf = ctypes.create_unicode_buffer(520)
    ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf)
    return buf.value


def _win_shortcuts():
    out = []
    for csidl in (0x10, 0x02):                           # Desktop, Start Menu > Programs
        try:
            d = _win_folder(csidl)
            if d and os.path.isdir(d):
                out.append(os.path.join(d, "Mogrt Font Scan.lnk"))
        except Exception:
            pass
    return out


def trim_python():
    """Tool ke apne Python me se wo cheezein hatao jo kabhi kaam nahi aati (debug files, tests, GUI kit)."""
    root = os.path.join(APP, "python")
    if not os.path.isdir(root) or os.path.exists(os.path.join(root, ".trimmed")):
        return 0
    freed = 0
    for sub in ("Lib/test", "Lib/idlelib", "Lib/tkinter", "Lib/turtledemo", "Lib/ensurepip", "Lib/lib2to3",
                "Lib/site-packages", "Lib/unittest/test", "tcl", "libs", "include", "share"):
        d = os.path.join(root, *sub.split("/"))
        if os.path.isdir(d):
            freed += sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(d) for f in fs)
            shutil.rmtree(d, ignore_errors=True)
    for r, dirs, files in os.walk(root):
        for d in list(dirs):
            if d == "__pycache__":
                shutil.rmtree(os.path.join(r, d), ignore_errors=True)
        for f in files:
            low = f.lower()
            if low.endswith(".pdb") or low.startswith(("tcl", "tk")) and low.endswith(".dll") or low.startswith("_tkinter"):
                fp = os.path.join(r, f)
                try:
                    freed += os.path.getsize(fp)
                    os.remove(fp)
                except OSError:
                    pass
    try:
        open(os.path.join(root, ".trimmed"), "w").close()
    except OSError:
        pass
    log("setup: Python halka kiya, %.0f MB khali" % (freed / 1e6))
    return freed


def setup_windows():
    """Auto-start (login pe) aur 'Mogrt Font Scan' shortcut."""
    import winreg
    stop_watcher()
    trim_python()
    me = os.path.abspath(__file__)
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, WIN_RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, "MogrtFontFixer", 0, winreg.REG_SZ, '"%s" "%s" watch' % (_pythonw(), me))
    log("setup: auto-start laga diya")
    ps = ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:MFF_LNK); $s.TargetPath = $env:MFF_T; "
          "$s.Arguments = $env:MFF_A; $s.WorkingDirectory = $env:MFF_W; "
          "$s.Description = 'Mogrt Font Fixer: full scan (ya .mogrt file is pe drop karo)'; $s.Save()")
    for lnk in _win_shortcuts():
        env = dict(os.environ, MFF_LNK=lnk, MFF_T=_pythonw(), MFF_A='"%s" gui' % me, MFF_W=APP)
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], env=env, timeout=90,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **NOWIN)
        log("setup: shortcut %s -> %s" % (lnk, "ok" if r.returncode == 0 else "FAIL"))


def unsetup_windows():
    import winreg
    stop_watcher()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WIN_RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, "MogrtFontFixer")
    except OSError:
        pass
    for lnk in _win_shortcuts():
        try:
            os.remove(lnk)
        except OSError:
            pass
    print("Stand-in fonts hataye: %d" % remove_standins())


def main(argv):
    os.makedirs(APP, exist_ok=True)
    cmd = argv[0] if argv else "scan"
    args = argv[1:]
    try:
        if cmd == "scan":
            run_scan(force="--force" in args, open_report="--open-report" in args)
        elif cmd == "watch":
            watch()
        elif cmd == "gui":
            paths = [os.path.abspath(a) for a in args if not a.startswith("--")]
            notify("Mogrt Font Fixer", "Scan chalu hai, khatam hote hi report khulegi")
            run_scan(force=True, open_report=True, extra_files=paths or None)
        elif cmd == "cleanup":
            print("%.1f MB khali hua" % (cleanup() / 1e6))
        elif cmd == "setup-windows":
            setup_windows()
        elif cmd == "unsetup-windows":
            unsetup_windows()
        elif cmd == "start-watch":
            start_watcher()
        elif cmd == "stop-watch":
            stop_watcher()
        elif cmd == "trim-python":
            print("%.0f MB khali" % (trim_python() / 1e6))
        elif cmd == "version":
            print(VERSION)
        elif cmd == "file":
            paths = [os.path.abspath(a) for a in args if not a.startswith("--")]
            run_scan(force=True, open_report=True, extra_files=paths)
        elif cmd == "add-folder":
            cfg = load_config()
            for a in args:
                a = os.path.abspath(os.path.expanduser(a))
                if a not in cfg["watch_dirs"]:
                    cfg["watch_dirs"].append(a)
            save_json(CONFIG_F, cfg)
            print("Watch folders:", *cfg["watch_dirs"], sep="\n  ")
        elif cmd == "remove-standins":
            cfg = load_config()
            cfg["standins"] = False
            save_json(CONFIG_F, cfg)
            st = load_json(STATE_F, {})
            for v in st.get("fonts", {}).values():
                if v.get("status") == "standin":
                    v["status"] = "notfound"
            save_json(STATE_F, st)
            write_report(st)
            print("Stand-in fonts hataye: %d (aur aage ke liye band kar diya)" % remove_standins())
        elif cmd == "status":
            st = load_json(STATE_F, {})
            f = st.get("fonts", {})
            print("Mogrt files:", len(st.get("mogrts", {})))
            for s in ("installed", "standin", "notfound", "present"):
                print("%s: %d" % (s, sum(1 for v in f.values() if v.get("status") == s)))
        else:
            print(__doc__)
    except Exception:
        log("ERROR:\n" + traceback.format_exc())
        raise


if __name__ == "__main__":
    main(sys.argv[1:])
