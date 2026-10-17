# -*- coding: utf-8 -*-
"""VOICEVOX 로 학습용 mp3 음원을 일괄 생성한다.
실행:  cd D:\\japanese-app  ->  python generate_audio.py
옵션:  --force  (전부 다시 생성)
결과:  audio/hiragana, audio/katakana, audio/words, manifest.json, examples.json
이미 있는 파일은 건너뛴다. 목소리·설정을 바꾸면 자동으로 전부 다시 만든다."""
import hashlib, json, os, shutil, subprocess, sys, tempfile, time, urllib.parse, urllib.request
from kana_data import HIRAGANA, KATAKANA, HIRA_EX, KATA_EX

ENGINE = os.environ.get("VOICEVOX_URL", "http://127.0.0.1:50021")
SPEAKER_ID = 8
SPEAKER_NAME = "春日部つむぎ"
SETTINGS = {"speaker": SPEAKER_ID, "speedScale": 0.85, "prePhonemeLength": 0.2,
            "postPhonemeLength": 0.2, "minSingleVowel": 0.22, "bitrate": "64k", "v": 1}
BASE = os.path.dirname(os.path.abspath(__file__))
AUDIO = os.path.join(BASE, "audio")
DIRS = {k: os.path.join(AUDIO, k) for k in ("hiragana", "katakana", "words")}
WORDS_TXT = os.path.join(BASE, "words.txt")

def die(msg):
    print("\n[중단] " + msg); sys.exit(1)

def find_ffmpeg():
    p = shutil.which("ffmpeg")
    if p: return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    die("ffmpeg 를 찾을 수 없어요. PowerShell 에서 아래 중 하나로 설치한 뒤 창을 새로 열고 다시 실행하세요.\n"
        "  winget install Gyan.FFmpeg\n"
        "  (또는)  pip install imageio-ffmpeg")

def req(method, path, params=None, body=None):
    url = ENGINE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    data = None if method == "GET" else (json.dumps(body).encode("utf-8") if body is not None else b"")
    r = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(r, timeout=60) as resp:
                return resp.read()
        except Exception as e:
            if attempt == 2: raise
            time.sleep(1.0)

def synth_wav(text, single):
    q = json.loads(req("POST", "/audio_query", {"text": text, "speaker": SPEAKER_ID}))
    q["speedScale"] = SETTINGS["speedScale"]
    q["prePhonemeLength"] = SETTINGS["prePhonemeLength"]
    q["postPhonemeLength"] = SETTINGS["postPhonemeLength"]
    adjusted = False
    if single:
        # 한 글자는 모음이 너무 짧으면 또렷하지 않아서 최소 길이를 보장
        for ph in q.get("accent_phrases", []):
            for m in ph.get("moras", []):
                if m.get("vowel_length") is not None and m["vowel_length"] < SETTINGS["minSingleVowel"]:
                    m["vowel_length"] = SETTINGS["minSingleVowel"]; adjusted = True
    reading = "".join(m.get("text", "") for ph in q.get("accent_phrases", []) for m in ph.get("moras", []))
    wav = req("POST", "/synthesis", {"speaker": SPEAKER_ID}, q)
    return wav, reading, adjusted

def to_mp3(ffmpeg, wav, out):
    fd, tmp = tempfile.mkstemp(suffix=".wav"); os.close(fd)
    try:
        with open(tmp, "wb") as f: f.write(wav)
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", tmp, "-ac", "1", "-b:a", SETTINGS["bitrate"], out],
                       check=True)
    finally:
        os.remove(tmp)

def word_file(text):
    h = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return "w_" + h + ".mp3"

def read_words():
    if not os.path.exists(WORDS_TXT):
        return []
    out = []
    with open(WORDS_TXT, encoding="utf-8-sig") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"): continue
            # "표시|읽기" 형식이면 읽기로 발음을 만들고 표시 글자로 manifest 에 등록 (예: 愛|あい)
            if "|" in s:
                show, read = [x.strip() for x in s.split("|", 1)]
            else:
                show = read = s
            out.append((show, read))
    return out

