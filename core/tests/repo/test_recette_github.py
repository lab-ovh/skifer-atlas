"""Recette #112 sur un dépôt GitHub privé dédié, vide ou déjà initialisé par Atlas.

Depuis core/ :
    ATLAS_GITHUB_TEST_REPO=owner/repo ATLAS_GITHUB_TOKEN=... \\
        uv run pytest tests/repo/test_recette_github.py -m github -q

Un seul compte GitHub suffit : seul membre de la gouvernance, il doit pouvoir lire et
écrire le dépôt, ses pull requests et ses références. Autoriser les trois méthodes de
fusion et les poussées de tags sur main. Commits et tags restent sur le dépôt dédié ;
ne pas exécuter la recette simultanément sur ce dépôt.
"""

import os
import re
from datetime import UTC, datetime
from urllib.parse import quote
from uuid import uuid4

import pytest
from workspace_helpers import USER, atlas_env

from skifer_atlas.githost import GitHubHost
from skifer_atlas.governance.rules import decide
from skifer_atlas.proposals.common import open_context
from skifer_atlas.proposals.create import create_proposal
from skifer_atlas.repo.git import RepoError, run_git
from skifer_atlas.repo.layout import WorkspaceMeta, read_meta
from skifer_atlas.repo.sync import create_workspace, join_workspace, set_remote, sync_workspace
from skifer_atlas.vault.keyring_vault import _memory
from skifer_atlas.workspaces import repo_dir

__all__ = ["atlas_env"]


def _document(document_id, account):
    return f"""schema_version: 1
kind: concept
data_product:
  id: {document_id}
  version: 1
  owner: {account}
  domain: recette
  description: Concept de recette GitHub.
label: Recette GitHub
entity:
  key: [id]
  attributes:
    - {{name: id, type: string}}
"""


def _remote_tags(repo, token):
    output = run_git(["ls-remote", "--tags", "--refs", "origin"], repo, token=token)
    return {ref.removeprefix("refs/tags/"): sha
            for sha, ref in (line.split() for line in output.splitlines())}


@pytest.mark.github
@pytest.mark.skipif(not (os.environ.get("ATLAS_GITHUB_TEST_REPO")
                         and os.environ.get("ATLAS_GITHUB_TOKEN")),
                    reason="ATLAS_GITHUB_TEST_REPO et ATLAS_GITHUB_TOKEN requis")
def test_github_merges_are_tagged_and_missing_remote_tag_is_republished(atlas_env, monkeypatch):
    monkeypatch.setenv("ATLAS_VAULT", "memory")
    monkeypatch.setenv("ATLAS_ACCOUNT", USER)
    monkeypatch.delenv("ATLAS_GITHUB_API_URL", raising=False)
    monkeypatch.setattr(_memory, "_items", {})
    repository = os.environ["ATLAS_GITHUB_TEST_REPO"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        pytest.fail("ATLAS_GITHUB_TEST_REPO doit être de la forme owner/repo.")
    owner, name = repository.split("/")
    token = os.environ["ATLAS_GITHUB_TOKEN"]
    host = GitHubHost(owner, name, token)
    account = host.current_account()
    info = host._request("GET", host._repo())
    assert info["private"], "Utiliser un dépôt privé dédié à la recette."
    assert all(info[key] for key in ("allow_merge_commit", "allow_squash_merge",
                                     "allow_rebase_merge"))
    url = f"https://github.com/{repository}.git"
    refs = run_git(["ls-remote", "--refs", "--", url], token=token)
    if not refs.strip():
        meta = WorkspaceMeta(id="recette-github", name="Recette GitHub")
        create_workspace(meta)
        workspace = set_remote(meta.id, url)
    else:
        workspace = join_workspace(url)
    repo = repo_dir(workspace.id)
    assert read_meta(repo).main_branch == "main"
    context = open_context(workspace.id)
    assert [member.account for member in context.governance.members] == [account]
    assert workspace.account == account
    decision = decide(context.governance, "new_version", "recette", account, [], "")
    assert decision.ready_to_merge and decision.merge_mode == "no_other_eligible"

    suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f") + uuid4().hex[:8]
    proposals = []
    merged_branches = []
    try:
        for method in ("merge", "squash", "rebase"):
            document_id = f"recette-{method}-{suffix}"
            proposal = create_proposal(workspace.id, _document(document_id, account),
                                       "Recette de synchronisation GitHub.", None)
            proposals.append((method, document_id, proposal))
            assert proposal["ready_to_merge"] and proposal["merge_mode"] == "no_other_eligible"

        expected = {}
        for method, document_id, proposal in proposals:
            result = host._request("PUT", f"{host._repo()}/pulls/{proposal['id']}/merge",
                                   {"merge_method": method})
            assert result["merged"]
            merged_branches.append(proposal["branch"])
            expected[f"doc/{document_id}/v1"] = result["sha"]

        result = sync_workspace(workspace.id)
        assert any(w["code"] == "versions_tagged" for w in result["warnings"])
        assert not any(w["code"] == "tags_not_pushed" for w in result["warnings"])
        remote_tags = _remote_tags(repo, token)
        for tag, commit in expected.items():
            assert run_git(["rev-parse", f"refs/tags/{tag}^{{commit}}"], repo).strip() == commit
            assert remote_tags.get(tag) == commit
            assert commit in run_git(["rev-list", "--first-parent", "main"], repo).split()
            path = f"concepts/{tag.split('/')[1]}.yaml"
            assert path in run_git(["diff-tree", "--no-commit-id", "--name-only", "-r",
                                    f"{commit}^", commit], repo).splitlines()

        tag, commit = next(iter(expected.items()))
        host._request("DELETE", f"{host._repo()}/git/refs/tags/{quote(tag, safe='/')}")
        assert tag not in _remote_tags(repo, token)
        assert run_git(["rev-parse", f"refs/tags/{tag}^{{commit}}"], repo).strip() == commit
        sync_workspace(workspace.id)
        assert _remote_tags(repo, token).get(tag) == commit
    finally:
        for branch in merged_branches:
            try:
                ref = quote(branch, safe="/")
                host._request("GET", f"{host._repo()}/git/ref/heads/{ref}")
                host._request("DELETE", f"{host._repo()}/git/refs/heads/{ref}")
            except RepoError as error:
                if error.code != "not_found":  # GitHub peut avoir déjà supprimé la branche.
                    raise
        config = run_git(["config", "--list"], repo)
        config_file = (repo / ".git" / "config").read_text(encoding="utf-8")
        if token in config or token in config_file:
            pytest.fail("Le jeton figure dans la configuration Git du clone.", pytrace=False)
