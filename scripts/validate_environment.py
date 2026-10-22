#!/usr/bin/env python3
"""
Environment and Toolchain Validator for NeuroPulse Monorepo
"""
import sys
import shutil
import subprocess

def check_python():
    version = sys.version_info
    print(f"[*] Python version: {version.major}.{version.minor}.{version.micro}")
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        print("[-] Error: Python 3.11 or higher is required.")
        return False
    print("[+] Python version OK.")
    return True

def check_node():
    node = shutil.which("node")
    npm = shutil.which("npm")
    if not node or not npm:
        print("[-] Warning: Node.js or npm is not in PATH. Frontend build requires Node 18+.")
        return False
    try:
        out = subprocess.check_output([node, "--version"], text=True).strip()
        print(f"[+] Node.js version: {out}")
        return True
    except Exception as e:
        print(f"[-] Error querying Node: {e}")
        return False

def check_git():
    git = shutil.which("git")
    if not git:
        print("[-] Warning: Git is not installed.")
        return False
    try:
        out = subprocess.check_output([git, "--version"], text=True).strip()
        print(f"[+] Git version: {out}")
        return True
    except Exception as e:
        print(f"[-] Error querying Git: {e}")
        return False

def main():
    print("=" * 60)
    print("NeuroPulse Environment Validator")
    print("=" * 60)
    py_ok = check_python()
    node_ok = check_node()
    git_ok = check_git()
    print("=" * 60)
    if py_ok and node_ok and git_ok:
        print("[SUCCESS] All core development prerequisites are available!")
        sys.exit(0)
    else:
        print("[WARNING] Some optional or required prerequisites were missing.")
        sys.exit(0)

if __name__ == "__main__":
    main()
