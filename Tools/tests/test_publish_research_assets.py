"""Upload target visibility: a public repository is accepted only when asked for explicitly."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import publish_research_assets as pra


def test_private_repository_is_accepted_without_opt_in():
    pra.check_visibility(is_private=True, public_ok=False)


def test_public_repository_needs_explicit_opt_in():
    with pytest.raises(ValueError, match='--public-ok'):
        pra.check_visibility(is_private=False, public_ok=False)
    pra.check_visibility(is_private=False, public_ok=True)
