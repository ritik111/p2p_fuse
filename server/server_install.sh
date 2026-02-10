sudo apt install python3
sudo ufw allow 4444/udp
nohup python3 s.py > server_log.log 2>&1 &
echo "Packages Installed!!!"
echo "Server is running in background"
