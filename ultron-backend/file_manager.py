"""
Ultron File Manager & Media Orchestrator
Enables Ultron to search and open files from Windows File Explorer across all drives.
- Video files (.mp4, .mkv, .avi, etc.) STRICTLY open in VLC Media Player only.
- Documents (PDF, PPT, DOC, Excel, Text, Images, etc.) open in their system default programs.
- Searches user standard directories and D: drive first, then C: drive, excluding system folders.
- Caches discovered files for sub-millisecond retrieval.
"""
import os
import sys
import re
import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Callable
from rapidfuzz import fuzz
from config import DATA_DIR

FILE_CACHE_FILE = DATA_DIR / "file_cache.json"

# Protected, system, or development folders that must NEVER be searched
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

# Categorized supported file extensions
FILE_CATEGORIES = {
    "video": {
        "extensions": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".3gp", ".ts", ".mpg", ".mpeg"},
        "keywords": ["video", "videos", "movie", "movies", "film", "films", "clip", "clips", "episode", "episodes", "show", "series", "vlc"],
        "open_with": "vlc",
        "label": "video"
    },
    "pdf": {
        "extensions": {".pdf"},
        "keywords": ["pdf", "pdfs", "ebook"],
        "open_with": "default",
        "label": "PDF"
    },
    "ppt": {
        "extensions": {".ppt", ".pptx", ".pps", ".ppsx", ".odp"},
        "keywords": ["ppt", "pptx", "presentation", "presentations", "slides", "slide", "powerpoint", "deck", "pitch deck"],
        "open_with": "default",
        "label": "presentation"
    },
    "doc": {
        "extensions": {".doc", ".docx", ".odt", ".rtf", ".dotx"},
        "keywords": ["doc", "docx", "word", "document", "documents", "paper", "report", "notes"],
        "open_with": "default",
        "label": "document"
    },
    "excel": {
        "extensions": {".xls", ".xlsx", ".csv", ".ods"},
        "keywords": ["excel", "sheet", "sheets", "spreadsheet", "csv", "workbook"],
        "open_with": "default",
        "label": "spreadsheet"
    },
    "image": {
        "extensions": {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".ico"},
        "keywords": ["image", "images", "photo", "photos", "picture", "pictures", "pic", "pics"],
        "open_with": "default",
        "label": "image"
    },
    "audio": {
        "extensions": {".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma"},
        "keywords": ["song", "songs", "music", "audio", "track", "tracks"],
        "open_with": "vlc",
        "label": "audio"
    },
    "text": {
        "extensions": {".txt", ".md", ".json", ".py", ".c", ".cpp", ".html", ".css", ".js"},
        "keywords": ["txt", "text", "notes", "note", "memo", "code"],
        "open_with": "default",
        "label": "text"
    }
}

ALL_SUPPORTED_EXTENSIONS = set()
EXT_TO_CATEGORY: Dict[str, str] = {}
for cat, info in FILE_CATEGORIES.items():
    for ext in info["extensions"]:
        ALL_SUPPORTED_EXTENSIONS.add(ext)
        EXT_TO_CATEGORY[ext] = cat

EXCLUDED_EXTENSIONS = {
    ".sys", ".dll", ".exe", ".ini", ".lnk", ".bat", ".tmp", ".log", ".dat",
    ".bak", ".cab", ".msi", ".cat", ".inf", ".bin", ".iso", ".cmd", ".vbs"
}

