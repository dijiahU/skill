# Install FORGE git hooks into the current repo's .git/hooks directory.
# Idempotent: backs up non-FORGE hooks to <name>.bak before installing.

$ErrorActionPreference = "Stop"

$repoRoot = (git rev-parse --show-toplevel) 2>$null
if (-not $repoRoot) {
    Write-Error "install-forge-hooks: not inside a git repository."
    exit 1
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceDir = Join-Path $scriptDir "..\ci\hooks"
if (-not (Test-Path $sourceDir)) {
    Write-Error "install-forge-hooks: source hooks not found at $sourceDir"
    exit 1
}

$targetDir = Join-Path $repoRoot ".git\hooks"
if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir | Out-Null
}

$installed = @()
$backedUp = @()
$skipped = @()

foreach ($hook in @("commit-msg", "pre-commit", "pre-push")) {
    $src = Join-Path $sourceDir $hook
    $tgt = Join-Path $targetDir $hook
    if (-not (Test-Path $src)) { continue }

    if (Test-Path $tgt) {
        if ((Get-FileHash $src).Hash -eq (Get-FileHash $tgt).Hash) {
            $skipped += $hook
            continue
        }
        $isForge = (Get-Content $tgt -TotalCount 3) -match '^# FORGE'
        if ($isForge) {
            Copy-Item $src $tgt -Force
            $installed += "$hook (updated)"
            continue
        }
        Copy-Item $tgt "$tgt.bak" -Force
        $backedUp += "$hook -> $hook.bak"
    }

    Copy-Item $src $tgt -Force
    $installed += $hook
}

Write-Host ("Installed: " + ($(if ($installed) { $installed -join ', ' } else { 'none' })))
if ($backedUp) { Write-Host ("Backed up: " + ($backedUp -join ', ')) }
if ($skipped)  { Write-Host ("Already current: " + ($skipped -join ', ')) }
