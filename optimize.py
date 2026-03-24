#!/usr/bin/env python3
"""Optimizer for Acorn Atom BASIC PROD output.

Reads a .atom file (PROD preprocessed) and applies size optimizations:
1. Strip cpp warnings from output
2. Remove trailing semicolons
3. Collapse multiple semicolons (;; -> ;)
4. Convert hex literals to decimal: #38 -> 56, #410 -> 1040
5. Evaluate constant parenthesized expressions: (-1-2) -> -3
6. Remove spaces after line numbers (and label suffixes)
7. Remove spaces after abbreviated commands (I. F. G. P. N. etc.)
8. Remove spaces after semicolons, closing parens, and string literals
9. Merge adjacent string literals ("A" "B" -> "AB")
10. Remove spaces after digits (when next char is non-digit)
11. Remove spaces after THEN (which is empty in PROD)
12. Merge consecutive short lines (respecting 63-char limit), except:
    - Lines that are GOTO/GOSUB targets (by line number)
    - Don't append to a line whose last statement is IF (THEN gates rest of line)
13. Remove empty lines
14. Truncate REM comments if line exceeds 63 characters:
    - Truncates comment text to fit within limit
    - Keeps at least "REM" if there's space
    - Removes entire REM statement if less than 3 chars available

Usage: python3 optimize.py < input.atom > output.atom
"""

import re
import sys


MAX_LINE = 63


def find_jump_targets(lines):
    """Find all line numbers that are GOTO or GOSUB targets."""
    targets = set()
    for line in lines:
        # PROD mode: G. 1280 or G.1280 or GOS. 1140 or GOS.1140
        for m in re.finditer(r'(?:G\.|GOS\.)\s*(\d+)', line):
            targets.add(m.group(1))
        # Non-PROD mode: GOTO 1280 or GOSUB 1140
        for m in re.finditer(r'\b(?:GOTO|GOSUB)\s+(\d+)', line):
            targets.add(m.group(1))
    return targets


def parse_line(line):
    """Parse a line into (line_number, label, body).
    
    Line format: <number>[<label>] [<body>]
    Examples:
        '10 W=40'        -> ('10', '', 'W=40')
        '1000p'          -> ('1000', 'p', '')
        '1000pGOS.h'     -> ('1000', 'p', 'GOS.h')
        '1100q I.B=0 R.' -> ('1100', 'q', ' I.B=0 R.')
        '60'             -> ('60', '', '')
    """
    m = re.match(r'^(\d+)([a-z]?)(.*)', line)
    if not m:
        return None, None, None
    num, label, body = m.group(1), m.group(2), m.group(3)
    return num, label, body


def contains_if(line):
    """Check if the line contains any IF statement (outside strings).
    
    In Atom BASIC, IF condition is false skips the ENTIRE rest of the line.
    So we can never safely append to a line that contains any IF — the
    appended code would be gated by that IF's condition.
    """
    in_string = False
    for i, c in enumerate(line):
        if c == '"':
            in_string = not in_string
        elif not in_string and c == 'I':
            # Check for "I." (PROD mode) or "IF" (non-PROD mode)
            if i + 1 < len(line) and line[i + 1] == '.':
                # I. pattern - exclude DIM etc: only match if not preceded by uppercase alpha
                if i == 0 or not line[i - 1].isupper():
                    return True
            elif i + 1 < len(line) and line[i + 1] == 'F':
                # IF pattern - check it's actually the keyword, not part of another word
                # Must not be preceded by uppercase letter (to avoid matching "DIFF" etc)
                # Lowercase letters and digits are OK before IF (e.g., "5200gIF" after label merge)
                # Must not be followed by letter (to avoid matching "IFX" etc)
                prev_ok = (i == 0 or not line[i - 1].isupper())
                next_ok = (i + 2 >= len(line) or not line[i + 2].isalpha())
                if prev_ok and next_ok:
                    return True
    return False


