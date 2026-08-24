#!/usr/bin/env bash
# Oracle VM setup for the Telegram Trading Bot.
# Run ON the VM: bash oracle_setup.sh
set -e

REPO_URL="https://github.com/lordboody2018/trading-scanner.git"
APP_DIR="$HOME/trading-scanner"
SERVICE_NAME="tradingbot"

echo "==> installing system packages..."
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip git

echo "==> cloning/updating code..."
if [ ! -d "$APP_DIR" ]; then
    git clone "$REPO_URL" "$APP_DIR"
else
    cd "$APP_DIR" && git pull --rebase || true
fi
cd "$APP_DIR"

echo "==> python environment..."
python3 -m venv venv
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r requirements.txt -q

if [ ! -f config.json ]; then
    echo "ERROR: config.json not found in $APP_DIR"
    echo "Upload it first (scp) then re-run this script."
    exit 1
fi

echo "==> systemd service..."
sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null <<EOF
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

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}
sudo systemctl restart ${SERVICE_NAME}
sleep 5
systemctl status ${SERVICE_NAME} --no-pager -l | head -12
echo ""
echo "Done. Live logs: journalctl -u ${SERVICE_NAME} -f"
