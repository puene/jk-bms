#!/bin/bash
# update.sh — Pull latest code and restart services
# Usage: sudo bash /home/pi/jk_bms/update.sh

set -e
REPO_BASE="https://raw.githubusercontent.com/puene/jk-bms/main"
INSTALL_DIR="/home/pi/jk_bms"
PI_USER="pi"

[[ $EUID -ne 0 ]] && echo "Run with sudo" && exit 1

echo "Updating JK BMS..."
FILES=(app.py jk_registers.py jk_reader.py jk_config.py jk_db.py jk_html.py mqtt_publisher.py requirements.txt)
for f in "${FILES[@]}"; do
    echo -n "  $f ... "
    curl -fsSL "$REPO_BASE/$f" -o "$INSTALL_DIR/$f" && echo "OK" || echo "FAILED"
done
# Note: mqtt_config.yml is NOT updated to preserve broker credentials

chown -R "$PI_USER:$PI_USER" "$INSTALL_DIR"
/home/pi/jk_bms/.venv/bin/pip install --quiet -r "$INSTALL_DIR/requirements.txt"
systemctl restart jk_bms jk_mqtt
echo ""
echo "Done. Dashboard: http://$(hostname -I | awk '{print $1}'):5000"
