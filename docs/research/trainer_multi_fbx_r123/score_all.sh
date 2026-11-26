#!/usr/bin/env bash
# #123 OBSERVE: score every FBX of the 9 several-FBX runs separately (unchanged scorer).
cd C:/Users/artsafro/agr-pilot/AGR-DigitalTwin/.worktrees/t_7045d6ec || exit 1
B=C:/x/trainer/runs; O=C:/x/ev_123
: > $O/index.tsv
for r in 63a-stage1-codex-r87-3 63b-stage1-codex-r87-3 g22-k2-stage1-codex-r111-1 g22-k2-stage1-codex-r115-C3 g22-k2-stage1-codex-r95-C3 g22-k2-stage1-codex-r97-C1 g22-k2-stage1-codex-r97-C3 kpp1-v004-codex-r95-C2 kpp1-v004-codex-r95-C3; do
  e=$(python -c "import json;print(json.load(open('$B/$r/run.json',encoding='utf-8'))['etalon'])")
  mkdir -p $O/$r; n=0
  find $B/$r/built -name '*.fbx' | sort | while read f; do
    out=$O/$r/$n.json; rm -rf $out ${out%.json}
    res=$(uv run agr trainer score $e --built "$f" --out $out 2>&1 | tail -n 1)
    sz=$(stat -c %s "$f"); mt=$(stat -c %Y "$f"); h=$(sha256sum "$f" | cut -c1-64)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$r" "$n" "${f#$B/$r/built/}" "$sz" "$mt" "$h" "$res" >> $O/index.tsv
    n=$((n+1))
  done
done
