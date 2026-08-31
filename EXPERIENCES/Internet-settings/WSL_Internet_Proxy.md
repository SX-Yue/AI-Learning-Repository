# WSL Proxy Setup Guide (Clash Verge)

This guide outlines the streamlined steps to connect a WSL (Windows Subsystem for Linux) instance to the internet using the Clash Verge proxy running on your Windows host.

## 1. Configure Clash Verge
1. Open Clash Verge on Windows.
2. Navigate to **Settings** (设置).
3. Ensure **Allow LAN** (局域网连接) is turned **ON**.
4. Check your **Port Settings** (端口设置). For this guide, we use `7897` (update the script below if yours is different).

## 2. Configure Windows Defender Firewall
Windows Firewall blocks traffic from the WSL virtual adapter by default. You need to create a rule to allow it using your exact adapter name.

1. Open **Windows PowerShell** as **Administrator**.
2. First, find the exact, un-truncated name of your WSL virtual network adapter by running:
   ```powershell
   Get-NetAdapter | Where-Object Name -like "*vEthernet*" | Select-Object -ExpandProperty Name
   ```
   *(This will output something like `vEthernet (WSL (Hyper-V firewall))`)*
3. Copy the exact name from the output.
4. Run the following command to allow inbound traffic, replacing `"YOUR_ADAPTER_NAME"` with the name you just copied:
   ```powershell
   New-NetFirewallRule -DisplayName "WSL Proxy Allow" -Direction Inbound -InterfaceAlias "YOUR_ADAPTER_NAME" -Action Allow
   ```
   *(Note: This creates a permanent rule, you only need to run this once).*

## 3. Add Proxy Script to WSL
Because the Windows host IP changes dynamically in WSL, hardcoding the IP won't work. This script automatically finds the correct gateway IP and applies it.

1. Open your WSL terminal.
2. Edit your shell configuration file (assuming bash):
   ```bash
   nano ~/.bashrc
   ```
3. Scroll to the very bottom and paste this code:
   ```bash
   # Set proxy to Windows Host (Clash Verge)
   function proxy_on() {
       # Extract the actual Windows host IP from the routing table
       export host_ip=$(ip route show | grep -i default | awk '{ print $3}')
       export port=7897 # Change this if your Clash Verge port is different
       
       export http_proxy="http://${host_ip}:${port}"
       export https_proxy="http://${host_ip}:${port}"
       export all_proxy="http://${host_ip}:${port}"
       
       echo "Proxy enabled for ${host_ip}:${port}"
   }

   function proxy_off() {
       unset http_proxy https_proxy all_proxy
       echo "Proxy disabled"
   }
   ```
4. Save the file (`Ctrl+O`, `Enter`) and exit nano (`Ctrl+X`).

## 4. Apply and Test
Whenever you start a new WSL session and need internet access, simply follow these steps:

1. Reload your configuration (only needed the first time after editing the file):
   ```bash
   source ~/.bashrc
   ```
2. Enable the proxy:
   ```bash
   proxy_on
   ```
3. Verify the connection:
   ```bash
   curl -I https://www.google.com
   ```
   *Success looks like a quick response starting with `HTTP/1.1 200` or `HTTP/2 200`.*
