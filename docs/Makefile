# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?= -a -j=auto
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build

requirements.txt:
	poetry export --with=dev > "$@"

# Put it first so that "make" without argument is like "make help".
help:
	poetry run @$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile serve dump-inv

serve:
	@poetry run sphinx-autobuild --open-browser --port 0 --watch ../nat20 "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS)

dump-inv: html
	@poetry run python ./dump_inv.py

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@poetry run $(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
