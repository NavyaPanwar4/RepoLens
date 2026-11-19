"""Git branch and commit metadata for analyzed repositories."""

import git


def get_history(repo_path: str, commit_limit: int = 20) -> dict:
    try:
        repository = git.Repo(repo_path)
        branches = sorted(
            {
                branch.name
                for branch in repository.branches
                if branch.name
            }
        )
        commits = []
        for commit in repository.iter_commits(max_count=min(commit_limit, 100)):
            commits.append({
                "sha": commit.hexsha,
                "short_sha": commit.hexsha[:7],
                "subject": commit.summary,
                "author": commit.author.name,
                "authored_at": commit.authored_datetime.isoformat(),
                "changed_files": len(commit.stats.files),
                "insertions": commit.stats.total.get("insertions", 0),
                "deletions": commit.stats.total.get("deletions", 0),
            })
        return {
            "branch": repository.active_branch.name,
            "branches": branches,
            "commits": commits,
            "commit_count": sum(1 for _ in repository.iter_commits()),
        }
    except Exception:
        return {
            "branch": None,
            "branches": [],
            "commits": [],
            "commit_count": 0,
        }
