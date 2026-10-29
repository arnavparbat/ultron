"""
Ultron Folder Manager & File Explorer Automation
Recursively searches and opens user folders in Windows File Explorer.
Strictly searches D: drive first, then C: drive, while excluding protected and system folders.
"""
import os
import re
import json
import subprocess
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Callable
from rapidfuzz import fuzz
from config import DATA_DIR

FOLDER_CACHE_FILE = DATA_DIR / "folder_cache.json"

# Protected, system, or development folders that must NEVER be searched or altered
SYSTEM_EXCLUDED_FOLDERS = {
    # Windows system & OS directories
    "windows", "winnt", "system32", "syswow64", "winsxs", "servicing",
    "$recycle.bin", "system volume information", "recovery", "boot", "bootmgr",
    "program files", "program files (x86)", "programdata", "perflogs", "msocache",
    "windowsapps", "wpsystem", "microsoft", "appdata", "locallow", "application data",
    "documents and settings", "config.msi",
    # Development / build / environment directories
    ".git", ".svn", ".hg", "node_modules", "__pycache__", ".cache",
    ".vscode", ".vscode-shared", ".gemini", ".insomniac", ".ssh",
    "venv", "env", ".env", "site-packages", "dist", "build",
    # Temporary caches
    "temp", "tmp", "msdownld.tmp"
}

