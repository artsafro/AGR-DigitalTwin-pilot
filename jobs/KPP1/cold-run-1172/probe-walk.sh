#!/usr/bin/env bash
# Fail-closed probes for the KPP1 cold-run checklist (#1172). Run from the worktree root.
set -u
W="uv run python -m dt_ai.procedure"
P=tmp/probe
mkdir -p $P
err() { python -c "import json,sys;d=json.load(open(sys.argv[1],encoding='utf-8'));print((d.get('errors') or [e for g in d.get('gates',[]) for e in g['errors']])[:1])" "$1" 2>/dev/null || echo "(no output file)"; }

awk '/^  parts:/{f=1} f&&/status: review/{sub("review","pass");f=0} {print}' jobs/KPP1/job.yaml > $P/p1.yaml
$W $P/p1.yaml --root . --output $P/o1.json >/dev/null; echo "P1 parts pass on draft PartsList: exit=$? $(err $P/o1.json)"

awk '/^  operations:/{f=1} f&&/status: missing/{sub("missing","pass");f=0} {print}' jobs/KPP1/job.yaml > $P/p2.yaml
$W $P/p2.yaml --root . --output $P/o2.json >/dev/null; echo "P2 operations pass without evidence: exit=$? $(err $P/o2.json)"

sed 's/a34cc18038e9440e164518523c39b25be0e7d82e0582348e4411b0763bcd020c/ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff/' jobs/KPP1/job.yaml > $P/p3.yaml
$W $P/p3.yaml --root . --output $P/o3.json >/dev/null; echo "P3 wrong input hash: exit=$? $(err $P/o3.json)"

cp jobs/KPP1/job.yaml $P/p4.yaml; H=$(sha256sum $P/p4.yaml | cut -c1-64)
$W $P/p4.yaml --root . --output $P/p4.yaml >/dev/null 2>&1; rc=$?
[ "$(sha256sum $P/p4.yaml | cut -c1-64)" = "$H" ] && u=yes || u=NO
echo "P4 output path = input: exit=$rc input unchanged=$u"

H=$(sha256sum jobs/KPP1/cold-run-1172/walk-v001.json | cut -c1-64)
$W jobs/KPP1/job.yaml --root . --output jobs/KPP1/cold-run-1172/walk-v001.json >/dev/null 2>&1; rc=$?
[ "$(sha256sum jobs/KPP1/cold-run-1172/walk-v001.json | cut -c1-64)" = "$H" ] && u=yes || u=NO
echo "P5 existing output reused: exit=$rc receipt unchanged=$u"

sed 's#path: jobs/KPP1/object.json#path: C:/Users/artsafro/agr-pilot/AGR-DigitalTwin/.worktrees/t_0b1dbdbf/jobs/KPP1/object.json#' jobs/KPP1/job.yaml > $P/p6.yaml
$W $P/p6.yaml --root . --output $P/o6.json >/dev/null; echo "P6 absolute alias of an input: exit=$? $(err $P/o6.json)"

sed "s#jobs/KPP1/cold-run-1172/inputs-manifest.json#$P/m.json#" jobs/KPP1/job.yaml > $P/p7.yaml
$W $P/p7.yaml --root . --output $P/o7.json >/dev/null; echo "P7 manifest edited after hashing: exit=$? $(err $P/o7.json)"

: > $P/p8.yaml; $W $P/p8.yaml --root . --output $P/o8.json >/dev/null 2>&1; echo "P8 empty checklist: exit=$? $(err $P/o8.json)"
