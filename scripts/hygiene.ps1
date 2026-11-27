# Pinned repo-hygiene check of this checkout against origin/main (#1950); see tools/hygiene/README.md.
# Usage: scripts/hygiene.ps1 [check] [--base <ref>] [--json]   exit 0 = no new findings, 1 = findings, 2 = error
$entry = Join-Path (Split-Path -Parent $PSScriptRoot) 'tools/hygiene/hygiene.py'
$rest = @($args)
if ($rest.Count -eq 0 -or "$($rest[0])".StartsWith('-')) { $rest = @('check') + $rest }
& py -3 $entry @rest
exit $LASTEXITCODE
