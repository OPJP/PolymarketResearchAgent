import pickle, sys
d = pickle.load(open("/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-btc5m-cluster/slim.pkl", "rb"))
for per in ("fit","test"):
    P=d[per]["prints"]; M=d[per]["maker_prints"]
    print(per, len(P), list(P.columns)); print(per, len(M), list(M.columns))
    print(P.head(2).to_string()); print(M.head(2).to_string())
    print(len(d[per]["windows"]), d[per]["windows"][0])
