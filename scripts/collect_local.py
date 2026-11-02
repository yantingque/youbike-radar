"""本機版收集：抓一次快照 → commit → push 到 data 分支。

給 Windows 工作排程器每 10 分鐘用 pythonw 執行（不跳視窗），輸出寫到 data/collect_local.log。
需要先建好 data 分支的工作目錄：git worktree add data/datarepo data
"""
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data" / "datarepo"
LOG = REPO / "data" / "collect_local.log"

sys.path.insert(0, str(REPO))
from ubike.collect import main as collect_main  # noqa: E402
from ubike.snapshot import TAIPEI  # noqa: E402


def git(*args: str, quiet: bool = False) -> subprocess.CompletedProcess:
    r = subprocess.run(["git", *args], cwd=DATA, capture_output=True, text=True,
                       encoding="utf-8", errors="replace",
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0 and not quiet:
        print(f"git {' '.join(args)} 失敗：{r.stderr.strip()}")
    return r


def run() -> int:
    if collect_main(["--out", str(DATA)]) != 0:
        return 1
    git("add", "-A")
    # 回傳 1 代表有變更，不算錯誤
    if git("diff", "--cached", "--quiet", quiet=True).returncode == 0:
        return 0
    stamp = datetime.now(TAIPEI).strftime("%Y-%m-%d %H:%M")
    if git("commit", "-q", "-m", f"data: 快照 {stamp}（本機）").returncode != 0:
        return 1
    # 上次 push 失敗留下的 commit 也會在這次一起推上去
    for i in range(3):
        # rebase 時 -X theirs 代表衝突以本機這次的檔案為準（只有 stations.csv 會衝突）
        if git("pull", "--rebase", "-X", "theirs", "-q", "origin", "data").returncode == 0:
            if git("push", "-q", "origin", "HEAD:data").returncode == 0:
                return 0
        else:
            git("rebase", "--abort")
        print(f"push 失敗，第 {i + 1} 次重試")
        time.sleep(5)
    return 1


def main() -> int:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as log:
        sys.stdout = sys.stderr = log  # pythonw 沒有主控台，全部寫進 log
        try:
            code = run()
        except Exception as e:  # 排程執行看不到畫面，例外也要留紀錄
            print(f"未預期錯誤：{e!r}")
            code = 1
        if code:
            print(f"{datetime.now(TAIPEI):%Y-%m-%d %H:%M:%S} 本次失敗（exit {code}）")
        return code


if __name__ == "__main__":
    sys.exit(main())
