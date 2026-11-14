"""new-case: project saved/native positions into an existing fixed metre chart.

Native mesh/chart helpers use NumPy; pixel/interval/vector metrics additionally
use Shapely outside the DCC process. Source frames and physical scale stay explicit.
No file writes or fit-scale search. Vertex coalescing requires named cut-node groups;
its surface/finish/coverage gates remain independent caller responsibilities.
"""
import math


def project_saved_points(points, reference_xyz, reference_chart):
    """Project actual stored XYZ, not ideal pre-cast cutter coordinates.

    Retain the source chart origin and its first-triangle linear map. This
    avoids interpreting native float32 storage noise as UV stretch in 10-mm
    strips. The caller must measure residuals and all directional densities.
    """
    for rows,dim,name in [(points,3,'points'),(reference_xyz,3,'reference_xyz'),(reference_chart,2,'reference_chart')]:
        if not isinstance(rows,list) or not rows or any(not isinstance(p,list) or len(p)!=dim or any(
            isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in p) for p in rows):
            raise ValueError(f'invalid {name}')
    if len(reference_xyz)<3 or len(reference_xyz)!=len(reference_chart):raise ValueError('partial reference frame')
    dot=lambda a,b:sum(x*y for x,y in zip(a,b))
    sub=lambda a,b:[x-y for x,y in zip(a,b)]
    e,f=[sub(p,reference_xyz[0]) for p in reference_xyz[1:3]]
    aa,ab,bb=dot(e,e),dot(e,f),dot(f,f)
    determinant=aa*bb-ab*ab
    if not math.isfinite(determinant) or determinant<=max(aa*bb*1e-14,1e-24):raise ValueError('degenerate source frame')
    u,v=[sub(p,reference_chart[0]) for p in reference_chart[1:3]]
    out=[]
    for point in points:
        delta=sub(point,reference_xyz[0]);a,b=dot(delta,e),dot(delta,f)
        s=(a*bb-b*ab)/determinant;t=(b*aa-a*ab)/determinant
        q=[reference_chart[0][k]+s*u[k]+t*v[k] for k in (0,1)]
        if not all(math.isfinite(x) for x in q):raise ValueError('nonfinite projected chart')
        out.append(q)
    return out


def rigid_triangle_uv(xyz, reference_uv, *, texel_px_m, tile_px):
    """Rectify an explicitly authorized minor triangle at the frozen density.

    Keep its longest source edge's UV heading and anchor; unfold its true stored
    surface, not its projection onto a neighbouring face. No pack rotation.
    """
    if len(xyz)!=3 or len(reference_uv)!=3:raise ValueError('triangle required')
    project_saved_points(xyz,xyz,reference_uv)  # finite/degenerate frame checks
    if isinstance(texel_px_m,bool) or not isinstance(texel_px_m,(int,float)) or not math.isfinite(texel_px_m) or not 512<=texel_px_m<=1706:
        raise ValueError('illegal texel_px_m')
    if type(tile_px) is not int or tile_px not in (2048,4096):raise ValueError('unsupported tile_px')
    sub=lambda a,b:[x-y for x,y in zip(a,b)]
    dot=lambda a,b:sum(x*y for x,y in zip(a,b))
    i,j=max(((0,1),(1,2),(2,0)),key=lambda ij:math.dist(xyz[ij[0]],xyz[ij[1]]))
    k=3-i-j
    edge=sub(xyz[j],xyz[i]);length=math.sqrt(dot(edge,edge));direction=[v/length for v in edge]
    off=sub(xyz[k],xyz[i]);s=dot(off,direction);height=math.sqrt(sum((off[d]-s*direction[d])**2 for d in range(3)))
    heading=sub(reference_uv[j],reference_uv[i]);size=math.hypot(*heading)
    if size<=0 or height<=0:raise ValueError('degenerate triangle heading')
    u=[v/size for v in heading];v=[-u[1],u[0]]
    if dot(sub(reference_uv[k],reference_uv[i]),v)<0:v=[-a for a in v]
    factor=texel_px_m/tile_px
    out=[list(q) for q in reference_uv];out[i]=list(reference_uv[i])
    out[j]=[out[i][d]+length*u[d]*factor for d in (0,1)]
    out[k]=[out[i][d]+(s*u[d]+height*v[d])*factor for d in (0,1)]
    return out


