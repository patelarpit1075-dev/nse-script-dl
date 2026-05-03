#!/bin/bash
# One-time setup for NSE Smart Money Agent

echo "Installing dependencies..."
pip3 install playwright pandas requests numpy --break-system-packages -q 2>/dev/null || pip3 install playwright pandas requests numpy -q

echo "Installing Chromium browser..."
python3 -m playwright install chromium

echo "Downloading scripts..."
mkdir -p ~/nse-smart-money
cd ~/nse-smart-money

curl -s "https://raw.githubusercontent.com/patelarpit1075-dev/nse-script-dl/main/nse_daily.py" -o nse_daily.py
curl -s "https://raw.githubusercontent.com/patelarpit1075-dev/nse-script-dl/main/nse_agent.py" -o nse_agent.py
curl -s "https://raw.githubusercontent.com/patelarpit1075-dev/nse-script-dl/main/run_agent.sh" -o run_agent.sh
chmod +x run_agent.sh

echo ""
echo "✅ Setup complete!"
echo ""
echo "Edit credentials:"
echo "  nano ~/nse-smart-money/run_agent.sh"
echo ""
echo "Test run:"
echo "  bash ~/nse-smart-money/run_agent.sh"
echo ""
echo "Schedule 7am Mon-Fri (run once):"
cat << 'PLIST' > ~/Library/LaunchAgents/com.nse.smartmoney.plist
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.nse.smartmoney</string>
<key>ProgramArguments</key><array><string>/bin/bash</string><string>/Users/arpitpatel/nse-smart-money/run_agent.sh</string></array>
<key>StartCalendarInterval</key><array>
<dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict>
<dict><key>Weekday</key><integer>2</integer><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict>
<dict><key>Weekday</key><integer>3</integer><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict>
<dict><key>Weekday</key><integer>4</integer><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict>
<dict><key>Weekday</key><integer>5</integer><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict>
</array>
<key>StandardOutPath</key><string>/Users/arpitpatel/nse-smart-money/nse.log</string>
<key>StandardErrorPath</key><string>/Users/arpitpatel/nse-smart-money/nse.log</string>
</dict></plist>
PLIST
launchctl unload ~/Library/LaunchAgents/com.nse.smartmoney.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.nse.smartmoney.plist
echo "  Scheduled at 7am Mon-Fri!"
