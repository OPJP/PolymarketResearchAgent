#!/usr/bin/env bash
# iteration 6: rerun the live replications on the longest extraction (14:06 UTC -> extract3_end)
cd "$(dirname "$0")/../../../.."
P=.venv/Scripts/python.exe; D=research/reverse_engineering/directional-maker/code6; L=.cache/re/directional-maker
A=1793455600; B=$(cat $L/it6/extract3_end.txt)
$P $D/m1_race.py $A $B > $L/log_it6_race_c.txt 2>&1
$P $D/sel_live.py $A $B > $L/log_it6_sel_c.txt 2>&1
$P $D/pres_live.py $A $B > $L/log_it6_pres_c.txt 2>&1
$P $D/i1_price_match.py 1793448000 $B > $L/log_it6_i1_c.txt 2>&1
echo DONE > $L/log_it6_final_live_done.txt