def encode_triangle_uv(xyz, ideal_uv, *, tile_px):
    """Choose a directed float32 encoding within 0.01 pixel of a rigid chart.

    Fixed-density geometry and packing are already frozen. Search only the two
    neighbouring float32 representable values per coordinate, not pixels or a
    density scale. Refuse if format quantization cannot satisfy legal bounds.
    """
    import itertools
    import numpy as np
    if type(tile_px) is not int or tile_px not in (2048,4096):raise ValueError('unsupported tile_px')
    if len(xyz)!=3 or len(ideal_uv)!=3:raise ValueError('triangle required')
    project_saved_points(xyz,xyz,ideal_uv)
    x=np.asarray(xyz,dtype=float);ideal=np.asarray(ideal_uv,dtype=float)
    e=x[1:]-x[0];a=e[0]/np.linalg.norm(e[0]);n=np.cross(e[0],e[1]);n/=np.linalg.norm(n);b=np.cross(n,a)
    physical=np.c_[e@a,e@b];inverse=np.linalg.inv(physical)
    rounded=ideal.astype(np.float32).ravel()
    if not np.isfinite(rounded).all():raise ValueError('float32 UV overflow')
    for radius in (1,2):
        choices=[]
        for v in rounded:
            low=[];high=[];lo=v;hi=v
            for _ in range(radius):
                lo=np.nextafter(lo,np.float32(-np.inf));hi=np.nextafter(hi,np.float32(np.inf));low.append(lo);high.append(hi)
            choices.append(low[::-1]+[v]+high)
        candidates=np.asarray(list(itertools.product(*choices)),dtype=float).reshape(-1,3,2)
        delta=(candidates[:,1:]-candidates[:,:1])*tile_px
        jac=np.einsum('ij,njk->nik',inverse,delta)
        singular=np.linalg.svd(jac,compute_uv=False)
        errors=np.max(np.linalg.norm(candidates-ideal,axis=2),axis=1)*tile_px
        ok=(singular[:,1]>=512)&(singular[:,0]<=1706)&(singular[:,0]/singular[:,1]<=1.02)&(errors<=.01)
        ok &= (np.linalg.det(delta)>0)&(candidates.min(axis=(1,2))>=0)&(candidates.max(axis=(1,2))<=1)
        good=np.flatnonzero(ok)
        if len(good):
            best=min(good,key=lambda i:(errors[i],float(np.sum((candidates[i]-ideal)**2))))
            return dict(uv=candidates[best].tolist(),singular_px_m=singular[best].tolist(),
                        max_encoding_error_px=float(errors[best]),ulp_radius=radius)
    raise ValueError('native float32 encoding exceeds density/anisotropy/subpixel budget')


