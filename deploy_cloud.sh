#!/usr/bin/env bash
# One-shot deployment of the trading bot onto an Oracle Ampere VM.
# Usage (on the VM, or via ssh): bash deploy_cloud.sh
# Assumes: git, python3-venv available; config.json already uploaded.
set -e

REPO_URL="https://github.com/lordboody2018/trading-scanner.git"
APP_DIR="$HOME/trading-scanner"

echo "==> apt packages"
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip git

echo "==> code"
if [ ! -d "$APP_DIR" ]; then
    git clone "$REPO_URL" "$APP_DIR"
else
    cd "$APP_DIR" && git pull --rebase || true
fi
cd "$APP_DIR"

echo "==> python venv"
python3 -m venv venv
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r requirements.txt -q

if [ ! -f config.json ]; then
    echo "ERROR: config.json missing. Upload it before running."
    exit 1
fi

echo "==> systemd service"
sudo tee /etc/systemd/system/tradingbot.service >/dev/null <<EOF
[Unit]
Description=Telegram Trading Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/python run_bot.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable tradingbot
sudo systemctl restart tradingbot
sleep 5
systemctl status tradingbot --no-pager | head -12 || true
echo ""
echo "Live: journalctl -u tradingbot -f"
