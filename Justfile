# Show this help
help:
  @just --list

# Get the CI status of the last commit
ci:
  poetry run watch_gha_runs

# Run the test suite
test *ARGS:
  poetry run pytest {{ARGS}}

# Lints
lint:
  poetry run flake8

# Call the docs Makefile
docs +TARGETS:
  make -C docs {{TARGETS}}

# Run the TUI app
pixelize:
  poetry run textual run --dev pixelize:PixelsApp

# Run the dev console for the TUI app
devconsole:
  poetry run textual console
