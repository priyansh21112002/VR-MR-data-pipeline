"""
Generate .meta files for all assets in the UPM package.
Run from the Github/ folder: python generate_meta_files.py
"""
import os
import hashlib
import uuid

def generate_guid(seed_string):
    """Generate a deterministic 32-char hex GUID from a seed string."""
    return hashlib.md5(seed_string.encode('utf-8')).hexdigest()

def write_folder_meta(folder_path, relative_path):
    """Write a .meta file for a folder."""
    meta_path = folder_path + ".meta"
    if os.path.exists(meta_path):
        return
    guid = generate_guid("folder:" + relative_path)
    content = f"""fileFormatVersion: 2
guid: {guid}
folderAsset: yes
DefaultImporter:
  externalObjects: {{}}
  userData: 
  assetBundleName: 
  assetBundleVariant: 
"""
    with open(meta_path, 'w', newline='\n') as f:
        f.write(content)
    print(f"  [folder] {relative_path}.meta")

def write_cs_meta(file_path, relative_path):
    """Write a .meta file for a C# script."""
    meta_path = file_path + ".meta"
    if os.path.exists(meta_path):
        return
    guid = generate_guid("cs:" + relative_path)
    content = f"""fileFormatVersion: 2
guid: {guid}
MonoImporter:
  externalObjects: {{}}
  serializedVersion: 2
  defaultReferences: []
  executionOrder: 0
  icon: {{instanceID: 0}}
  userData: 
  assetBundleName: 
  assetBundleVariant: 
"""
    with open(meta_path, 'w', newline='\n') as f:
        f.write(content)
    print(f"  [cs]     {relative_path}.meta")

def write_asmdef_meta(file_path, relative_path):
    """Write a .meta file for an assembly definition."""
    meta_path = file_path + ".meta"
    if os.path.exists(meta_path):
        return
    guid = generate_guid("asmdef:" + relative_path)
    content = f"""fileFormatVersion: 2
guid: {guid}
AssemblyDefinitionImporter:
  externalObjects: {{}}
  userData: 
  assetBundleName: 
  assetBundleVariant: 
"""
    with open(meta_path, 'w', newline='\n') as f:
        f.write(content)
    print(f"  [asmdef] {relative_path}.meta")

def write_text_meta(file_path, relative_path):
    """Write a .meta file for text assets (md, json, txt)."""
    meta_path = file_path + ".meta"
    if os.path.exists(meta_path):
        return
    guid = generate_guid("text:" + relative_path)
    content = f"""fileFormatVersion: 2
guid: {guid}
TextScriptImporter:
  externalObjects: {{}}
  userData: 
  assetBundleName: 
  assetBundleVariant: 
"""
    with open(meta_path, 'w', newline='\n') as f:
        f.write(content)
    print(f"  [text]   {relative_path}.meta")

def main():
    root = os.path.dirname(os.path.abspath(__file__))
    print(f"Generating .meta files in: {root}\n")
    
    count = 0
    
    # Folders and files that need .meta files (NOT ~ folders)
    process_dirs = ["Runtime", "Editor"]
    
    # 1. Generate .meta for top-level folders
    for d in process_dirs:
        dir_path = os.path.join(root, d)
        if os.path.isdir(dir_path):
            write_folder_meta(dir_path, d)
            count += 1
    
    # 2. Walk Runtime/ and Editor/ and generate .meta for all contents
    for d in process_dirs:
        dir_path = os.path.join(root, d)
        if not os.path.isdir(dir_path):
            continue
        
        for dirpath, dirnames, filenames in os.walk(dir_path):
            # Generate .meta for subdirectories
            for subdir in dirnames:
                if subdir.endswith('~') or subdir.startswith('.'):
                    continue
                full_subdir = os.path.join(dirpath, subdir)
                rel = os.path.relpath(full_subdir, root).replace('\\', '/')
                write_folder_meta(full_subdir, rel)
                count += 1
            
            # Generate .meta for files
            for filename in filenames:
                if filename.endswith('.meta'):
                    continue
                
                full_file = os.path.join(dirpath, filename)
                rel = os.path.relpath(full_file, root).replace('\\', '/')
                
                if filename.endswith('.cs'):
                    write_cs_meta(full_file, rel)
                    count += 1
                elif filename.endswith('.asmdef'):
                    write_asmdef_meta(full_file, rel)
                    count += 1
                elif filename.endswith(('.md', '.json', '.txt')):
                    write_text_meta(full_file, rel)
                    count += 1
    
    print(f"\nDone! Generated {count} .meta files.")

if __name__ == "__main__":
    main()
