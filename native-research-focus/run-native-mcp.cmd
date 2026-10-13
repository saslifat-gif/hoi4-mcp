@echo off
set "PYTHONPATH=%~dp0;%~dp0..;%PYTHONPATH%"
"%~dp0..\.venv\Scripts\python.exe" "%~dp0native_mcp_server.py" %*
