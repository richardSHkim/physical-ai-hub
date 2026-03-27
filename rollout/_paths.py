from __future__ import annotations

import sys
from pathlib import Path


def ensure_local_sources_on_path() -> Path:
    """Expose repo-local source trees without requiring editable installs."""
    project_root = Path(__file__).resolve().parents[1]
    source_roots = (
        project_root / "robots/lerobot/src",
        project_root / "robots/piper/piper_common/src",
        project_root / "robots/piper/lerobot_robot_piper_follower/src",
    )
    for source_root in source_roots:
        if source_root.is_dir():
            source_root_str = str(source_root)
            if source_root_str not in sys.path:
                sys.path.insert(0, source_root_str)
    return project_root
