"""X172 step 0 (information panel iter-12 P1): hawk.live series pages of the wallet's DEVELOPMENT Dota 2 series, one
normal-visitor GET each through the shared cached client. Only the series' own maps are kept (odds bundles, states,
picks, streams); the head-to-head list (other series, some of them sealed units) is dropped unread.
Output: .cache/re/tommy-cs2-maker/hawk/<event_slug>.json"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.http import shared_client  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker/hawk"
PAGES = {
    "dota2-ty-gl-2026-10-22": "pari-universe-group-stage/team-yandex-vs-gamerlegion",
    "dota2-ts8-legion1-2026-10-22": "pari-universe-group-stage/team-spirit-vs-legion",
    "dota2-liquid-1win-2026-10-22": "pari-universe-group-stage/team-liquid-vs-1win",
    "dota2-ty-gl-2026-10-31": "pari-universe-playoffs/team-yandex-vs-gamerlegion",
}
BS = chr(92)


def extract(html: str):
    import html as _h
    i = html.find('data-page="')
    if i >= 0:
        j = html.find('"', i + len('data-page="'))
        page = json.loads(_h.unescape(html[i + len('data-page="'):j]))
        return (page.get("props") or {}).get("seriesPageData")
    i = html.find('"seriesPageData"')
    if i < 0:
        return None
    j = html.find("{", i + len('"seriesPageData"'))
    depth = 0
    k = j
    ins = False
    esc = False
    while k < len(html):
        ch = html[k]
        if ins:
            if esc:
                esc = False
            elif ch == BS:
                esc = True
            elif ch == '"':
                ins = False
        else:
            if ch == '"':
                ins = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
        k += 1
    return json.loads(html[j:k + 1])


def main():
    h = shared_client()
    pages = dict(PAGES)
    if len(sys.argv) > 2:
        pages = {sys.argv[1]: sys.argv[2]}
    for ev, path in pages.items():
        url = f"https://hawk.live/dota-2/matches/{path}"
        try:
            b, _ = h.get_bytes(url, adapter="hawk.page", max_age=None)
        except Exception as e:  # noqa: BLE001
            print(ev, "FAIL", type(e).__name__, str(e)[:160])
            continue
        html = b.decode("utf-8", "replace")
        d = extract(html)
        if d is None:
            print(ev, "no seriesPageData; len", len(html))
            continue
        keep = {k: d.get(k) for k in ("id", "slug", "championship", "team1", "team2", "bestOf", "startAt", "streams")}
        keep["matches"] = d.get("matches")
        (OUT / f"{ev}.json").write_text(json.dumps(keep), encoding="utf-8")
        print(ev, d.get("slug"), d.get("startAt"), "maps", len(d.get("matches") or []),
              [(m.get("number"), [(bb["oddsProviderCodeName"], len(bb["odds"])) for bb in m.get("oddsBundles") or []])
               for m in d.get("matches") or []])


if __name__ == "__main__":
    main()
