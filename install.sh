#!/bin/bash
# install.sh — JK BMS one-line installer
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/puene/jk-bms/main/install.sh | sudo bash
#
# Or if using a web server:
#   curl -fsSL http://your-server/jk_bms/install.sh | sudo bash
#
# What this does:
#   1. Install system packages (python3-venv, libgpiod2)
#   2. Create /home/pi/jk_bms/ and download all project files
#   3. Create Python venv and install pip packages
#   4. Install and enable systemd services (jk_bms + jk_mqtt)
#   5. Start both services immediately
#
# Requirements: Raspberry Pi OS, user 'pi', Python 3.9+

set -e

# ── Config ─────────────────────────────────────────────────────────────────
REPO_BASE="https://raw.githubusercontent.com/puene/jk-bms/main"
# If using a web server instead:
# REPO_BASE="http://your-server/jk_bms"

INSTALL_DIR="/home/pi/jk_bms"
VENV_DIR="$INSTALL_DIR/.venv"
SERVICE_DIR="/etc/systemd/system"
PI_USER="pi"

# ── Colour helpers ─────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; exit 1; }
step()  { echo -e "\n${YELLOW}=== $* ===${NC}"; }

# ── Must run as root ────────────────────────────────────────────────────────
[[ $EUID -ne 0 ]] && error "Run with sudo: curl ... | sudo bash"

step "JK BMS Installer"
echo "  Install dir : $INSTALL_DIR"
echo "  Python venv : $VENV_DIR"
echo "  Source      : $REPO_BASE"
echo ""

# ── 1. System packages ──────────────────────────────────────────────────────
step "1/5  System packages"
apt-get update -qq
apt-get install -y -qq python3-venv python3-pip libgpiod2
info "System packages ready"

# ── 2. Download project files ───────────────────────────────────────────────
step "2/5  Download project files"
mkdir -p "$INSTALL_DIR"
chown "$PI_USER:$PI_USER" "$INSTALL_DIR"

# Python source files
FILES=(
    "app.py"
    "jk_registers.py"
    "jk_reader.py"
    "jk_config.py"
    "jk_db.py"
    "jk_html.py"
    "mqtt_publisher.py"
    "requirements.txt"
)

for f in "${FILES[@]}"; do
    echo -n "  Downloading $f ... "
    if curl -fsSL "$REPO_BASE/$f" -o "$INSTALL_DIR/$f"; then
        echo "OK"
    else
        error "Failed to download $f from $REPO_BASE/$f"
    fi
done

# mqtt_config.yml — only download if it doesn't already exist
# (avoid overwriting user's broker credentials on re-install)
if [[ ! -f "$INSTALL_DIR/mqtt_config.yml" ]]; then
    echo -n "  Downloading mqtt_config.yml (template) ... "
    curl -fsSL "$REPO_BASE/mqtt_config.yml" -o "$INSTALL_DIR/mqtt_config.yml"
    echo "OK"
    warn "Edit $INSTALL_DIR/mqtt_config.yml and add your broker credentials!"
else
    info "mqtt_config.yml already exists — keeping existing (broker credentials preserved)"
fi

chown -R "$PI_USER:$PI_USER" "$INSTALL_DIR"
info "All files downloaded"

# ── 3. Python venv + packages ───────────────────────────────────────────────
step "3/5  Python virtual environment"
if [[ ! -d "$VENV_DIR" ]]; then
    sudo -u "$PI_USER" python3 -m venv "$VENV_DIR"
    info "venv created"
else
    info "venv already exists — updating packages"
fi

sudo -u "$PI_USER" "$VENV_DIR/bin/pip" install --quiet --upgrade pip
sudo -u "$PI_USER" "$VENV_DIR/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"
info "Python packages installed"

# ── 4. systemd services ─────────────────────────────────────────────────────
step "4/5  Install systemd services"

cat > "$SERVICE_DIR/jk_bms.service" << 'EOF'
[Unit]
Description=JK BMS Web Dashboard
After=network.target
Wants=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/jk_bms
ExecStart=/home/pi/jk_bms/.venv/bin/python3 /home/pi/jk_bms/app.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=jk_bms

[Install]
WantedBy=multi-user.target
EOF

cat > "$SERVICE_DIR/jk_mqtt.service" << 'EOF'
[Unit]
Description=JK BMS MQTT Publisher
After=network.target jk_bms.service
Requires=jk_bms.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/jk_bms
ExecStart=/home/pi/jk_bms/.venv/bin/python3 /home/pi/jk_bms/mqtt_publisher.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=jk_mqtt

[Install]
WantedBy=multi-user.target
EOF

chmod 644 "$SERVICE_DIR/jk_bms.service" "$SERVICE_DIR/jk_mqtt.service"
systemctl daemon-reload
systemctl enable jk_bms.service jk_mqtt.service
info "Services installed and enabled on boot"

# ── 5. Start services ───────────────────────────────────────────────────────
step "5/5  Start services"
systemctl restart jk_bms.service
echo -n "  Waiting for dashboard to start"
for i in {1..10}; do
    sleep 1
    echo -n "."
    if curl -sf http://127.0.0.1:5000/api/status > /dev/null 2>&1; then
        echo " ready!"
        break
    fi
done
echo ""
systemctl restart jk_mqtt.service
info "Both services started"

# ── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║       JK BMS Install Complete!           ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo "  Dashboard : http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "  Logs:"
echo "    sudo journalctl -u jk_bms  -f"
echo "    sudo journalctl -u jk_mqtt -f"
echo ""
echo "  Control:"
echo "    sudo systemctl status  jk_bms jk_mqtt"
echo "    sudo systemctl restart jk_bms jk_mqtt"
echo "    sudo systemctl stop    jk_bms jk_mqtt"
echo ""

if [[ -f "$INSTALL_DIR/mqtt_config.yml" ]]; then
    if grep -q "your-broker.example.com" "$INSTALL_DIR/mqtt_config.yml" 2>/dev/null; then
        echo -e "${YELLOW}  ⚠️  Don't forget to edit mqtt_config.yml with your broker credentials!${NC}"
        echo "    nano $INSTALL_DIR/mqtt_config.yml"
        echo "    sudo systemctl restart jk_mqtt"
        echo ""
    fi
fi