def conform_source_mesh(vertices, faces, lineage, uv, source_vertices, source_faces, *, epsilon_m=2e-5, collapsed_sources=()):
    """Resolve only source-proven duplicate endpoints, then node shared edges.

    Coordinates must be in the same metre frame. Original vertices remain in
    their original slots; unused duplicates are reported, not silently deleted.
    This is not a 2-mm weld: disconnected source surfaces never share identity.
    The caller must certify native tessellation, surface and interpolated UVs.
    """
    import numpy as np
    from collections import defaultdict
    def points(value, dim, name):
        if not isinstance(value,list) or not value or any(not isinstance(p,list) or len(p)!=dim or any(
            isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in p) for p in value):
            raise ValueError('invalid '+name)
    points(vertices,3,'vertices');points(source_vertices,3,'source_vertices')
    if isinstance(epsilon_m,bool) or not isinstance(epsilon_m,(int,float)) or not math.isfinite(epsilon_m) or not 0<epsilon_m<=2e-5:
        raise ValueError('invalid epsilon_m')
    if not isinstance(faces,list) or not faces or len(faces)!=len(lineage) or len(faces)!=len(uv):raise ValueError('partial faces/lineage/uv')
    if not isinstance(source_faces,dict) or not source_faces:raise ValueError('empty source_faces')
    for key,face in source_faces.items():
        if type(key) is not int or len(face)<3 or len(set(face))!=len(face) or any(type(i) is not int or not 0<=i<len(source_vertices) for i in face):
            raise ValueError('invalid source face '+str(key))
    for face,src,coords in zip(faces,lineage,uv):
        if type(src) is not int or src not in source_faces:raise ValueError('unmapped source face '+str(src))
        if len(face)<3 or len(set(face))!=len(face) or any(type(i) is not int or not 0<=i<len(vertices) for i in face):raise ValueError('invalid face')
        points(coords,2,'uv')
        if len(coords)!=len(face):raise ValueError('partial uv')
    nsource=len(source_vertices)
    if vertices[:nsource]!=source_vertices:raise ValueError('original vertex prefix changed')
    v=np.array(vertices,dtype=float);owners=defaultdict(set)
    for face,src in zip(faces,lineage):
        for i in face:owners[i].add(src)
    edges={src:{tuple(sorted((a,b))) for a,b in zip(f,f[1:]+f[:1])} for src,f in source_faces.items()}
    def on_edge(p, edge):
        a,b=v[list(edge)];d=b-a;length=float(d@d)
        if length==0:return False
        t=float((p-a)@d/length)
        return 0<=t<=1 and np.linalg.norm(p-a-t*d)<=epsilon_m
    def compatible(i,j):
        if owners[i]&owners[j]:return True
        for a in owners[i]:
            for b in owners[j]:
                if any(on_edge(v[i],e) and on_edge(v[j],e) for e in edges[a]&edges[b]):return True
        return False
    remap=list(range(len(v)));changes=[]
    # Original source vertex identity wins; only the actual owning source
    # face may nominate an endpoint, not an arbitrary nearby surface.
    for i in sorted(owners):
        if i<nsource:continue
        candidates={j for src in owners[i] for j in source_faces[src] if np.linalg.norm(v[i]-v[j])<=epsilon_m}
        if len(candidates)>1:raise ValueError('ambiguous source endpoint '+str(i))
        if candidates:
            j=candidates.pop();remap[i]=j;changes.append({'from':i,'to':j,'distance_m':float(np.linalg.norm(v[i]-v[j]))})
    active=sorted(i for i in owners if remap[i]==i)
    # Bound each merge directly to its representative (no distance chains).
    for ii,i in enumerate(active):
        if remap[i]!=i:continue
        for j in active[ii+1:]:
            if j<nsource or remap[j]!=j:continue
            if np.linalg.norm(v[i]-v[j])<=epsilon_m and compatible(i,j):
                remap[j]=i;changes.append({'from':j,'to':i,'distance_m':float(np.linalg.norm(v[i]-v[j]))})
    for i in range(len(remap)):
        while remap[i]!=remap[remap[i]]:remap[i]=remap[remap[i]]
    if not isinstance(collapsed_sources,(list,tuple)) or any(type(s) is not int or s not in source_faces for s in collapsed_sources):raise ValueError('invalid collapse source scope')
    newfaces=[];newuv=[];new_lineage=[];input_face=[];dropped=[]
    for fi,(face,src,coords) in enumerate(zip(faces,lineage,uv)):
        mapped=[remap[i] for i in face];keep=[i for i in range(len(face)) if mapped[i]!=mapped[i-1]]
        clean=[mapped[i] for i in keep]
        if len(set(clean))<3:
            if src not in collapsed_sources:raise ValueError('conforming would collapse a face')
            dropped.append(dict(face=fi,source=src,reason='explicit minor scope: proven sub-native identity collapsed connectivity cell'))
            continue
        if len(set(clean))!=len(clean):raise ValueError('conforming repeats nonconsecutive vertex')
        newfaces.append(clean);newuv.append([coords[i] for i in keep]);new_lineage.append(src);input_face.append(fi)
    if set(new_lineage)!=set(lineage):raise ValueError('conforming loses source identity')
    owners=defaultdict(set)
    for f,src in zip(newfaces,new_lineage):
        for i in f:owners[i].add(src)
    active=np.array(sorted(owners),dtype=int);positions=v[active];out=[];outuv=[];insertions=[]
    for fi,(face,src,coords) in enumerate(zip(newfaces,new_lineage,newuv)):
        nf=[];nu=[]
        for k,a in enumerate(face):
            b=face[(k+1)%len(face)];d=v[b]-v[a];length=float(d@d)
            if length==0:raise ValueError('zero length edge')
            ts=(positions-v[a])@d/length
            ds=np.linalg.norm(positions-v[a]-ts[:,None]*d,axis=1)
            candidates=active[(ts>0)&(ts<1)&(ds<=epsilon_m)]
            cuts=[]
            for j in candidates:
                j=int(j)
                if j in face:continue
                distances=[]
                for edge_index,x in enumerate(face):
                    y=face[(edge_index+1)%len(face)];edge=v[y]-v[x];size=float(edge@edge)
                    fraction=float(np.clip((v[j]-v[x])@edge/size,0,1)) if size else 0.
                    distances.append(float(np.linalg.norm(v[j]-v[x]-fraction*edge)))
                if min(range(len(face)),key=lambda edge_index:distances[edge_index])!=k:continue
                if src not in owners[j] and not any(on_edge(v[a],e) and on_edge(v[b],e) and on_edge(v[j],e)
                    for other in owners[j] for e in edges[src]&edges[other]):continue
                t=float((v[j]-v[a])@d/length);cuts.append((t,j))
            nf.append(a);nu.append(list(coords[k]))
            for t,j in sorted(cuts):
                nf.append(j);nu.append([(1-t)*coords[k][z]+t*coords[(k+1)%len(face)][z] for z in (0,1)])
                insertions.append({'face':fi,'edge':[a,b],'vertex':j})
        if len(set(nf))!=len(nf):raise ValueError('repeated conforming vertex')
        out.append(nf);outuv.append(nu)
    return dict(vertices=[list(p) for p in vertices],faces=out,uv=outuv,remap=remap,merges=changes,insertions=insertions,input_face=input_face,dropped_faces=dropped,
                unused_vertices=sorted(set(range(len(vertices)))-{i for f in out for i in f}))


