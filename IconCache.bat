@echo off
:: Устанавливаем кодировку консоли в UTF-8 для поддержки кириллицы
chcp 65001 > nul

:: Этот скрипт сбрасывает кэш иконок в Windows

echo Закрытие Проводника Windows...
:: Принудительно завершает процесс explorer.exe.
taskkill /f /im explorer.exe > nul
timeout /t 2 /nobreak >nul

echo Очистка файлов кэша иконок...
:: Переход в директорию, где хранится основной файл кэша
cd /d %userprofile%\AppData\Local
:: Удаление файла IconCache.db.
if exist IconCache.db del /a IconCache.db

:: Переход в директорию, где хранятся дополнительные файлы кэша
cd /d %userprofile%\AppData\Local\Microsoft\Windows\Explorer
:: Удаление файлов кэша иконок.
del /f /q /a iconcache* > nul

echo Восстановление кэша завершено.

echo Запуск Проводника Windows...
:: Запускает explorer.exe заново.
start explorer.exe

echo Готово! Кэш иконок был сброшен.
pause