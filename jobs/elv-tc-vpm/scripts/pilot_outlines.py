"""elv-tc-vpm pilot И-А: the two plan outlines of build_pilot_ia.py (U = upper wood/CW face, L = ground-floor metal face).

Copied 1:1 from build_pilot_ia.py so texture/UV scripts can use them without running the build. uA / uB = arc length of
the wood | CW | wood boundaries on U.
"""
from pilot_geom import Poly, arc

ARC_ANG = [0, 4.9, 10.5, 16.0, 21.6, 27.2, 32.8, 38.3, 43.9, 49.5, 55.1, 60.7, 66.3, 71.8, 77.4, 83.0, 87.6]
U_pts = [(41.85, -50.76)] + arc(75.88, -47.61, 3.15, -90, 0, n=10) + arc(75.92, -30.33, 3.11, 0, 0, angles=ARC_ANG)
U_pts += arc(75.92, -17.13, 3.11, 0, 0, angles=[-a for a in reversed(ARC_ANG)]) + arc(75.88, 0.14, 3.15, 0, 90, n=10)
U_pts += [(59.40, 3.29)]
U = Poly(U_pts)
uA, uB = U.project((79.03, -42.885)), U.project((79.03, -4.575))

L_pts = [(41.88, -50.61)] + arc(74.40, -48.83, 1.77, -90, 0, n=8)
L_pts += [(76.17, -44.477), (76.36, -44.477), (76.36, -33.487), (76.17, -33.487)] + arc(74.40, -29.13, 1.77, 0, 90, n=8)
L_pts += [(73.13, -27.36), (73.13, -20.11)] + arc(74.40, -18.34, 1.77, -90, 0, n=8)
L_pts += [(76.17, -14.027), (76.36, -14.027), (76.36, -2.937), (76.17, -2.937)] + arc(74.40, 1.37, 1.77, 0, 90, n=8)
L_pts += [(59.43, 3.14)]
L = Poly(L_pts)
