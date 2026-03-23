import serial
import re
import argparse
import sys

# Self-modification code template for ESC optimization
# Converts backslash (\) to ESC (27) in string literals
SELF_MOD_TEMPLATE = [
    "1 I={start_addr}; Q=0",
    "2 DO",
    "3 IF ?I=13 I=I+2; GOTO 7",
    "4 IF ?I=34 Q=Q:1",
    "5 IF Q AND ?I=92 THEN ?I=27",
    "7 I=I+1",
    "8 UNTIL I>=TOP",
    "9 END"
]

def process_line(line, strip_remarks):
    """
    Process a BASIC program line, optionally stripping REM remarks.
    """
    line = line.strip()  # Strip outer whitespace, but preserve internal
    if not line:
        return None
    
    # Match line number and optional single lowercase letter label
    match = re.match(r'^(\d+)([a-z]?)', line)
    if not match:
        return None
    
    num = match.group(1)
    label = match.group(2)
    rest = line[match.end():]  # Preserve original whitespace in rest
    
    if not strip_remarks:
        return num + label + rest
    
    # For stripping: split by ; (assuming no ; inside strings)
    # Stop at first REM statement
    parts = re.split(r';\s*', rest.lstrip())  # lstrip to remove leading spaces after label
    new_parts = []
    for part in parts:
        p = part.strip()
        if p.upper().startswith('REM'):
            break
        new_parts.append(part.strip())  # Strip individual parts for cleanliness
    
    new_rest = '; '.join(new_parts)
    
    full_line = num + label
    if new_rest:
        full_line += ' ' + new_rest  # Add space only if needed
    return full_line if full_line.strip() else None

MAX_LINE = 63

def validate_program(lines):
    """
    Validate BASIC program lines for common issues.
    Returns (is_valid, warnings, errors) where:
    - is_valid: True if no critical errors
    - warnings: list of warning messages
    - errors: list of error messages
    """
    warnings = []
    errors = []
    seen_line_numbers = {}  # line_number -> (file_line_num, full_line)
    prev_line_num = 0
    
    for file_line_num, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        
        # Extract line number
        match = re.match(r'^(\d+)([a-z]?)', line)
        if not match:
            continue
        
        line_num = int(match.group(1))
        label = match.group(2)
        
        # Check for duplicate line numbers
        if line_num in seen_line_numbers:
            prev_file_line, prev_full = seen_line_numbers[line_num]
            errors.append(
                f"Line {file_line_num}: Duplicate line number {line_num}\n"
                f"  First occurrence at file line {prev_file_line}: {prev_full[:60]}\n"
                f"  Duplicate at file line {file_line_num}: {line[:60]}"
            )
        else:
            seen_line_numbers[line_num] = (file_line_num, line)
        
        # Check for lines out of order
        if line_num < prev_line_num:
            warnings.append(
                f"Line {file_line_num}: Line number {line_num} comes after {prev_line_num} (out of order)"
            )
        
        # Check line length
        if len(line) > MAX_LINE:
            errors.append(
                f"Line {file_line_num}: Line {line_num} exceeds {MAX_LINE} chars ({len(line)}): {line[:60]}{'...' if len(line) > 60 else ''}"
            )
        
        prev_line_num = line_num
    
    is_valid = len(errors) == 0
    return is_valid, warnings, errors

def validate_no_lines_1_to_9(lines):
    """Check that lines 1-9 are not used in the program.
    
    Returns (is_free, conflict_line) where:
    - is_free: True if lines 1-9 are all free
    - conflict_line: The conflicting line number, or None if all free
    """
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        match = re.match(r'^(\d+)', line)
        if match:
            line_num = int(match.group(1))
            if 1 <= line_num <= 9:
                return False, line_num
    
    return True, None

def send_and_get_response(ser, cmd, is_line_entry=False, timeout=None):
    """
    Send a command character by character, verify echoes, send CR,
    verify LF then CR (as per board behavior), then collect output until '>' prompt.
    
    timeout: Optional timeout in seconds for waiting for prompt (uses serial port default if None)
    """
    output = b""
    
    # Save original timeout and set custom one if specified
    original_timeout = ser.timeout
    if timeout is not None:
        ser.timeout = timeout
    
    cmd_bytes = cmd.encode('ascii')
    
    # Send each byte and verify echo
    for b in cmd_bytes:
        ser.write(bytes([b]))
        echo = ser.read(1)
        if not echo:
            raise ValueError(f"Timeout on echo for {b}")
        if echo != bytes([b]):
            raise ValueError(f"Echo mismatch: sent {b}, got {echo}")
    
    # Send CR
    ser.write(b'\r')
    
    # Now collect output until we see the '>' prompt
    # The board sends output (if any) followed immediately by '>'
    while True:
        byte = ser.read(1)
        if not byte:
            raise ValueError(f"Timeout waiting for prompt (command was: {cmd})")
        
        if byte == b'>':
            # Found prompt, done
            break
        
        # Collect any output before the prompt
        output += byte
    
    # Restore original timeout
    if timeout is not None:
        ser.timeout = original_timeout
    
    # Decode output with ascii, ignoring errors
    output_str = output.decode('ascii', errors='ignore')
    
    # For line entry, expect no output
    if is_line_entry and output_str.strip():
        print("Warning: Unexpected output during line entry:", output_str, file=sys.stderr)
    
    return output_str

