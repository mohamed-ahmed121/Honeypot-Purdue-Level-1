@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
set "PY=%ROOT%.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

if "%~1"=="" goto usage

if /I "%~1"=="read" goto read
if /I "%~1"=="blower" goto blower
if /I "%~1"=="heater" goto blower
if /I "%~1"=="pump" goto pump

echo [!] Unknown command: %~1
goto usage

:read
if "%~3"=="" goto usage
"%PY%" "%ROOT%control_panel.py" "read(%~2, %~3)"
goto end

:blower
if "%~3"=="" goto usage
"%PY%" "%ROOT%control_panel.py" "blower(%~2, %~3)"
goto end

:pump
if "%~4"=="" goto usage
"%PY%" "%ROOT%control_panel.py" "pump(%~2 %~3, %~4)"
goto end

:usage
echo Usage:
echo   tank read ^<pressure^|temperature^|all^> ^<modbus^|s7^|iec61850^>
echo   tank blower ^<on^|off^> ^<modbus^|s7^|iec61850^>
echo   tank pump ^<inlet^|outlet^> ^<on^|off^> ^<modbus^|s7^|iec61850^>
exit /b 1

:end
endlocal
