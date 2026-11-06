-- Own implementation. Installs versioned files, refuses stale/partial destinations.
(
    global AGRToolsInstallRoot, AGRToolsStartupRoot
    local source = getFilenamePath (getSourceFileName())
    if AGRToolsInstallRoot == undefined do AGRToolsInstallRoot = (getDir #userScripts) + "/AGRTools-0.9.0/"
    if AGRToolsStartupRoot == undefined do AGRToolsStartupRoot = (getDir #userStartupScripts) + "/"
    if doesDirectoryExist AGRToolsInstallRoot do throw "AGR Tools destination already exists; choose a new versioned path"
    local boot = AGRToolsStartupRoot + "AGRTools-0.9.0.ms"
    if doesFileExist boot do throw "AGR Tools startup file already exists"
    local files = getFiles (source + "agr_tools/*")
    if files.count < 118 do throw "AGR Tools archive incomplete"
    local required = #("runtime.py", "atlas_core.py", "uv_nudge_core.py", "startup.ms", "agr_tools.mcr", "menu.ms", "bootstrap.py", "hygiene_core.py", "README.md", "ucx_core.py", "texel_core.py", "ucx_audit_core.py", "export_core.py", "checks_core.py", "checks_max.py", "CHANGELOG.md", "ui_model.py", "ui_qt.py", "ui_panel.py", "ui_max.py", "suite_core.py", "suite_max.py", "roadmap.py", "agr-tools-suite.json", "edit_core.py", "edit_max.py", "geom_core.py", "geom_max.py", "tex_core.py", "tex_max.py", "names_core.py", "names_max.py", "udim_core.py", "udim_max.py", "package_core.py", "package_max.py", "place_core.py", "place_max.py", "texqa_core.py", "texqa_max.py", "finish_core.py", "finish_max.py", "uvtile_core.py", "uvtile_max.py", "flora_atlas_max.py", "qa9_core.py", "qa9_max.py", "facade_core.py", "facade_max.py", "batch_core.py", "batch_max.py", "mapsuse_core.py", "mapsuse_max.py", "light_core.py", "light_max.py", "session_core.py", "contract_core.py", "journal_core.py", "host_max.py", "openings_core.py", "uvlayout_core.py", "vpmmaps_core.py", "passport_core.py", "passport_max.py", "intake_core.py", "intake_max.py", "scene10_core.py", "scene10_max.py", "body_core.py", "body_max.py", "model10_core.py", "model10_max.py", "gridclean_core.py", "gridclean_max.py", "glass_core.py", "glass_max.py", "windowgen_core.py", "windowgen_max.py", "winplace_core.py", "winplace_max.py", "capsule_core.py", "capsule_max.py", "roof_core.py", "roof_max.py", "matlib_core.py", "matlib_max.py", "tiles_core.py", "tiles_max.py", "plugcolour_core.py", "plugcolour_max.py", "vpm_core.py", "vpm_max.py", "udim10_core.py", "udim10_max.py", "dilate_core.py", "dilate_max.py", "udimplug_core.py", "udimplug_max.py", "npm_core.py", "npm_max.py", "facadeatlas_core.py", "facadeatlas_max.py", "npm2vpm_core.py", "npm2vpm_max.py", "udimview_core.py", "udimview_max.py", "deliver_core.py", "deliver_max.py", "ucx10_core.py", "ucx10_max.py", "ucxstairs_core.py", "ucxstairs_max.py", "omk_core.py", "omk_max.py", "placegeo_core.py", "placegeo_max.py", "agentbridge_core.py", "agentbridge_max.py")
    for name in required do (
        local found = false
        for f in files where (filenameFromPath f) == name do found = true
        if not found do throw ("AGR Tools archive missing " + name)
    )
    local themes = #("Dark", "Light")
    for theme in themes do (
        local icons = getFiles (source + "agr_tools/icons/" + theme + "/AgrIcons/*.png")
        if icons.count < 400 do throw ("AGR Tools archive missing icons " + theme)
    )
    -- 0.9 (#979): data/ (owner files of branch C) is a tree of at most one sub-folder level
    local dataSrc = source + "agr_tools/data/"
    if (getFiles (dataSrc + "procedural_classes.json")).count != 1 do throw "AGR Tools archive missing data/procedural_classes.json"
    if (getFiles (dataSrc + "streets/PROVENANCE.md")).count != 1 do throw "AGR Tools archive missing data/streets/PROVENANCE.md"
    makeDir AGRToolsInstallRoot all:true
    for f in files do (
        if not copyFile f (AGRToolsInstallRoot + filenameFromPath f) do throw ("AGR Tools cannot install " + f)
    )
    for theme in themes do (
        local dst = AGRToolsInstallRoot + "icons/" + theme + "/AgrIcons/"
        makeDir dst all:true
        for f in getFiles (source + "agr_tools/icons/" + theme + "/AgrIcons/*") do (
            if not copyFile f (dst + filenameFromPath f) do throw ("AGR Tools cannot install " + f)
        )
    )
    local dataDst = AGRToolsInstallRoot + "data/"
    makeDir dataDst all:true
    for f in getFiles (dataSrc + "*") do (
        if not copyFile f (dataDst + filenameFromPath f) do throw ("AGR Tools cannot install " + f)
    )
    for d in getDirectories (dataSrc + "*") do (
        local sub = dataDst + (filenameFromPath (trimRight d "\\/")) + "/"
        makeDir sub all:true
        for f in getFiles (d + "*") do (
            if not copyFile f (sub + filenameFromPath f) do throw ("AGR Tools cannot install " + f)
        )
    )
    local stream = createFile boot
    format "fileIn @\"%startup.ms\"\n" (substituteString AGRToolsInstallRoot "\\" "/") to:stream
    close stream
    fileIn (AGRToolsInstallRoot + "startup.ms")
)