def get_program_start(ser):
    """Query TOP to get program start address after NEW.
    
    Returns the start address as an integer.
    """
    # Send NEW command
    print("NEW", file=sys.stderr)
    send_and_get_response(ser, "NEW", is_line_entry=False)
    
    # Query TOP
    output = send_and_get_response(ser, "PRINT TOP", is_line_entry=False)
    
    # Parse the number from output
    match = re.search(r'(\d+)', output)
    if not match:
        raise ValueError(f"Could not parse TOP address from: {output}")
    
    start_addr = int(match.group(1))
    print(f"TOP #{start_addr:X}", file=sys.stderr)
    return start_addr

def upload_self_mod_code(ser, start_addr):
    """Upload self-modification code (lines 1-9)."""
    print("ADD patch esc code", file=sys.stderr)
    for line_template in SELF_MOD_TEMPLATE:
        line = line_template.format(start_addr=start_addr)
        send_and_get_response(ser, line, is_line_entry=True)

def execute_and_cleanup_self_mod(ser):
    """Execute self-modification code and delete lines 1-9."""
    # Execute with 30 second timeout
    print("RUN patch", file=sys.stderr)
    send_and_get_response(ser, "RUN", timeout=30)
    
    # Delete lines 1-9
    print("DELETE patch", file=sys.stderr)
    for line_num in range(1, 10):
        send_and_get_response(ser, str(line_num), is_line_entry=True)

def main():
    parser = argparse.ArgumentParser(description="Utility for uploading/downloading BASIC programs to Acorn Atom via serial.")
    parser.add_argument('--port', required=True, help='Serial port (e.g., /dev/ttyUSB0)')
    parser.add_argument('--baud', type=int, default=9600, help='Baud rate (default: 9600)')
    parser.add_argument('--upload', help='File to upload (BASIC program)')
    parser.add_argument('--download', help='File to save downloaded program to')
    parser.add_argument('--strip', action='store_true', help='Strip REM remarks during upload')
    parser.add_argument('--optimize-esc', action='store_true', 
                       help='Optimize ESC sequences using self-modifying code (requires lines 1-9 to be free)')
    
    args = parser.parse_args()
    
    if not args.upload and not args.download:
        parser.error("Specify --upload or --download (or both)")
    
    ser = serial.Serial(args.port, args.baud, timeout=3, xonxoff=True)
    ser.reset_input_buffer()
    
    try:
        if args.upload:
            # Read and validate the file first
            with open(args.upload, 'r') as f:
                file_lines = f.readlines()
            
            is_valid, warnings, errors = validate_program(file_lines)
            
            # Print warnings
            for warning in warnings:
                print(f"WARNING: {warning}", file=sys.stderr)
            
            # Print errors and abort if any
            if errors:
                print("\nERROR: Program validation failed:", file=sys.stderr)
                for error in errors:
                    print(f"  {error}", file=sys.stderr)
                print("\nUpload aborted due to validation errors.", file=sys.stderr)
                sys.exit(1)
            
            if warnings:
                print(f"\nFound {len(warnings)} warning(s). Proceeding with upload...\n", file=sys.stderr)
            
            # Additional validation for --optimize-esc
            if args.optimize_esc:
                is_free, conflict_line = validate_no_lines_1_to_9(file_lines)
                if not is_free:
                    print(f"\nERROR: --optimize-esc requires lines 1-9 to be free", file=sys.stderr)
                    print(f"  Line {conflict_line} conflicts with self-modification code", file=sys.stderr)
                    print("  Please renumber your program to start at line 10 or higher", file=sys.stderr)
                    sys.exit(1)
            
            # Sync with board - send CR and wait for prompt, flushing any garbage
            try:
                send_and_get_response(ser, "", is_line_entry=False)
            except ValueError as e:
                print(f"Error: No prompt received - board may not be responding", file=sys.stderr)
                sys.exit(1)
            
            # Handle optimize-esc workflow
            if args.optimize_esc:
                # Get start address (NEW is called inside get_program_start)
                try:
                    start_addr = get_program_start(ser)
                except ValueError as e:
                    print(f"Error querying start address: {e}", file=sys.stderr)
                    sys.exit(1)
                
                # Upload self-modification code
                try:
                    upload_self_mod_code(ser, start_addr)
                except ValueError as e:
                    print(f"Error uploading self-modification code: {e}", file=sys.stderr)
                    sys.exit(1)
            else:
                # Clear memory with NEW - it's a command, not a line entry
                print("NEW", file=sys.stderr)
                try:
                    send_and_get_response(ser, "NEW", is_line_entry=False)
                except ValueError as e:
                    print(f"Error sending NEW command: {e}", file=sys.stderr)
                    sys.exit(1)
            
            # Upload the user program
            print("UPLOAD program", file=sys.stderr)
            for line_num, file_line in enumerate(file_lines, 1):
                processed = process_line(file_line, args.strip)
                if processed:
                    try:
                        send_and_get_response(ser, processed, is_line_entry=True)
                    except ValueError as e:
                        print(f"Error on line {line_num}: {e}", file=sys.stderr)
                        sys.exit(1)
            
            # Execute and cleanup if optimize-esc
            if args.optimize_esc:
                try:
                    execute_and_cleanup_self_mod(ser)
                except ValueError as e:
                    print(f"Error during ESC optimization: {e}", file=sys.stderr)
                    print("Board may be in inconsistent state. Reset and try again.", file=sys.stderr)
                    sys.exit(1)
        
        if args.download:
            print("DOWNLOAD program", file=sys.stderr)
            listing = send_and_get_response(ser, "LIST")
            # Normalize line endings to single \n, remove extra newlines
            listing = re.sub(r'[\r\n]+', '\n', listing).strip()
            with open(args.download, 'w') as f:
                f.write(listing + '\n')  # Ensure trailing newline
            print(f"Saved to {args.download}", file=sys.stderr)
    
    finally:
        ser.close()

if __name__ == "__main__":
    main()