class FolderManager:
    def __init__(self):
        self.cache: Dict[str, str] = self._load_cache()
        self.user_home = Path.home()  # C:\Users\ASUS
        self.onedrive = self.user_home / "OneDrive"
        self._init_standard_shortcuts()

    def _init_standard_shortcuts(self):
        """Initializes direct instant paths for Windows standard user directories."""
        standard_map = {
            "downloads": self.user_home / "Downloads",
            "download": self.user_home / "Downloads",
            "videos": self.user_home / "Videos",
            "video": self.user_home / "Videos",
            "music": self.user_home / "Music",
            "songs": self.user_home / "Music",
            "ultron": self.user_home / "Ultron"
        }

        # Documents (check OneDrive then user_home)
        if (self.onedrive / "Documents").is_dir():
            standard_map["documents"] = self.onedrive / "Documents"
            standard_map["document"] = self.onedrive / "Documents"
            standard_map["docs"] = self.onedrive / "Documents"
        elif (self.user_home / "Documents").is_dir():
            standard_map["documents"] = self.user_home / "Documents"
            standard_map["document"] = self.user_home / "Documents"
            standard_map["docs"] = self.user_home / "Documents"

        # Desktop (check OneDrive then user_home)
        if (self.onedrive / "Desktop").is_dir():
            standard_map["desktop"] = self.onedrive / "Desktop"
        elif (self.user_home / "Desktop").is_dir():
            standard_map["desktop"] = self.user_home / "Desktop"

        # Pictures (check OneDrive then user_home)
        if (self.onedrive / "Pictures").is_dir():
            standard_map["pictures"] = self.onedrive / "Pictures"
            standard_map["photos"] = self.onedrive / "Pictures"
            standard_map["images"] = self.onedrive / "Pictures"
        elif (self.user_home / "Pictures").is_dir():
            standard_map["pictures"] = self.user_home / "Pictures"
            standard_map["photos"] = self.user_home / "Pictures"
            standard_map["images"] = self.user_home / "Pictures"

        for k, path in standard_map.items():
            if path.is_dir():
                self.cache[k] = str(path)

    def _load_cache(self) -> Dict[str, str]:
        if FOLDER_CACHE_FILE.exists():
            try:
                with open(FOLDER_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return {k: v for k, v in data.items() if os.path.isdir(v)}
            except Exception:
                pass
        return {}

    def _save_cache(self):
        try:
            with open(FOLDER_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2)
        except Exception:
            pass

    def clean_query(self, query: str) -> str:
        """Cleans user spoken query into target folder search string."""
        q = query.lower().strip()
        # Remove polite prefixes
        q = re.sub(r"^(?:can you\s+|could you\s+|please\s+)?(?:open|access|show|view|find|go to|explore|launch)\s+", "", q)
        # Remove polite suffixes
        q = re.sub(r"\s+(?:for me|please)$", "", q)
        # Remove trailing "in drive d", "in drive c", "on drive d", "in d drive"
        q = re.sub(r"\s+(?:in|on)\s+(?:drive\s+[a-zA-Z]|[a-zA-Z]\s+drive|[a-zA-Z]:?)$", "", q)
        # Remove leading 'my', 'the'
        q = re.sub(r"^(?:my|the)\s+", "", q)
        # Remove trailing 'folder', 'directory', 'dir'
        q = re.sub(r"\s+(?:folder|directory|dir)$", "", q)
        # Remove leading 'folder', 'directory' (e.g. 'folder social internship')
        q = re.sub(r"^(?:folder|directory)\s+(?:named\s+|called\s+)?", "", q)
        # Second pass trailing 'folder' if it was before 'in drive d'
        q = re.sub(r"\s+(?:folder|directory|dir)$", "", q)
        # Clean special chars to spaces
        q = re.sub(r"[-_]+", " ", q).strip()
        return q

    def _search_directory_tree(self, root_path: str, target_clean: str, max_depth: int = 5,
                               is_cancelled: Optional[Callable[[], bool]] = None) -> Tuple[Optional[str], List[Tuple[str, str, int]]]:
        """
        BFS search of directory tree starting at root_path.
        Returns (exact_match_path_or_None, list_of_partial_candidates).
        """
        if not os.path.isdir(root_path):
            return None, []

        queue = [(os.path.abspath(root_path), 0)]
        candidates = []

        while queue:
            if is_cancelled and is_cancelled():
                return None, []

            curr_dir, depth = queue.pop(0)
            try:
                with os.scandir(curr_dir) as entries:
                    for entry in entries:
                        try:
                            if not entry.is_dir(follow_symlinks=False):
                                continue
                        except OSError:
                            continue

                        name_lower = entry.name.lower()
                        # Strict system folder and hidden file exclusion
                        if name_lower in SYSTEM_EXCLUDED_FOLDERS or name_lower.startswith("."):
                            continue

                        name_clean = re.sub(r"[-_ ]+", " ", name_lower).strip()

                        # 1. Exact match -> return immediately
                        if name_clean == target_clean:
                            return entry.path, []

                        # 2. Substring match
                        # Query is inside folder name (e.g. "internship" in "social internship")
                        if len(target_clean) >= 3 and target_clean in name_clean:
                            ratio = len(target_clean) / len(name_clean)
                            score = int(85 + (10 * ratio))
                            candidates.append((entry.path, name_clean, score))
                        # Folder name is inside query only if folder name is substantial and covers majority of query
                        elif len(name_clean) >= 4 and len(name_clean) / len(target_clean) >= 0.7 and name_clean in target_clean:
                            score = int(80 * (len(name_clean) / len(target_clean)))
                            if score >= 70:
                                candidates.append((entry.path, name_clean, score))
                        else:
                            # 3. Fuzzy match check
                            ratio = int(fuzz.ratio(target_clean, name_clean))
                            if ratio >= 80:
                                candidates.append((entry.path, name_clean, ratio))

                        # Traverse subfolders up to max_depth
                        if depth < max_depth:
                            queue.append((entry.path, depth + 1))

            except (PermissionError, OSError):
                continue

        return None, candidates

    def find_folder(self, raw_query: str, is_cancelled: Optional[Callable[[], bool]] = None) -> Tuple[Optional[str], str]:
        """
        Searches for a folder matching raw_query.
        PRIORITY ORDER:
        1. D: Drive FIRST (root and all subfolders)
        2. C: Drive SECOND (User home, OneDrive, non-system folders, and subfolders)
        Returns (found_path_or_None, status_description).
        """
        target = self.clean_query(raw_query)
        if not target:
            return None, "Empty folder name"

        print(f"[FolderManager] Searching for folder: '{target}' (Search Priority: D: drive -> C: drive)")

        # Direct drive root shortcuts
        if target in ["d", "d drive", "drive d", "d:"]:
            if os.path.isdir("D:\\"):
                return "D:\\", "D: drive root"
        if target in ["c", "c drive", "drive c", "c:"]:
            if os.path.isdir("C:\\"):
                return "C:\\", "C: drive root"
        if target in ["file explorer", "explorer", "my computer", "this pc"]:
            return str(self.user_home), "File Explorer"

        # Check Cache first (<1ms)
        if target in self.cache:
            cached_path = self.cache[target]
            if os.path.isdir(cached_path):
                print(f"[FolderManager] Cache hit: '{target}' -> {cached_path}")
                return cached_path, "cache"

        has_d_drive = os.path.isdir("D:\\")
        has_c_drive = os.path.isdir("C:\\")

        # -------------------------------------------------------------
        # STEP 1: Search D: DRIVE FIRST (Fully searched)
        # -------------------------------------------------------------
        candidates_d = []
        if has_d_drive:
            print("[FolderManager] Step 1: Searching D: drive (root and subfolders)...")
            exact_d, candidates_d = self._search_directory_tree("D:\\", target, max_depth=5, is_cancelled=is_cancelled)
            if exact_d:
                print(f"[FolderManager] Exact match found on D: drive: {exact_d}")
                self.cache[target] = exact_d
                self._save_cache()
                return exact_d, "D: drive (exact)"

            # If candidates were found on D: with high confidence (>=90)
            high_d = [c for c in candidates_d if c[2] >= 90]
            if high_d:
                best_d = max(high_d, key=lambda x: x[2])
                print(f"[FolderManager] High-confidence match on D: drive: {best_d[0]}")
                self.cache[target] = best_d[0]
                self._save_cache()
                return best_d[0], "D: drive (high confidence)"

        if is_cancelled and is_cancelled():
            return None, "Cancelled"

        # -------------------------------------------------------------
        # STEP 2: Search C: DRIVE SECOND (If not found in D:)
        # -------------------------------------------------------------
        print("[FolderManager] Step 2: D: drive search completed. Searching C: drive...")
        c_search_roots = []

        # Prioritize user directory and OneDrive
        if self.user_home.is_dir():
            c_search_roots.append(str(self.user_home))
        if self.onedrive.is_dir() and str(self.onedrive) not in c_search_roots:
            c_search_roots.append(str(self.onedrive))

        # Also non-system roots on C:\ (e.g. C:\Projects, C:\data, etc.)
        if has_c_drive:
            try:
                with os.scandir("C:\\") as it:
                    for entry in it:
                        if entry.is_dir(follow_symlinks=False):
                            n_low = entry.name.lower()
                            if n_low not in SYSTEM_EXCLUDED_FOLDERS and not n_low.startswith(".") and n_low != "users":
                                c_search_roots.append(entry.path)
            except Exception:
                pass

        candidates_c = []
        for c_root in c_search_roots:
            if is_cancelled and is_cancelled():
                return None, "Cancelled"
            exact_c, cands = self._search_directory_tree(c_root, target, max_depth=5, is_cancelled=is_cancelled)
            if exact_c:
                print(f"[FolderManager] Exact match found on C: drive: {exact_c}")
                self.cache[target] = exact_c
                self._save_cache()
                return exact_c, "C: drive (exact)"
            candidates_c.extend(cands)

        # -------------------------------------------------------------
        # STEP 3: Check Partial & Fuzzy Candidates (Prioritizing D: then C:)
        # -------------------------------------------------------------
        if has_d_drive and candidates_d:
            best_d = max(candidates_d, key=lambda x: x[2])
            if best_d[2] >= 80:
                print(f"[FolderManager] Best partial match found on D: drive: {best_d[0]} (Score: {best_d[2]})")
                self.cache[target] = best_d[0]
                self._save_cache()
                return best_d[0], "D: drive (fuzzy)"

        if candidates_c:
            best_c = max(candidates_c, key=lambda x: x[2])
            if best_c[2] >= 80:
                print(f"[FolderManager] Best partial match found on C: drive: {best_c[0]} (Score: {best_c[2]})")
                self.cache[target] = best_c[0]
                self._save_cache()
                return best_c[0], "C: drive (fuzzy)"

        print(f"[FolderManager] Folder '{target}' not found in D: or C: drives.")
        return None, "Not found"

    def open_folder(self, folder_path: str) -> Tuple[bool, str]:
        """Opens the specified directory in Windows File Explorer."""
        abs_path = os.path.abspath(folder_path)
        if not os.path.isdir(abs_path):
            return False, f"Folder does not exist: {abs_path}"

        norm_path = os.path.normpath(abs_path)
        print(f"[FolderManager] Launching File Explorer for: '{norm_path}'")

        try:
            os.startfile(norm_path)
            return True, f"Opened {os.path.basename(norm_path)} in File Explorer"
        except Exception as e:
            try:
                subprocess.Popen(["explorer.exe", norm_path])
                return True, f"Opened {os.path.basename(norm_path)} in File Explorer"
            except Exception as e2:
                return False, f"Could not launch File Explorer: {e2}"

    def find_and_open(self, query: str, is_cancelled: Optional[Callable[[], bool]] = None) -> Tuple[bool, str, Optional[str]]:
        """
        High-level orchestrator: cleans query, searches D: then C:, and opens File Explorer.
        Returns (success, spoken_message, folder_path_or_None).
        """
        path, match_info = self.find_folder(query, is_cancelled=is_cancelled)
        target_name = self.clean_query(query).title()
        if not target_name:
            target_name = "File Explorer"

        if is_cancelled and is_cancelled():
            return False, "Cancelled", None

        if path and os.path.isdir(path):
            norm_p = os.path.normpath(path)
            folder_base = os.path.basename(norm_p)
            if not folder_base:
                drive_ch = norm_p[0].upper()
                spoken = f"Opening {drive_ch} drive in File Explorer, boss."
            else:
                drive_letter = os.path.splitdrive(norm_p)[0].upper()
                drive_info = f" from {drive_letter} drive" if drive_letter else ""
                spoken = f"Opening {folder_base}{drive_info} in File Explorer, boss."

            success, msg = self.open_folder(path)
            if success:
                return True, spoken, path
            else:
                return False, f"I located {folder_base}, but could not launch File Explorer, boss.", path
        else:
            spoken = f"I searched your D drive and C drive, boss, but could not find the {target_name} folder."
            return False, spoken, None
