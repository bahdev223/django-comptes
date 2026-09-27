$ErrorActionPreference = "Stop"

$root = Join-Path $PSScriptRoot "..\comptes\assets\providers\ml"
New-Item -ItemType Directory -Force -Path (Join-Path $root "banks"), (Join-Path $root "mobile-money") | Out-Null

function New-LogoFallback($Path, $Name, $Primary, $Secondary) {
    $safe = [System.Security.SecurityElement]::Escape($Name)
    $svg = @"
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 160" role="img" aria-labelledby="title desc">
  <title id="title">$safe</title>
  <desc id="desc">Logo fallback nominatif pour $safe, à remplacer par le logo officiel si un brand kit public est fourni.</desc>
  <rect width="420" height="160" rx="18" fill="$Primary"/>
  <rect x="18" y="18" width="384" height="124" rx="14" fill="$Secondary" opacity="0.12"/>
  <text x="210" y="90" text-anchor="middle" dominant-baseline="middle" font-family="Arial, Helvetica, sans-serif" font-size="34" font-weight="700" fill="#ffffff">$safe</text>
</svg>
"@
    Set-Content -LiteralPath $Path -Value $svg -Encoding UTF8
}

function New-LogoFromUrl($Path, $Url, $Title) {
    $tmp = [System.IO.Path]::GetTempFileName()
    try {
        Invoke-WebRequest -Uri $Url -OutFile $tmp -TimeoutSec 35 -Headers @{"User-Agent" = "Mozilla/5.0"} | Out-Null
        $bytes = [System.IO.File]::ReadAllBytes($tmp)
        $ext = ([System.IO.Path]::GetExtension(($Url -split "\?")[0])).ToLowerInvariant()
        $mime = switch ($ext) {
            ".svg" { "image/svg+xml" }
            ".jpg" { "image/jpeg" }
            ".jpeg" { "image/jpeg" }
            ".webp" { "image/webp" }
            default { "image/png" }
        }
        if ($mime -eq "image/svg+xml") {
            Copy-Item -LiteralPath $tmp -Destination $Path -Force
        } else {
            $b64 = [Convert]::ToBase64String($bytes)
            $safe = [System.Security.SecurityElement]::Escape($Title)
            $safeUrl = [System.Security.SecurityElement]::Escape($Url)
            $svg = @"
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 160" role="img" aria-labelledby="title desc">
  <title id="title">$safe</title>
  <desc id="desc">Logo récupéré depuis $safeUrl.</desc>
  <rect width="420" height="160" rx="18" fill="#ffffff"/>
  <image href="data:$mime;base64,$b64" x="24" y="24" width="372" height="112" preserveAspectRatio="xMidYMid meet"/>
</svg>
"@
            Set-Content -LiteralPath $Path -Value $svg -Encoding UTF8
        }
    } finally {
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    }
}

function New-LogoFromDataSvg($Path, $PageUrl) {
    $r = Invoke-WebRequest -Uri $PageUrl -UseBasicParsing -TimeoutSec 35 -Headers @{"User-Agent" = "Mozilla/5.0"}
    $src = ($r.Images | Where-Object { $_.src -like "data:image/svg+xml*" } | Select-Object -First 1).src
    if (-not $src) {
        throw "No data SVG found at $PageUrl"
    }
    if ($src -like "data:image/svg+xml,%*") {
        $payload = [System.Uri]::UnescapeDataString($src.Substring("data:image/svg+xml,".Length))
    } elseif ($src -like "data:image/svg+xml;base64,*") {
        $payload = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($src.Substring("data:image/svg+xml;base64,".Length)))
    } else {
        throw "Unsupported data SVG format"
    }
    if ($payload -notmatch "<(path|image|text|rect|circle|polygon|g)\b") {
        throw "Data SVG at $PageUrl does not contain visible logo content"
    }
    Set-Content -LiteralPath $Path -Value $payload -Encoding UTF8
}

New-LogoFallback (Join-Path $root "banks\bdm.svg") "BDM" "#006f3c" "#ffffff"
New-LogoFallback (Join-Path $root "banks\bim.svg") "BIM" "#0b4ea2" "#ffffff"
New-LogoFromUrl (Join-Path $root "banks\bnda.svg") "https://www.bnda-mali.com/sites/default/files/Logo-bnda-2.png" "BNDA"
try {
    New-LogoFromDataSvg (Join-Path $root "banks\bcs.svg") "https://bcssa-mali.com/"
} catch {
    New-LogoFallback (Join-Path $root "banks\bcs.svg") "BCS" "#008c45" "#ffffff"
}
New-LogoFromUrl (Join-Path $root "banks\boa.svg") "https://bank-of-africa.net/wp-content/uploads/2025/01/Logo_PP_Positif-small.png" "Bank of Africa"
New-LogoFromUrl (Join-Path $root "banks\afg-bank.svg") "https://afgbankmali.com/template/images/logo.png" "AFG Bank Mali"
New-LogoFromUrl (Join-Path $root "banks\banque-atlantique.svg") "https://www.banqueatlantique.net/wp-content/uploads/2020/03/Banque-Atlantique-Logo.png" "Banque Atlantique"
New-LogoFromUrl (Join-Path $root "banks\bms.svg") "https://bms-sa.ml/wp-content/uploads/2021/04/logo_web.png" "BMS"
New-LogoFromUrl (Join-Path $root "banks\bci.svg") "https://bci-banque.com/wp-content/uploads/2025/02/bci-banque-mali-logo2025.png" "BCI Mali"
New-LogoFallback (Join-Path $root "banks\bsic.svg") "BSIC Mali" "#005aa9" "#ffffff"
New-LogoFromUrl (Join-Path $root "banks\ecobank.svg") "https://www.ecobank.com/img/eco/eco-logo-svg.svg" "Ecobank"
New-LogoFallback (Join-Path $root "banks\coris-bank.svg") "Coris Bank" "#f9b000" "#003b71"
New-LogoFallback (Join-Path $root "banks\uba.svg") "UBA" "#d71920" "#ffffff"
New-LogoFallback (Join-Path $root "banks\orabank.svg") "Orabank" "#00a3ad" "#ffffff"

New-LogoFromUrl (Join-Path $root "mobile-money\orange-money.svg") "https://www.orangemali.com/2/menu_resources/uploads/logo_1.png" "Orange Money"
New-LogoFallback (Join-Path $root "mobile-money\moov-money.svg") "Moov Money" "#005bbb" "#ffffff"
New-LogoFromUrl (Join-Path $root "mobile-money\sama-money.svg") "https://www.sama.money/img/logov2.jpg" "Sama Money"
New-LogoFromUrl (Join-Path $root "mobile-money\wave.svg") "https://www.wave.com/img/nav-logo.png" "Wave"
New-LogoFallback (Join-Path $root "mobile-money\coris-money.svg") "Coris Money" "#f9b000" "#003b71"
New-LogoFallback (Join-Path $root "mobile-money\wizall.svg") "Wizall" "#ed1c24" "#ffffff"
New-LogoFromUrl (Join-Path $root "mobile-money\zelia.svg") "https://zeliamali.com/wp-content/uploads/2018/11/Groupe-35@2x.png" "Zelia"
New-LogoFallback (Join-Path $root "mobile-money\t-lia.svg") "T-LIA" "#6d28d9" "#ffffff"
New-LogoFallback (Join-Path $root "mobile-money\optima.svg") "Optima" "#0f766e" "#ffffff"

Get-ChildItem -Recurse -File $root | Select-Object FullName, Length
