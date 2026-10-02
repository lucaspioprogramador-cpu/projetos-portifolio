@echo off
cd /d %~dp0
setlocal enabledelayedexpansion
set PYTHONPATH=%CD%
python -m streamlit run ui/main_app.py --server.port=8502
pause