def convert_hex_to_decimal(line):
    """Convert hex literals (#XX) to decimal equivalents.

    '#38' -> '56', '#410' -> '1040', '#7FFF' -> '32767'
    Skips content inside strings. This enables the space-after-digit
    rule to be simplified (no more A-F hex digit concerns).
    """
    result = []
    i = 0
    in_string = False
    while i < len(line):
        c = line[i]
        if c == '"':
            in_string = not in_string
            result.append(c)
            i += 1
            continue
        if in_string:
            result.append(c)
            i += 1
            continue
        if c == '#' and i + 1 < len(line) and line[i + 1] in '0123456789ABCDEFabcdef':
            # Collect hex digits
            j = i + 1
            while j < len(line) and line[j] in '0123456789ABCDEFabcdef':
                j += 1
            hex_str = line[i + 1:j]
            result.append(str(int(hex_str, 16)))
            i = j
            continue
        result.append(c)
        i += 1
    return ''.join(result)


def remove_trailing_semicolons(line):
    """Remove trailing semicolons (and whitespace after them)."""
    return re.sub(r';\s*$', '', line)


def collapse_multiple_semicolons(line):
    """Replace multiple consecutive semicolons with a single semicolon."""
    return re.sub(r';{2,}', ';', line)


def remove_unnecessary_spaces(line):
    """Remove unnecessary spaces in PROD BASIC code.
    
    - Space after label: '1100q I.' -> '1100qI.'
    - Space after abbreviated commands: 'I. ', 'G. ', 'GOS. ', 'F. ', 'P. ',
      'N. ', 'R. ', 'T. ', 'S. ', 'U. ', 'E. '
    - Spaces around OR: ' OR ' -> 'OR'
    - But NOT inside strings
    """
    result = []
    i = 0
    in_string = False
    
    while i < len(line):
        c = line[i]
        
        if c == '"':
            in_string = not in_string
            result.append(c)
            i += 1
            continue
        
        if in_string:
            result.append(c)
            i += 1
            continue
        
        # Remove spaces around OR: ' OR ' -> 'OR', ' OR' -> 'OR', 'OR ' -> 'OR'
        if (c == ' ' and i + 3 <= len(line) and line[i+1:i+3] == 'OR'
                and (i + 3 >= len(line) or not line[i+3].isalpha())):
            # Skip space before OR
            i += 1
            continue
        if (c == 'O' and i + 2 <= len(line) and line[i+1] == 'R'
                and i + 2 < len(line) and line[i+2] == ' '
                and (i == 0 or not line[i-1].isalpha())):
            # Emit OR, skip space after
            result.append('O')
            result.append('R')
            i += 3  # skip 'OR '
            continue
        
        # Remove space after semicolons, closing parens, and string literals
        if c == ' ' and i > 0 and line[i-1] in ';)"':
            i += 1
            continue
        
        # Remove space before opening quote
        if c == ' ' and i + 1 < len(line) and line[i+1] == '"':
            i += 1
            continue
        
        # Remove duplicate spaces (keep only one space)
        if c == ' ' and i > 0 and line[i-1] == ' ':
            i += 1
            continue
        
        # Remove space after digit when next char is not a digit.
        # (Hex literals are already converted to decimal, so A-F
        # no longer need special handling.)
        if (c == ' ' and i > 0 and line[i-1].isdigit()
                and i + 1 < len(line)
                and not line[i+1].isdigit()):
            i += 1
            continue
        
        # Remove space after abbreviated commands ending in '.'
        # Pattern: letter(s) + '.' + space -> letter(s) + '.'
        # But only for known commands
        if (c == ' ' and i > 0 and line[i-1] == '.' and i >= 2):
            # Check if this is after an abbreviated command
            # Look back to find the command
            j = i - 2
            while j >= 0 and line[j].isalpha():
                j -= 1
            cmd = line[j+1:i-1]  # the letters before the dot
            if cmd in ('A', 'I', 'G', 'GOS', 'F', 'P', 'N', 'R', 'T', 'S', 'U', 'E'):
                # Skip the space
                i += 1
                continue
        
        result.append(c)
        i += 1
    
    return ''.join(result)


