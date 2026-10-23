$ErrorActionPreference = 'Stop'
$source = (Resolve-Path -LiteralPath 'C:\Users\Thinkpad\Desktop\NeuroPulse').Path
$stage = Join-Path $source '.transfer-staging'
$target = 'C:\Users\Thinkpad\Desktop\neuropulse_transfer'
$targetExpected = [IO.Path]::GetFullPath($target)
if ($source -ne 'C:\Users\Thinkpad\Desktop\NeuroPulse') { throw "Unexpected source: $source" }
if ($targetExpected -ne 'C:\Users\Thinkpad\Desktop\neuropulse_transfer' -or -not (Test-Path -LiteralPath $targetExpected -PathType Container)) { throw 'Transfer target missing or path mismatch.' }
if (-not (Test-Path -LiteralPath (Join-Path $targetExpected '.git') -PathType Container)) { throw 'Expected existing transfer .git directory; refusing to proceed.' }
if (Test-Path -LiteralPath $stage) {
  $resolvedStage = (Resolve-Path -LiteralPath $stage).Path
  if ($resolvedStage -ne (Join-Path $source '.transfer-staging')) { throw "Unexpected stage path: $resolvedStage" }
  Remove-Item -LiteralPath $resolvedStage -Recurse -Force
}
New-Item -ItemType Directory -Path $stage | Out-Null
$excludeDirs = @('.git','.venv','venv','node_modules','dist','.pytest_cache','.setup-tmp','.test-tmp','.transfer-staging','__pycache__','.pio','.vscode','neuropulse-backup-1pcz48i_','neuropulse-backup-b2qe5rdo','tmp7vq9ww23','tmpdroiwzbx','tmpty8ezmhv','_avg_','electron-user-data')
$excludeFiles = @('*.db','*.sqlite','*.sqlite3','*.h5','*.hdf5','*.pyc','*.pyo','.env.desktop')
$roboArgs = @($source,$stage,'/MIR','/R:1','/W:1','/NFL','/NDL','/NP') + @('/XD') + $excludeDirs + @('/XF') + $excludeFiles
& robocopy @roboArgs
if ($LASTEXITCODE -ge 8) { throw "Robocopy source-to-stage failed: $LASTEXITCODE" }
New-Item -ItemType Directory -Force -Path (Join-Path $stage 'data\sessions'),(Join-Path $stage 'exports') | Out-Null
New-Item -ItemType File -Force -Path (Join-Path $stage 'data\sessions\.gitkeep'),(Join-Path $stage 'exports\.gitkeep') | Out-Null
$readme = @'
# NeuroPulse transfer package

Updated source snapshot for another developer/AI agent or a GitHub repository. It includes app/backend/frontend source, firmware, migrations, tests, scripts, project specifications, Idea Hub context, and safe synthetic reference files. It is not an installer or a clinically validated product.

## Start here
1. Read `AGENTS.md` and `Idea Hub/NEUROPULSE_ANTIGRAVITY_MVP_MASTER_SPEC.md`.
2. Read `Idea Hub/context_dev/HANDOFF.md`, `drift-away.md`, and `implementation plan 0.1.md`.
3. Read `README.md`, then check `git status` and the diff before changing code.
4. Follow the Windows setup instructions in `README.md`. Dependencies and a clean-machine installer are not bundled.

## Excluded from this package
Python/Node environments, build outputs, caches, machine-specific settings, local databases, raw recordings, exports and backup archives are omitted. Synthetic fixtures under `data/simulated` are retained and must stay labeled synthetic.

The existing `.git` directory in the Desktop transfer folder is preserved. The SHA-256 manifest covers transferred project files but excludes Git internals and the manifest itself.

## GitHub and safety
Before publishing, inspect the full diff and Git history for secrets, personal information, licensing, and files that should not be public. No remote is configured by this transfer operation. Do not publish participant data, raw recordings, databases, or backups.

NeuroPulse remains a local research prototype. NPI and alert bands are experimental and are not clinical diagnoses or validated risk estimates. Physical MVP/HIL, launch reliability, hardware throughput, expert review, clinical validation, and commercial/regulatory readiness remain open; see the handoff and implementation plan.
'@
Set-Content -LiteralPath (Join-Path $stage 'TRANSFER_README.md') -Value $readme -Encoding UTF8
$manifestPath = Join-Path $stage 'TRANSFER_MANIFEST_SHA256.txt'
$manifestLines = Get-ChildItem -LiteralPath $stage -Recurse -File | Where-Object { $_.FullName -ne $manifestPath } | Sort-Object { $_.FullName.Substring($stage.Length + 1) } | ForEach-Object {
  $relative = $_.FullName.Substring($stage.Length + 1).Replace('\','/')
  $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
  "$hash  $relative"
}
Set-Content -LiteralPath $manifestPath -Value $manifestLines -Encoding UTF8
# Replace only the transfer snapshot's non-Git contents, preserving its existing .git history.
Get-ChildItem -LiteralPath $targetExpected -Force | Where-Object { $_.Name -ne '.git' } | ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }
$copyArgs = @($stage,$targetExpected,'/E','/R:1','/W:1','/NFL','/NDL','/NP')
& robocopy @copyArgs
if ($LASTEXITCODE -ge 8) { throw "Robocopy stage-to-transfer failed: $LASTEXITCODE" }
$expected = Get-Content -LiteralPath $manifestPath
$failures = @()
foreach ($line in $expected) {
  if ($line -match '^([0-9a-f]{64})  (.+)$') {
    $file = Join-Path $targetExpected ($Matches[2] -replace '/', '\')
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { $failures += "Missing: $($Matches[2])"; continue }
    $actual = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $Matches[1]) { $failures += "Mismatch: $($Matches[2])" }
  } else { $failures += "Malformed manifest line: $line" }
}
if ($failures.Count) { throw ($failures -join "`n") }
Write-Host "Transfer updated and verified: $($expected.Count) files; .git preserved." -ForegroundColor Green
