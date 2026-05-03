#!/bin/bash
# NSE Smart Money Agent Runner
# Run this every morning for fully automated report

export NSE_EMAIL_FROM="your_gmail@gmail.com"
export NSE_EMAIL_TO="your_receive_email@gmail.com"
export NSE_EMAIL_PASSWORD="your_16char_app_password"

cd ~/nse-smart-money
python3 nse_agent.py
