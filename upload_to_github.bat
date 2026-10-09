@echo off
title Upload MarsClient to GitHub
color 0a
echo ========================================================
echo   Uploading MarsClient files to GitHub (RomanchikPro228)
echo ========================================================
echo.
cd /d "C:\Users\Master\.lunarclient\LunarClient\MarsWeb"
"C:\Program Files\Git\cmd\git.exe" push -u origin main
echo.
echo ========================================================
echo   Done!
echo ========================================================
pause
