-- Own implementation. Installs versioned files, refuses stale/partial destinations.
(
    global AGRToolsInstallRoot, AGRToolsStartupRoot
    local source = getFilenamePath (getSourceFileName())
    if AGRToolsInstallRoot == undefined do AGRToolsInstallRoot = (getDir #userScripts) + "/AGRTools-0.6.0/"
    if AGRToolsStartupRoot == undefined do AGRToolsStartupRoot = (getDir #userStartupScripts) + "/"
    if doesDirectoryExist AGRToolsInstallRoot do throw "AGR Tools destination already exists; choose a new versioned path"
    local boot = AGRToolsStartupRoot + "AGRTools-0.6.0.ms"
    if doesFileExist boot do throw "AGR Tools startup file already exists"
    local files = getFiles (source + "agr_tools/*")
    if files.count < 20 do throw "AGR Tools archive incomplete"
    local required = #("runtime.py", "atlas_core.py", "uv_nudge_core.py", "startup.ms", "agr_tools.mcr", "menu.ms", "bootstrap.py", "hygiene_core.py", "README.md", "ucx_core.py", "texel_core.py", "ucx_audit_core.py", "export_core.py", "checks_core.py", "checks_max.py", "CHANGELOG.md", "ui_model.py", "ui_qt.py", "ui_panel.py", "ui_max.py")
    for name in required do (
        local found = false
        for f in files where (filenameFromPath f) == name do found = true
        if not found do throw ("AGR Tools archive missing " + name)
    )
    local themes = #("Dark", "Light")
    for theme in themes do (
        local icons = getFiles (source + "agr_tools/icons/" + theme + "/AgrIcons/*.png")
        if icons.count < 92 do throw ("AGR Tools archive missing icons " + theme)
    )
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
    local stream = createFile boot
    format "fileIn @\"%startup.ms\"\n" (substituteString AGRToolsInstallRoot "\\" "/") to:stream
    close stream
    fileIn (AGRToolsInstallRoot + "startup.ms")
)
