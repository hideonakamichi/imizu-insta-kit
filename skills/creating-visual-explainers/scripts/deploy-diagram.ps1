# 図解 HTML を Surge 公開する。Surge はフォルダ単位（HTML ファイル直指定は ENOTDIR）。
param(
    [Parameter(Mandatory = $true)]
    [string]$HtmlFile,
    [string]$Slug
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Error "Node.js がありません。references/node-install-guide.md を案内し、ローカルで終える。"
    exit 1
}

if (-not (Test-Path -LiteralPath $HtmlFile -PathType Leaf)) {
    Write-Error "HTML が見つかりません: $HtmlFile"
    exit 1
}

if ([string]::IsNullOrWhiteSpace($Slug)) {
    $Slug = Get-Date -Format "yyMMddHHmm"
}

$Domain = "diagram-$Slug.surge.sh"
$TempDir = Join-Path $env:TEMP "surge-diagram-$Slug"
New-Item -ItemType Directory -Force -Path $TempDir | Out-Null
Copy-Item -LiteralPath $HtmlFile -Destination (Join-Path $TempDir "index.html") -Force
Set-Content -Path (Join-Path $TempDir "robots.txt") -Value "User-agent: *`nDisallow: /"

Write-Host "公開中..."
npx --yes surge $TempDir --domain $Domain
if ($LASTEXITCODE -ne 0) {
    Write-Host "Surge 失敗。ローカル HTML だけで完了する。"
    exit $LASTEXITCODE
}

Write-Host "URL: https://$Domain"
Write-Host "削除するとき: npx surge teardown $Domain"