def main():
    force = "--force" in sys.argv
    ffmpeg = find_ffmpeg()
    try:
        ver = req("GET", "/version").decode("utf-8").strip('"')
    except Exception as e:
        die(f"VOICEVOX 엔진({ENGINE})에 연결할 수 없어요: {e}\nVOICEVOX 앱을 켜 두고 다시 실행하세요.")
    print(f"VOICEVOX {ver} 연결됨 · 목소리 {SPEAKER_NAME} (id {SPEAKER_ID})")
    for d in DIRS.values(): os.makedirs(d, exist_ok=True)

    sfile = os.path.join(AUDIO, ".settings.json")
    old = None
    if os.path.exists(sfile):
        with open(sfile, encoding="utf-8") as f: old = json.load(f)
    if old != SETTINGS and old is not None:
        print("목소리 또는 설정이 바뀌어서 전부 다시 만들어요."); force = True

    jobs = []  # (key, synth_text, rel_path, kind, single)
    for k, r in HIRAGANA: jobs.append((k, k, f"audio/hiragana/{r}.mp3", "hiragana", True))
    for k, r in KATAKANA: jobs.append((k, k, f"audio/katakana/{r}.mp3", "katakana", True))
    examples = {}
    for table in (HIRA_EX, KATA_EX):
        for kana, ex in table.items():
            if not ex: continue
            examples[kana] = {"word": ex[0], "meaning": ex[1]}
            jobs.append((ex[0], ex[0], "audio/words/" + word_file(ex[0]), "words", False))
    for show, read in read_words():
        jobs.append((show, read, "audio/words/" + word_file(read), "words", False))

    manifest, made, skipped, adjusted, notes = {}, {"hiragana": 0, "katakana": 0, "words": 0}, 0, [], []
    seen = set()
    total = len(jobs)
    for i, (key, text, rel, kind, single) in enumerate(jobs, 1):
        if key in manifest:
            continue
        manifest[key] = rel
        if rel in seen: continue
        seen.add(rel)
        out = os.path.join(BASE, rel.replace("/", os.sep))
        if os.path.exists(out) and not force:
            skipped += 1; continue
        try:
            wav, reading, adj = synth_wav(text, single)
        except Exception as e:
            notes.append(f"실패: {text} ({e})"); manifest.pop(key, None); continue
        to_mp3(ffmpeg, wav, out)
        made[kind] += 1
        if adj: adjusted.append(text)
        print(f"[{i}/{total}] {text} -> {rel}  (읽기: {reading})")

    with open(os.path.join(BASE, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    with open(os.path.join(BASE, "examples.json"), "w", encoding="utf-8") as f:
        json.dump(examples, f, ensure_ascii=False, indent=1)
    with open(os.path.join(BASE, "credit.txt"), "w", encoding="utf-8") as f:
        f.write(f"VOICEVOX:{SPEAKER_NAME}\n")
    with open(sfile, "w", encoding="utf-8") as f:
        json.dump(SETTINGS, f)

    counts = {k: len([n for n in os.listdir(d) if n.endswith(".mp3")]) for k, d in DIRS.items()}
    size = sum(os.path.getsize(os.path.join(d, n)) for d in DIRS.values() for n in os.listdir(d) if n.endswith(".mp3"))
    print("\n===== 완료 =====")
    print(f"이번에 새로 만든 파일: 히라가나 {made['hiragana']}, 가타카나 {made['katakana']}, 단어 {made['words']} (건너뜀 {skipped})")
    print(f"전체 파일: 히라가나 {counts['hiragana']}, 가타카나 {counts['katakana']}, 단어 {counts['words']}")
    print(f"전체 용량: {size/1024/1024:.2f} MB")
    print(f"manifest.json 항목: {len(manifest)}")
    if adjusted: print(f"한 글자 모음 길이 보정: {len(adjusted)}개")
    for n in notes: print(n)
    for k in ("あ", "きゃ", "ありがとう"):
        print(f"확인용  {k}: " + (os.path.join(BASE, manifest[k].replace('/', os.sep)) if k in manifest else "manifest 에 없음"))

if __name__ == "__main__":
    main()
