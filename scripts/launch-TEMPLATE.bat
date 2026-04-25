@echo off
:: Template de script de lancement pour un workspace.
:: Duplique ce fichier en launch-<nom>.bat et remplace <NOM> et le chemin ci-dessous.
echo.
echo  +======================================+
echo  ^|   Claude Code -- ^<NOM^>              ^|
echo  +======================================+
echo.
cd /d "%~dp0..\workspaces\<NOM>"
claude
