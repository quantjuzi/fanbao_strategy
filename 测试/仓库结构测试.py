# -*- coding: utf-8 -*-
"""检查仓库里是否重新出现本机绝对路径和失效目录说明。"""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_USER_PREFIX = "C:" + chr(92) + "Users" + chr(92)


class RepositoryStructureTests(unittest.TestCase):
    """防止脚本再次绑定到某一台电脑。"""

    def test_python_files_do_not_contain_local_user_paths(self) -> None:
        offenders = []
        for directory in (ROOT / "脚本", ROOT / "回测", ROOT / "测试"):
            for path in directory.rglob("*.py"):
                text = path.read_text(encoding="utf-8")
                if LOCAL_USER_PREFIX in text:
                    offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [], f"发现本机绝对路径：{offenders}")

    def test_readme_does_not_reference_removed_daily_notes(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("daily_notes/", readme)

    def test_readme_mentions_expected_data_file(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("聚宽因子_2026-01-01_2026-09-30.csv", readme)


if __name__ == "__main__":
    unittest.main()