def triangulate_conforming_polygon(points):
    """Maximize the worst aspect quality while retaining EVERY boundary node.

    No simplify, DCC-chosen diagonal, inserted centre or omitted collinear node.
    Return ordered corner indices; refuse a non-simple or zero-area polygon.
    """
    from shapely.geometry import Polygon
    if not isinstance(points,list) or len(points)<3 or any(not isinstance(p,list) or len(p)!=2 or any(
        isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in p) for p in points):
        raise ValueError('invalid conforming polygon')
    poly=Polygon(points);n=len(points)
    if not poly.is_valid or poly.area<=1e-12 or not poly.exterior.is_ccw:raise ValueError('invalid conforming winding/surface')
    score={};result={}
    for i in range(n-1):score[i,i+1]=math.inf;result[i,i+1]=[]
    for span in range(2,n):
        for i in range(n-span):
            j=i+span;best=-1;chosen=None
            for k in range(i+1,j):
                if (i,k) not in result or (k,j) not in result:continue
                tri=Polygon([points[i],points[k],points[j]])
                if tri.area<=1e-12 or not tri.exterior.is_ccw or tri.difference(poly).area>max(1e-14,tri.area*1e-12):continue
                longest=max(math.dist(points[a],points[b])**2 for a in (i,k,j) for b in (i,k,j))
                quality=min(score[i,k],score[k,j],tri.area/longest)
                if quality>best:best=quality;chosen=result[i,k]+result[k,j]+[[i,k,j]]
            if chosen is not None:score[i,j]=best;result[i,j]=chosen
    if (0,n-1) not in result:raise ValueError('unrepresentable conforming triangulation')
    triangles=result[0,n-1]
    if len(triangles)!=n-2 or {i for t in triangles for i in t}!=set(range(n)):raise ValueError('incomplete conforming triangulation')
    return triangles


