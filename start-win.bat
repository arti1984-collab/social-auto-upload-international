@echo off
TITLE social-auto-upload CLI
ECHO ==================================================
ECHO  social-auto-upload - CLI entry point
ECHO ==================================================
ECHO.
ECHO This checkout has no web UI. It ships only the `sau` CLI for
ECHO YouTube, Facebook, Facebook Page, Instagram and TikTok.
ECHO.
ECHO One-time setup:
ECHO   uv venv
ECHO   .venv\Scripts\Activate.ps1
ECHO   uv pip install -e .
ECHO   patchright install chromium
ECHO   Copy-Item conf.example.py conf.py
ECHO.
ECHO Opening a shell with the CLI help...
ECHO.
cmd /k "sau --help"
