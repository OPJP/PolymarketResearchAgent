"""Probe one row group of the capture's polymarket day file (pinned revision): event types, which size columns are set, book lists."""
import sys, time, json
sys.path.insert(0, sys.argv[1])
import importlib.util
spec = importlib.util.spec_from_file_location("hfi", sys.argv[1] + "/hfingest13.py")
src = open(sys.argv[1] + "/hfingest13.py").read().split("def main():")[0]
src = src.replace("SHA = sys.argv[5] if len(sys.argv) > 5 else None", "SHA=None").replace("DAY, OUT = sys.argv[1], sys.argv[2]", "DAY, OUT='2026-10-20','x'").replace("TH = int(sys.argv[3]) if len(sys.argv) > 3 else 6", "TH=1").replace("CONF = sys.argv[4] if len(sys.argv) > 4 else \"polymarket\"", "CONF='polymarket'")
g = {}
exec(src, g)
import pyarrow.parquet as pq, pyarrow.compute as pc
cl = g["cl"]; RangeFile = g["RangeFile"]
sha = "f848a77ccfce4421d3cedbbe585576db77d36662"
url = f"https://huggingface.co/datasets/Fahri-5/updown-5m-polymarket-raw/resolve/{sha}/polymarket/2026-10-20.parquet"
size = int(cl.head(url).headers["content-length"])
f0 = RangeFile(url, size); md = pq.ParquetFile(f0).metadata
i = int(sys.argv[2])
cols = ["eventType", "exchangeTimestampMs", "timestampMs", "tokenId", "askPrice", "askSize", "bidPrice", "bidSize", "bestBid", "bestAsk", "bids", "asks", "outcome", "marketId"]
rg = md.row_group(i); rr = []
for j in range(rg.num_columns):
    cc = rg.column(j)
    if cc.path_in_schema.split(".")[0] in cols:
        a0 = cc.dictionary_page_offset if cc.has_dictionary_page and cc.dictionary_page_offset else cc.data_page_offset
        rr.append((a0, a0 + cc.total_compressed_size))
t0 = time.time(); f = RangeFile(url, size); f.prefetch(rr)
t = pq.ParquetFile(f, metadata=md).read_row_group(i, columns=cols)
print("bytes", f.nbytes, "s", round(time.time() - t0, 1), "rows", t.num_rows)
d = t.to_pandas()
print(d.eventType.value_counts())
for ev in d.eventType.unique():
    x = d[d.eventType == ev]
    print(ev, {c: float(x[c].notna().mean()) for c in ["askPrice", "askSize", "bidPrice", "bidSize", "bestBid", "bestAsk"]}, "bids_nonnull", float(x.bids.notna().mean()))
    print(x.head(3)[["exchangeTimestampMs", "timestampMs", "tokenId", "askPrice", "askSize", "bidPrice", "bidSize", "bestBid", "bestAsk", "outcome", "marketId"]].to_string())
bk = d[d.bids.notna()]
if len(bk):
    r = bk.iloc[0]; print("book example n_bids", len(r.bids), "n_asks", len(r.asks), list(r.bids)[:3], list(r.asks)[:3])
print("ts range", d.exchangeTimestampMs.min(), d.exchangeTimestampMs.max(), "ntok", d.tokenId.nunique())
st = md.row_group(i).column([md.schema.column(k).name for k in range(md.num_columns)].index("timestampMs")).statistics
print("stats", st.min if st else None, st.max if st else None, "nrg", md.num_row_groups)
