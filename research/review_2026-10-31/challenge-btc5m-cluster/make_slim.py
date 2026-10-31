import pickle, sys
import pandas as pd
from grid import Grid
d = pickle.load(open("data.pkl", "rb"))
slim = {}
for per in ("fit", "test"):
    t = d[per]
    g = Grid(t)
    slim[per] = {"prints": t["prints"], "maker_prints": t["maker_prints"], "flow": t["flow"], "windows": t["windows"], "spot_ev": t["spot_ev"], "spot_vals": t["spot_vals"],
                 "grid_g": g.g, "blocks": t["blocks"]}
pickle.dump(slim, open("slim.pkl", "wb"))
print("ok")
