"""Regression tests for copyable upgrade commands."""

from html import escape
from pathlib import Path
import runpy
import unittest


CHECKER = runpy.run_path(str(Path(__file__).with_name("check_upgrade.py")))
check_upgrade = CHECKER["check_upgrade"]
upgrade_commands = CHECKER["upgrade_commands"]
APPROVED = 'python -m pip install --upgrade "rsTimes[pandas,polars]==1.1.0"'
OLD_PIN = APPROVED.replace("1.1.0", "1.0.0")
GLOBAL_OLD_PIN = OLD_PIN.replace("pip install", "pip --no-cache-dir install")


def page(*lines):
    return "<main>" + "".join(f"<pre>{escape(line)}</pre>" for line in lines) + "</main>"


class UpgradeCommandsTest(unittest.TestCase):
    def test_rejects_second_install_after_a_pip_global_switch(self):
        with self.assertRaises(ValueError) as raised:
            check_upgrade(page(APPROVED, GLOBAL_OLD_PIN), "1.1.0")
        self.assertIn(GLOBAL_OLD_PIN, str(raised.exception))

    def test_keeps_the_unique_exact_command_rule(self):
        self.assertEqual(check_upgrade(page(APPROVED), "1.1.0"), [APPROVED])
        for commands in [(OLD_PIN,), (APPROVED, OLD_PIN)]:
            with self.subTest(commands=commands), self.assertRaises(ValueError) as raised:
                check_upgrade(page(*commands), "1.1.0")
            self.assertIn(OLD_PIN, str(raised.exception))

    def test_finds_install_after_global_options_and_their_values(self):
        commands = [
            'pip --debug --log "path with spaces" --quiet install rsTimes==1.0.0',
            'pip3.13 --timeout=30 --isolated install -U "rsTimes[polars]==1.0.0"',
            'python -I -m pip --log install install rsTimes==1.0.0',
            'py -3.13 -m pip --retries 2 install rsTimes==1.0.0',
        ]
        self.assertEqual(upgrade_commands(page(*commands)), commands)

    def test_keeps_nested_code_inline_code_and_shell_continuations(self):
        wrapped = 'pip3 install \\\n    "rsTimes[polars]==1.0.0"'
        inline = "$ pip -q install 'RsTiMeS==1.0.0'"
        html = (
            f"<pre>{escape(OLD_PIN)}</pre><main><pre><code>{escape(wrapped)}</code></pre>"
            f"<p>Run <code>{escape(inline)}</code> from a terminal.</p></main>"
        )
        self.assertEqual(upgrade_commands(html), ['pip3 install  "rsTimes[polars]==1.0.0"', inline])

    def test_distinguishes_install_targets_from_prose_and_option_values(self):
        unrelated = [
            "Run pip install rsTimes from a terminal.",
            "python -c 'print(\"pip install rsTimes\")'",
            "pip --log install show rsTimes",
            "pip show install rsTimes",
            "pip install rstimes-helper",
            "pip install --target rsTimes packaging",
            "pip install packaging # rsTimes is installed separately",
        ]
        self.assertEqual(upgrade_commands(page(*unrelated, APPROVED)), [APPROVED])

    def test_detects_explicit_named_requirements_and_distribution_files(self):
        commands = [
            'pip install "rsTimes @ https://example.invalid/release.whl"',
            'pip install "./rstimes-1.0.0-cp313-cp313-macosx_11_0_arm64.whl"',
        ]
        self.assertEqual(upgrade_commands(page(*commands)), commands)


if __name__ == "__main__":
    unittest.main()
