# Laboratório 01 — Windows 11
# Gerado automaticamente em 2026-10-19 13:58 a partir de catalogo/ e dos pedidos aprovados.
# Não edite à mão: altere o catálogo ou o status do pedido e deixe o GitHub Actions gerar de novo.
# Rodar como Administrador na máquina-modelo, antes de capturar a imagem no FOG.

$ErrorActionPreference = 'Continue'
$log = "$env:ProgramData\ifpr-labs\instalacao-$(Get-Date -Format yyyyMMdd-HHmm).log"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
$falhas = @()

$winget = @(
    @{ Id = 'TheDocumentFoundation.LibreOffice'; Nome = 'LibreOffice' }
    @{ Id = 'EclipseAdoptium.Temurin.21.JDK'; Nome = 'Java JDK 21 (Temurin)' }
    @{ Id = 'Apache.NetBeans'; Nome = 'Apache NetBeans' }
    @{ Id = 'Microsoft.VisualStudioCode'; Nome = 'Visual Studio Code' }
    @{ Id = 'Git.Git'; Nome = 'Git' }
    @{ Id = 'Python.Python.3.13'; Nome = 'Python 3.13' }
)
foreach ($p in $winget) {
    Write-Host "==> $($p.Nome)" -ForegroundColor Cyan
    winget install --id $p.Id --exact --silent --scope machine `
        --accept-package-agreements --accept-source-agreements --disable-interactivity *>> $log
    # 0 = instalado; -1978335189 = já estava instalado e atualizado
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne -1978335189) { $falhas += $p.Nome }
}

if ($falhas) { Write-Host "Falharam: $($falhas -join ', ') — veja $log" -ForegroundColor Red; exit 1 }
Write-Host "Concluído. Log: $log" -ForegroundColor Green
