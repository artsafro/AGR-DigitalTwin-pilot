-- Headless-safe registration. Does not create a dialog at startup.
(
    global AGRToolsRegistered, AGRToolsRoot
    AGRToolsRoot = getFilenamePath (getSourceFileName())
    python.ExecuteFile (AGRToolsRoot + "bootstrap.py")
    fileIn (AGRToolsRoot + "agr_tools.mcr")
    AGRToolsRegistered = true
    format "AGR_TOOLS_REGISTERED version=0.2.0 category=AGR Tools macros=XView,Cleanup,MatID,Open,Nudge,NudgeApply,Atlas,AtlasApply\n"
)

