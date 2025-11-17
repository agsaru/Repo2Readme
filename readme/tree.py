import os

def generate_tree(root:str):
    
    """
    Generates tree structure for readme file
    """

    tree_lines=[]

    for current_dir_path,dirs,files in os.walk(root):

        level=current_dir_path.replace(root,"").count(os.sep)

        indentation=" " * 4 * level

        folder_name = os.path.basename(current_dir_path)

        if level==0:

            tree_lines.append(f"{folder_name}/")

        else:

            tree_lines.append(f"{indentation}├──{folder_name}/")

        for file in files:

            tree_lines.append(f"{indentation}│   └── {file}")

    return "\n".join(tree_lines)


def extract_tree(root:str):

    """Returns tree structure and all file paths"""

    tree_stucture=generate_tree(root)

    file_paths=[]

    for current_dir_path,dirs,files in os.walk(root):

        for file in files:

            file_paths.append(os.path.join(current_dir_path,file))

    return tree_stucture,file_paths


