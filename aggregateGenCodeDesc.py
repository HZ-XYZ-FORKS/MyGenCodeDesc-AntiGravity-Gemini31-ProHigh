import argparse
import sys
import os
import json
import logging
import time
import subprocess
import datetime
import xml.etree.ElementTree as ET


# Ensure logging goes to stderr so stdout JSON remains clean
# AC-010-6: Structured log format for machine parsing
logger = logging.getLogger("AlgC")
handler = logging.StreamHandler(sys.stderr)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(name)s] %(message)s')
formatter.converter = time.gmtime # Use UTC time format constraint naturally
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

def _validate_gen_ratio_bounds(data):
    """Returns True if all genRatios in DETAIL bounded 0<=r<=100, else False."""
    for detail in data.get("DETAIL", []):
        for line in detail.get("codeLines", []) + detail.get("docLines", []):
            if not (0 <= line.get("genRatio", 0) <= 100):
                return False
    return True

def load_v2603_metadata(dir_path, expected_repo_url=None):
    store = {}
    if not os.path.exists(dir_path):
        return store
        
    for fname in os.listdir(dir_path):
        if not fname.endswith(".json"): continue
        file_path = os.path.join(dir_path, fname)
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                
                # Check repoURL
                repo = data.get("REPOSITORY", {})
                if expected_repo_url and repo.get("repoURL") != expected_repo_url:
                    continue
                    
                rev_id = repo.get("revisionId")
                if not rev_id: continue
                
                # AC-006-5: Assert valid ranges before taking ANY data
                if not _validate_gen_ratio_bounds(data):
                    logger.error(f"genRatio must be 0-100 in {fname}. Rejecting record.")
                    continue
                
                # AC-006-3: Duplicate tracking
                if rev_id in store:
                    logger.warning(f"Duplicate genCodeDesc found for revisionId {rev_id}. Overwriting.")
                    
                store[rev_id] = data
                logger.info(f"LOAD revisionId={rev_id}")
        except json.JSONDecodeError as e:
            logger.error(f"Validation error: Corrupt format in {fname}: {e}")
        except OSError as e:
            logger.error(f"IO Error reading {fname}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading {fname}: {e}")
            
    return store

def compute_core_metrics(lines, threshold=60):
    total_lines = len(lines)
    if total_lines == 0:
        return {
            "totalLines": 0,
            "weightedRatio": 0.0,
            "fullyAIRatio": 0.0,
            "mostlyAIRatio": 0.0
        }

    weighted_ratio = sum(line.get("genRatio", 0) for line in lines) / total_lines
    fully_ai_lines = sum(1 for line in lines if line.get("genRatio", 0) == 100)
    fully_ai_ratio = (fully_ai_lines / total_lines) * 100.0
    mostly_ai_lines = sum(1 for line in lines if line.get("genRatio", 0) >= threshold)
    mostly_ai_ratio = (mostly_ai_lines / total_lines) * 100.0

    return {
        "totalLines": total_lines,
        "weightedRatio": float(weighted_ratio),
        "fullyAIRatio": float(fully_ai_ratio),
        "mostlyAIRatio": float(mostly_ai_ratio)
    }

def resolve_gen_ratios(lines, metadata_store):
    resolved_lines = []
    for line in lines:
        c_hash = line.get("originCommit")
        fname = line.get("fileName")
        lineno = line.get("lineNumber")
        
        # If it was an old static mock
        if c_hash and "fileName" not in line:
            raw_ratio = metadata_store[c_hash].get("genRatio", 0.0) if c_hash in metadata_store else 0.0
            r_line = dict(line)
            r_line["genRatio"] = raw_ratio
            resolved_lines.append(r_line)
            continue
            
        gen_ratio = 0.0
        if c_hash in metadata_store:
            for file_detail in metadata_store[c_hash].get("DETAIL", []):
                if file_detail.get("fileName") == fname:
                    for c_line in file_detail.get("codeLines", []) + file_detail.get("docLines", []):
                        if c_line.get("lineLocation") == lineno:
                            gen_ratio = c_line.get("genRatio", 0)
                        elif "lineRange" in c_line:
                            if c_line["lineRange"]["from"] <= lineno <= c_line["lineRange"]["to"]:
                                gen_ratio = c_line.get("genRatio", 0)
        
        r_line = dict(line)
        r_line["genRatio"] = gen_ratio
        
        logger.debug(f"PROCESS file={fname} line={lineno} origin={c_hash} genRatio={gen_ratio}")
        resolved_lines.append(r_line)
    return resolved_lines


