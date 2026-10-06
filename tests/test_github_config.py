import pytest
from pydantic import ValidationError

from src.models import GitHubSourceConfig


def test_repo_url_is_normalized_to_owner_and_repo() -> None:
    source = GitHubSourceConfig(
        type="repo_releases", owner="YD4223", repo="https://github.com/YD4223/aihub"
    )

    assert (source.owner, source.repo) == ("YD4223", "aihub")


def test_owner_slash_repo_without_owner_field() -> None:
    source = GitHubSourceConfig(type="repo_releases", repo="vllm-project/vllm.git")

    assert (source.owner, source.repo) == ("vllm-project", "vllm")


def test_plain_repo_name_is_unchanged() -> None:
    source = GitHubSourceConfig(type="repo_releases", owner="sgl-project", repo="sglang")

    assert (source.owner, source.repo) == ("sgl-project", "sglang")


@pytest.mark.parametrize(
    ("owner", "repo"),
    [("acme", "https://github.com/other/tool"), (None, "https://github.com/acme/tool/releases")],
)
def test_inconsistent_or_ambiguous_repo_is_rejected(owner, repo) -> None:
    with pytest.raises(ValidationError):
        GitHubSourceConfig(type="repo_releases", owner=owner, repo=repo)
