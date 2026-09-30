# STORM PS4 PKG SENDER - Automated Production Build and Release Pipeline (STORM ALL PROJECTS FORMAT)
$ErrorActionPreference = "Stop"

$baseDir = $PSScriptRoot
if (-not $baseDir) { $baseDir = "E:\STORM PS4 PKG SENDER" }
$appProjDir = $baseDir
$installerProjDir = Join-Path $baseDir "installer\StormInstaller"
$assemblingDir = Join-Path $baseDir "Assembling"
$filesDir = Join-Path $baseDir "Files"
$outputDir = Join-Path $baseDir "installer\Output"

if (-not (Test-Path $assemblingDir)) { New-Item -ItemType Directory -Path $assemblingDir | Out-Null }
if (-not (Test-Path $filesDir)) { New-Item -ItemType Directory -Path $filesDir | Out-Null }
if (-not (Test-Path $outputDir)) { New-Item -ItemType Directory -Path $outputDir | Out-Null }

$appVersion = "1.4.0"
$appDisplayName = "STORM PS4 PKG SENDER"
$appExeName = "STORM PS4 PKG SENDER.exe"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   $appDisplayName $appVersion - STORM ALL PROJECTS FORMAT" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$setupExeName = "STORM_PS4_PKG_SENDER_${appVersion}_Setup.exe"
$setupExePath = Join-Path $filesDir $setupExeName
$outputSetupExePath = Join-Path $outputDir $setupExeName
$portableZipPath = Join-Path $outputDir "STORM_PS4_PKG_SENDER_${appVersion}_win-x64.zip"
$bundleZipPath = Join-Path $outputDir "STORM_PS4_PKG_SENDER_${appVersion}_Setup_Bundle.zip"

# Step 0: Terminate running instances
Write-Host "[0/6] Closing running instances to release file locks..." -ForegroundColor Yellow
cmd.exe /c "taskkill /F /IM ""$appExeName"" /T >nul 2>&1"
cmd.exe /c "taskkill /F /IM StormInstaller.exe /T >nul 2>&1"
Get-Process "STORM PS4 PKG SENDER", "stormps4pkgsender", "StormInstaller", "XamlCompiler", "VBCSCompiler", "msbuild" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

# Step 1: Clean build outputs
Write-Host "[1/6] Cleaning build directories..." -ForegroundColor Yellow
if (Test-Path "$installerProjDir\bin") { Remove-Item "$installerProjDir\bin" -Recurse -Force -ErrorAction SilentlyContinue }
if (Test-Path "$installerProjDir\obj") { Remove-Item "$installerProjDir\obj" -Recurse -Force -ErrorAction SilentlyContinue }
if (Test-Path $assemblingDir) { Remove-Item $assemblingDir -Recurse -Force -ErrorAction SilentlyContinue }
if (Test-Path $portableZipPath) { Remove-Item $portableZipPath -Force -ErrorAction SilentlyContinue }
if (Test-Path $bundleZipPath) { Remove-Item $bundleZipPath -Force -ErrorAction SilentlyContinue }
if (Test-Path $outputSetupExePath) { Remove-Item $outputSetupExePath -Force -ErrorAction SilentlyContinue }

# Step 2: Assemble Application payload
Write-Host "[2/6] Preparing Application payload in Assembling folder..." -ForegroundColor Yellow
if (-not (Test-Path $assemblingDir)) { New-Item -ItemType Directory -Path $assemblingDir | Out-Null }

$distExe = Join-Path $baseDir "dist\$appExeName"
if (-not (Test-Path $distExe)) {
    throw "Error: $distExe not found! Please build the Python application first."
}

Copy-Item $distExe (Join-Path $assemblingDir $appExeName) -Force
Copy-Item (Join-Path $baseDir "AppIcon.ico") (Join-Path $assemblingDir "AppIcon.ico") -Force
Copy-Item (Join-Path $baseDir "AppIcon.ico") (Join-Path $assemblingDir "app.ico") -Force

# Step 3: Digital Signature with STORM Authenticode Certificate + RFC 3161 Timestamp
Write-Host "[3/6] Applying digital signature (STORM Authenticode SHA-256 + RFC 3161)..." -ForegroundColor Yellow
$signtool = (Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin\*\x64\signtool.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1).FullName
$tsUrl = "http://timestamp.digicert.com"

$store = New-Object System.Security.Cryptography.X509Certificates.X509Store([System.Security.Cryptography.X509Certificates.StoreName]::My, [System.Security.Cryptography.X509Certificates.StoreLocation]::CurrentUser)
$store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadOnly)

$cert = $store.Certificates | Where-Object { $_.HasPrivateKey -and $_.Subject -like "*STORM TEAM*" } | Select-Object -First 1
if (-not $cert) {
    $cert = $store.Certificates | Where-Object { $_.HasPrivateKey -and $_.Subject -like "*CN=STORM Software*" } | Select-Object -First 1
}
if (-not $cert) {
    $cert = $store.Certificates | Where-Object { $_.HasPrivateKey -and ($_.Subject -like "*STORM SOFT*" -or $_.Subject -like "*STORM*") } | Select-Object -First 1
}
if (-not $cert) {
    $cert = $store.Certificates | Where-Object { $_.HasPrivateKey } | Select-Object -First 1
}
$store.Close()

$certThumb = $cert.Thumbprint
Write-Host "  -> Master Certificate: $($cert.Subject) [$certThumb]" -ForegroundColor Green

