# Script PowerShell para criar atalho do Marq Lab na Area de Trabalho
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir

$wsh = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "Marq Lab.lnk"
$targetBat = Join-Path $projectDir "iniciar_sistema.bat"
$iconFile = Join-Path $projectDir "app\static\marqlab.ico"

$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetBat
$shortcut.WorkingDirectory = $projectDir
$shortcut.Description = "Marq Lab - Prospeccao Ativa B2B e Vendas"
$shortcut.WindowStyle = 7 # Minimizada na barra de tarefas

if (Test-Path $iconFile) {
    $shortcut.IconLocation = "$iconFile,0"
} else {
    $shortcut.IconLocation = "shell32.dll,14"
}

$shortcut.Save()
Write-Host "[OK] Atalho criado com sucesso em: $shortcutPath" -ForegroundColor Green