def coalesce_cut_nodes(vertices, faces, lineage, *, original_vertex_count, groups, allow_original_anchor=False):
    """Apply explicit minor-cut node groups bounded to 2 mm, never auto-weld.

    Original vertices cannot move or be removed. Report every collapsed cell;
    refuse loss of ANY source identity. Surface, finish, joint-width and native
    readback gates remain the caller's responsibility, not implied by success.
    """
    if not isinstance(vertices,list) or not vertices or any(not isinstance(p,list) or len(p)!=3 or any(
        isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in p) for p in vertices):raise ValueError('invalid vertices')
    if type(original_vertex_count) is not int or not 0<original_vertex_count<=len(vertices):raise ValueError('invalid original_vertex_count')
    if not isinstance(faces,list) or not faces or len(faces)!=len(lineage):raise ValueError('partial faces/lineage')
    if any(len(f)<3 or len(set(f))!=len(f) or any(type(i) is not int or not 0<=i<len(vertices) for i in f) for f in faces):raise ValueError('invalid faces')
    if any(type(s) is not int or s<0 for s in lineage):raise ValueError('invalid source identity')
    if not isinstance(groups,list) or not groups:raise ValueError('empty explicit groups')
    out=[list(v) for v in vertices];remap=list(range(len(vertices)));seen=set();maximum=0
    for group in groups:
        if not isinstance(group,dict) or set(group)!={'vertices','position'}:raise ValueError('invalid explicit group')
        ids=group['vertices'];p=group['position']
        if not isinstance(ids,list) or len(ids)<2 or len(set(ids))!=len(ids) or any(type(i) is not int or not 0<=i<len(vertices) or i in seen for i in ids):raise ValueError('original/duplicate/invalid cut-node group')
        if not isinstance(p,list) or len(p)!=3 or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in p):raise ValueError('nonfinite/partial cut-node position')
        anchors=[i for i in ids if i<original_vertex_count]
        if type(allow_original_anchor) is not bool or anchors and not allow_original_anchor or len(anchors)>1 or anchors and p!=vertices[anchors[0]]:
            raise ValueError('original anchor must remain unchanged and unique')
        motion=max(math.dist(vertices[i],p) for i in ids)
        if motion>.002:raise ValueError('cut-node movement exceeds 2 mm')
        maximum=max(maximum,motion);rep=min(ids);out[rep]=list(p)
        for i in ids:remap[i]=rep
        seen.update(ids)
    new=[];sources=[];dropped=[];retained=[]
    for fi,(f,src) in enumerate(zip(faces,lineage)):
        mapped=[remap[i] for i in f];clean=[i for k,i in enumerate(mapped) if i!=mapped[k-1]]
        if len(set(clean))<3:
            dropped.append(dict(face=fi,source=src,reason='explicit cut-node coalescence; collapsed connectivity cell'));continue
        if len(set(clean))!=len(clean):raise ValueError('coalescing creates repeated nonconsecutive vertex')
        new.append(clean);sources.append(src);retained.append(fi)
    if set(sources)!=set(lineage):raise ValueError('coalescing loses source identity')
    return dict(vertices=out,faces=new,lineage=sources,input_face=retained,dropped=dropped,remap=remap,max_displacement_m=maximum)


