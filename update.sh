#!/bin/bash
# update.sh — Pull latest code and restart services
# Usage: sudo bash /home/pi/jk_bms/update.sh

set -e
REPO_BASE="https://raw.githubusercontent.com/puene/jk-bms/main"
INSTALL_DIR="/home/pi/jk_bms"
PI_USER="pi"

[[ $EUID -ne 0 ]] && echo "Run with sudo" && exit 1

echo "Updating JK BMS..."
FILES=(app.py jk_registers.py jk_reader.py jk_config.py jk_db.py jk_html.py jk_ble.py mqtt_publisher.py requirements.txt)
for f in "${FILES[@]}"; do
    echo -n "  $f ... "
    curl -fsSL "$REPO_BASE/$f" -o "$INSTALL_DIR/$f" && echo "OK" || echo "FAILED"
done
# Update this script too, so the next run knows about new files. Download to a
# temp file and swap it in: overwriting a running bash script in place is unsafe.
echo -n "  update.sh ... "
if curl -fsSL "$REPO_BASE/update.sh" -o "$INSTALL_DIR/update.sh.new"; then
    mv -f "$INSTALL_DIR/update.sh.new" "$INSTALL_DIR/update.sh" && echo "OK"
else
    rm -f "$INSTALL_DIR/update.sh.new"; echo "FAILED"
fi
# Note: mqtt_config.yml and comm_config.json are NOT updated (per-site settings)

chown -R "$PI_USER:$PI_USER" "$INSTALL_DIR"
/home/pi/jk_bms/.venv/bin/pip install --quiet -r "$INSTALL_DIR/requirements.txt"
systemctl restart jk_bms jk_mqtt
echo ""
echo "Done. Dashboard: http://$(hostname -I | awk '{print $1}'):5000"