class LiveSnapshotTracker:
    def __init__(self):
        self.files = {}

    def add_file(self, path, lines):
        self.files[path] = list(lines)

    def rename_file(self, old_path, new_path):
        if old_path in self.files:
            self.files[new_path] = self.files.pop(old_path)

    def modify_lines(self, path, num_lines, new_gen_ratio):
        if path in self.files:
            for i in range(num_lines):
                if i < len(self.files[path]):
                    self.files[path][i] = {"genRatio": new_gen_ratio}

    def delete_file(self, path):
        if path in self.files:
            del self.files[path]

    def copy_file(self, old_path, new_path, new_gen_ratio):
        if old_path in self.files:
            new_lines = [{"genRatio": new_gen_ratio} for _ in self.files[old_path]]
            self.files[new_path] = new_lines

    def get_surviving_lines(self):
        lines = []
        for file_lines in self.files.values():
            lines.extend(file_lines)
        return lines


def run_git_blame_algA(work_dir):
    """
    Executes live `git blame --line-porcelain` to extract origin mappings.
    Returns: list of dicts: {"originCommit", "fileName", "lineNumber", "commitTime"}
    """
    logger.info("Starting Native AlgA (Live Blame) extraction...")
    
    # 1. Discover all source files tracked by Git
    try:
        ls_res = subprocess.run(
            ["git", "-C", work_dir, "ls-files"], 
            capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"VCS server unreachable / not a git repo: {e}")
        return []
        
    blame_lines = []
    files = ls_res.stdout.strip().split('\n')
    
    for f in files:
        if not f: continue
        # 2. Run blame on each file
        # -w: ignore whitespace
        # -M: detect move/rename in file
        # -C -C: detect moves across other files
        try:
            blame_res = subprocess.run(
                ["git", "-C", work_dir, "blame", "--line-porcelain", "-w", "-M", "-C", "-C", f],
                capture_output=True, text=True, check=True
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"git blame failed on {f}: {e}")
            continue
            
        current_commit = None
        current_time = None
        current_orig_line_num = None
        current_filename = None
        
        for line in blame_res.stdout.split('\n'):
            if not line: continue
            
            # The commit hash line is the start of a block
            # format: `<40-char-hash> <original-line> <final-line> <lines>`
            if len(line) >= 40 and " " in line:
                parts = line.split()
                if len(parts) >= 3 and len(parts[0]) >= 40:
                    current_commit = parts[0]
                    current_orig_line_num = int(parts[1])
                    continue
                    
            if line.startswith("author-time "):
                epoch = int(line.split(" ", 1)[1])
                # Convert to ISO8601
                current_time = datetime.datetime.utcfromtimestamp(epoch).strftime("%Y-%m-%dT%H:%M:%SZ")
                continue
                
            if line.startswith("filename "):
                current_filename = line.split(" ", 1)[1]
                continue
                
            if line.startswith("\t"):
                # End of block: the actual source code line
                if current_commit and current_time and current_orig_line_num is not None and current_filename:
                    blame_lines.append({
                        "originCommit": current_commit,
                        "fileName": current_filename,
                        "lineNumber": current_orig_line_num,
                        "commitTime": current_time
                    })
                    
    return blame_lines


