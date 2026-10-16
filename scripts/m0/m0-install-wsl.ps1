$ErrorActionPreference = 'Continue'
$log = 'E:\workspace_work\GuardLM\m0-wsl-install.log'
Set-Content -Path $log -Value "=== started $(Get-Date) ===" -Encoding UTF8

"--- 1. bcdedit hypervisorlaunchtype (before) ---" | Add-Content $log -Encoding UTF8
bcdedit /enum '{current}' | Select-String 'hypervisorlaunchtype' | Add-Content $log -Encoding UTF8

"--- 2. set hypervisorlaunchtype auto ---" | Add-Content $log -Encoding UTF8
bcdedit /set hypervisorlaunchtype auto 2>&1 | Add-Content $log -Encoding UTF8

"--- 3. enable WSL optional features (dism, norestart) ---" | Add-Content $log -Encoding UTF8
dism /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart | Select-Object -Last 5 | Add-Content $log -Encoding UTF8
dism /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart | Select-Object -Last 5 | Add-Content $log -Encoding UTF8

"--- 4. wsl --install -d Ubuntu --no-launch ---" | Add-Content $log -Encoding UTF8
wsl --install -d Ubuntu --no-launch 2>&1 | Add-Content $log -Encoding UTF8

"--- 5. wsl version after install ---" | Add-Content $log -Encoding UTF8
wsl --version 2>&1 | Add-Content $log -Encoding UTF8

"=== finished $(Get-Date) ===" | Add-Content $log -Encoding UTF8
