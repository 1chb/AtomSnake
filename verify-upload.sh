#!/bin/bash
# Verify program upload by comparing LIST output with source

set -e

DEVICE="${1:-/dev/ttyUSB0}"
BAUD="${2:-9600}"
PROGRAM="${3:-Snake.atom}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}6502 Board Program Verification${NC}"
echo "Device: $DEVICE"
echo "Baud: $BAUD"
echo "Program: $PROGRAM"
echo

# Check if device exists
if [ ! -e "$DEVICE" ]; then
    echo -e "${RED}Error: Device $DEVICE not found${NC}"
    exit 1
fi

# Configure serial port
stty -F "$DEVICE" "$BAUD" cs8 -cstopb -parenb raw -echo

# Send LIST command and capture output
echo -e "${GREEN}Sending LIST command...${NC}"
echo "LIST" > "$DEVICE"

# Wait a moment for the listing to start
sleep 0.5

echo -e "${GREEN}Capturing program listing...${NC}"
echo "(Press Ctrl+C after listing completes)"
echo

# Capture output to file
OUTPUT_FILE="/tmp/board-listing.txt"
cat "$DEVICE" | tee "$OUTPUT_FILE"
