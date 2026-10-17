# -*- coding: utf-8 -*-
"""VOICEVOX 로 학습용 mp3 음원을 목소리별로 일괄 생성한다.
실행:  cd D:\\japanese-app  ->  python generate_audio.py
옵션:  --voice 8   (한 목소리만)   --force  (전부 다시 생성)
결과:  audio/v<id>/hiragana, katakana, words + audio/v<id>/manifest.json
       voices.json (목소리 목록), manifest.json (기본 목소리), examples.json
이미 있는 파일은 건너뛴다. 설정이 바뀐 목소리는 자동으로 다시 만든다."""
import hashlib, json, os, shutil, subprocess, sys, tempfile, time, urllib.parse, urllib.request
from kana_data import HIRAGANA, KATAKANA, HIRA_EX, KATA_EX

ENGINE = os.environ.get("VOICEVOX_URL", "http://127.0.0.1:50021")
# 앱 목소리 목록 (앞쪽이 기본 목소리)
VOICES = [
    {"id": 8,  "name": "春日部つむぎ", "style": "ノーマル", "label": "밝고 또렷한 여성"},
    {"id": 14, "name": "冥鳴ひまり",   "style": "ノーマル", "label": "낮고 차분한 여성"},
    {"id": 20, "name": "もち子さん",   "style": "ノーマル", "label": "부드러운 여성"},
    {"id": 13, "name": "青山龍星",     "style": "ノーマル", "label": "낮고 차분한 남성"},
]
COMMON = {"speedScale": 0.85, "prePhonemeLength": 0.2, "postPhonemeLength": 0.2,
          "minSingleVowel": 0.22, "bitrate": "64k", "v": 1}
BASE = os.path.dirname(os.path.abspath(__file__))
AUDIO = os.path.join(BASE, "audio")
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
    die("ffmpeg 를 찾을 수 없어요. 아래 명령으로 설치한 뒤 다시 실행하세요.\n"
        "  python -m pip install imageio-ffmpeg")

def req(method, path, params=None, body=None):
    url = ENGINE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    data = None if method == "GET" else (json.dumps(body).encode("utf-8") if body is not None else b"")
    r = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(r, timeout=60) as resp:
                return resp.read()
        except Exception:
            if attempt == 2: raise
            time.sleep(1.0)

def synth_wav(text, sid, single):
    q = json.loads(req("POST", "/audio_query", {"text": text, "speaker": sid}))
    q["speedScale"] = COMMON["speedScale"]
    q["prePhonemeLength"] = COMMON["prePhonemeLength"]
    q["postPhonemeLength"] = COMMON["postPhonemeLength"]
    adjusted = False
    if single:  # 한 글자는 모음이 너무 짧으면 또렷하지 않아서 최소 길이를 보장
        for ph in q.get("accent_phrases", []):
            for m in ph.get("moras", []):
                if m.get("vowel_length") is not None and m["vowel_length"] < COMMON["minSingleVowel"]:
                    m["vowel_length"] = COMMON["minSingleVowel"]; adjusted = True
    reading = "".join(m.get("text", "") for ph in q.get("accent_phrases", []) for m in ph.get("moras", []))
    return req("POST", "/synthesis", {"speaker": sid}, q), reading, adjusted

def to_mp3(ffmpeg, wav, out):
    fd, tmp = tempfile.mkstemp(suffix=".wav"); os.close(fd)
    try:
        with open(tmp, "wb") as f: f.write(wav)
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", tmp, "-ac", "1", "-b:a", COMMON["bitrate"], out], check=True)
    finally:
        os.remove(tmp)

def word_file(text):
    return "w_" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:10] + ".mp3"

def read_words():
    if not os.path.exists(WORDS_TXT): return []
    out = []
    with open(WORDS_TXT, encoding="utf-8-sig") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"): continue
            show, read = ([x.strip() for x in s.split("|", 1)] if "|" in s else (s, s))
            out.append((show, read))
    return out

def migrate_old_layout():
    """이전 버전(audio/hiragana 등, 春日部つむぎ)의 파일을 audio/v8/ 로 옮긴다."""
    old_set = os.path.join(AUDIO, ".settings.json")
    if not os.path.exists(os.path.join(AUDIO, "hiragana")): return
    sid = 8
    try:
        with open(old_set, encoding="utf-8") as f: sid = json.load(f).get("speaker", 8)
    except Exception: pass
    dst = os.path.join(AUDIO, f"v{sid}")
    os.makedirs(dst, exist_ok=True)
    for k in ("hiragana", "katakana", "words"):
        src = os.path.join(AUDIO, k)
        if os.path.isdir(src) and not os.path.exists(os.path.join(dst, k)):
            shutil.move(src, os.path.join(dst, k))
    if os.path.exists(old_set):
        with open(old_set, encoding="utf-8") as f: s = json.load(f)
        s.pop("speaker", None)
        with open(os.path.join(dst, ".settings.json"), "w", encoding="utf-8") as f: json.dump(s, f)
        os.remove(old_set)
    print(f"이전 음원을 audio/v{sid}/ 로 옮겼어요.")

