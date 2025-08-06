import re
from pathlib import Path


def format_keymap_file_content(code_string):
    """
    Formats the keymaps array within a given C source code string.
    """
    # Find the keymaps array block
    keymaps_pattern = re.compile(
        r"(const uint16_t PROGMEM keymaps\[\]\[MATRIX_ROWS\]\[MATRIX_COLS\] = \{)(.*?)(\};)",
        re.DOTALL,
    )

    def format_keymaps_block(match):
        declaration = match.group(1)
        content = match.group(2)
        closing = match.group(3)

        # Find each layout block - use a more specific pattern
        # This pattern looks for [_NAME] = LAYOUT( and then finds the matching closing )
        def find_and_format_layouts(text):
            result = ""
            pos = 0

            while True:
                # Find the next layout declaration
                layout_start = re.search(
                    r"(\s*/\*.*?\*/\s*)?(\s*\[_\w+\]\s*=\s*LAYOUT\()",
                    text[pos:],
                    re.DOTALL,
                )
                if not layout_start:
                    # Add remaining text and break
                    result += text[pos:]
                    break

                # Add text before this layout
                result += text[pos : pos + layout_start.start()]

                # Extract the comment and declaration
                comment = layout_start.group(1) or ""
                declaration = layout_start.group(2)

                # Find the matching closing parenthesis - but ignore parens inside strings
                paren_start = pos + layout_start.end()
                paren_count = 1
                content_start = paren_start
                content_end = paren_start
                in_string = False

                i = paren_start
                while i < len(text) and paren_count > 0:
                    char = text[i]

                    # Handle string literals (though unlikely in keycodes)
                    if char == '"' and (i == 0 or text[i - 1] != "\\"):
                        in_string = not in_string
                    elif not in_string:
                        if char == "(":
                            paren_count += 1
                        elif char == ")":
                            paren_count -= 1
                            if paren_count == 0:
                                content_end = i
                                break
                    i += 1

                # Extract the content between parentheses
                layout_content = text[content_start:content_end]

                # Check if there's a comma after the closing paren
                comma = ""
                if content_end + 1 < len(text) and text[content_end + 1] == ",":
                    comma = ","
                    pos = content_end + 2
                else:
                    pos = content_end + 1

                # Format this layout
                formatted_layout = format_single_layout(
                    comment, declaration, layout_content, comma
                )
                result += formatted_layout

            return result

        formatted_content = find_and_format_layouts(content)
        return declaration + formatted_content + closing

    return keymaps_pattern.sub(format_keymaps_block, code_string)


def format_single_layout(comment, declaration, content, comma):
    """Format a single layout block"""
    # Clean up the declaration
    clean_declaration = declaration.strip()
    clean_declaration = clean_declaration.replace("MO(1)", "MO(_LOWER)")
    clean_declaration = clean_declaration.replace("MO(2)", "MO(_RAISE)")
    clean_declaration = clean_declaration.replace("MO(3)", "MO(_ADJUST)")

    # Extract keycodes - split by comma and clean, but be smarter about it
    keycodes = []
    current_token = ""
    paren_count = 0

    for char in content:
        if char == "(":
            paren_count += 1
            current_token += char
        elif char == ")":
            paren_count -= 1
            current_token += char
        elif char == "," and paren_count == 0:
            # This comma is a separator, not part of a keycode
            if current_token.strip():
                keycodes.append(current_token.strip())
            current_token = ""
        else:
            current_token += char

    # Add the last token
    if current_token.strip():
        keycodes.append(current_token.strip())

    if not keycodes:
        return comment + clean_declaration + content + ")" + comma

    # Format the layout
    if len(keycodes) >= 58:
        formatted_lines = format_full_layout(keycodes)
    else:
        # Simple fallback for shorter layouts
        formatted_lines = [f"  {', '.join(keycodes)}"]

    # Don't add extra newline before declaration - preserve existing spacing
    if comment.strip():
        return (
            f"{comment}{clean_declaration}\n"
            + "\n".join(formatted_lines)
            + "\n)"
            + comma
        )
    else:
        return f"{clean_declaration}\n" + "\n".join(formatted_lines) + "\n)" + comma


