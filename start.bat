@echo off
echo ===================================================
echo   Starting GuiGazer Dashboard
echo ===================================================
echo.
echo Launching FastAPI server...
echo Go to http://localhost:8001 in your browser!
echo.

uvicorn main:app --host 0.0.0.0 --port 8001 --reload