class FileManager:
    FILE_CATEGORIES = FILE_CATEGORIES
    EXT_TO_CATEGORY = EXT_TO_CATEGORY

    def __init__(self):
        self.user_home = Path.home()
        self.onedrive = self.user_home / "OneDrive"
        self.vlc_path = self._detect_vlc_path()
        self.cache: Dict[str, str] = self._load_cache()
        print(f"[FileManager] Initialized. VLC Path: {self.vlc_path or 'Not Found'}")

    def _detect_vlc_path(self) -> Optional[str]:
        """Locates the VLC Media Player executable on Windows."""
        candidates = [
            r"C:\Program Files\VideoLAN\VLC\vlc.exe",
            r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
            os.path.expandvars(r"%ProgramFiles%\VideoLAN\VLC\vlc.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\VideoLAN\VLC\vlc.exe"),
            os.path.expandvars(r"%LocalAppData%\Programs\VideoLAN\VLC\vlc.exe"),
        ]
        for p in candidates:
            if os.path.isfile(p):
                return p

        # Check system PATH
        w = shutil.which("vlc") or shutil.which("vlc.exe")
        if w and os.path.isfile(w):
            return w

        # Check Windows Registry
        try:
            import winreg
            for root in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                for subkey in [
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\vlc.exe",
                    r"SOFTWARE\VideoLAN\VLC"
                ]:
                    try:
                        with winreg.OpenKey(root, subkey) as key:
                            val, _ = winreg.QueryValueEx(key, "" if "App Paths" in subkey else "InstallDir")
                            if "InstallDir" in subkey:
                                val = os.path.join(val, "vlc.exe")
                            if os.path.isfile(val):
                                return val
                    except Exception:
                        pass
        except Exception:
            pass

        return None

    def _load_cache(self) -> Dict[str, str]:
        if FILE_CACHE_FILE.exists():
            try:
                with open(FILE_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return {k: v for k, v in data.items() if os.path.isfile(v)}
            except Exception:
                pass
        return {}

    def _save_cache(self):
        try:
            with open(FILE_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def clean_query(self, raw_query: str) -> Tuple[Optional[str], str]:
        """
        Extracts target file category and cleans user spoken query into target filename search string.
        e.g. 'open bigg boss video' -> ('video', 'bigg boss')
             'play breaking bad episode 2' -> ('video', 'breaking bad e02')
             'open pitch deck ppt' -> ('ppt', 'pitch deck')
             'open coep hostel fee pdf' -> ('pdf', 'coep hostel fee')
        """
        q = raw_query.lower().strip()

        # 1. Detect Category
        detected_cat = None
        for cat, info in FILE_CATEGORIES.items():
            if any(re.search(r'\b' + re.escape(kw) + r'\b', q) for kw in info["keywords"]):
                detected_cat = cat
                break

        if not detected_cat:
            for ext, cat in EXT_TO_CATEGORY.items():
                if ext in q:
                    detected_cat = cat
                    break

        if not detected_cat and q.startswith("play "):
            detected_cat = "video"

        # 2. Clean conversational prefixes
        q = re.sub(r"^(?:can you\s+|could you\s+|please\s+|will you\s+)?(?:open|play|launch|start|find|access|show|view|explore)\s+(?:up\s+)?(?:my\s+|the\s+)?", "", q)
        # Remove "in/on/with vlc"
        q = re.sub(r"\s+(?:in|with|on)\s+vlc\b", "", q)
        # Remove polite suffixes
        q = re.sub(r"\s+(?:for me|please)$", "", q)
        # Remove trailing "in drive d", "on drive d", "in d drive", etc.
        q = re.sub(r"\s+(?:in|on)\s+(?:drive\s+[a-zA-Z]|[a-zA-Z]\s+drive|[a-zA-Z]:?)$", "", q)
        # Remove leading category descriptors: "video bigg boss", "pdf hostel fee", "file report"
        q = re.sub(r"^(?:video|movie|film|pdf|ppt|pptx|presentation|doc|docx|document|file|notes|spreadsheet)\s+", "", q)
        # Remove trailing category descriptors: "bigg boss video", "hostel fee pdf", "report file"
        q = re.sub(r"\s+(?:video|movie|film|pdf|ppt|pptx|presentation|doc|docx|document|file|notes|spreadsheet)$", "", q)

        # Normalize season/episode numbers (e.g. "episode 2" -> "e02", "season 2" -> "s02")
        q = re.sub(r"\b(?:episode|ep)\s*(\d)\b", r"e0\1", q)
        q = re.sub(r"\b(?:episode|ep)\s*(\d{2,})\b", r"e\1", q)
        q = re.sub(r"\b(?:season|s)\s*(\d)\b", r"s0\1", q)
        q = re.sub(r"\b(?:season|s)\s*(\d{2,})\b", r"s\1", q)

        q = q.strip()
        return detected_cat, q

    def _get_tokens(self, text: str) -> List[str]:
        t = text.lower()
        t = re.sub(r"\b(?:episode|ep)\s*(\d)\b", r"e0\1", t)
        t = re.sub(r"\b(?:episode|ep)\s*(\d{2,})\b", r"e\1", t)
        t = re.sub(r"\b(?:season|s)\s*(\d)\b", r"s0\1", t)
        t = re.sub(r"\b(?:season|s)\s*(\d{2,})\b", r"s\1", t)
        tokens = re.split(r"[^a-zA-Z0-9]+", t)
        stop_words = {"the", "a", "an", "my", "in", "of", "and", "or", "for", "to", "at", "by", "on"}
        return [x for x in tokens if len(x) > 0 and x not in stop_words]

    def score_file(self, file_path: str, target_clean: str, target_cat: Optional[str]) -> int:
        """Calculates matching score between target search query and file."""
        name = os.path.basename(file_path)
        stem, ext = os.path.splitext(name)
        stem_lower = stem.lower()
        ext_lower = ext.lower()
        file_cat = EXT_TO_CATEGORY.get(ext_lower)

        # Exclude system files and temp lock files
        if ext_lower in EXCLUDED_EXTENSIONS or stem_lower.startswith((".", "~$")):
            return 0

        stem_tokens = self._get_tokens(stem_lower)
        target_tokens = self._get_tokens(target_clean)

        if not target_tokens:
            return 0

        # Category score modifier
        cat_bonus = 0
        if target_cat:
            if file_cat == target_cat:
                cat_bonus = 15
            else:
                cat_bonus = -30

        clean_stem_str = " ".join(stem_tokens)
        clean_target_str = " ".join(target_tokens)

        # 1. Exact stem match
        if clean_stem_str == clean_target_str:
            return 100 + cat_bonus

        # 2. All target tokens present in filename tokens
        all_present = all(any(tt == st or (len(tt) >= 4 and tt in st) for st in stem_tokens) for tt in target_tokens)
        if all_present:
            return 95 + cat_bonus

        # 3. Substring match
        if clean_target_str in clean_stem_str:
            return 90 + cat_bonus

        # 4. Fuzzy token set ratio
        ratio = fuzz.token_set_ratio(clean_target_str, clean_stem_str)
        if ratio >= 75:
            return int(ratio) + cat_bonus

        return 0

    def clean_title_for_speech(self, filename: str) -> str:
        """Strips technical release metadata, hashes, and emojis for smooth voice output."""
        stem = filename.rsplit(".", 1)[0]
        # Remove emojis
        emoji_pattern = re.compile(
            "[\U00010000-\U0010ffff]|[\uD800-\uDBFF][\uDC00-\uDFFF]|[\u2600-\u27BF]|[\u2300-\u23FF]|[\ufe00-\ufe0f]|[\u200d]",
            flags=re.UNICODE
        )
        stem = emoji_pattern.sub("", stem)
        # Remove release tags e.g. 720p, 1080p, BluRay, WEB-DL, x264, etc.
        stem = re.sub(
            r"(?i)\b(?:720p|1080p|2160p|4k|bluray|web-?dl|brrip|dvdrip|x264|x265|hevc|hindi|english|org|esub|hdhub4u|tv|ms)\b.*$",
            "",
            stem
        )
        # Clean special chars to spaces
        stem = re.sub(r"[-_.]+", " ", stem).strip()
        return stem.title() if stem else filename.rsplit(".", 1)[0]

    def find_file(self, raw_query: str, is_cancelled: Optional[Callable[[], bool]] = None) -> Tuple[Optional[str], str, Optional[str]]:
        """
        Searches for a matching file across user directories and drives.
        Returns (file_path_or_None, status_info, detected_category).
        """
        target_cat, target_clean = self.clean_query(raw_query)
        if not target_clean:
            return None, "Empty search query", None

        print(f"[FileManager] Searching for file: '{target_clean}' (Category: {target_cat or 'any'})")

        # Check Cache first (<1ms)
        cache_key = f"{target_cat or 'any'}:{target_clean}"
        if cache_key in self.cache:
            cached_path = self.cache[cache_key]
            if os.path.isfile(cached_path):
                print(f"[FileManager] Cache hit: '{cache_key}' -> {cached_path}")
                return cached_path, "cache", target_cat
        if target_clean in self.cache:
            cached_path = self.cache[target_clean]
            if os.path.isfile(cached_path):
                print(f"[FileManager] Cache hit: '{target_clean}' -> {cached_path}")
                return cached_path, "cache", target_cat

        candidates: List[Tuple[str, int]] = []

        # -------------------------------------------------------------
        # STEP 1: Quick Search in Standard User Folders (High probability)
        # -------------------------------------------------------------
        user_dirs = [
            self.user_home / "Downloads",
            self.user_home / "Videos",
            self.user_home / "Documents",
            self.onedrive / "Documents",
            self.user_home / "Desktop",
            self.onedrive / "Desktop",
            self.user_home / "Pictures",
            self.onedrive / "Pictures",
            self.user_home / "Music"
        ]

        for udir in user_dirs:
            if is_cancelled and is_cancelled():
                return None, "Cancelled", target_cat
            if not udir.is_dir():
                continue
            try:
                for root, dirs, files in os.walk(str(udir)):
                    if is_cancelled and is_cancelled():
                        return None, "Cancelled", target_cat
                    dirs[:] = [d for d in dirs if d.lower() not in SYSTEM_EXCLUDED_FOLDERS and not d.startswith(".")]
                    rel = os.path.relpath(root, str(udir))
                    if rel != "." and len(Path(rel).parts) > 3:
                        continue
                    for f in files:
                        if f.startswith((".", "~$")):
                            continue
                        full_p = os.path.join(root, f)
                        sc = self.score_file(full_p, target_clean, target_cat)
                        if sc >= 75:
                            candidates.append((full_p, sc))
                            if sc >= 105:  # High confidence match with category bonus
                                break
                    if candidates and max(candidates, key=lambda x: x[1])[1] >= 110:
                        break
            except Exception:
                continue

            if candidates and max(candidates, key=lambda x: x[1])[1] >= 110:
                break

        # If high-confidence match found in user folders, return it immediately!
        if candidates:
            best_p, best_sc = max(candidates, key=lambda x: x[1])
            if best_sc >= 105:
                print(f"[FileManager] Immediate high-confidence match found: {best_p} (Score: {best_sc})")
                self.cache[cache_key] = best_p
                self.cache[target_clean] = best_p
                self._save_cache()
                return best_p, "user_folders (exact)", target_cat

        # -------------------------------------------------------------
        # STEP 2: D: Drive Search (D: root and all subfolders up to depth 5)
        # -------------------------------------------------------------
        if os.path.exists("D:\\"):
            print("[FileManager] Step 2: Searching D: drive...")
            try:
                for root, dirs, files in os.walk("D:\\"):
                    if is_cancelled and is_cancelled():
                        return None, "Cancelled", target_cat
                    dirs[:] = [d for d in dirs if d.lower() not in SYSTEM_EXCLUDED_FOLDERS and not d.startswith(".")]
                    rel = os.path.relpath(root, "D:\\")
                    if rel != "." and len(Path(rel).parts) > 5:
                        continue
                    for f in files:
                        if f.startswith((".", "~$")):
                            continue
                        full_p = os.path.join(root, f)
                        sc = self.score_file(full_p, target_clean, target_cat)
                        if sc >= 75:
                            candidates.append((full_p, sc))
                            if sc >= 105:
                                break
                    if candidates and max(candidates, key=lambda x: x[1])[1] >= 110:
                        break
            except Exception:
                pass

        if is_cancelled and is_cancelled():
            return None, "Cancelled", target_cat

        # -------------------------------------------------------------
        # STEP 3: Deep search on C: Drive (Non-system user roots)
        # -------------------------------------------------------------
        if not candidates or max(candidates, key=lambda x: x[1])[1] < 90:
            print("[FileManager] Step 3: Searching C: drive user directories...")
            try:
                with os.scandir("C:\\") as it:
                    for entry in it:
                        if entry.is_dir(follow_symlinks=False):
                            n_low = entry.name.lower()
                            if n_low not in SYSTEM_EXCLUDED_FOLDERS and not n_low.startswith(".") and n_low != "users":
                                for root, dirs, files in os.walk(entry.path):
                                    if is_cancelled and is_cancelled():
                                        return None, "Cancelled", target_cat
                                    dirs[:] = [d for d in dirs if d.lower() not in SYSTEM_EXCLUDED_FOLDERS and not d.startswith(".")]
                                    rel = os.path.relpath(root, entry.path)
                                    if rel != "." and len(Path(rel).parts) > 3:
                                        continue
                                    for f in files:
                                        if f.startswith((".", "~$")):
                                            continue
                                        full_p = os.path.join(root, f)
                                        sc = self.score_file(full_p, target_clean, target_cat)
                                        if sc >= 75:
                                            candidates.append((full_p, sc))
            except Exception:
                pass

        if candidates:
            # Sort by score descending, then by file modification time (newer preferred)
            candidates.sort(key=lambda x: (x[1], os.path.getmtime(x[0]) if os.path.exists(x[0]) else 0), reverse=True)
            best_path, best_score = candidates[0]
            if best_score >= 75:
                print(f"[FileManager] Best match found: {best_path} (Score: {best_score})")
                self.cache[cache_key] = best_path
                self.cache[target_clean] = best_path
                self._save_cache()
                return best_path, f"score_{best_score}", target_cat

        print(f"[FileManager] File '{target_clean}' not found.")
        return None, "Not found", target_cat

    def open_file(self, file_path: str) -> Tuple[bool, str]:
        """
        Opens the specified file:
        - Videos are strictly opened with VLC Media Player.
        - Other files (PDF, PPT, DOC, etc.) are opened with the Windows system default handler.
        """
        abs_path = os.path.abspath(file_path)
        if not os.path.isfile(abs_path):
            return False, f"File does not exist: {abs_path}"

        norm_path = os.path.normpath(abs_path)
        filename = os.path.basename(norm_path)
        ext = os.path.splitext(norm_path)[1].lower()
        clean_title = self.clean_title_for_speech(filename)

        is_video = ext in FILE_CATEGORIES["video"]["extensions"]

        if is_video:
            # VIDEO -> STRICTLY VLC ONLY
            vlc_exe = self.vlc_path or self._detect_vlc_path()
            if not vlc_exe or not os.path.isfile(vlc_exe):
                return False, f"I found {clean_title}, but VLC Media Player is not installed on your system, boss."

            print(f"[FileManager] Opening video in VLC: '{norm_path}' using '{vlc_exe}'")
            try:
                subprocess.Popen([vlc_exe, norm_path])
                return True, f"Opening {clean_title} in VLC, boss."
            except Exception as e:
                return False, f"Failed to launch VLC for {clean_title}: {e}"
        else:
            # NON-VIDEO -> Open with default Windows application (PDF viewer, PowerPoint, Word, Excel, etc.)
            print(f"[FileManager] Opening document with default program: '{norm_path}'")
            try:
                os.startfile(norm_path)
                return True, f"Opening {clean_title}, boss."
            except Exception as e:
                try:
                    subprocess.Popen(["cmd", "/c", "start", "", norm_path], shell=True)
                    return True, f"Opening {clean_title}, boss."
                except Exception as e2:
                    return False, f"I located {clean_title}, but could not open it: {e2}"

    def find_and_open(self, raw_query: str, is_cancelled: Optional[Callable[[], bool]] = None) -> Tuple[bool, str, Optional[str]]:
        """
        High-level orchestrator: parses natural command, searches drives, and opens file.
        Returns (success, spoken_message, file_path_or_None).
        """
        file_path, match_info, target_cat = self.find_file(raw_query, is_cancelled=is_cancelled)
        _, target_clean = self.clean_query(raw_query)

        if is_cancelled and is_cancelled():
            return False, "Cancelled", None

        if file_path and os.path.isfile(file_path):
            success, msg = self.open_file(file_path)
            return success, msg, file_path
        else:
            cat_label = FILE_CATEGORIES.get(target_cat, {}).get("label", "file") if target_cat else "file"
            display_q = target_clean.title() if target_clean else "requested"
            spoken = f"I searched your files and drives, boss, but could not find the {display_q} {cat_label}."
            return False, spoken, None
