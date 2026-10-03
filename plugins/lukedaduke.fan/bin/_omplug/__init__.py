"""Shared helper primitives for omarchy-plugins helpers.

Vendored into plugins/<id>/bin/_omplug/ by scripts/sync-shared.py; never edit
a vendored copy. Modules: proc (deadline-bounded exec), fsio (descriptor-
relative capped reads and atomic publish), text (clean_text), envelope (the
versioned JSON envelope), sysfs (root-parameterised hardware readers).
Python stdlib only; importing any module has no side effects.
"""
