"""D3: apparatus-token share in the bundled samples, before/after _clean_text."""
import json, re, sys, unicodedata
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"engine"))
import find_text_reuse as H
from flame import flame_pure as F

WORD = re.compile(r"\b\w+\b", re.UNICODE)
GREEK = re.compile(r"[Ͱ-Ͽἀ-῿]")
LATIN = re.compile(r"^[A-Za-z]+$")

def classify(words):
    d = {"digit":0, "latin":0, "greek":0, "other":0}
    lat = {}
    for w in words:
        if w.isdigit(): d["digit"] += 1
        elif LATIN.match(w): d["latin"] += 1; lat[w] = lat.get(w,0)+1
        elif GREEK.search(w): d["greek"] += 1
        else: d["other"] += 1
    return d, lat

for name, p in [("plato 598", "engine/samples/plato_respublica_598.json"),
                ("proclus 101r", "engine/samples/proclus_in_rem_publicam_101r.json")]:
    data = json.loads((ROOT/p).read_text(encoding="utf-8"))
    raw = " ".join(s["text"] for s in data["segments"])
    cleaned = H._clean_text(raw)
    print(f"=== {name}")
    for tag, txt in [("RAW", raw), ("after _clean_text", cleaned)]:
        # what the engine actually tokenizes: _strip_milestones then \b\w+\b
        ws = WORD.findall(F._strip_milestones(txt))
        d, lat = classify(ws)
        n = len(ws)
        print(f"  {tag:18s} words={n}  digit={d['digit']} ({100*d['digit']/n:.2f}%) "
              f"latin={d['latin']} ({100*d['latin']/n:.2f}%) greek={d['greek']} other={d['other']}")
        if tag != "RAW":
            top = sorted(lat.items(), key=lambda kv:-kv[1])[:10]
            print(f"     top latin: {top}")
    # what _clean_text removed
    print(f"  removed by _clean_text: {len(WORD.findall(raw))-len(WORD.findall(cleaned))} word tokens")
