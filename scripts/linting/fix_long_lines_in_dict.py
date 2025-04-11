def fix_long_lines(file_path, start_line=212, max_length=88):
    with open(file_path, "r") as file:
        lines = file.readlines()

    for i in range(start_line - 1, len(lines)):
        line = lines[i]
        if len(line) > max_length and '"' in line:
            # Find the last whitespace before max_length
            last_space = line.rfind(" ", 0, max_length)
            if last_space != -1:
                # Split the line and add concatenation
                lines[i] = line[:last_space] + '" \\\n'
                lines.insert(i + 1, '    + "' + line[last_space + 1 :].lstrip())

    # Write the modified lines back to the file
    with open(file_path, "w") as file:
        file.writelines(lines)


# Usage
fix_long_lines("tests/conftest.py")
