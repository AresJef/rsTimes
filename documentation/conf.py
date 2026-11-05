"""Static English documentation; never imports a source-checkout product."""
import json
import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = json.loads((HERE / "target.json").read_text())
runpy.run_path(str(HERE / '_tools/render_namespaces.py'))['render'](
    HERE / '_stubs/rstimes/namespaces.json', HERE / 'api')
project = "rsTimes"
author = "rsTimes contributors"
copyright = "2026, rsTimes contributors"
language = "en"
version = release = TARGET["version"]
extensions = ["myst_parser", "autoapi.extension", "sphinx.ext.napoleon", "sphinx.ext.doctest", "sphinx_copybutton"]
source_suffix = {".md": "markdown", ".rst": "restructuredtext"}
exclude_patterns = ["_build", "_stubs", "_tools", "_data", "**/.DS_Store"]
myst_enable_extensions = ["colon_fence", "deflist", "fieldlist"]
myst_heading_anchors = 5
html_theme = "pydata_sphinx_theme"
html_title = f"rsTimes {release} documentation"
html_static_path = ["_static"]
html_css_files = ["rstimes.css"]
html_theme_options = {
    "logo": {"text": "rsTimes"},
    "navbar_end": ["theme-switcher", "navbar-icon-links"],
    "github_url": "https://github.com/AresJef/rsTimes",
    "navigation_with_keys": False,
    "show_toc_level": 2,
    "navigation_depth": 3,
    "footer_start": ["copyright"],
    "footer_end": ["sphinx-version"],
    "announcement": "Development preview — being verified against the latest implementation." if TARGET["status"] == "candidate" else f"Documentation for rsTimes {release} (beta).",
}
html_context = {"default_mode": "auto"}
html_show_sourcelink = False
autoapi_type = "python"
autoapi_dirs = [str(HERE / "_stubs")]
autoapi_file_patterns = ["*.pyi"]
autoapi_root = "api/reference"
autoapi_options = ["members", "show-module-summary", "special-members"]
autoapi_add_toctree_entry = False
autoapi_keep_files = False
autoapi_python_class_content = "class"
autoapi_member_order = "bysource"
autoapi_python_use_implicit_namespaces = False
napoleon_numpy_docstring = True
napoleon_google_docstring = False
napoleon_preprocess_types = True
napoleon_type_aliases = {"date": "datetime.date", "datetime": "datetime.datetime", "time": "datetime.time", "timedelta": "datetime.timedelta"}
copybutton_prompt_text = r">>> |\.\.\. "
copybutton_prompt_is_regexp = True
doctest_default_flags = 0


def skip_private(app, what, name, obj, skip, options):
    if any(part.startswith("_") and not (part.startswith("__") and part.endswith("__")) for part in name.split(".")):
        return True
    if name.rsplit('.', 1)[-1] in ('__new__', '__init__'):
        # AutoAPI otherwise hides constructor methods, including the actual
        # immutable-class signature declared in __new__.
        return False
    return skip



# Built-in type references must not resolve by suffix to namespace accessors
# such as Pddt.str/Pldt.str or Pldt.list. Fully-qualified public API references
# are left untouched. No warning categories are suppressed.
BUILTIN_TYPES = frozenset(('str', 'bytes', 'bytearray', 'bool', 'int', 'float', 'complex', 'list', 'tuple', 'dict', 'set', 'frozenset', 'object', 'type', 'memoryview', 'range', 'slice'))


def qualify_builtin_types(app, doctree):
    from sphinx import addnodes

    for node in doctree.findall(addnodes.pending_xref):
        if node.get('refdomain') == 'py' and node.get('reftype') in ('class', 'obj') and node.get('reftarget') in BUILTIN_TYPES:
            node['reftarget'] = 'builtins.' + node['reftarget']


def setup(app):
    app.connect("autoapi-skip-member", skip_private)
    app.connect("doctree-read", qualify_builtin_types)
    integrity = runpy.run_path(str(HERE / '_tools/build_integrity.py'))
    app.connect('builder-inited', integrity['build_started'], priority=900)
    app.connect('build-finished', integrity['build_finished'], priority=900)
