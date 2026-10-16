# swap_signals.ps1 — replace pyqtSignal/pyqtSlot with QtPy's Signal/Slot.

$root = "E:\Downloads\academy-system"

$skipDirs = @('\.git\', '\build\', '\dist\', '\dist_installer\',
              '\__pycache__\', '\.venv\', '\venv\', '\.pytest_cache\',
              '\.qodo\', '\.vscode\')

$files = Get-ChildItem -Path $root -Recurse -Filter *.py -File | Where-Object {
    $full = $_.FullName
    $skip = $false
    foreach ($dir in $skipDirs) {
        if ($full -like "*$dir*") { $skip = $true; break }
    }
    -not $skip
}

$changed = 0
foreach ($f in $files) {
    $content = Get-Content -LiteralPath $f.FullName -Raw
    if ($content -match 'pyqtSignal|pyqtSlot') {
        # Use \b word boundaries so we don't mangle longer identifiers.
        $new = $content `
            -replace '\bpyqtSignal\b', 'Signal' `
            -replace '\bpyqtSlot\b', 'Slot'
        Set-Content -LiteralPath $f.FullName -Value $new -NoNewline
        Write-Host "Modified: $($f.FullName)"
        $changed++
    }
}

Write-Host ""
Write-Host "Done. $changed file(s) modified."