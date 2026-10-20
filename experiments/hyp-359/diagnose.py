"""Post-measurement explanation only: never changes frozen inputs or criteria."""
from collections import Counter
from fractions import Fraction
from driver import check_frozen, digest, embed, install, load, oracle, save, variants

check_frozen()
inputs = load('inputs.json')
# The tracked exact integer determinant also operates exactly on Fraction values.
# This diagnosis is NOT substituted for the issue's required inherited labels.
changes = []
for factor in (2,4):
    for i,poly in enumerate(inputs['derivatives'][str(factor)]):
        exact = [[Fraction(c) for c in p] for p in poly]
        pairs = oracle._count_proper_crossing_pairs(exact)
        original = inputs['pair_counts'][i]
        if bool(pairs) != bool(original):
            changes.append({'polygon':i,'factor':factor,'original_pairs':original,
                            'derivative_proper_pairs':pairs,'original':inputs['population'][i],
                            'derivative':poly})

counts = Counter()
failures = []
for key,vertices in variants(inputs):
    faces = [tuple(range(len(vertices)))]
    before = digest([vertices,faces])
    a = install('A')(vertices,faces)
    b = install('B')(vertices,faces)
    counts['all_cases'] += 1
    counts['full_dictionary_parity'] += a == b
    counts['no_mutation'] += before == digest([vertices,faces])
    counts['report_only_both'] += all(r['delivery_passed'] is False and
                                     r['intersection_test_performed'] is False for r in (a,b))
    expected = int(inputs['pair_counts'][key[1]] > 0)
    good = a['self_intersecting_polygons'] == b['self_intersecting_polygons'] == expected
    counts[key[0]+'_oracle_pass'] += good
    if not good:
        failures.append({'key':key,'expected':expected,'A':a,'B':b})

# Explain the first original crossing: exact line parameters t/u on the two edges.
first = changes[0]
p = inputs['population'][first['polygon']]
intersections = []
for i in range(len(p)):
    for j in range(i+1,len(p)):
        if j == i+1 or (i == 0 and j == len(p)-1):
            continue
        a,b,c,d = p[i],p[(i+1)%len(p)],p[j],p[(j+1)%len(p)]
        cross = lambda u,v: u[0]*v[1]-u[1]*v[0]
        r = [b[k]-a[k] for k in range(2)]
        s = [d[k]-c[k] for k in range(2)]
        q = [c[k]-a[k] for k in range(2)]
        det = cross(r,s)
        if not det:
            continue
        t,u = Fraction(cross(q,s),det),Fraction(cross(q,r),det)
        if 0 < t < 1 and 0 < u < 1:
            intersections.append({'edges':[i,j],'t':str(t),'u':str(u),
                                  'point':[str(Fraction(a[k])+t*r[k]) for k in range(2)]})
save('diagnosis.json',{'counts':dict(counts),'all_48_inherited_label_failures':failures,
     'exact_derivative_label_changes':changes,'first_original_intersections':intersections,
     'note':'Post-measurement explanation, not a replacement oracle or retuning.',
     'delivery_passed':False})
print(dict(counts))
print('label changes',[(x['polygon'],x['factor']) for x in changes])
print('first intersections',intersections)