def convert_numeric_literals_in_escapes(line):
    """Convert numeric literals to string literals in escape sequence lines.
    
    Only applies to lines containing $27 or "\" (escape sequence markers).
    Converts standalone numeric literals that meet LEFT and RIGHT conditions.
    
    'P.$27"["1"H"' -> 'P.$27"[" "1" "H"'
    
    Must run BEFORE merge_adjacent_strings().
    """
    # Check if line contains escape sequence markers
    if '$27' not in line and '"\\"' not in line:
        return line
    
    # Find the first escape marker position
    esc_pos = line.find('$27')
    if esc_pos == -1:
        esc_pos = line.find('"\\"')
    if esc_pos == -1:
        return line  # Shouldn't happen
    
    # Copy everything before the first escape marker as-is
    result = []
    result.append(line[:esc_pos])
    
    # Start processing from the escape marker
    i = esc_pos
    left = False
    
    while i < len(line):
        # Check for 3-character patterns BEFORE checking for single quote
        # This prevents "\" from being treated as a regular string
        
        # Check for $27
        if i + 2 < len(line) and line[i:i+3] == '$27':
            result.append('$27')
            i += 3
            left = True
            continue
        
        # Check for "\" (must come before general string check)
        if i + 2 < len(line) and line[i:i+3] == '"\\"':
            result.append('"\\"')
            i += 3
            left = True
            continue
        
        # Check for string literal (general case)
        if line[i] == '"':
            result.append('"')
            i += 1
            # Skip to matching quote
            while i < len(line) and line[i] != '"':
                result.append(line[i])
                i += 1
            if i < len(line):
                result.append('"')
                i += 1
            left = True
            continue
        
        # Check for digit - could be numeric literal or addition expression
        if line[i].isdigit():
            # Collect first operand (all consecutive digits)
            j = i
            while j < len(line) and line[j].isdigit():
                j += 1
            operand1 = line[i:j]
            
            # Check if followed by + operator and another digit
            k = j
            while k < len(line) and line[k] == ' ':
                k += 1  # Skip spaces after first operand
            
            # Check for addition expression: <digit>+<digit>
            if k < len(line) and line[k] == '+':
                # Found +, look for second operand
                m = k + 1
                while m < len(line) and line[m] == ' ':
                    m += 1  # Skip spaces after +
                
                if m < len(line) and line[m].isdigit():
                    # Collect second operand
                    n = m
                    while n < len(line) and line[n].isdigit():
                        n += 1
                    operand2 = line[m:n]
                    
                    # Evaluate the expression
                    sum_result = str(int(operand1) + int(operand2))
                    
                    # Now check if we should convert this to a string (same LEFT/RIGHT logic)
                    if left:
                        # Check right condition after the expression
                        p = n
                        while p < len(line) and line[p] == ' ':
                            p += 1
                        
                        right_ok = (p >= len(line) or 
                                   line[p] == ';' or 
                                   line[p] == '"' or
                                   line[p].isupper())
                        
                        if right_ok:
                            # Convert evaluated result to string literal
                            result.append(' "')
                            result.append(sum_result)
                            result.append('" ')
                            left = True
                            i = n
                            continue
                    
                    # Don't convert - just output the evaluated result
                    result.append(sum_result)
                    left = False
                    i = n
                    continue
            
            # Not an addition expression, handle as simple numeric literal
            if left:
                # Check right condition
                k = j
                while k < len(line) and line[k] == ' ':
                    k += 1
                
                right_ok = (k >= len(line) or 
                           line[k] == ';' or 
                           line[k] == '"' or
                           line[k].isupper())
                
                if right_ok:
                    # Convert to string literal
                    result.append(' "')
                    result.append(operand1)
                    result.append('" ')
                    left = True
                    i = j
                    continue
            
            # Don't convert
            result.append(operand1)
            left = False
            i = j
            continue
        
        # Check for semicolon (ends current escape sequence context)
        if line[i] == ';':
            result.append(';')
            i += 1
            left = False
            continue
        
        # Space: preserve left state if True, otherwise no change
        if line[i] == ' ':
            result.append(' ')
            i += 1
            # left unchanged
            continue
        
        # Any other character
        result.append(line[i])
        i += 1
        left = False
    
    return ''.join(result)