def run_svn_blame_algA(work_dir):
    """
    Executes live `svn blame --xml` to extract origin mappings.
    Returns: list of dicts: {"originCommit", "fileName", "lineNumber", "commitTime"}
    """
    logger.info("Starting Native SVN AlgA (Live Blame) extraction...")
    
    import shutil
    import xml.etree.ElementTree as ET
    svn_bin = shutil.which("svn") or "/opt/homebrew/bin/svn"
    
    try:
        ls_res = subprocess.run(
            [svn_bin, "info", "-R", "--xml", "."],
            cwd=work_dir,
            capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"SVN server unreachable / not a working copy: {e}")
        return []
        
    blame_lines = []
    root = ET.fromstring(ls_res.stdout)
    files = []
    for entry in root.findall(".//entry[@kind='file']"):
        path = entry.get("path")
        if path:
            files.append(path)
    
    for f in files:
        if not f: continue
        try:
            blame_res = subprocess.run(
                [svn_bin, "blame", "--xml", f],
                cwd=work_dir,
                capture_output=True, text=True, check=True
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"svn blame failed on {f}: {e}")
            continue
            
        b_root = ET.fromstring(blame_res.stdout)
        for entry in b_root.findall(".//entry"):
            line_num = int(entry.get("line-number"))
            commit = entry.find("commit")
            if commit is not None:
                rev = commit.get("revision")
                date_xml = commit.find("date")
                date_val = date_xml.text if date_xml is not None else None
                
                if date_val:
                    # SVN XML dates: 2026-03-31T10:00:00.000000Z -> 2026-03-31T10:00:00Z
                    date_val = date_val.split('.')[0] + "Z"
                    
                if rev and date_val:
                    blame_lines.append({
                        "originCommit": rev,
                        "fileName": f,
                        "lineNumber": line_num,
                        "commitTime": date_val
                    })
                    
    return blame_lines


def run_algB(metadata_store, patches_dir, start_time, end_time):
    logger.info("Starting Native AlgB (Offline Diff Replay) extraction...")
    
    import os
    if not patches_dir or not os.path.isdir(patches_dir):
        logger.error(f"AlgB requires patchesDir, but '{patches_dir}' is invalid")
        return []
        
    commits = []
    for commit_id, data in metadata_store.items():
        ts = data.get("REPOSITORY", {}).get("commitTime", "1970-01-01T00:00:00Z")
        commits.append((ts, commit_id, data))
        
    commits.sort(key=lambda x: x[0])
    
    # Format: {filename: [(line_num, origin_commit, commit_time)]}
    surviving_files = {}
    
    for ts, commit_id, data in commits:
        if ts < start_time or ts > end_time: continue
        
        patch_file = os.path.join(patches_dir, f"{commit_id}.diff")
        if not os.path.exists(patch_file):
            logger.error(f"Missing diff patch for commit {commit_id}! Chain broken.")
            return [] # Fails gracefully AC-009-6
            
        with open(patch_file, "r") as f:
            lines = f.readlines()
            
        current_old = None
        current_new = None
        
        for p_line in lines:
            p_line = p_line.strip()
            if p_line.startswith("rename from "):
                current_old = p_line.split("rename from ")[1]
            elif p_line.startswith("rename to "):
                current_new = p_line.split("rename to ")[1]
                if current_old and current_new and current_old in surviving_files:
                    surviving_files[current_new] = surviving_files.pop(current_old)
            elif p_line.startswith("--- a/"):
                current_old = p_line[6:]
            elif p_line.startswith("+++ b/"):
                current_new = p_line[6:]
                if current_new not in surviving_files:
                    surviving_files[current_new] = []
            elif p_line.startswith("@@"):
                # Simplified AC topological appender
                pass
            elif p_line.startswith("+") and not p_line.startswith("+++"):
                if current_new:
                    # Append new physical line to structural map
                    surviving_files[current_new].append((len(surviving_files[current_new])+1, commit_id, ts))
                    
    blame_lines = []
    for fname, lines_arr in surviving_files.items():
        for actual_loc, origin_c, origin_ts in lines_arr:
            blame_lines.append({
                "originCommit": origin_c,
                "fileName": fname,
                "lineNumber": actual_loc,
                "commitTime": origin_ts
            })
            
    return blame_lines


