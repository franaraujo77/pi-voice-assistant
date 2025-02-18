#!/bin/bash

# Exit on error
set -e

# Function to log messages
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Function to check if command succeeded
check_status() {
    if [ $? -eq 0 ]; then
        log "✓ Success: $1"
    else
        log "✗ Error: $1"
        exit 1
    fi
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log "Please run as root (sudo ./install.sh)"
    exit 1
fi

# Get username for service files
ACTUAL_USER=$(logname)
USER_HOME="/home/$ACTUAL_USER"

log "Starting installation with user: $ACTUAL_USER"

# Update system
log "Updating system packages..."
apt-get update
#apt-get upgrade -y
check_status "System update"

# Install prerequisites
log "Installing required packages..."
apt-get install --no-install-recommends -y git python3-venv libopenblas-dev python3-spidev python3-gpiozero
check_status "Package installation"

# Wyoming Satellite setup
log "Clonning Wyoming Satellite..."
cd ~
git clone https://github.com/rhasspy/wyoming-satellite.git
cd wyoming-satellite/

log "Setting up ReSpeaker..."
sudo bash etc/install-respeaker-drivers.sh
check_status "ReSpeaker setup"

log "Setting up Wyoming Satellite..."
python3 -m venv .venv
source .venv/bin/activate
pip3 install --upgrade pip wheel setuptools
pip3 install -f 'https://synesthesiam.github.io/prebuilt-apps/' \
    -e '.[all]'
.venv/bin/pip3 install 'pysilero-vad==1.0.0'
deactivate
check_status "Wyoming Satellite installation"

# OpenWakeword setup
log "Setting up OpenWakeword..."
cd ~
git clone https://github.com/rhasspy/wyoming-openwakeword.git
cd wyoming-openwakeword
script/setup
#check_status "OpenWakeword installation"

# LED service setup
log "Setting up LED service..."
cd ~/wyoming-satellite/examples
python3 -m venv --system-site-packages .venv
.venv/bin/pip3 install --upgrade pip wheel setuptools
.venv/bin/pip3 install 'wyoming==1.5.2'
.venv/bin/pip3 install 'pixel-ring'
#check_status "LED service setup"
EOF

# Create service files
log "Creating service files..."

# OpenWakeword Service
cat > /etc/systemd/system/wyoming-openwakeword.service << EOL
[Unit]
Description=Wyoming openWakeWord

[Service]
Type=simple
ExecStart=${USER_HOME}/wyoming-openwakeword/script/run \
    --preload-model 'hey_jarvis' \
    --uri 'tcp://0.0.0.0:10400'
WorkingDirectory=${USER_HOME}/wyoming-openwakeword
Restart=always
RestartSec=1

[Install]
WantedBy=default.target
EOL

# Wyoming Satellite Service
cat > /etc/systemd/system/wyoming-satellite.service << EOL
[Unit]
Description=Wyoming Satellite
Wants=network-online.target
After=network-online.target
Requires=wyoming-openwakeword.service

[Service]
Type=simple
ExecStart=${USER_HOME}/wyoming-satellite/script/run \
  --debug \
  --vad \
  --name '${HOSTNAME}' \
  --uri 'tcp://0.0.0.0:10700' \
  --mic-auto-gain 5 \
  --mic-noise-suppression 2 \
  --wake-word-name 'hey_jarvis' \
  --awake-wav awake.wav \
  --done-wav done.wav \
  --timer-finished-wav timer_finished.wav \
  --mic-command 'arecord -D plughw:CARD=seeed2micvoicec,DEV=0 -r 16000 -c 1 -f S16_LE -t raw' \
  --snd-command 'aplay -D plughw:CARD=seeed2micvoicec,DEV=0 -r 22050 -c 1 -f S16_LE -t raw'
WorkingDirectory=${USER_HOME}/wyoming-satellite
Restart=always
RestartSec=1

[Install]
WantedBy=default.target
EOL

# LED Service
cat > /etc/systemd/system/2mic_leds.service << EOL
[Unit]
Description=2Mic LEDs

[Service]
Type=simple
ExecStart=${USER_HOME}/wyoming-satellite/examples/.venv/bin/python3 2mic_service.py \
    --uri 'tcp://127.0.0.1:10500'
WorkingDirectory=${USER_HOME}/wyoming-satellite/examples
Restart=always
RestartSec=1

[Install]
WantedBy=default.target
EOL

# Set proper permissions
chown root:root /etc/systemd/system/*.service
chmod 644 /etc/systemd/system/*.service
check_status "Service file creation"

# Enable and start services
log "Enabling and starting services..."
systemctl daemon-reload
systemctl enable wyoming-satellite.service wyoming-openwakeword.service 2mic_leds.service
systemctl start wyoming-satellite.service wyoming-openwakeword.service 2mic_leds.service
check_status "Service activation"

log "Installation complete! Please reboot your system."
log "After reboot, you can check service status with:"
log "systemctl status wyoming-satellite"
log "systemctl status wyoming-openwakeword"
log "systemctl status 2mic_leds"