def merge_adjacent_strings(line):
    """Merge adjacent string literals separated by space.
    
    '"AB" "CD"' -> '"ABCD"'
    '" "' is left alone (string containing a space)
    '"A""B"' is left alone ("" is escaped quote in Atom BASIC)
    Must run BEFORE space removal.
    """
    result = []
    i = 0
    while i < len(line):
        if line[i] == '"':
            # Collect string content
            i += 1
            content = []
            while i < len(line) and line[i] != '"':
                content.append(line[i])
                i += 1
            if i >= len(line):
                # Unterminated string — emit as-is
                result.append('"')
                result.extend(content)
                break
            # i is at closing quote
            i += 1  # skip closing quote
            merged = True
            while merged:
                merged = False
                # Merge space-separated adjacent string: "A" "B" or "A"  "B" (any number of spaces)
                if i < len(line) and line[i] == ' ':
                    # Skip all spaces to find the next string
                    j = i
                    while j < len(line) and line[j] == ' ':
                        j += 1
                    # Check if there's a string after the spaces
                    if j < len(line) and line[j] == '"':
                        # Found adjacent string, merge it
                        k = j + 1
                        while k < len(line) and line[k] != '"':
                            k += 1
                        if k < len(line):
                            next_content = line[j+1:k]
                            if content or next_content:
                                content.append(next_content)
                                i = k + 1
                                merged = True
            result.append('"')
            result.extend(content)
            result.append('"')
        else:
            result.append(line[i])
            i += 1
    return ''.join(result)


def eval_const_parens(line):
    """Evaluate parenthesized constant integer expressions.
    
    '(-1-2)' -> '-3', '(-1-4)' -> '-5'
    Only evaluates parens containing just integers and +-*/.
    Respects strings.
    """
    result = []
    i = 0
    in_string = False
    while i < len(line):
        c = line[i]
        if c == '"':
            in_string = not in_string
        if not in_string and c == '(':
            # Skip if preceded by letter/$ (array access, DIM, function)
            if i > 0 and (line[i-1].isalpha() or line[i-1] == '$'):
                result.append(c)
                i += 1
                continue
            # Find matching close paren
            j = i + 1
            while j < len(line) and line[j] != ')':
                j += 1
            if j < len(line):
                inner = line[i+1:j]
                if re.fullmatch(r'[-+*/\d ]+', inner):
                    try:
                        val = int(eval(inner))  # noqa: S307
                        result.append(str(val))
                        i = j + 1
                        continue
                    except Exception:
                        pass
        result.append(c)
        i += 1
    return ''.join(result)


def remove_line_number_space(line):
    """Remove space or semicolon after line number (with or without label).
    
    '1100q I.B=0 R.' -> '1100qI.B=0 R.'
    '2200l;P=P*8'    -> '2200lP=P*8'
    '10 W=40'        -> '10W=40'
    """
    m = re.match(r'^(\d+[a-z]?)[ ;](.*)', line)
    if m:
        return m.group(1) + m.group(2)
    return line


