"""Iteration 10 (panel iter9 information P4 = X76): record PolyBolt's PUBLIC price.polymarket channel (best bid and ask per
outcome token, producer timestamp, conflated 'latest wins' for slow clients, a `dropped` counter) for the current and next BTC 5m
windows, next to the CLOB market channel that the other recorders keep (btc5m_clob_raw2 / btc5m_xclob). Purpose: is the bot's
view of the Polymarket touch this channel rather than the CLOB market channel (limit == PolyBolt ask at a - delta more often
than the CLOB ask; lost_1000 decisions coinciding with conflation / dropped frames)?
Contract: https://ws-live-v2.polymarket.com/asyncapi.json (HTTP 200, read 10-31 21:35 UTC): server wss://ws-live-v2.polymarket.com/ws;
subscribe {"op": "subscribe", "rid": .., "subscriptions": [{"channel": "price.polymarket", "filter": {"asset_id": <token>}}]}
(public, no auth; no credentials are created or used); envelope {v, channel, seq, ts (producer ms), snapshot?, dropped?,
payload: {market, asset_id, best_bid, best_ask, hash, timestamp}}.
Records go through tools/live.py Writer (feed btc5m_pb; every block filed by its receive time; this process never reads,
lists or counts anything in .cache/live/sealed/; the status file reports acks and counts only while the block is development).
    {"k":"S","t","m":start,"u":up,"d":down}
    {"k":"b","t":recv ms,"ts":producer ms,"q":seq,"n":1 if snapshot,"x":dropped,"m":start,"u":1|0,"bb","ba","pt":payload ms}
    {"k":"a","t","op","code","rid"}   acks / errors (subscribe results)
Hard stop --stop; launcher sleeps until --start; disk cap 150 MB; memory ~50 MB.
Usage: python rec_pb10.py --start 1793512800 --stop 1793620800 [--test 30]"""
import os, sys, json, time, asyncio, argparse
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools")
import live, sealed
import websockets, httpx

STATUS = os.path.join(_ROOT, ".cache", "re", "btc5m-bot", "rec_pb10.status")
URL = "wss://ws-live-v2.polymarket.com/ws"
GAMMA = "https://gamma-api.polymarket.com/markets"
DISK_CAP_MB = 150.0
ST = {"start": int(time.time()), "pid": os.getpid(), "err": {}, "reconnects": 0, "acks_dev": {}}
DEVN = {}
W = live.Writer("btc5m_pb")
SIZES = {}
TOK = {}


def dev_now():
    return not sealed.future_block_sealed(time.time())


def err(k, e):
    ST["err"][k] = f"{time.strftime('%H:%M:%S')} {e!r}"[:200]


def out(obj, key):
    if ST.get("disk_full"):
        return
    W.write(obj)
    if dev_now():
        DEVN[key] = DEVN.get(key, 0) + 1


def tokens(start):
    if start in TOK:
        return TOK[start]
    with httpx.Client(timeout=15, headers={"User-Agent": "polyrea-research"}) as c:
        j = c.get(GAMMA, params={"slug": f"btc-updown-5m-{start}"}).json()
    t = json.loads(j[0]["clobTokenIds"]) if j else []  # listing field only (token ids)
    if len(t) == 2:
        TOK[start] = t
    return t


async def run(stop_at):
    subs = {}  # start -> (up, dn)
    while time.time() < stop_at and not ST.get("disk_full"):
        try:
            async with websockets.connect(URL, open_timeout=15, ping_interval=20, max_size=2 ** 22, max_queue=4096) as ws:
                subs.clear(); last_ping = time.time()
                while time.time() < stop_at and not ST.get("disk_full"):
                    now = time.time(); cur = int(now // 300 * 300)
                    for st in (cur, cur + 300):
                        if st not in subs and st - now < 250:
                            try:
                                up, dn = await asyncio.to_thread(tokens, st)
                            except Exception as e:
                                err("tok", e); continue
                            subs[st] = (up, dn)
                            out({"k": "S", "t": int(now * 1000), "m": st, "u": up, "d": dn}, "S")
                            await ws.send(json.dumps({"op": "subscribe", "rid": f"s{st}",
                                                      "subscriptions": [{"channel": "price.polymarket", "filter": {"asset_id": up}},
                                                                        {"channel": "price.polymarket", "filter": {"asset_id": dn}}]}))
                    for st in [s for s in subs if s + 300 + 15 < now]:
                        up, dn = subs.pop(st)
                        await ws.send(json.dumps({"op": "unsubscribe", "rid": f"u{st}",
                                                  "subscriptions": [{"channel": "price.polymarket", "filter": {"asset_id": up}},
                                                                    {"channel": "price.polymarket", "filter": {"asset_id": dn}}]}))
                    if now - last_ping > 15:
                        await ws.send(json.dumps({"op": "ping"})); last_ping = now
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=1)
                    except asyncio.TimeoutError:
                        continue
                    t = int(time.time() * 1000)
                    try:
                        j = json.loads(raw)
                    except ValueError:
                        continue
                    for it in (j if isinstance(j, list) else [j]):
                        if not isinstance(it, dict):
                            continue
                        if it.get("channel") == "price.polymarket" and isinstance(it.get("payload"), dict):
                            p = it["payload"]; a = str(p.get("asset_id"))
                            m_ = next((s for s, (u, d) in subs.items() if a in (u, d)), None)
                            out({"k": "b", "t": t, "ts": it.get("ts"), "q": it.get("seq"), "n": 1 if it.get("snapshot") else 0, "x": it.get("dropped") or 0,
                                 "m": m_, "u": int(m_ is not None and a == subs[m_][0]), "bb": p.get("best_bid"), "ba": p.get("best_ask"), "pt": p.get("timestamp")}, "b")
                        elif it.get("op") in ("subscribed", "unsubscribed", "error", "pong", "authed"):
                            if it.get("op") != "pong":
                                out({"k": "a", "t": t, "op": it.get("op"), "code": it.get("code"), "rid": it.get("rid")}, "a")
                            if dev_now():
                                kk = f"{it.get('op')}:{it.get('code')}"
                                ST["acks_dev"][kk] = ST["acks_dev"].get(kk, 0) + 1
        except Exception as e:
            err("ws", e); ST["reconnects"] += 1
            await asyncio.sleep(3)


async def status(stop_at):
    while time.time() < stop_at:
        await asyncio.sleep(10)
        W.flush()
        if W.fh is not None:
            try:
                SIZES[str(W.path)] = W.fh.buffer.fileobj.tell()
            except Exception as e:
                err("size", e)
        mb = sum(SIZES.values()) / 1e6
        ST.update({"updated": int(time.time()), "stop_at": int(stop_at), "dev_now": dev_now(), "disk_mb_total_own": round(mb, 1), "dev_counts": DEVN})
        if mb > DISK_CAP_MB:
            ST["disk_full"] = True
        with open(STATUS, "w") as fh:
            fh.write(json.dumps(ST))
        if ST.get("disk_full"):
            break


async def main(stop_at):
    try:
        await asyncio.gather(run(stop_at), status(stop_at))
    finally:
        W.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--stop", type=float, required=True)
    ap.add_argument("--test", type=float, default=0)
    a = ap.parse_args()
    while time.time() < a.start:
        time.sleep(min(60.0, max(0.5, a.start - time.time())))
    ST["start"] = int(time.time())
    stop_at = min(a.stop, time.time() + a.test) if a.test else a.stop
    asyncio.run(main(stop_at))
    print(json.dumps(ST)[:2000])
