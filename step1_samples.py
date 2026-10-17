# -*- coding: utf-8 -*-
"""1단계: VOICEVOX 연결 확인 + 목소리 후보 4개 샘플 생성
실행:  cd D:\\japanese-app  ->  python step1_samples.py
"""
import json, os, sys, urllib.request, urllib.parse

ENGINE = os.environ.get("VOICEVOX_URL", "http://127.0.0.1:50021")
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "samples")
os.makedirs(OUT, exist_ok=True)

# 학습용으로 차분하고 또렷한 후보 (캐릭터명, 스타일). id는 엔진 버전마다 달라서 이름으로 찾음
CANDIDATES = [
    ("冥鳴ひまり", "ノーマル"),
    ("春日部つむぎ", "ノーマル"),
    ("もち子さん", "ノーマル"),
    ("青山龍星", "ノーマル"),
]
BACKUP = [("WhiteCUL", "ノーマル"), ("九州そら", "ノーマル"), ("四国めたん", "ノーマル"), ("小夜/SAYO", "ノーマル")]
TEXTS = [("a", "あ"), ("arigatou", "ありがとう"), ("kokoro", "こころ")]

def get(path):
    with urllib.request.urlopen(ENGINE + path, timeout=10) as r:
        return r.read()

def post(path, params, body=None):
    url = ENGINE + path + "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode("utf-8") if body is not None else b""
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def synth(text, sid):
    q = json.loads(post("/audio_query", {"text": text, "speaker": sid}))
    q["speedScale"] = 0.85
    q["prePhonemeLength"] = 0.2
    q["postPhonemeLength"] = 0.2
    return post("/synthesis", {"speaker": sid}, q)

def main():
    log = []
    try:
        ver = get("/version").decode("utf-8").strip('"')
    except Exception as e:
        print("[실패] VOICEVOX 엔진에 연결할 수 없어요:", e)
        print("VOICEVOX 앱이 켜져 있는지 확인해 주세요. 주소:", ENGINE)
        sys.exit(1)
    log.append(f"VOICEVOX engine version: {ver}")
    speakers = json.loads(get("/speakers"))
    with open(os.path.join(OUT, "speakers.json"), "w", encoding="utf-8") as f:
        json.dump(speakers, f, ensure_ascii=False, indent=1)
    table = {}
    for sp in speakers:
        for st in sp["styles"]:
            table[(sp["name"], st["name"])] = st["id"]
    log.append(f"speakers: {len(speakers)}명, 스타일 {len(table)}개")

    chosen = []
    for c in CANDIDATES + BACKUP:
        if c in table and len(chosen) < 4:
            chosen.append((c[0], c[1], table[c]))
    if len(chosen) < 4:
        for k, v in table.items():
            if len(chosen) >= 4: break
            if k[1] == "ノーマル" and all(k[0] != x[0] for x in chosen):
                chosen.append((k[0], k[1], v))

    log.append("")
    log.append("후보 목록 (번호 / 캐릭터 / 스타일 / speaker id)")
    for n, (name, style, sid) in enumerate(chosen, 1):
        log.append(f"{n}. {name} / {style} / id={sid}")
        for key, text in TEXTS:
            fn = f"{n}_id{sid}_{key}.wav"
            with open(os.path.join(OUT, fn), "wb") as f:
                f.write(synth(text, sid))
            log.append(f"     {text:6} -> samples\\{fn}")
    text = "\n".join(log)
    print(text)
    with open(os.path.join(OUT, "result.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print("\n완료! samples 폴더의 wav 파일을 들어보고 마음에 드는 번호를 알려주세요.")

if __name__ == "__main__":
    main()