def optimize(text):
    """Apply all optimizations to the input text."""
    # Split into lines
    lines = text.rstrip('\n').split('\n')
    
    # Step 1: Strip cpp warnings (lines not starting with a digit)
    lines = [l for l in lines if re.match(r'^\d', l)]
    
    # Find jump targets before any modifications
    targets = find_jump_targets(lines)
    
    # Step 2: Per-line optimizations
    optimized = []
    for line in lines:
        line = line.rstrip()
        if not line:
            continue
        
        # Remove trailing semicolons
        line = remove_trailing_semicolons(line)
        
        # Collapse multiple semicolons
        line = collapse_multiple_semicolons(line)
        
        # Convert hex literals to decimal
        line = convert_hex_to_decimal(line)
        
        # Remove space after line number / label
        line = remove_line_number_space(line)
        
        # Evaluate constant parenthesized expressions
        line = eval_const_parens(line)
        
        # Convert numeric literals to strings in escape sequences
        line = convert_numeric_literals_in_escapes(line)
        
        # Merge adjacent string literals ("A" "B" -> "AB")
        line = merge_adjacent_strings(line)
        
        # Remove unnecessary spaces
        line = remove_unnecessary_spaces(line)
        
        # Skip empty lines (just a line number)
        num, label, body = parse_line(line)
        if num and not label and not body.strip():
            continue
        
        optimized.append(line)
    
    # Step 3: Merge consecutive lines
    merged = []
    for line in optimized:
        num, label, body = parse_line(line)
        if num is None or body is None:
            merged.append(line)
            continue
        
        if not merged:
            merged.append(line)
            continue
        
        # Don't merge if this line is a jump target
        if num in targets:
            merged.append(line)
            continue
        
        # Don't merge if this line has a label (it's a GOSUB target)
        if label:
            merged.append(line)
            continue
        
        # Don't merge into previous line if it contains any IF
        if contains_if(merged[-1]):
            merged.append(line)
            continue
        
        # Try to merge: previous line + ';' + this line's body
        prev = merged[-1]
        prev_num, prev_label, prev_body = parse_line(prev)
        if prev_label and not prev_body:
            # Label-only line: no semicolon needed
            append_text = body.lstrip()
        else:
            append_text = ';' + body.lstrip()
        
        if len(prev) + len(append_text) <= MAX_LINE:
            merged[-1] = prev + append_text
        else:
            merged.append(line)
    
    # Step 3b: Collapse multiple semicolons created by merging
    merged = [collapse_multiple_semicolons(line) for line in merged]
    
    # Step 4: Truncate REM comments if line is too long
    truncated = []
    for line in merged:
        if len(line) > MAX_LINE:
            # Try to find and truncate REM comment
            # Match REM preceded by non-uppercase letter (digit, lowercase, punctuation)
            # Examples: 1000REM, 1010pREM, A=1;REM, IF A=1REM, IF A=1T.REM
            # Won't match: XREM (uppercase before REM means it's part of identifier)
            rem_match = re.search(r'^(.*)([^A-Z])(REM)(.*)$', line)
            if rem_match:
                prefix = rem_match.group(1)      # Everything before the char preceding REM
                pre_rem_char = rem_match.group(2) # The [^A-Z] char (must preserve)
                rem_keyword = rem_match.group(3) # "REM"
                comment = rem_match.group(4)     # The comment text
                
                # Calculate space available for REM + comment
                # Line = prefix + pre_rem_char + "REM" + comment
                prefix_len = len(prefix + pre_rem_char)
                available = MAX_LINE - prefix_len
                
                if available >= 3:
                    # Enough space for "REM" at minimum
                    # Truncate comment to fit
                    comment_space = available - 3  # 3 chars for "REM"
                    if comment_space > 0:
                        line = prefix + pre_rem_char + rem_keyword + comment[:comment_space]
                    else:
                        line = prefix + pre_rem_char + rem_keyword
                else:
                    # Not enough space even for "REM", remove entire REM statement
                    line = (prefix + pre_rem_char).rstrip(';').rstrip()
        truncated.append(line)
    
    # Step 5: Validate line lengths after truncation
    errors = []
    for line in truncated:
        if len(line) > MAX_LINE:
            errors.append((line, len(line)))
    
    if errors:
        # Report all lines that are too long
        print(f"ERROR: {len(errors)} line(s) exceed {MAX_LINE} character limit:", file=sys.stderr)
        for line, length in errors:
            # Parse to get line number for better error reporting
            num, label, body = parse_line(line)
            line_ref = f"Line {num}" if num else "Unknown line"
            print(f"  {line_ref}: {length} chars: {line[:80]}{'...' if len(line) > 80 else ''}", file=sys.stderr)
        sys.exit(1)
    
    return '\n'.join(truncated) + '\n'


def main():
    text = sys.stdin.read()
    result = optimize(text)
    sys.stdout.write(result)
    print(f"Optimized: {len(text)} -> {len(result)} bytes "
          f"(saved {len(text) - len(result)})", file=sys.stderr)


if __name__ == '__main__':
    main()