def joint_cross_section(face, expected_zones, observed_zones, origin, inward):
    """Measure complete interval sets against independent face-clipped design.

    A nominal owner-side centre may lie outside a thin/sloped face. At a crossing
    the union can be wider than 10 mm. Neither is permission to omit a sample:
    compare all expected/observed components and report the classification.
    Empty required coverage and additional false intervals never pass.
    """
    from shapely.geometry import Polygon,LineString,Point
    from shapely.ops import unary_union
    def vector(value):
        return isinstance(value,list) and len(value)==2 and all(not isinstance(x,bool) and isinstance(x,(int,float)) and math.isfinite(x) for x in value)
    def polygon(value):
        if not isinstance(value,list) or len(value)<3 or not all(vector(p) for p in value):raise ValueError('invalid joint polygon')
        p=Polygon(value)
        if not p.is_valid or p.area<=1e-12:raise ValueError('invalid joint surface')
        return p
    domain=polygon(face)
    if not vector(origin) or not vector(inward):raise ValueError('invalid joint probe')
    norm=math.hypot(*inward)
    if norm==0:raise ValueError('zero joint normal')
    normal=[x/norm for x in inward]
    if not isinstance(expected_zones,list) or not expected_zones or not isinstance(observed_zones,list):raise ValueError('partial joint mask')
    expected=unary_union([polygon(p) for p in expected_zones]).intersection(domain)
    observed=unary_union([polygon(p) for p in observed_zones]).intersection(domain)
    reach=max(math.dist(origin,p) for p in face)+.1
    line=LineString([[origin[k]+sign*reach*normal[k] for k in (0,1)] for sign in (-1,1)])
    def intervals(shape):
        cut=shape.intersection(line)
        parts=[cut] if cut.geom_type=='LineString' else list(getattr(cut,'geoms',[]))
        out=[]
        for part in parts:
            if part.geom_type!='LineString' or part.length<=1e-10:continue
            values=[sum((p[k]-origin[k])*normal[k] for k in (0,1)) for p in part.coords]
            out.append([min(values),max(values)])
        return sorted(out)
    e=intervals(expected);a=intervals(observed);used=set();errors=[];endpoint_errors=[];missing=0
    for lo,hi in e:
        candidates=[i for i,(x,y) in enumerate(a) if i not in used and min(hi,y)>max(lo,x)]
        if not candidates:missing+=1;continue
        i=min(candidates,key=lambda i:abs(sum(a[i])/2-(lo+hi)/2));used.add(i)
        x,y=a[i];errors.append(abs((x+y-lo-hi)/2)*1000);endpoint_errors.extend([abs(x-lo)*1000,abs(y-hi)*1000])
    width=sum(hi-lo for lo,hi in e)*1000
    classification='clipped' if width<9.98 else 'junction' if width>10.02 else 'single'
    false=len(a)-len(used)
    return dict(passed=bool(e) and missing==0 and false==0 and max(errors,default=math.inf)<=5 and max(endpoint_errors,default=math.inf)<=5,
                classification=classification,expected_intervals_m=e,observed_intervals_m=a,
                expected_width_mm=width,observed_width_mm=sum(hi-lo for lo,hi in a)*1000,
                max_centre_error_mm=max(errors,default=None),max_endpoint_error_mm=max(endpoint_errors,default=None),
                nominal_centre_outside_face=not domain.covers(Point([origin[k]+.005*normal[k] for k in (0,1)])),
                missing_intervals=missing,false_intervals=false)


