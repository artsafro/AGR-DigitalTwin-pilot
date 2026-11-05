-- Opens delivery v004 for viewing in an own 3ds Max 2026 (no save) and textures Main with the user's
-- «UDIM Viewer_V1.4.ms» (Andrew_scripts): Blend(Multi/Sub per UDIM tile + Standard/MultiTile preview).
-- The viewer script is run as is (fileIn, not modified) from an ASCII-path copy.
(
  local dir = @"C:\x\elv_view_v004\"
  local viewer = @"C:\x\tools\UDIM_Viewer_V1.4.ms"  -- byte-identical copy of Andrew_scripts «UDIM Viewer_V1.4.ms» (ASCII path)
  local stem = "SM_Elevatornaya_Vl_1_A_001"
  local log = createFile (dir + "view_status_udim.txt")
  units.SystemType = #meters
  FBXImporterSetParam "Mode" #create
  FBXImporterSetParam "ScaleConversion" false
  FBXImporterSetParam "ConvertUnit" "m"
  importFile (dir + stem + ".fbx") #noPrompt using:FBXIMP
  local ucx = for o in objects where matchPattern o.name pattern:"UCX_*" collect o
  hide ucx
  format "imported objects=% ucx_hidden=%\n" objects.count ucx.count to:log

  fileIn viewer   -- creates the dialog CombinedImporterRollout
  local r = ::CombinedImporterRollout  -- explicit global: a bare name inside this block resolves as a local
  local texDir = trimRight dir "\\"
  r.texFolder = texDir
  r.foundChannels = r.scanFolderForUDIM texDir
  for g in r.foundChannels do format "channel % tiles=%\n" g[2] g[6].count to:log
  try (r.lblUdimFolder.Text = "elv_view_v004"; r.lblUdimStatus.Text = "Channels: " + (r.foundChannels.count as string)) catch ()
  try (r.lstUdimChannels.Items.Clear(); for g in r.foundChannels do r.lstUdimChannels.Items.Add (g[2] + "  (" + (g[6].count as string) + " tiles)")) catch ()

  r.initCaches()
  for nm in #(stem + "_Main", stem + "_MainGlass") do (
    local o = getNodeByName nm
    if o == undefined then format "% missing\n" nm to:log
    else (
      local ok = r.applyUDIMToObject o r.foundChannels false
      format "% udim=% material=%\n" nm ok (if o.material != undefined then o.material.name else "none") to:log
    )
  )
  r.clearCaches()
  local main = getNodeByName (stem + "_Main")
  if main != undefined do select main
  try (r.lblUdimObj.Text = "Object: " + main.name) catch ()
  viewport.setLayout #layout_4
  max zoomext sel all
  redrawViews()
  format "done\n" to:log
  close log
)
