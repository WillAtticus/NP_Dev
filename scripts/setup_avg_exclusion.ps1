# NeuroPulse AVG Whitelist Setup
# Adds the NeuroPulse project folder to AVG exclusions via registry.
# Run this ONCE as Administrator after restoring quarantined files from AVG.

$ProjectPath = "C:\Users\Thinkpad\Desktop\NeuroPulse"

Write-Host "Adding NeuroPulse to AVG exclusions..." -ForegroundColor Cyan

# AVG stores exclusions in registry
$avgKey = "HKLM:\SOFTWARE\AVG\Antivirus\Exclusions\Paths"
$avgKeyAlt = "HKCU:\SOFTWARE\AVG\Antivirus\Exclusions\Paths"

function Add-AVGExclusion {
    param($RegPath, $FolderPath)
    try {
        if (-not (Test-Path $RegPath)) {
            New-Item -Path $RegPath -Force | Out-Null
        }
        $existing = Get-ItemProperty -Path $RegPath -ErrorAction SilentlyContinue
        $name = ($FolderPath -replace '[\\:]', '_')
        Set-ItemProperty -Path $RegPath -Name $name -Value $FolderPath -ErrorAction SilentlyContinue
        Write-Host "  Added to $RegPath" -ForegroundColor Green
    } catch {
        Write-Host "  Could not write to $RegPath (may need Admin)" -ForegroundColor Yellow
    }
}

Add-AVGExclusion $avgKey $ProjectPath
Add-AVGExclusion $avgKeyAlt $ProjectPath

Write-Host ""
Write-Host "IMPORTANT: Also manually add the exclusion in AVG UI:" -ForegroundColor Yellow
Write-Host "  AVG -> Menu -> Settings -> General -> Exceptions -> Add Exception" -ForegroundColor White
Write-Host "  Path: $ProjectPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "Then restore quarantined files:" -ForegroundColor Yellow
Write-Host "  AVG -> Menu -> Virus Chest -> right-click run_dev.ps1 -> Restore and add to exclusions" -ForegroundColor White
Write-Host ""
Read-Host "Press Enter to exit"
