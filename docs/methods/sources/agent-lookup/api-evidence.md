## Blender 5.0 FBX
Source: https://raw.githubusercontent.com/blender/blender/blender-v5.0-release/scripts/addons_core/io_scene_fbx/__init__.py
SHA256 (full response): 1049100a78d5360cc64486d5f3e2a9782ed0fe4a8ba961b886385b61f498f699
Upstream lines: 129-134
```
    use_anim: BoolProperty(
        name="Import Animation",
        description="Import FBX animation",
        default=True,
    )
    anim_offset: FloatProperty(
```

## trimesh convex hull
Source: https://raw.githubusercontent.com/mikedh/trimesh/main/trimesh/base.py
SHA256 (full response): 0090309bfd53eba33136076799c86525506b1d1aeff706d7a06af2f020469854
Upstream lines: 2507-2519 (cache_decorator exposes this as a cached property)
```
    @cache_decorator
    def convex_hull(self) -> "Trimesh":
        """
        Returns a Trimesh object representing the convex hull of
        the current mesh.

        Returns
        --------
        convex : trimesh.Trimesh
          Mesh of convex hull of current mesh
        """
        return convex.convex_hull(self)

```
