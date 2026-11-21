"""Fetch Mandarin sentences that have native-speaker audio on Tatoeba.

Stage 1 (no candidates.tsv yet): build candidates.tsv = simplified Mandarin
sentences with audio (id, text, audio_id, username, license, attribution, eng).
Stage 2 (ids.txt present): download mp3 for every id listed into audio/<id>.mp3.
"""
import bz2, csv, io, os, sys, tarfile, time, urllib.request

UA = {"User-Agent": "chinese-audio-study/1.0 (personal study; github.com/Healer1207/chinese-audio-v2)"}
BASE = "https://downloads.tatoeba.org/exports"

def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read()
        except Exception as e:
            print("retry", url, e, flush=True); time.sleep(3 * (i + 1))
    return None

def stage1():
    import opencc
    t2s = opencc.OpenCC("t2s")
    print("download cmn sentences", flush=True)
    raw = bz2.decompress(get(f"{BASE}/per_language/cmn/cmn_sentences.tsv.bz2")).decode()
    cmn = {}
    for line in raw.splitlines():
        p = line.split("\t")
        if len(p) >= 3:
            cmn[p[0]] = p[2]
    print("cmn sentences", len(cmn), flush=True)
    print("download audio list", flush=True)
    tb = get(f"{BASE}/sentences_with_audio.tar.bz2")
    tf = tarfile.open(fileobj=io.BytesIO(tb), mode="r:bz2")
    member = [m for m in tf.getmembers() if m.name.endswith(".csv")][0]
    audio = {}
    for line in tf.extractfile(member).read().decode().splitlines():
        p = line.split("\t")
        if p and p[0] in cmn and p[0] not in audio:
            audio[p[0]] = p[1:]
    print("cmn with audio", len(audio), flush=True)
    eng = {}
    try:
        er = bz2.decompress(get(f"{BASE}/per_language/eng/eng_sentences.tsv.bz2")).decode()
        engtxt = {}
        for line in er.splitlines():
            p = line.split("\t")
            if len(p) >= 3:
                engtxt[p[0]] = p[2]
        lr = bz2.decompress(get(f"{BASE}/per_language/cmn/cmn-eng_links.tsv.bz2")).decode()
        for line in lr.splitlines():
            a, b = line.split("\t")[:2]
            if a in audio and a not in eng and b in engtxt:
                eng[a] = engtxt[b]
    except Exception as e:
        print("eng translations skipped:", e, flush=True)
    rows = 0
    with open("candidates.tsv", "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["id", "text", "audio_id", "username", "license", "attribution", "eng"])
        for sid, meta in audio.items():
            text = cmn[sid]
            if t2s.convert(text) != text:  # keep simplified only
                continue
            if not (3 <= len(text) <= 30):
                continue
            meta = (meta + ["", "", "", ""])[:4]
            w.writerow([sid, text] + meta + [eng.get(sid, "")])
            rows += 1
    print("candidates", rows, flush=True)

def stage2():
    os.makedirs("audio", exist_ok=True)
    meta = {}
    with open("candidates.tsv") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            meta[r["id"]] = r
    ids = [l.strip() for l in open("ids.txt") if l.strip()]
    ok = miss = 0
    for sid in ids:
        out = f"audio/{sid}.mp3"
        if os.path.exists(out) and os.path.getsize(out) > 1000:
            continue
        aid = meta.get(sid, {}).get("audio_id", "")
        data = None
        for url in ([f"https://tatoeba.org/audio/download/{aid}"] if aid else []) + [f"https://audio.tatoeba.org/sentences/cmn/{sid}.mp3"]:
            data = get(url, tries=2)
            if data and len(data) > 1000:
                break
            data = None
        if data:
            open(out, "wb").write(data); ok += 1
        else:
            miss += 1; print("missing", sid, flush=True)
        time.sleep(0.3)
    print("downloaded", ok, "missing", miss, flush=True)

if __name__ == "__main__":
    if not os.path.exists("candidates.tsv"):
        stage1()
    if os.path.exists("ids.txt"):
        stage2()
