-- Synthetic AGR Tools polygon. The .max is an output in 2024 format (opens in 2026).
-- Run inside 3ds Max 2024 or newer. Does not overwrite files under test-polygon/.
--
--   python.ExecuteFile (scriptDir + "build_scene.py")
-- Then in the listener: build("polygon_all") and save <new path>
(
    local scriptDir = getFilenamePath (getThisScriptFilename())
    python.ExecuteFile (scriptDir + "build_scene.py")
    format "AGR polygon builder loaded from %\n" scriptDir
)