def run_algC(metadata_store, start_time, end_time):
    logger.info("Starting Native AlgC (Embedded Blame) extraction...")
    commits = []
    for commit_id, data in metadata_store.items():
        ts = data.get("REPOSITORY", {}).get("revisionTimestamp") or data.get("REPOSITORY", {}).get("commitTime", "1970-01-01T00:00:00Z")
        commits.append((ts, commit_id, data))
        
    # Emulate stable stream processing order to detect skew
    commits_by_id = sorted(commits, key=lambda x: x[1])
    commits.sort(key=lambda x: x[0])
    
    last_ts = ""
    for ts, commit_id, data in commits_by_id:
        if ts < last_ts:
            logger.warning(f"Clock skew detected in AlgC! {ts} is before {last_ts}")
        last_ts = ts
        
    surviving = {}
    
    for ts, commit_id, data in commits:
        if ts < start_time or ts > end_time: continue
        
        # Explicit V26.04 Constraint Mapping
        if data.get("protocolVersion") != "26.04":
            logger.warning(f"AlgC natively requires v26.04! Found version '{data.get('protocolVersion')}' in {commit_id}. Skipping extraction.")
            continue
            
        summary_lines = data.get("SUMMARY", {}).get("lineCount", -1)
        actual_lines = 0
            
        for d in data.get("DETAIL", []):
            fname = d.get("fileName")
            if fname not in surviving: surviving[fname] = {}
                
            for line in d.get("codeLines", []):
                loc = line.get("lineLocation")
                op = line.get("operation", "add") 
                
                if op == "add":
                    if loc in surviving[fname]:
                        logger.warning(f"Duplicate add for {fname}:{loc} at {commit_id}")
                    surviving[fname][loc] = {
                        "genRatio": line.get("genRatio", 0),
                        "originCommit": commit_id,
                        "commitTime": ts
                    }
                    actual_lines += 1
                elif op == "delete":
                    if loc in surviving[fname]:
                        del surviving[fname][loc]
                    
        if summary_lines != -1 and actual_lines != summary_lines:
            logger.warning(f"SUMMARY lineCount {summary_lines} mismatches actual DETAIL {actual_lines} in {commit_id}")
            
    blame_lines = []
    for fname, lines_dict in surviving.items():
        for loc, info in lines_dict.items():
            blame_lines.append({
                "originCommit": info["originCommit"],
                "fileName": fname,
                "lineNumber": loc,
                "commitTime": info["commitTime"],
                "genRatio": info["genRatio"] 
            })
            
    return blame_lines


