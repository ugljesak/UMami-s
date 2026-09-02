@echo off
REM Usage:  make_model.bat mymodel.obj  [model.mif]
REM Needs Python 3 from python.org (tick "Add python.exe to PATH").
if "%~1"=="" (
  echo Usage: make_model.bat mymodel.obj [model.mif]
  exit /b 1
)
set OUT=%~2
if "%OUT%"=="" set OUT=model.mif
python mkmodel.py "%~1" "%OUT%"
