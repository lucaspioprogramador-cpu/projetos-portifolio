@echo off
REM Script para rodar L-Trade-AI Bot
REM Adiciona o diretório ao PYTHONPATH

setlocal enabledelayedexpansion
cd /d %~dp0

echo.
echo ========================================
echo  L-TRADE-AI BOT - INICIANDO...
echo ========================================
echo.

REM Definir PYTHONPATH
set PYTHONPATH=%CD%;%PYTHONPATH%

REM Rodar o teste primeiro
echo [1/2] Testando ambiente...
python test_app.py --logger.level=error
if %errorlevel% neq 0 (
    echo.
    echo ? Erro ao rodar teste!
    pause
    exit /b 1
)

echo.
echo [2/2] Iniciando bot principal...
echo.

REM Rodar bot principal
python -m streamlit run ui/main_app.py --client.showErrorDetails=true

pause