def build_jobs():
    jobs, examples = [], {}
    for k, r in HIRAGANA: jobs.append((k, k, f"hiragana/{r}.mp3", "hiragana", True))
    for k, r in KATAKANA: jobs.append((k, k, f"katakana/{r}.mp3", "katakana", True))
    for table in (HIRA_EX, KATA_EX):
        for kana, ex in table.items():
            if not ex: continue
            examples[kana] = {"word": ex[0], "meaning": ex[1]}
            jobs.append((ex[0], ex[0], "words/" + word_file(ex[0]), "words", False))
    for show, read in read_words():
        jobs.append((show, read, "words/" + word_file(read), "words", False))
    return jobs, examples

def run_voice(ffmpeg, voice, jobs, force):
    sid = voice["id"]; vdir = os.path.join(AUDIO, f"v{sid}"); rel_base = f"audio/v{sid}/"
    for k in ("hiragana", "katakana", "words"): os.makedirs(os.path.join(vdir, k), exist_ok=True)
    sfile = os.path.join(vdir, ".settings.json")
    if os.path.exists(sfile):
        with open(sfile, encoding="utf-8") as f:
            if json.load(f) != COMMON:
                print("  설정이 바뀌어서 이 목소리는 전부 다시 만들어요."); force = True
    manifest, made, skipped, adjusted, notes, seen = {}, {"hiragana": 0, "katakana": 0, "words": 0}, 0, 0, [], set()
    for i, (key, text, rel, kind, single) in enumerate(jobs, 1):
        if key in manifest: continue
        manifest[key] = rel_base + rel
        if rel in seen: continue
        seen.add(rel)
        out = os.path.join(vdir, rel.replace("/", os.sep))
        if os.path.exists(out) and not force:
            skipped += 1; continue
        try:
            wav, reading, adj = synth_wav(text, sid, single)
        except Exception as e:
            notes.append(f"  실패: {text} ({e})"); manifest.pop(key, None); continue
        to_mp3(ffmpeg, wav, out)
        made[kind] += 1; adjusted += adj
        print(f"  [{voice['name']} {i}/{len(jobs)}] {text} -> {rel_base}{rel}  (읽기: {reading})")
    with open(os.path.join(vdir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    with open(sfile, "w", encoding="utf-8") as f: json.dump(COMMON, f)
    counts = {k: len([n for n in os.listdir(os.path.join(vdir, k)) if n.endswith(".mp3")]) for k in made}
    size = sum(os.path.getsize(os.path.join(vdir, k, n)) for k in made for n in os.listdir(os.path.join(vdir, k)) if n.endswith(".mp3"))
    return manifest, made, skipped, adjusted, notes, counts, size

def main():
    force = "--force" in sys.argv
    only = None
    if "--voice" in sys.argv:
        only = int(sys.argv[sys.argv.index("--voice") + 1])
    ffmpeg = find_ffmpeg()
    try:
        ver = req("GET", "/version").decode("utf-8").strip('"')
    except Exception as e:
        die(f"VOICEVOX 엔진({ENGINE})에 연결할 수 없어요: {e}\nVOICEVOX 앱을 켜 두고 다시 실행하세요.")
    print(f"VOICEVOX {ver} 연결됨")
    os.makedirs(AUDIO, exist_ok=True)
    migrate_old_layout()
    jobs, examples = build_jobs()
    summary, total_size, default_manifest = [], 0, None
    for v in VOICES:
        if only is not None and v["id"] != only:
            mp = os.path.join(AUDIO, f"v{v['id']}", "manifest.json")
            if v is VOICES[0] and os.path.exists(mp):
                with open(mp, encoding="utf-8") as f: default_manifest = json.load(f)
            continue
        print(f"\n▶ {v['name']} (id {v['id']})")
        manifest, made, skipped, adjusted, notes, counts, size = run_voice(ffmpeg, v, jobs, force)
        if v is VOICES[0]: default_manifest = manifest
        total_size += size
        summary.append((v, made, skipped, adjusted, notes, counts, size, len(manifest)))
    voices_out = [dict(v, manifest=f"audio/v{v['id']}/manifest.json", credit=f"VOICEVOX:{v['name']}")
                  for v in VOICES if os.path.exists(os.path.join(AUDIO, f"v{v['id']}", "manifest.json"))]
    with open(os.path.join(BASE, "voices.json"), "w", encoding="utf-8") as f:
        json.dump(voices_out, f, ensure_ascii=False, indent=1)
    if default_manifest is not None:
        with open(os.path.join(BASE, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(default_manifest, f, ensure_ascii=False, indent=1)
    with open(os.path.join(BASE, "examples.json"), "w", encoding="utf-8") as f:
        json.dump(examples, f, ensure_ascii=False, indent=1)
    with open(os.path.join(BASE, "credit.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(v["credit"] for v in voices_out) + "\n")

    print("\n===== 완료 =====")
    for v, made, skipped, adjusted, notes, counts, size, n in summary:
        print(f"{v['name']} (id {v['id']}): 새로 만듦 히라가나 {made['hiragana']} / 가타카나 {made['katakana']} / 단어 {made['words']}"
              f" · 건너뜀 {skipped} · 전체 {counts['hiragana']}/{counts['katakana']}/{counts['words']} · {size/1024/1024:.2f} MB · manifest {n}")
        for x in notes: print(x)
    all_size = 0
    for root, _, files in os.walk(AUDIO):
        all_size += sum(os.path.getsize(os.path.join(root, n)) for n in files if n.endswith(".mp3"))
    print(f"audio 폴더 전체 용량: {all_size/1024/1024:.2f} MB")
    print(f"voices.json 목소리: {', '.join(v['name'] for v in voices_out)}")

if __name__ == "__main__":
    main()