def format_full_layout(keycodes):
    """Format a full 58+ key layout"""
    lines = []

    # Ensure we have at least 58 keycodes
    if len(keycodes) < 58:
        return [f"  {', '.join(keycodes)}"]

    # Split into rows based on the layout structure
    row1 = keycodes[0:12]  # Row 1: keys 0-11 (12 keys)
    row2 = keycodes[12:24]  # Row 2: keys 12-23 (12 keys)
    row3 = keycodes[24:36]  # Row 3: keys 24-35 (12 keys)
    row4 = keycodes[36:50]  # Row 4: keys 36-49 (14 keys: 6+2+6)
    row5 = keycodes[50:58]  # Row 5: keys 50-57 (8 keys)

    # Calculate column widths for alignment
    left_cols = [row1[0:6], row2[0:6], row3[0:6], row4[0:6]]
    right_cols = [row1[6:12], row2[6:12], row3[6:12], row4[8:14]]

    left_widths = []
    right_widths = []

    for i in range(6):
        left_width = max(len(row[i]) for row in left_cols)
        right_width = max(len(row[i]) for row in right_cols)
        left_widths.append(left_width)
        right_widths.append(right_width)

    # Format rows 1-3 (standard 6+6 layout)
    for row in [row1, row2, row3]:
        # Build left half with proper spacing
        left_parts = []
        for i in range(6):
            if i < 5:  # Not the last item in left half
                left_parts.append(row[i] + ",   ")
            else:  # Last item in left half
                left_parts.append(row[i] + ",")

        # Build right half with proper spacing
        right_parts = []
        for i in range(6):
            if i < 5:  # Not the last item in right half
                right_parts.append(row[i + 6] + ",   ")
            else:  # Last item in right half
                right_parts.append(row[i + 6] + ",")

        # Pad the left parts to align properly
        left_formatted = []
        for i, part in enumerate(left_parts):
            if i < 5:
                # Pad to width + 4 for ",   "
                left_formatted.append(part.ljust(left_widths[i] + 4))
            else:
                # Pad to width + 1 for ","
                left_formatted.append(part.ljust(left_widths[i] + 1))

        # Pad the right parts to align properly
        right_formatted = []
        for i, part in enumerate(right_parts):
            if i < 5:
                # Pad to width + 4 for ",   "
                right_formatted.append(part.ljust(right_widths[i] + 4))
            else:
                # Last item, no padding needed
                right_formatted.append(part)

        line = (
            "  "
            + "".join(left_formatted)
            + "                     "
            + "".join(right_formatted)
        )
        lines.append(line)

    # Format row 4 (6+2+6 layout)
    left_parts = []
    for i in range(6):
        left_parts.append(row4[i] + ",  ")

    middle_keys = row4[6:8]
    middle_parts = [middle_keys[0] + ", ", middle_keys[1] + ",  "]

    right_parts = []
    for i in range(6):
        if i < 5:
            right_parts.append(row4[i + 8] + ",   ")
        else:
            right_parts.append(row4[i + 8] + ",")

    # Pad left parts
    left_formatted = []
    for i, part in enumerate(left_parts):
        if i < 5:
            left_formatted.append(part.ljust(left_widths[i] + 4))
        else:
            left_formatted.append(part.ljust(left_widths[i] + 2))  # +2 for ", "

    # Pad middle parts - fix the spacing here
    middle_width = max(len(middle_keys[0]), len(middle_keys[1]))
    middle_formatted = [
        middle_parts[0].ljust(middle_width + 2),  # +2 for ", "
        middle_parts[1].ljust(middle_width + 2),  # +2 for ", " (changed from +3)
    ]

    # Pad right parts
    right_formatted = []
    for i, part in enumerate(right_parts):
        if i < 5:
            right_formatted.append(part.ljust(right_widths[i] + 4))
        else:
            right_formatted.append(part)

    line = (
        "  "
        + "".join(left_formatted)
        + "".join(middle_formatted)
        + "".join(right_formatted)
    )
    lines.append(line)

    # Format row 5 (bottom row with 8 keys)
    line = "                       " + ", ".join(row5)
    lines.append(line)

    return lines


if __name__ == "__main__":
    target_file_path = Path(__file__).parent / "keymap.c"

    if not target_file_path.exists():
        print(f"Error: File not found at {target_file_path}")
    else:
        print(f"Processing file: {target_file_path}")
        try:
            original_content = target_file_path.read_text()
            formatted_content = format_keymap_file_content(original_content)

            if original_content != formatted_content:
                target_file_path.write_text(formatted_content)
                print("File formatted successfully.")
            else:
                print("No changes needed. File is already formatted.")

        except Exception as e:
            print(f"Error: {e}")
            import traceback

            traceback.print_exc()
