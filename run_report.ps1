# Lance le rapport hebdomadaire depuis l'environnement virtuel
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$python = Join-Path $scriptDir ".venv\Scripts\python.exe"
$report = Join-Path $scriptDir "rapport_hebdomadaire.py"

if (Test-Path $python) {
    & $python $report
} else {
    Write-Error "Python venv introuvable : $python"
}
