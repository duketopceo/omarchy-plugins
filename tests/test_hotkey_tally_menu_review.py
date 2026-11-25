"""Regression coverage for the machine keybinding menu's record boundaries."""

import subprocess
from pathlib import Path


MENU = Path(__file__).resolve().parents[1] / "machine/bin/omarchy-menu-keybindings"


def run_functions(commands: str) -> str:
    functions = MENU.read_text().split('\ncase "${1:-}" in', 1)[0]
    result = subprocess.run(["bash", "-c", functions + "\n" + commands], check=True, text=True, capture_output=True)
    return result.stdout


def test_translate_only_display_not_command():
    for key in ("B", "code:12", "mouse:272"):
        for command in ("notify-send code:12", "notify-send mouse:272"):
            output = run_functions(f"printf 'SUPER + {key} → Test\\texec\\t{command}\\n' | parse_keycodes")
            display, dispatcher, actual_command = output.rstrip("\n").split("\t")
            assert "code:12" not in display and "mouse:272" not in display
            assert dispatcher == "exec"
            assert actual_command == command


def test_binding_description_and_command_preserve_commas():
    output = run_functions('''
hyprctl() { printf 'bind\\n\\tmodmask: 64\\n\\tkey: B\\n\\tkeycode: 0\\n\\tdescription: Build, test\\n\\tdispatcher: exec\\n\\targ: notify-send one,two\\n'; }
dynamic_bindings | parse_binding_records
''')
    display, dispatcher, command = output.rstrip("\n").split("\t")
    assert display.endswith("→ Build, test")
    assert dispatcher == "exec"
    assert command == "notify-send one,two"
