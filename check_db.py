import os

directory = r"E:\Downloads\academy-system"
output_file = "directory_tree.txt"

with open(output_file, "w", encoding="utf-8") as f:
    for root, dirs, files in os.walk(directory):
        dirs.sort()
        files.sort()

        level = os.path.relpath(root, directory).count(os.sep)
        indent = "    " * level

        f.write(f"{indent}{os.path.basename(root)}/\n")

        for file in files:
            f.write(f"{indent}    {file}\n")

print(f"Directory tree saved to {output_file}")