def source_joint_footprint(image, source_uv, chart_m):
    """Read the delivered (40,32,32), L1<=4 mask at original pixel edges.

    Input RGB uint8 image uses PNG's top-down row order. Only the actual face UV
    bbox is scanned. No legacy 5-mm resampling or implicit endpoint truncation.
    A measured empty bitmap footprint is an explicit empty geometry, not a pass.
    """
    import numpy as np
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    if not isinstance(image,np.ndarray) or image.dtype!=np.uint8 or image.ndim!=3 or image.shape[2]!=3 or min(image.shape[:2])<1:raise ValueError('unsupported source RGB image')
    # Reuse finite/dimension and nondegenerate affine-frame validation.
    for rows in (source_uv,chart_m):
        if not isinstance(rows,list) or len(rows)<3 or any(not isinstance(p,list) or len(p)!=2 or any(
            isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in p) for p in rows):raise ValueError('invalid source UV/chart')
    if len(source_uv)!=len(chart_m):raise ValueError('partial source UV/chart')
    uv=np.asarray(source_uv,dtype=float);chart=np.asarray(chart_m,dtype=float);domain=Polygon(chart)
    if not domain.is_valid or domain.area<=1e-12 or uv.min()<0 or uv.max()>1:raise ValueError('unsupported source UV domain')
    h,w=image.shape[:2];pixels=uv*np.array([w,h]);a=np.c_[pixels-pixels[0],np.ones(len(pixels))]
    matrix=np.linalg.lstsq(a,chart-chart[0],rcond=None)[0]
    if np.linalg.matrix_rank(matrix[:2])!=2 or np.max(np.linalg.norm(a@matrix-(chart-chart[0]),axis=1))>2e-5:raise ValueError('unsupported nonaffine source UV frame')
    lo=np.maximum(0,np.floor(pixels.min(0)).astype(int));hi=np.minimum([w-1,h-1],np.ceil(pixels.max(0)).astype(int))
    active={};rectangles=[]
    for y in range(int(lo[1]),int(hi[1])+2):
        runs=[]
        if y<=hi[1]:
            row=image[h-1-y,lo[0]:hi[0]+1].astype(np.int16)
            xs=np.flatnonzero(np.abs(row-[40,32,32]).sum(1)<=4)+lo[0]
            if len(xs):
                for group in np.split(xs,np.flatnonzero(np.diff(xs)>1)+1):runs.append((int(group[0]),int(group[-1])+1))
        for run,start in list(active.items()):
            if run not in runs:rectangles.append([run[0],start,run[1],y]);del active[run]
        for run in runs:active.setdefault(run,y)
    polygons=[]
    for x0,y0,x1,y1 in rectangles:
        p=np.array([[x0,y0],[x1,y0],[x1,y1],[x0,y1]],dtype=float)
        polygons.append(Polygon(np.c_[p-pixels[0],np.ones(4)]@matrix+chart[0]))
    return unary_union(polygons).intersection(domain)


def rectify_axis_joint_footprint(footprint, *, face=None):
    """Fit explicit chart-axis 10-mm bands to a measured raster footprint.

    Use only on authorized minor-part joint masks. Unlike tracing 1.95-mm pixel
    stairs into topology, fit nominal-width lines, merge collinear fragments and
    prove BOTH false/missing shape containment at the fixed 5-mm contract.
    Refuse broad/diagonal source shapes rather than silently reinterpreting them.
    """
    from shapely.geometry import box
    from shapely.ops import unary_union
    if footprint.is_empty:return footprint
    if not footprint.is_valid:raise ValueError('invalid reference joint footprint')
    components=[footprint] if footprint.geom_type=='Polygon' else list(getattr(footprint,'geoms',[]))
    bands=[]
    for part in components:
        if part.geom_type!='Polygon' or part.area<=1e-12:continue
        x0,y0,x1,y1=part.bounds;dx=x1-x0;dy=y1-y0
        if min(dx,dy)>.025:raise ValueError('unsupported broad/diagonal reference joint')
        axis=0 if dx<=dy else 1
        center=(x0+x1)/2 if axis==0 else (y0+y1)/2
        lo,hi=(y0,y1) if axis==0 else (x0,x1)
        if hi-lo<.01:lo,hi=(lo+hi)/2-.005,(lo+hi)/2+.005
        bands.append(dict(axis=axis,center=center,lo=lo,hi=hi,weight=part.area))
    changed=True
    while changed:
        changed=False
        for i,a in enumerate(bands):
            for j in range(i+1,len(bands)):
                b=bands[j]
                if a['axis']!=b['axis'] or abs(a['center']-b['center'])>.004 or max(a['lo'],b['lo'])-min(a['hi'],b['hi'])>.005:continue
                weight=a['weight']+b['weight']
                a.update(center=(a['center']*a['weight']+b['center']*b['weight'])/weight,lo=min(a['lo'],b['lo']),hi=max(a['hi'],b['hi']),weight=weight)
                bands.pop(j);changed=True;break
            if changed:break
    polygons=[]
    for a in bands:
        c=a['center'];lo=a['lo'];hi=a['hi']
        polygons.append(box(c-.005,lo,c+.005,hi) if a['axis']==0 else box(lo,c-.005,hi,c+.005))
    result=unary_union(polygons)
    if face is not None:
        if face.is_empty or not face.is_valid or footprint.difference(face).area>1e-12:raise ValueError('invalid reference face clipping')
        result=result.intersection(face)
    if footprint.difference(result.buffer(.005)).area>1e-12 or result.difference(footprint.buffer(.005)).area>1e-12:
        # Cap/return charts can carry a sloping source stripe. Preserve its
        # measured long axis instead of imposing the main-wall chart axes.
        from shapely.geometry import Polygon
        oriented=[]
        for part in components:
            if part.geom_type!='Polygon' or part.area<=1e-12:continue
            corners=list(part.minimum_rotated_rectangle.exterior.coords[:-1])
            lengths=[math.dist(corners[i],corners[(i+1)%4]) for i in range(4)]
            index=max(range(4),key=lambda i:lengths[i]);length=lengths[index]
            if length==0:raise ValueError('degenerate reference joint axis')
            direction=[(corners[(index+1)%4][k]-corners[index][k])/length for k in (0,1)];normal=[-direction[1],direction[0]]
            center=[sum(p[k] for p in corners)/4 for k in (0,1)];half=max(length,.006)/2
            oriented.append(Polygon([[center[k]+s*half*direction[k]+t*.005*normal[k] for k in (0,1)] for s,t in [(-1,-1),(1,-1),(1,1),(-1,1)]]))
        result=unary_union(oriented)
        if face is not None:result=result.intersection(face)
        if footprint.difference(result.buffer(.005)).area>1e-12 or result.difference(footprint.buffer(.005)).area>1e-12:
            raise ValueError('axis joint fit exceeds fixed 5 mm correspondence')
    return result


