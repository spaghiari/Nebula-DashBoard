@echo off
setlocal
echo.
echo  +==========================================+
echo  ^|   Nouveau workspace -- Claude            ^|
echo  +==========================================+
echo.
set /p NOM="Nom du workspace (ex: proxmox, python-ml) : "
set /p DESC="Description courte : "
set /p OUTILS="Outils principaux : "

set ROOT=%~dp0..
set BASE=%ROOT%\workspaces\%NOM%
mkdir "%BASE%" 2>nul
mkdir "%BASE%\notes" 2>nul

(
echo # Workspace -- %NOM%
echo.
echo ## Contexte
echo %DESC%
echo.
echo ## Outils
echo %OUTILS%
echo.
echo ## Taches frequentes
echo - ^(a completer^)
echo.
echo ## Conventions
echo - Repondre en francais
echo - Code complet et fonctionnel
) > "%BASE%\CLAUDE.md"

(
echo @echo off
echo echo.
echo echo  +======================================+
echo echo  ^^^|   Claude Code -- %NOM%
echo echo  +======================================+
echo echo.
echo cd /d "%%~dp0..\workspaces\%NOM%"
echo claude
) > "%ROOT%\scripts\launch-%NOM%.bat"

echo.
echo  OK Workspace "%NOM%" cree : %BASE%
echo  OK Script de lancement : scripts\launch-%NOM%.bat
echo  -^> Complete le CLAUDE.md pour que Claude comprenne le contexte
echo.
set /p OUVRIR="Ouvrir le CLAUDE.md maintenant ? (O/N) : "
if /i "%OUVRIR%"=="O" notepad "%BASE%\CLAUDE.md"
endlocal
