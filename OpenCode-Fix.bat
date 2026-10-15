@echo off
title OpenCode Fix - Destravador e Reparador Unificado
chcp 65001 >nul
color 0A

where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo [!] Python nao encontrado no PATH.
    echo     Instale o Python 3.10+ em https://www.python.org/downloads/
    echo     e marque "Add python.exe to PATH" durante a instalacao.
    echo.
    pause
    exit /b 1
)

python "%~dp0fix_opencode.py"

if errorlevel 1 (
    echo.
    echo =================================================================
    echo  [!] Ocorreu um erro ou a operacao foi cancelada pelo usuario.
    echo  Esta janela continuara aberta para voce ler o historico acima.
    echo =================================================================
    pause
) else (
    exit
)
