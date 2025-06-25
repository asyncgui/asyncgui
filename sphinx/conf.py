# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import importlib.metadata

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
project = 'asyncgui'
copyright = '2023, Mitō Nattōsai'
author = 'Mitō Nattōsai'
release = importlib.metadata.version(project)

rst_epilog = """
.. |ja| replace:: 🇯🇵
"""

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    # 'sphinx.ext.viewcode',
    'sphinx.ext.githubpages',
    'sphinx_tabs.tabs',

]
templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
language = 'en'
add_module_names = False
gettext_auto_build = False
gettext_location = False


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output
html_theme = "furo"
html_static_path = ['_static']
html_theme_options = {
    "top_of_page_button": "edit",
}

# -- Options for todo extension ----------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/todo.html#configuration
todo_include_todos = True

# -- Options for intersphinx extension ---------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/intersphinx.html#configuration
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'trio': ('https://trio.readthedocs.io/en/stable/', None),
    'trio_util': ('https://trio-util.readthedocs.io/en/latest/', None),
    # 'requests': ('https://docs.python-requests.org/en/latest/', None),
    # 'asyncgui_ext.synctools': ('https://asyncgui.github.io/asyncgui-ext-synctools/', None),
}


# -- Options for tabs extension ---------------------------------------
# https://sphinx-tabs.readthedocs.io/en/latest/
sphinx_tabs_disable_tab_closing = True


# -- Options for autodoc extension ---------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#configuration

def modify_signature(app, what: str, name: str, obj, options, signature, return_annotation: str,
                     prefix="asyncgui.",
                     len_prefix=len("asyncgui."),
                     group1={'Nursery', 'TaskState', 'Task.cancel', 'Task.close', },
                     group2={'current_task', 'sleep_forever', 'open_nursery', },
                     # group3={"TaskState." + s for s in "CREATED STARTED CANCELLED FINISHED".split()},
                     group4={'wait_all_cm', 'wait_any_cm', 'run_as_daemon', 'run_as_main', },
                     group5={'open_nursery', },
                     ):
    if not name.startswith(prefix):
        return (signature, return_annotation, )
    name = name[len_prefix:]
    if name in group1:
        print(f"Hide the signature of {name!r}")
        return ('', None)
    if name in group2:
        print(f"Modify the signature of {name!r}")
        return ('()', return_annotation)
    if name in group4:
        print(f"add a return-annotation to {name!r}")
        return (signature, '~typing.AsyncContextManager[Task]')
    if name in group5:
        print(f"Modify the return-annotation of {name!r}")
        return (signature, return_annotation.replace("AsyncIterator", "AsyncContextManager"))
    return (signature, return_annotation, )


def setup(app):
    app.connect('autodoc-process-signature', modify_signature)
