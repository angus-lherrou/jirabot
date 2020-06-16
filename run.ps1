# jirabot v0.6
# Angus L'Herrou
# piraka@brandeis.edu
# github.com/angus-lherrou/jirabot
# Windows PowerShell run script

. .\env.ps1;
Invoke-Expression "$Env:JIRABOT_VENV_PATH\Scripts\activate.ps1";
python wsgi_win.py;
