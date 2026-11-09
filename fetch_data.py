#!/usr/bin/env python3
"""変体仮名画像を全取得してdata.jsonを生成するスクリプト"""
import subprocess, re, json, os, sys
from html.parser import HTMLParser

BASE_URL = "http://www.book-seishindo.jp/kana/"
PAGES = ["onjun_1", "onjun_2", "onjun_3"]
OUT_DIR = os.path.join(os.path.dirname(__file__), "images")

# bgcolor -> level
LEVEL_MAP = {
    "#f3d3a9": 2,  # 現行の五十音かなと同じ字母
    "#cff894": 1,  # 比較的よく使われる変体仮名
    "#d1cc9c": 3,  # それ以外
    "#fcfc61": None,  # 見出し行（あ行/い行 etc）
}

class HentaiganaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.entries = []  # {src, kana, kanji, level}
        self._current_kana = None
        self._current_kanji = None
        self._current_level = None
        self._in_kanji_td = False
        self._in_kanji_span = False
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "td":
            bg = (attrs.get("bgcolor") or "").lower()
            if bg == "#fcfc61":
                # 見出し行: 次のaタグのnameから仮名を取る
                self._current_kanji = None
                self._current_level = None
                self._in_kanji_td = False
            elif bg in ("#f3d3a9", "#cff894", "#d1cc9c"):
                self._current_level = LEVEL_MAP[bg]
                self._current_kanji = None
                self._in_kanji_td = True
            else:
                self._in_kanji_td = False
        elif tag == "a" and self._in_kanji_td:
            pass
        elif tag == "span" and self._in_kanji_td:
            self._in_kanji_span = True
            self._kanji_buf = ""
        elif tag == "a":
            # 見出し行のaタグからkanaを取る
            name = attrs.get("name", "")
            # name は "a", "i", "u" etc — 後でaltから取る
            pass
        elif tag == "img":
            src = attrs.get("src", "")
            alt = attrs.get("alt", "")
            if src.endswith(".jpg") and alt and len(alt) >= 1 and 'ぁ' <= alt[0] <= 'ゖ':
                kana = alt[0]
                kanji = alt[1:].strip() if len(alt) > 1 else ""
                # HTMLの不正なクォートなど非CJK文字を除去（基本CJK + 互換漢字）
                kanji = re.sub(r'[^　-鿿豈-﫿]', '', kanji)
                # 複数文字は異体字の併記。先頭1文字を主、残りをextra_kanjiとして保持
                extra = list(kanji[1:]) if len(kanji) > 1 else []
                kanji = kanji[:1] if kanji else ""
                if kanji and self._current_level is not None:
                    entry = {"src": src, "kana": kana, "kanji": kanji, "level": self._current_level}
                    if extra:
                        entry["extra_kanji"] = extra
                    self.entries.append(entry)

    def handle_endtag(self, tag):
        if tag == "span" and self._in_kanji_span:
            self._in_kanji_span = False
            kanji = self._kanji_buf.strip().replace("　", "").replace("\xa0", "").replace(" ", "")
            if kanji:
                self._current_kanji = kanji
        if tag == "td":
            self._in_kanji_td = False

    def handle_data(self, data):
        if self._in_kanji_span:
            self._kanji_buf += data


def fetch_html(page):
    r = subprocess.run(
        ["curl", "-s", "--insecure", BASE_URL + page + ".html"],
        capture_output=True, text=True
    )
    return r.stdout


def download_image(src):
    parts = src.split("/")
    subdir = os.path.join(OUT_DIR, parts[0])
    os.makedirs(subdir, exist_ok=True)
    dest = os.path.join(OUT_DIR, src)
    if os.path.exists(dest):
        return True
    url = BASE_URL + src
    r = subprocess.run(
        ["curl", "-s", "--insecure", "-o", dest, url],
        capture_output=True
    )
    return r.returncode == 0


def main():
    all_entries = []
    for page in PAGES:
        print(f"Fetching {page}.html ...", flush=True)
        html = fetch_html(page)
        parser = HentaiganaParser()
        parser.feed(html)
        all_entries.extend(parser.entries)
        print(f"  → {len(parser.entries)} entries", flush=True)

    print(f"\nTotal entries: {len(all_entries)}")

    # 重複除去（同じsrcが複数ページに現れた場合）
    seen = set()
    unique = []
    for e in all_entries:
        if e["src"] not in seen:
            seen.add(e["src"])
            unique.append(e)
    print(f"Unique images: {len(unique)}")

    # level分布
    from collections import Counter
    dist = Counter(e["level"] for e in unique)
    print(f"Level distribution: {dict(dist)}")

    # 画像ダウンロード
    os.makedirs(OUT_DIR, exist_ok=True)
    total = len(unique)
    ok = 0
    for i, e in enumerate(unique):
        sys.stdout.write(f"\rDownloading {i+1}/{total}: {e['src'][:50]:<50}")
        sys.stdout.flush()
        if download_image(e["src"]):
            ok += 1
    print(f"\nDownloaded {ok}/{total}")

    # data.json 生成
    out_path = os.path.join(os.path.dirname(__file__), "data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)
    print(f"Saved {out_path}")

    # data.js 生成（file:// で直接開くための埋め込み用、1エントリ1行）
    js_path = os.path.join(os.path.dirname(__file__), "data.js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("// 変体仮名カードデータ（fetch_data.py により自動生成）\n")
        lines = [json.dumps(e, ensure_ascii=False, separators=(",", ":")) for e in unique]
        f.write("const CARDS = [\n" + ",\n".join(lines) + "\n];\n")
    print(f"Saved {js_path}")


if __name__ == "__main__":
    main()