# Export CER and copy to root, Files, installer, output
$cerRoot = Join-Path $baseDir "STORM_Certificate.cer"
$cerFiles = Join-Path $filesDir "STORM_Certificate.cer"
$cerInstaller = Join-Path $baseDir "installer\STORM_Certificate.cer"
$cerOutput = Join-Path $outputDir "STORM_Certificate.cer"

[System.IO.File]::WriteAllBytes($cerRoot, $cert.Export([System.Security.Cryptography.X509Certificates.X509ContentType]::Cert))
Copy-Item $cerRoot $cerFiles -Force
Copy-Item $cerRoot $cerInstaller -Force
Copy-Item $cerRoot $cerOutput -Force
Copy-Item $cerRoot (Join-Path $assemblingDir "STORM_Certificate.cer") -Force

# Sign app binary
& $signtool sign /fd SHA256 /tr $tsUrl /td SHA256 /d "$appDisplayName $appVersion" /du "https://github.com/ReiKatari/STORM_PS4_PKG_SENDER" /sha1 $certThumb (Join-Path $assemblingDir $appExeName)

# Package portable zip
Write-Host "  -> Packaging Portable ZIP..." -ForegroundColor Yellow
if (Test-Path $portableZipPath) { Remove-Item $portableZipPath -Force -ErrorAction SilentlyContinue }
$sevenZip = "C:\Program Files\7-Zip\7z.exe"
if (-not (Test-Path $sevenZip)) { $sevenZip = "E:\STORM SWITCH BOX\tools\7z.exe" }

if (Test-Path $sevenZip) {
    & $sevenZip a -tzip -mx=7 -mmt=on $portableZipPath "$assemblingDir\*"
} else {
    Compress-Archive -Path "$assemblingDir\*" -DestinationPath $portableZipPath -Force
}
Copy-Item $portableZipPath $filesDir -Force
Copy-Item $portableZipPath (Join-Path $outputDir "STORM_PS4_PKG_SENDER_${appVersion}.zip") -Force
Copy-Item $portableZipPath (Join-Path $filesDir "STORM_PS4_PKG_SENDER_${appVersion}.zip") -Force

# Step 4: Build Custom StormInstaller
Write-Host "[4/6] Building and Signing StormInstaller (Cyber Dark UI)..." -ForegroundColor Yellow
dotnet publish "$installerProjDir\StormInstaller.csproj" -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -p:EnableCompressionInSingleFile=true

$publishedInstaller = "$installerProjDir\bin\Release\net8.0-windows\win-x64\publish\StormInstaller.exe"
if (-not (Test-Path $publishedInstaller)) {
    throw "Error: StormInstaller.exe was not created in $publishedInstaller!"
}

# Copy to Files and Output
Copy-Item $publishedInstaller $setupExePath -Force
Copy-Item $publishedInstaller $outputSetupExePath -Force

# Sign Installers
& $signtool sign /fd SHA256 /tr $tsUrl /td SHA256 /d "$appDisplayName $appVersion" /du "https://github.com/ReiKatari/STORM_PS4_PKG_SENDER" /sha1 $certThumb $setupExePath
& $signtool sign /fd SHA256 /tr $tsUrl /td SHA256 /d "$appDisplayName $appVersion" /du "https://github.com/ReiKatari/STORM_PS4_PKG_SENDER" /sha1 $certThumb $outputSetupExePath

# Install certificate locally into TrustedPublisher for seamless local execution
try {
    $pubStore = New-Object System.Security.Cryptography.X509Certificates.X509Store([System.Security.Cryptography.X509Certificates.StoreName]::TrustedPublisher, [System.Security.Cryptography.X509Certificates.StoreLocation]::CurrentUser)
    $pubStore.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
    $pubStore.Add($cert)
    $pubStore.Close()
} catch { }

# Step 5: Packaging Smart App Control Setup Bundle
Write-Host "[5/6] Packaging Setup Bundle..." -ForegroundColor Yellow
if (Test-Path $bundleZipPath) { Remove-Item $bundleZipPath -Force -ErrorAction SilentlyContinue }
if (Test-Path $sevenZip) {
    $bundleItems = @($outputSetupExePath, $cerOutput)
    & $sevenZip a -tzip -mx=7 -mmt=on $bundleZipPath @bundleItems
    Copy-Item $bundleZipPath $filesDir -Force
}

# Step 6: Unblock output files
Write-Host "[6/6] Unblocking files..." -ForegroundColor Yellow
Get-ChildItem -Path $outputDir, $filesDir -Recurse -Include *.exe, *.dll, *.bat, *.cmd, *.ps1, *.cer, *.zip -ErrorAction SilentlyContinue | ForEach-Object {
    Unblock-File -Path $_.FullName -ErrorAction SilentlyContinue
}

Write-Host "============================================================" -ForegroundColor Green
Write-Host "BUILD AND PACKAGING COMPLETED ACCORDING TO STORM STANDARDS!" -ForegroundColor Green
Write-Host "1. Installer (Files):     $setupExePath" -ForegroundColor Green
Write-Host "2. Installer (Output):    $outputSetupExePath" -ForegroundColor Green
Write-Host "3. Setup Bundle:          $bundleZipPath" -ForegroundColor Green
Write-Host "4. Portable Archive:      $portableZipPath" -ForegroundColor Green
Write-Host "5. Certificate:           $cerOutput" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
