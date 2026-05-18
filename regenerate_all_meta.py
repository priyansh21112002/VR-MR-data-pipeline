"""
Regenerate ALL .meta files with truly unique GUIDs using uuid4.
Overwrites any existing .meta files.
"""
import os
import uuid

def make_guid():
    """Generate a random 32-char hex GUID (no dashes)."""
    return uuid.uuid4().hex

def write_meta(file_path, content):
    with open(file_path, 'w', newline='\n') as f:
        f.write(content)

def folder_meta(guid):
    return f"""fileFormatVersion: 2
guid: {guid}
folderAsset: yes
DefaultImporter:
  externalObjects: {{}}
  userData: 
  assetBundleName: 
  assetBundleVariant: 
"""

def cs_meta(guid):
    return f"""fileFormatVersion: 2
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

def asmdef_meta(guid):
    return f"""fileFormatVersion: 2
guid: {guid}
AssemblyDefinitionImporter:
  externalObjects: {{}}
  userData: 
  assetBundleName: 
  assetBundleVariant: 
"""

def text_meta(guid):
    return f"""fileFormatVersion: 2
guid: {guid}
TextScriptImporter:
  externalObjects: {{}}
  userData: 
  assetBundleName: 
  assetBundleVariant: 
"""

def default_meta(guid):
    return f"""fileFormatVersion: 2
guid: {guid}
DefaultImporter:
  externalObjects: {{}}
  userData: 
  assetBundleName: 
  assetBundleVariant: 
"""

def package_meta(guid):
    return f"""fileFormatVersion: 2
guid: {guid}
PackageManifestImporter:
  externalObjects: {{}}
  userData: 
  assetBundleName: 
  assetBundleVariant: 
"""

def main():
    root = os.path.dirname(os.path.abspath(__file__))
    print(f"Regenerating ALL .meta files with uuid4 GUIDs in: {root}\n")

    count = 0

    # === Root-level files ===
    root_files = {
        "README.md": text_meta,
        "CHANGELOG.md": text_meta,
        "LICENSE": default_meta,
        "package.json": package_meta,
    }
    for fname, meta_fn in root_files.items():
        fpath = os.path.join(root, fname)
        if os.path.exists(fpath):
            guid = make_guid()
            write_meta(fpath + ".meta", meta_fn(guid))
            print(f"  [root]   {fname}.meta  guid={guid}")
            count += 1

    # === Runtime/ and Editor/ folders and contents ===
    process_dirs = ["Runtime", "Editor"]

    # Top-level folder .meta
    for d in process_dirs:
        dpath = os.path.join(root, d)
        if os.path.isdir(dpath):
            guid = make_guid()
            write_meta(dpath + ".meta", folder_meta(guid))
            print(f"  [folder] {d}.meta  guid={guid}")
            count += 1

    # Walk all contents
    for d in process_dirs:
        dpath = os.path.join(root, d)
        if not os.path.isdir(dpath):
            continue

        for dirpath, dirnames, filenames in os.walk(dpath):
            # Subfolders
            for subdir in dirnames:
                if subdir.endswith('~') or subdir.startswith('.'):
                    continue
                full = os.path.join(dirpath, subdir)
                rel = os.path.relpath(full, root).replace('\\', '/')
                guid = make_guid()
                write_meta(full + ".meta", folder_meta(guid))
                print(f"  [folder] {rel}.meta  guid={guid}")
                count += 1

            # Files
            for fname in filenames:
                if fname.endswith('.meta'):
                    continue
                full = os.path.join(dirpath, fname)
                rel = os.path.relpath(full, root).replace('\\', '/')

                guid = make_guid()
                if fname.endswith('.cs'):
                    write_meta(full + ".meta", cs_meta(guid))
                    print(f"  [cs]     {rel}.meta  guid={guid}")
                    count += 1
                elif fname.endswith('.asmdef'):
                    write_meta(full + ".meta", asmdef_meta(guid))
                    print(f"  [asmdef] {rel}.meta  guid={guid}")
                    count += 1

    print(f"\nDone! Regenerated {count} .meta files with unique uuid4 GUIDs.")

if __name__ == "__main__":
    main()
