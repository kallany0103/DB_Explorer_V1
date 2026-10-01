#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
set_crypto_provider.py

This script switches the cryptographic provider used by the product.
Works on both Linux and Windows.
"""

from __future__ import print_function

import os
import stat
import sys
import shutil
import filecmp
import platform

# ------------------------------------------------------------
# Detect OS
# ------------------------------------------------------------

IS_WINDOWS = platform.system().lower().startswith("win")

# Library directory depending on OS
LIB_DIR_NAME = "bin" if IS_WINDOWS else "lib"

# ------------------------------------------------------------
# Library configuration
# (TARGET_LIB_NAME, NEXTGEN_SOURCE_LIB_NAME, LEGACY_BACKUP_LIB_NAME)
# ------------------------------------------------------------

if IS_WINDOWS:

    # Required Windows libraries
    LIB_CONFIGS = [
        ("orannzsbb19.dll", "orannzoslsbb19.dll", "orannzmessbb19.dll"),
        ("orannzsbb19.sym", "orannzoslsbb19.sym", "orannzmessbb19.sym"),
    ]

    # OCI Windows libraries, which are present only in instantclient environemnt
    LIB_CONFIGS_OCI = [
        ("oraociei19.dll", "oraocieiosl19.dll", "oraocieimes19.dll"),
        ("oraociei19.sym", "oraocieiosl19.sym", "oraocieimes19.sym"),
        ("oraociicus19.dll", "oraociicusosl19.dll", "oraociicusmes19.dll"),
        ("oraociicus19.sym", "oraociicusosl19.sym", "oraociicusmes19.sym"),
    ]

else:

    # Linux libraries
    LIB_CONFIGS = [
        ("libnnz19.so", "libnnzosl19.so", "libnnz_mes19.so"),
        ("libnnzsrv19.so", "libnnzoslsrv19.so", "libnnzsrv_mes19.so"),
    ]

    LIB_CONFIGS_OCI = []

MODE_NEXT_GENERATION = "next-generation"
MODE_LEGACY = "legacy"
MODE_STATUS = "status"

# ------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------

def get_env_lib_paths():
    """Collects all unique library directories from ORACLE_HOME and OKV_HOME."""
    paths = []
    env_okv_home = os.environ.get("OKV_HOME")
    if env_okv_home:
        okv_lib_path = os.path.join(env_okv_home, LIB_DIR_NAME)
        if okv_lib_path not in paths:
            paths.append(okv_lib_path)
            print("Found OKV_HOME: {}".format(env_okv_home))

    env_oracle_home = os.environ.get("ORACLE_HOME")
    if env_oracle_home:
        oracle_lib_path = os.path.join(env_oracle_home, LIB_DIR_NAME)
        if oracle_lib_path not in paths:
            paths.append(oracle_lib_path)
            print("Found ORACLE_HOME: {}".format(env_oracle_home))
    if not paths:
        cwd = os.getcwd()
        paths.append(cwd)
        print("Adding current directory: {}".format(cwd))
    return paths


def resolve_symlink_to_file(path):
    if not os.path.exists(path) and not os.path.islink(path):
        print("file {} does not exist".format(path))
        return

    try:
        target = os.path.realpath(path)
        tmp = path + ".tmp"

        shutil.copy2(target, tmp)

        os.chmod(path, stat.S_IWRITE)
        os.remove(path)
        shutil.move(tmp, path)

    except Exception as e:
        print("Error resolving symlink {}: {}".format(path, e))


def perform_single_switch(lib_dir, target_lib_name, next_gen_source, legacy_source, mode):

    target_path = os.path.join(lib_dir, target_lib_name)
    next_gen_path = os.path.join(lib_dir, next_gen_source)
    legacy_backup_path = os.path.join(lib_dir, legacy_source)

    if mode == MODE_NEXT_GENERATION and not os.path.exists(next_gen_path):
        print("Skipping {}: next-gen variant not found.".format(target_lib_name))
        return None

    if mode == MODE_NEXT_GENERATION:
        if os.path.exists(target_path) and os.path.exists(next_gen_path) and filecmp.cmp(target_path, next_gen_path, shallow=False):
            print("{} is already the next-gen version.".format(target_lib_name))
            return True

        if os.path.exists(target_path) and not os.path.exists(legacy_backup_path):
            print("Backing up legacy provider libraries")
            try:
                shutil.copy2(target_path, legacy_backup_path)
            except Exception:
                print("Error during backing up legacy provider library.")
                return None
        elif os.path.exists(legacy_backup_path):
            print("Backup already exists. Skipping backup.")

        elif not os.path.exists(target_path):
            print("Warning: legacy library not found. Proceeding.")

        print("Switching {} to {} version.".format(target_lib_name, mode))

        try:
            if IS_WINDOWS:
                resolve_symlink_to_file(target_path)
                shutil.copy2(next_gen_path , target_path)
            else:
                if os.path.exists(target_path):
                    os.remove(target_path)
                shutil.copy2(next_gen_path, target_path)

            print("Switched successfully.")

        except Exception as e:
            print("Error during switch: {}".format(e))

        return False

    elif mode == MODE_LEGACY:
        # 1. Check if the backup of legacy provider libraries is present (Preferred method for restore)
        if os.path.exists(legacy_backup_path):

            if os.path.exists(target_path) and filecmp.cmp(target_path, legacy_backup_path, shallow=False):
                print("{} is already legacy variant.".format(target_lib_name))
                return None

            print("Restoring {} from backup.".format(target_lib_name))

            try:
                if os.path.exists(target_path):
                    os.remove(target_path)

                shutil.copy2(legacy_backup_path, target_path)
                print("Restored successfully.")

            except Exception as e:
                print("Error during restore of the library: {}".format(e))

            return None

        # Integrity check when backup is missing
        if os.path.exists(target_path):
            if os.path.exists(next_gen_path):
                try:
                    if filecmp.cmp(target_path, next_gen_path, shallow=False):
                        print("CRITICAL ERROR: {} is next-gen but no backup exists. Original legacy library is lost.".format(target_lib_name))
                        sys.exit(1)
                except Exception:
                    pass
            else:
                print("Warning: {} next-gen reference missing. Cannot verify integrity.".format(next_gen_source))

        # 3. Assume already legacy if not matching next-gen
        print("No backup found for {}. Assuming already legacy.".format(target_lib_name))
        return None


def switch_library(lib_dir, mode):

    print("\n=== Processing {} ===".format(lib_dir))

    if not os.path.isdir(lib_dir):
        print("Skipped: {} does not exist.".format(lib_dir))
        return

    if not os.access(lib_dir, os.W_OK):
        print("Skipped: {} is read-only. Cannot perform switch.".format(lib_dir))
        return

    files_in_dir = os.listdir(lib_dir)

    # Build effective configs (only libraries that actually exist)
    if IS_WINDOWS:
        all_configs = LIB_CONFIGS + LIB_CONFIGS_OCI
    else:
        all_configs = LIB_CONFIGS

    effective_configs = [c for c in all_configs if c[0] in files_in_dir]

    if not effective_configs:
        print("No relevant crypto libraries found. Skipping.")
        return

    # Detect Instant Client (Linux only: no srv libs)
    is_instant_client = False
    if not IS_WINDOWS:
        has_srv = any("srv" in c[0] and c[0] in files_in_dir for c in LIB_CONFIGS)
        is_instant_client = not has_srv

    # ------------------------------------------------------------
    # NEXT-GENERATION MODE → global coherence check (DB Home only)
    # ------------------------------------------------------------
    if mode == MODE_NEXT_GENERATION and not is_instant_client:
        missing = [
            next_gen for (_, next_gen, _) in effective_configs
            if not os.path.exists(os.path.join(lib_dir, next_gen))
        ]

        if missing:
            print("Coherence check failed. Missing next-gen libraries: {}".format(", ".join(missing)))
            return

    # ------------------------------------------------------------
    # LEGACY MODE → global pre-check (all-or-nothing restore)
    # ------------------------------------------------------------
    if mode == MODE_LEGACY:
        missing_backups = []
        critical_errors = []

        for target, next_gen, legacy in effective_configs:
            target_path = os.path.join(lib_dir, target)
            next_gen_path = os.path.join(lib_dir, next_gen)
            backup_path = os.path.join(lib_dir, legacy)

            if not os.path.exists(backup_path):
                if os.path.exists(target_path) and os.path.exists(next_gen_path):
                    try:
                        if filecmp.cmp(target_path, next_gen_path, shallow=False):
                            critical_errors.append(target)
                    except Exception:
                        pass
                else:
                    missing_backups.append(target)

        if critical_errors:
            print("CRITICAL ERROR: Missing backups for next-gen libraries: {}".format(", ".join(critical_errors)))
            print("Aborting to prevent inconsistent restore.")
            return

        if missing_backups:
            print("Cannot restore legacy. Missing backups for: {}".format(", ".join(missing_backups)))
            print("Aborting to prevent partial restore.")
            return

    # ------------------------------------------------------------
    # Perform switching (safe after all checks)
    # ------------------------------------------------------------
    for target, next_gen, legacy in effective_configs:
        perform_single_switch(lib_dir, target, next_gen, legacy, mode)


def recursive_search_and_switch(root_dir, mode):

    print("\nSearching from: {}\n".format(root_dir))

    # Accept directory if ANY relevant library is present
    if IS_WINDOWS:
        all_configs = LIB_CONFIGS + LIB_CONFIGS_OCI
    else:
        all_configs = LIB_CONFIGS

    required = set([c[0] for c in all_configs])

    for dirpath, _, filenames in os.walk(root_dir):
        if any(f in filenames for f in required):
            switch_library(dirpath, mode)


def files_match(path1, path2):
    try:
        return (os.path.isfile(path1) and
                os.path.isfile(path2) and
                filecmp.cmp(path1, path2, shallow=False))
    except Exception:
        return False

def get_mode():
    """
    Determines the current crypto provider mode by comparing
    the legacy and next-gen libraries.
    """
    # Pick the canonical library pair
    target_lib, next_gen_lib, backup_lib = LIB_CONFIGS[0]

    lib_dirs = []

    oracle_home = os.environ.get("ORACLE_HOME")
    okv_home = os.environ.get("OKV_HOME")

    # 1. If custom directory is provided → use it
    if custom_directory:
        found_dirs = set()

        if IS_WINDOWS:
            all_configs = LIB_CONFIGS + LIB_CONFIGS_OCI
        else:
            all_configs = LIB_CONFIGS

        # Only consider target libraries (not .sym)
        target_libs = set([c[0] for c in all_configs])

        for dirpath, _, filenames in os.walk(custom_directory):
            if any(f in filenames for f in target_libs):
                found_dirs.add(dirpath)

        if not found_dirs:
            print("No crypto libraries found under {}".format(custom_directory))
            return "UNKNOWN"

        lib_dirs.extend(sorted(found_dirs))
    # 2. else use ORACLE_HOME/OKV_HOME if defined
    elif oracle_home or okv_home:
         if oracle_home:
            lib_dirs.append(os.path.join(oracle_home, LIB_DIR_NAME))
         if okv_home:
            lib_dirs.append(os.path.join(okv_home, LIB_DIR_NAME))

    # 3. Else fallback to current working directory
    else:
        cwd = os.getcwd()
        lib_dirs.append(cwd)
        print("Using current directory for detection: {}".format(cwd))

    for lib_dir in lib_dirs:
        target_lib_path = os.path.join(lib_dir, target_lib)
        next_gen_path = os.path.join(lib_dir, next_gen_lib)
        backup_lib_path = os.path.join(lib_dir, backup_lib)

        target_lib_exists = os.path.isfile(target_lib_path)
        next_gen_exists = os.path.isfile(next_gen_path)
        backup_lib_exists = os.path.isfile(backup_lib_path)
        # Skip directories where nothing relevant exists
        if not (target_lib_exists or next_gen_exists or backup_lib_exists):
            continue

        # If target missing, cannot determine mode → try next dir
        if not target_lib_exists:
            continue

        try:
            # 1. Exact match with next-gen
            if next_gen_exists and files_match(target_lib_path, next_gen_path):
                return "Next Generation"

            # 2. Match target with backup
            if backup_lib_exists and files_match(target_lib_path, backup_lib_path):
                return "Legacy"

            # 3. Heuristic: next-gen exists but target differs: likely legacy
            if next_gen_exists:
                return "Legacy"

            # 4. If only target exists, assume legacy (for instantclient)
            if not next_gen_exists and not backup_lib_exists:
                return "Legacy"

            # 5. Otherwise ambiguous
            return "UNKNOWN"
        except Exception as e:
            print("Warning: comparison failed in {}: {}".format(lib_dir, e))
            continue

    return "UNKNOWN"

def print_usage_and_exit(exit_code=1, msg=None):
    if msg:
        print(msg)
    print("Usage (Status): python set_crypto_provider.py status")
    print("Usage (Env Mode): python set_crypto_provider.py [next-generation|legacy]")
    print("Usage (Recursive Mode): python set_crypto_provider.py [next-generation|legacy] <directory>")
    sys.exit(exit_code)

# --- Main Execution ---

if __name__ == "__main__":

    # No args => show help, exit
    if len(sys.argv) == 1:
        print_usage_and_exit(1)

    # Too many args => show help, exit
    if len(sys.argv) > 3:
        print_usage_and_exit(1, "Error: Too many arguments.")

    mode = None
    custom_directory = None

    # Parse args
    if len(sys.argv) >= 2:
        mode = sys.argv[1].lower()

    if len(sys.argv) == 3:
        custom_directory = sys.argv[2]
 
    if mode not in (MODE_NEXT_GENERATION, MODE_LEGACY, MODE_STATUS):
        print_usage_and_exit(1, "Invalid mode. Must be next-generation, legacy, or status")

    # Status-only mode: query current provider and exit without modifications
    if mode == MODE_STATUS:
        print("Current mode is: {}".format(get_mode()))
        sys.exit(0)

    provider_mode = mode
    print("Current mode is: {}".format(get_mode()))

    if custom_directory:
        if not os.path.isdir(custom_directory):
            print_usage_and_exit(1, "Error: The provided path is not a valid directory: {}".format(custom_directory))
        recursive_search_and_switch(custom_directory, provider_mode)

    else:
        # No custom directory: fall back to the original environment variable logic
        print("\nUsing ENVIRONMENT VARIABLE search (No custom directory specified).")
        lib_paths = get_env_lib_paths()

        if not lib_paths:
            print_usage_and_exit(1, "Error: Neither OKV_HOME nor ORACLE_HOME environment variables are set.")

        for lib_dir in lib_paths:
            switch_library(lib_dir, provider_mode)
