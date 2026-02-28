#!/bin/bash
# Upload Snake.atom to 6502 board via USB-to-serial adapter

set -e

DEVICE="${1:-/dev/ttyUSB0}"
BAUD="${2:-9600}"
PROGRAM="${3:-Snake.atom}"
LINE_DELAY="${4:-0.05}"  # 50ms delay between lines

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}6502 Board Program Upload Utility${NC}"
echo "Device: $DEVICE"
echo "Baud: $BAUD"
echo "Program: $PROGRAM"
echo "Line delay: ${LINE_DELAY}s"
echo

# Check if device exists
if [ ! -e "$DEVICE" ]; then
    echo -e "${RED}Error: Device $DEVICE not found${NC}"
    echo "Available serial devices:"
    ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || echo "  None found"
    exit 1
fi

# Check if program file exists
if [ ! -f "$PROGRAM" ]; then
    echo -e "${RED}Error: Program file $PROGRAM not found${NC}"
    exit 1
fi

# Configure serial port
echo -e "${GREEN}Configuring serial port...${NC}"
stty -F "$DEVICE" "$BAUD" cs8 -cstopb -parenb raw -echo

# Send NEW command to clear existing program
echo -e "${GREEN}Clearing existing program (NEW)...${NC}"
echo "NEW" > "$DEVICE"
sleep 1

# Upload program line by line
echo -e "${GREEN}Uploading program ($(wc -l < "$PROGRAM") lines)...${NC}"
line_count=0
total_lines=$(wc -l < "$PROGRAM")

while IFS= read -r line; do
    ((line_count++))
    echo -ne "\rLine $line_count/$total_lines"
    echo "$line" > "$DEVICE"
    sleep "$LINE_DELAY"
done < "$PROGRAM"

echo
echo -e "${GREEN}Upload complete!${NC}"
echo
echo "To verify the upload:"
echo "  1. Run: ./verify-upload.sh $DEVICE $BAUD"
echo
echo "To reconnect your VT100:"
echo "  1. Disconnect USB cable"
echo "  2. Reconnect VT100 terminal"
echo "  3. Type RUN to start the program"
