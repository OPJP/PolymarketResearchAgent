import json, numpy as np
a = json.load(open("h1_null_partial.json"))  # seed 0, 100 draws (run OOM-killed after draw 100; partial saved every 20)
b = json.load(open("h1_null_s1.json")) if __import__("os").path.exists("h1_null_s1.json") else None
bp = json.load(open("h1_null_partial_s1.json"))
out = {}
for n in a["real"]:
    v = np.array(a["nulls"][n] + bp["nulls"][n]); r = a["real"][n]
    out[n] = {"real_auc": r, "n_null": len(v), "null_mean": float(v.mean()), "null_max": float(v.max()), "exceed": int((v >= r).sum()), "perm_p": float((1 + (v >= r).sum()) / (1 + len(v))), "real_minus_null_mean": r - float(v.mean())}
print(json.dumps(out, indent=1))
json.dump(out, open("h1_null_combined.json", "w"), indent=1)
