#!/bin/bash
# Automatically create desktop launcher for qr_scanner.py in current folder

APP_DIR="$(pwd)"
APP_FILE="$APP_DIR/qr_scanner.py"
ICON_FILE="$APP_DIR/icon.jpeg"
DESKTOP_NAME="QR Scanner.desktop"
DESKTOP_FILE="$HOME/Desktop/$DESKTOP_NAME"

# Check requirements
if [ ! -f "$APP_FILE" ]; then
    echo "❌ No qr_scanner.py found in $APP_DIR"
    exit 1
fi

if [ ! -f "$ICON_FILE" ]; then
    echo "⚠️ No icon.jpeg found — using default system icon."
    ICON_FILE="application-x-executable"
fi

PYTHON_BIN=$(command -v python3 || command -v python)
if [ -z "$PYTHON_BIN" ]; then
    echo "❌ Python not found."
    exit 1
fi

# Create Desktop entry
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=QR Scanner
Comment=QR code scanner that copies results to clipboard
Exec=$PYTHON_BIN "$APP_FILE"
Icon=$ICON_FILE
Terminal=true
Categories=Utility;
EOF

# Make it executable
chmod +x "$DESKTOP_FILE"

# Mark as trusted so GNOME allows launching
gio set "$DESKTOP_FILE" metadata::trusted true 2>/dev/null || true

echo "✅ Desktop launcher created at: $DESKTOP_FILE"
echo "📦 Executes: $APP_FILE"
