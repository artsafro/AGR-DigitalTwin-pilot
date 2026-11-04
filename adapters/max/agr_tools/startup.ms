-- Headless-safe registration. Does not create a dialog at startup.
-- Documented MAXScript globals: AGRToolsRoot, AGRToolsRegistered, AGRToolsRegisterMenus (menu.ms);
-- AGRToolsDialog only when the classic rollout is opened. Everything else is local.
(
    global AGRToolsRegistered, AGRToolsRoot
    AGRToolsRoot = getFilenamePath (getSourceFileName())
    python.ExecuteFile (AGRToolsRoot + "bootstrap.py")
    fileIn (AGRToolsRoot + "agr_tools.mcr")
    fileIn (AGRToolsRoot + "menu.ms")
    AGRToolsRegistered = true
    format "AGR_TOOLS_REGISTERED version=0.6.0 category=AGR Tools macros=Open,Classic,XView,MatID,Names,Tris,Textures,Pivot,Nudge,NudgeApply,Atlas,AtlasApply,Texel,Ucx,UcxApply,Cleanup,CleanupApply,Export,Geojson\n"
)
