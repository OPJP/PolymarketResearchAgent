"""Ground-truth check of prng15's V8 model on REAL V8 output (local Node v22): salts = Math.round(Math.random() * Date.now()) from
consecutive calls. A group of 5 calls taken 3 apart (sparse), others = 40 later calls."""
import json, sys, importlib.util
sys.argv = ["x", "x", "x", "12", "hi", "1", "10", "2"]
spec = importlib.util.spec_from_file_location("p15", __import__("os").path.dirname(__file__) + "/prng15.py"); p15 = importlib.util.module_from_spec(spec); spec.loader.exec_module(p15)
S = json.load(open(__import__("os").path.dirname(__file__) + "/node_salts.json"))
words = p15.sym_words(2 * p15.B + p15.P + 5)
res = []
for start in (5, 70, 140):
    grp = [tuple(S[start + 2 * j]) for j in range(5)]
    oth = [tuple(S[start + 20 + j]) for j in range(40)]
    r = p15.search(grp, words, oth)
    res.append({"start": start, "found": r[:2]})
    print(res[-1], flush=True)
json.dump(res, open(__import__("os").path.dirname(__file__) + "/v8real15.json", "w"))