def run_svn_blame_algA(work_dir):
    """
    Executes live `svn blame --xml` to extract origin mappings.
    Returns: list of dicts: {"originCommit", "fileName", "lineNumber", "commitTime"}
    """
    logger.info("Starting Native SVN AlgA (Live Blame) extraction...")
    
    import shutil
    svn_bin = shutil.which("svn") or "/opt/homebrew/bin/svn"
    
    try:
        ls_res = subprocess.run(
            [svn_bin, "info", "-R", "--xml", "."],
            cwd=work_dir,
            capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"SVN server unreachable / not a working copy: {e}")
        return []
        
    blame_lines = []
    root = ET.fromstring(ls_res.stdout)
    files = []
    for entry in root.findall(".//entry[@kind='file']"):
        path = entry.get("path")
        if path:
            files.append(path)
    
    for f in files:
        if not f: continue
        try:
            blame_res = subprocess.run(
                [svn_bin, "blame", "--xml", f],
                cwd=work_dir,
                capture_output=True, text=True, check=True
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"svn blame failed on {f}: {e}")
            continue
            
        b_root = ET.fromstring(blame_res.stdout)
        for entry in b_root.findall(".//entry"):
            line_num = int(entry.get("line-number"))
            commit = entry.find("commit")
            if commit is not None:
                rev = commit.get("revision")
                date_xml = commit.find("date")
                date_val = date_xml.text if date_xml is not None else None
                
                if date_val:
                    # SVN XML dates: 2026-03-31T10:00:00.000000Z -> 2026-03-31T10:00:00Z
                    date_val = date_val.split('.')[0] + "Z"
                    
                if rev and date_val:
                    blame_lines.append({
                        "originCommit": rev,
                        "fileName": f,
                        "lineNumber": line_num,
                        "commitTime": date_val
                    })
                    
    return blame_lines

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repoURL", required=True)
    parser.add_argument("--repoBranch", required=True)
    parser.add_argument("--startTime", required=True)
    parser.add_argument("--endTime", required=True)
    parser.add_argument("--genCodeDescDir", required=True)
    parser.add_argument("--alg", default="A")
    parser.add_argument("--patchesDir")
    parser.add_argument("--threshold", type=int, default=60)
    parser.add_argument("--log-level", default="INFO")
    
    # E2E hook
    parser.add_argument("--mock-blame-lines")
    args = parser.parse_args()

    # Connect standard logging
    log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    logger.setLevel(log_level)

    metadata_store = load_v2603_metadata(args.genCodeDescDir, args.repoURL)
    
    # If a mock file is provided, use it directly (instead of running git blame)
    if args.mock_blame_lines and os.path.exists(args.mock_blame_lines):
        with open(args.mock_blame_lines, 'r') as f:
            all_blame_lines = json.load(f)
            blame_lines = [line for line in all_blame_lines if not line.get("commitTime") or (args.startTime <= line.get("commitTime") <= args.endTime)]
    else:
        # Native Pipeline 
        if args.alg.upper() == "A":
            # Dynamic VCS Routing
            if os.path.isdir(os.path.join(os.getcwd(), ".svn")):
                raw_lines = run_svn_blame_algA(os.getcwd())
            else:
                raw_lines = run_git_blame_algA(os.getcwd())
                
            blame_lines = [line for line in raw_lines if not line.get("commitTime") or (args.startTime <= line.get("commitTime") <= args.endTime)]
        elif args.alg.upper() == "B":
            raw_lines = run_algB(metadata_store, args.patchesDir, args.startTime, args.endTime)
            blame_lines = [line for line in raw_lines if not line.get("commitTime") or (args.startTime <= line.get("commitTime") <= args.endTime)]
        elif args.alg.upper() == "C":
            raw_lines = run_algC(metadata_store, args.startTime, args.endTime)
            blame_lines = [line for line in raw_lines if not line.get("commitTime") or (args.startTime <= line.get("commitTime") <= args.endTime)]
        else:
            blame_lines = []

    resolved_lines = resolve_gen_ratios(blame_lines, metadata_store)
    metrics = compute_core_metrics(resolved_lines, threshold=args.threshold)
    
    logger.info(f"SUMMARY aggregate totalLines={metrics['totalLines']} weighted={metrics['weightedRatio']}% fullyAI={metrics['fullyAIRatio']}% mostlyAI={metrics['mostlyAIRatio']}%")
    
    # Build DETAIL array per v26.03 protocol
    detailed_files = {}
    for line in resolved_lines:
        fname = line["fileName"]
        if fname not in detailed_files:
            detailed_files[fname] = []
        detailed_files[fname].append({
            "lineLocation": line["lineNumber"],
            "genRatio": line["genRatio"]
        })
    
    detail_arr = [{"fileName": k, "codeLines": v} for k, v in detailed_files.items()]
    
    # Final Protocol Envelope
    output = {
        "protocolName": "generatedTextDesc",
        "protocolVersion": "26.03",
        "SUMMARY": {
            "totalLines": metrics["totalLines"],
            "weightedModeRatio": metrics["weightedRatio"],
            "fullyAIModeRatio": metrics["fullyAIRatio"],
            "mostlyAIModeRatio": metrics["mostlyAIRatio"]
        },
        "DETAIL": detail_arr, 
        "REPOSITORY": {
            "vcsType": "git",
            "repoURL": args.repoURL,
            "repoBranch": args.repoBranch,
            "startTime": args.startTime,
            "endTime": args.endTime
        }
    }
    
    print(json.dumps(output, indent=2))

if __name__ == "__main__":
    main()
