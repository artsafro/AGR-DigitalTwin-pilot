-- AGR Tools `assets` browser (#1024): opens the window from the folder of this script.
-- Separate launcher on purpose: panel/menu/macro registration is done by the 1.0 branch (see the PR).
-- Run: Scripting > Run Script > assets_launch.ms, or fileIn from a toolbar button.
(
	local d = substituteString (getFilenamePath (getThisScriptFilename())) "\\" "/"
	python.Execute ("import sys\nif '" + d + "' not in sys.path: sys.path.insert(0, '" + d + "')\nimport assets_ui\nassets_ui.show()")
)
