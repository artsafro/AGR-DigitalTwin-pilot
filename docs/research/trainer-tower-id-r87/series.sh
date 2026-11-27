#!/usr/bin/env bash
# r87 series (#87): pairs (63a_i tuning, 63b_i held-out), i=1..3, scratch bank with the tower map.
cd C:/Users/artsafro/agr-pilot/AGR-DigitalTwin/.worktrees/t_f534cfb1 || exit 1
EV=C:/x/ev_t_f534cfb1
B=$EV/bank_r87_towermap.json
for i in 1 2 3; do
  uv run -q python tools/trainer/trainer.py --bank $B run 63a-stage1 --out C:/x/trainer/runs/63a-stage1-codex-r87-$i \
    --timeout-s 1800 > $EV/63a-$i.out 2>&1 &
  uv run -q python tools/trainer/trainer.py --bank $B run 63b-stage1 --out C:/x/trainer/runs/63b-stage1-codex-r87-$i \
    --timeout-s 1800 > $EV/63b-$i.out 2>&1 &
  wait
  echo "pair $i done $(date -Is)" >> $EV/series.log
done
echo DONE >> $EV/series.log
