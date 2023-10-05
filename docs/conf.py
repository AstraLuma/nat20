# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'nat20'
copyright = '2023, Jamie Bliss'
author = 'Jamie Bliss'
release = '0.1.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.intersphinx',
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
    # 'sphinxcontrib.prettyspecialmethods',
    'sphinx_inline_tabs',
    'sphinx.ext.todo',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'bleak': ('https://bleak.readthedocs.io/en/latest/', None),
    'aioevents': ('https://aioevents.readthedocs.io/en/stable/', None),
    # Textual
}

autodoc_default_options = {
    'members': True,
    'undoc-members': True,
    'special-members': ', '.join([
        '__aenter__', '__aexit__',
    ]),
}