def vectorize_joint_footprint(footprint, *, face):
    """Retain measured tapered strip ends without tracing raster stair vertices.

    Authorized minor-part masks only. Nearby source pixel components may be
    joined, but every resulting polygon must remain within 5 mm of the actual
    source in BOTH directions. This is not permission to fill arbitrary holes
    or to replace a broad/unsupported reference with a guessed nominal joint.
    """
    from shapely.ops import unary_union
    if face.geom_type != 'Polygon' or not face.is_valid or face.area <= 1e-12:
        raise ValueError('invalid reference face')
    if footprint.is_empty:
        return footprint
    if not footprint.is_valid or footprint.geom_type not in ('Polygon', 'MultiPolygon'):
        raise ValueError('unsupported reference joint footprint')
    if footprint.difference(face.buffer(1e-10)).area > 1e-12:
        raise ValueError('reference footprint outside face')
    parts = [footprint] if footprint.geom_type == 'Polygon' else list(footprint.geoms)
    groups = []
    for part in parts:
        # A stripe may be sloped, but a broad patch is not a panel joint.
        corners = list(part.minimum_rotated_rectangle.exterior.coords)
        if min(math.dist(a, b) for a, b in zip(corners, corners[1:])) > .025:
            raise ValueError('unsupported broad reference joint')
        nearby = [i for i, group in enumerate(groups) if group.distance(part) < .005]
        merged = unary_union([part] + [groups[i] for i in nearby])
        groups = [group for i, group in enumerate(groups) if i not in nearby]
        groups.append(merged)
    from shapely import snap
    result = unary_union([g.convex_hull.simplify(.0021, preserve_topology=True)
                          for g in groups]).intersection(face)
    # Select unchanged source corners BEFORE topology, rather than repairing a
    # triangulated foldover afterward. Every resulting mask still has to satisfy
    # the independent 5-mm source-shape bound below.
    result = snap(result, face, .0021).intersection(face)
    if not result.is_valid:
        raise ValueError('invalid corner-anchored joint footprint')
    if (footprint.difference(result.buffer(.005)).area > 1e-12 or
            result.difference(footprint.buffer(.005)).area > 1e-12):
        raise ValueError('vector joint fit exceeds fixed 5 mm correspondence')
    return result
