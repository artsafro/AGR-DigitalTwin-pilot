-- Own implementation. Installs versioned files, refuses stale/partial destinations.
(
    global AGRToolsInstallRoot, AGRToolsStartupRoot
    local source = getFilenamePath (getSourceFileName())
    if AGRToolsInstallRoot == undefined do AGRToolsInstallRoot = (getDir #userScripts) + "/AGRTools-0.1.0/"
    if AGRToolsStartupRoot == undefined do AGRToolsStartupRoot = (getDir #userStartupScripts) + "/"
    if doesDirectoryExist AGRToolsInstallRoot do throw "AGR Tools destination already exists; choose a new versioned path"
    local boot = AGRToolsStartupRoot + "AGRTools-0.1.0.ms"
    if doesFileExist boot do throw "AGR Tools startup file already exists"
    makeDir AGRToolsInstallRoot all:true
    local files = getFiles (source + "agr_tools/*")
    if files.count < 5 do throw "AGR Tools archive incomplete"
    for f in files do (
        if not copyFile f (AGRToolsInstallRoot + filenameFromPath f) do throw ("AGR Tools cannot install " + f)
    )
    local stream = createFile boot
    format "fileIn @\"%startup.ms\"\n" (substituteString AGRToolsInstallRoot "\\" "/") to:stream
    close stream
    fileIn (AGRToolsInstallRoot + "startup.ms")
)

