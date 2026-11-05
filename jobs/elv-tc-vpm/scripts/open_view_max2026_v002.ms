-- Opens delivery v004 for viewing in an own 3ds Max 2026 (no save). Textures via OSL UberBitmap2 <UDIM>.
(
  local dir = @"C:\x\elv_view_v004\"
  units.SystemType = #meters
  FBXImporterSetParam "Mode" #create
  FBXImporterSetParam "ScaleConversion" false
  FBXImporterSetParam "ConvertUnit" "m"
  importFile (dir + "SM_Elevatornaya_Vl_1_A_001.fbx") #noPrompt using:FBXIMP
  local ucx = for o in objects where matchPattern o.name pattern:"UCX_*" collect o
  hide ucx
  fn udimMap kind lin = (
    local m = OSLMap()
    m.OSLPath = (getDir #maxRoot) + @"OSL\UberBitmap2.osl"
    m.OSLAutoUpdate = true
    try (m.Filename = dir + "T_Elevatornaya_Vl_1_A_001_" + kind + "_1.<UDIM>.png") catch ()
    try (m.UDIM = 1) catch ()
    m
  )
  local main = getNodeByName "SM_Elevatornaya_Vl_1_A_001_Main"
  if main != undefined do (
    local mat = PhysicalMaterial name:"M_Elevatornaya_Vl_1_A_001_view"
    try (mat.base_color_map = udimMap "Diffuse" false) catch (format "diffuse map failed\n")
    try (mat.bump_map = Normal_Bump normal_map:(udimMap "Normal" true); mat.bump_map_amt = 1.0) catch ()
    mat.roughness = 0.6
    main.material = mat
  )
  local gl = getNodeByName "SM_Elevatornaya_Vl_1_A_001_MainGlass"
  if gl != undefined do gl.material = PhysicalMaterial name:"M_Glass_view" base_color:(color 40 60 70) roughness:0.05 metalness:0.84
  max views redraw
  actionMan.executeAction 0 "310"  -- zoom extents all
  viewport.setLayout #layout_4
  max zoomext sel all
  format "elv view ready: % objects, % UCX hidden\n" objects.count ucx.count
  local f = createFile (dir + "view_status.txt")
  format "objects=% ucx_hidden=% main=% glass=%\n" objects.count ucx.count (main != undefined) (gl != undefined) to:f
  close f
)
