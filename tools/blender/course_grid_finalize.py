"""new-case: apply a hash-bound, fixed-node native finalization plan in Blender.

Run with Blender --background <copy.blend> --python-exit-code 3 --python
this_script -- --plan <new-plan.json> --output <new-directory>.
No live-session connection; original files and map links are never overwritten.
The plan is prepared with course_grid_native.plan_boundary_finalization outside
Blender, where Shapely is available. Export/readback QA remains mandatory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def check_native_metadata(metadata):
    """Refuse payloads the fixed-node adapter cannot preserve, before edits."""
    if (metadata.get('custom_normals') is not False
            or metadata.get('uv_channels')!=1 or metadata.get('edge_seams')!=0):
        raise ValueError('unsupported custom normals, UV channels or edge seams')
    if (not isinstance(metadata.get('uv_names'),list) or len(metadata['uv_names'])!=1
            or not metadata['uv_names'][0] or not metadata.get('attributes')):
        raise ValueError('missing native UV/attribute metadata')
    builtins={
        'position':('POINT','FLOAT_VECTOR'),'.select_vert':('POINT','BOOLEAN'),
        '.corner_vert':('CORNER','INT'),'.corner_edge':('CORNER','INT'),
        '.edge_verts':('EDGE','INT32_2D'),'.select_edge':('EDGE','BOOLEAN'),
        '.select_poly':('FACE','BOOLEAN'),'sharp_face':('FACE','BOOLEAN')}
    for attr in metadata.get('attributes',[]):
        if builtins.get(attr['name'])==(attr['domain'],attr['type']):continue
        if attr['domain']=='FACE' and attr['type']=='INT':continue
        if (attr['domain']=='CORNER' and attr['type']=='FLOAT2'
                and attr['name'] in metadata.get('uv_names',[])):continue
        raise ValueError(f"unsupported native attribute: {attr['name']}")


def apply(plan, output):
    import bpy
    if plan.get('schema')!='course-grid-native-finalize/1':raise ValueError('invalid native plan')
    source=Path(plan['source_scene']['path']).resolve();output=Path(output).resolve()
    if Path(bpy.data.filepath).resolve()!=source:raise ValueError('wrong open document')
    if bpy.app.version_string!=plan['blender_version'] or bpy.context.scene.unit_settings.scale_length!=1:
        raise ValueError('wrong Blender version or non-metre units')
    if digest(source)!=plan['source_scene']['sha256']:raise ValueError('stale source scene')
    if output.exists() or output in source.parents:raise ValueError('output exists or aliases source')
    names=plan['export_objects']
    if not names or len(set(names))!=len(names):raise ValueError('invalid export object set')
    if not plan['faces']:raise ValueError('empty native plan')
    targets={}
    for record in plan['faces']:
        name=record['object'];obj=bpy.data.objects.get(name)
        if name not in names or obj is None or obj.type!='MESH':raise ValueError('missing target mesh')
        mesh=obj.data
        check_native_metadata(dict(custom_normals=mesh.has_custom_normals,
            uv_channels=len(mesh.uv_layers),uv_names=[layer.name for layer in mesh.uv_layers],
            edge_seams=sum(e.use_seam for e in mesh.edges),
            attributes=[dict(name=a.name,domain=a.domain,type=a.data_type) for a in mesh.attributes]))
        face=mesh.polygons[record['face']]
        if (list(face.vertices)!=record['vertices']
                or [list(mesh.vertices[i].co) for i in face.vertices]!=record['local_xyz']
                or [list(mesh.uv_layers.active.data[i].uv) for i in face.loop_indices]!=record['uv']
                or face.material_index+1!=record['material_id']
                or mesh.attributes['agr_source_face'].data[face.index].value!=record['source_face']):
            raise ValueError('stale native source/corner association')
        key=(name,face.index)
        if key in targets:raise ValueError('duplicate native face')
        n=len(face.vertices)
        if record.get('operation')=='cyclic-anchor':
            loops=record['boundary_loops']
            if (len(loops)!=1 or len(loops[0])!=n or sorted(loops[0])!=list(range(n))
                    or any(loops[0][(i+1)%n]!=(loops[0][i]+1)%n for i in range(n))):
                raise ValueError('not an exact cyclic boundary permutation')
        else:
            triangles=record['triangles']
            if len(triangles)!=n-2 or set(i for t in triangles for i in t)!=set(range(n)):
                raise ValueError('incomplete boundary triangulation')
            if any(len(t)!=3 or len(set(t))!=3 or any(type(i) is not int or not 0<=i<n for i in t) for t in triangles):
                raise ValueError('invalid boundary triangle')
        targets[key]=record
    # All source/corner checks precede any mesh mutation.
    reports=[]
    for name in names:
        obj=bpy.data.objects[name];old=obj.data
        if not any(k[0]==name for k in targets):continue
        faces=[];coords=[];previous=[]
        for face in old.polygons:
            record=targets.get((name,face.index));triangles=(record['boundary_loops'] if record.get('operation')=='cyclic-anchor' else record['triangles']) if record else [list(range(len(face.vertices)))]
            for triangle in triangles:
                faces.append([face.vertices[i] for i in triangle]);coords.append([list(old.uv_layers.active.data[face.loop_indices[i]].uv) for i in triangle]);previous.append(face.index)
        mesh=bpy.data.meshes.new(name+'_fixed_node_diagonals');mesh.from_pydata([list(v.co) for v in old.vertices],[],faces);mesh.update()
        for material in old.materials:mesh.materials.append(material)
        uv=mesh.uv_layers.new(name=old.uv_layers.active.name)
        attrs=[a for a in old.attributes if a.domain=='FACE' and a.data_type=='INT' and not a.name.startswith('.')]
        for attr in attrs:mesh.attributes.new(attr.name,'INT','FACE')
        for face,values,prev in zip(mesh.polygons,coords,previous):
            face.material_index=old.polygons[prev].material_index;face.use_smooth=old.polygons[prev].use_smooth
            for attr in attrs:mesh.attributes[attr.name].data[face.index].value=attr.data[prev].value
            for li,value in zip(face.loop_indices,values):uv.data[li].uv=value
        if [list(v.co) for v in mesh.vertices]!=[list(v.co) for v in old.vertices]:raise ValueError('vertex mutation')
        obj.data=mesh;reports.append(dict(object=name,input_faces=len(old.polygons),output_faces=len(mesh.polygons),vertices_unchanged=True))
    def enable(layer):
        layer.exclude=False;layer.hide_viewport=False
        for child in layer.children:enable(child)
    enable(bpy.context.view_layer.layer_collection)
    for coll in bpy.data.collections:coll.hide_viewport=False
    for obj in bpy.data.objects:
        obj.hide_set(False);obj.select_set(False)
        if obj.name in names:obj.hide_viewport=False;obj.hide_render=False;obj.hide_select=False
    bpy.context.view_layer.update()
    for name in names:
        obj=bpy.data.objects[name];obj.select_set(True)
        if not obj.visible_get():raise ValueError('invisible export target')
    if sorted(obj.name for obj in bpy.context.selected_objects)!=sorted(names):raise ValueError('wrong export selection')
    output.mkdir(parents=True,exist_ok=False)
    blend=output/'course_grid_finalized_QA_OPEN.blend';fbx=output/'course_grid_finalized_QA_OPEN.fbx'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH'},use_mesh_modifiers=False,use_triangles=False,add_leaf_bones=False,apply_unit_scale=True,path_mode='ABSOLUTE',axis_forward='-Z',axis_up='Y')
    if digest(source)!=plan['source_scene']['sha256']:raise ValueError('source changed during finalization')
    report=dict(passed=False,status='native_finalized_export_readback_required',rows=reports,artifacts=[dict(path=str(p),sha256=digest(p)) for p in (blend,fbx)])
    (output/'native-finalization.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf8')
    print('NATIVE_FINALIZATION',json.dumps(report),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.output.resolve()==args.plan.resolve() or args.output.resolve() in args.plan.resolve().parents:raise ValueError('plan/output alias')
    apply(json.loads(args.plan.read_text(encoding='utf8')),args.output)


if __name__=='__main__':main()
