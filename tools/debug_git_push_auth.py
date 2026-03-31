import json
import os
import subprocess
import time
from pathlib import Path

LOG_PATH = Path("/Users/mounitha/Desktop/PantryBuddy/.cursor/debug-cad646.log")
SESSION_ID = "cad646"
RUN_ID = os.environ.get("DEBUG_RUN_ID", "pre-fix-auth-probe")


def log_event(hypothesis_id, location, message, data):
    payload = {
        "sessionId": SESSION_ID,
        "runId": RUN_ID,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")


def run_cmd(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "cmd": " ".join(cmd),
        "code": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def main():
    # #region agent log
    log_event("H0", "tools/debug_git_push_auth.py:main", "Starting auth probe", {"cwd": str(Path.cwd())})
    # #endregion

    remote_info = run_cmd(["git", "remote", "-v"])
    # #region agent log
    log_event("H1", "tools/debug_git_push_auth.py:main", "Remote configuration", remote_info)
    # #endregion

    helper_info = run_cmd(["git", "config", "--get-all", "credential.helper"])
    # #region agent log
    log_event("H2", "tools/debug_git_push_auth.py:main", "Credential helper configuration", helper_info)
    # #endregion

    gh_status = run_cmd(["gh", "auth", "status", "-t"])
    # #region agent log
    log_event(
        "H3",
        "tools/debug_git_push_auth.py:main",
        "GitHub auth status",
        {"cmd": gh_status["cmd"], "code": gh_status["code"], "stderr": gh_status["stderr"]},
    )
    # #endregion

    ls_remote = run_cmd(["git", "ls-remote", "--heads", "origin"])
    # #region agent log
    log_event("H4", "tools/debug_git_push_auth.py:main", "Remote read check", ls_remote)
    # #endregion

    push_dry_run = run_cmd(["git", "push", "--dry-run", "origin", "main"])
    # #region agent log
    log_event("H5", "tools/debug_git_push_auth.py:main", "Push dry-run check", push_dry_run)
    # #endregion


if __name__ == "__main__":
    main()
