#!/usr/bin/env bash
set -euo pipefail

ruff check .
black --check .
mypy jovykit tests main.py
