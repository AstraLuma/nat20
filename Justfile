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
