@echo off
setlocal
set PROJECT=UMami-s

echo Updating ROM MIF...
quartus_cdb --update_mif "%PROJECT%"
if errorlevel 1 (
    echo ERROR: Failed to update MIF.
    pause
    exit /b 1
)

echo Generating new SOF...
quartus_asm "%PROJECT%"
if errorlevel 1 (
    echo ERROR: Failed to generate SOF.
    pause
    exit /b 1
)

echo.
echo Done! New SOF generated.
echo Open Quartus Programmer and program the new SOF.
pause
