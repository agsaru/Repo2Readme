import os
from repo2readme.utils.filter import github_file_filter


def generate_tree(root: str):
    tree_lines = []

    for current_dir_path, dirs, files in os.walk(root):

        # Keep only dirs that are allowed to load
        dirs[:] = [
            d for d in dirs
            if github_file_filter(os.path.join(current_dir_path, d))
        ]

        level = current_dir_path.replace(root, "").count(os.sep)
        indent = " " * 4 * level

        folder_name = os.path.basename(current_dir_path)

        if level == 0:
            tree_lines.append(f"{folder_name}/")
        else:
            tree_lines.append(f"{indent}├── {folder_name}/")

        for idx, file in enumerate(files):
            full = os.path.join(current_dir_path, file)

            if not github_file_filter(full):
                continue

            file_indent = " " * 4 * (level + 1)
            branch = "└──" if idx == len(files) - 1 else "├──"
            tree_lines.append(f"{file_indent}{branch} {file}")

    return "\n".join(tree_lines)


def extract_tree(root: str):
    tree_structure = generate_tree(root)
    file_paths = []

    for current_dir_path, dirs, files in os.walk(root):

        dirs[:] = [
            d for d in dirs
            if github_file_filter(os.path.join(current_dir_path, d))
        ]

        for file in files:
            full = os.path.join(current_dir_path, file)

            if github_file_filter(full):
                file_paths.append(full)

    return tree_structure, file_paths
