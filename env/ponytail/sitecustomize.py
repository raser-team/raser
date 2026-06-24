"""RASER Python startup hooks for environment-level compatibility.

This module is loaded automatically by Python when ``env/setup.sh`` prepends
``env/ponytail`` to ``PYTHONPATH``.  Keep hooks here narrow and version-gated:
they run before user code, so a quiet stale workaround would be worse than the
original warning.
"""

import importlib.abc
import importlib.machinery
import importlib.metadata
import sys


_G4PPYY_MODULE = "g4ppyy._lazy_loader"
_SUPPORTED_G4PPYY_VERSIONS = {"0.1.0"}

# g4ppyy 0.1.0 assumes only the first token from ``geant4-config --libs`` is a
# ``-L`` directory.  CERN LCG Geant4 builds also emit CLHEP as a later ``-L``
# token, so g4ppyy tries to load that directory as a library and reports a false
# failure.  When g4ppyy changes this file or version, review this ponytail and
# either remove it or update the parser below.
_G4PPYY_010_LIBRARY_PARSE = """\
    vals = lib_output.split()
    lib_dir = vals[0].replace("-L","")

    libraries = []
    for x in vals[1:]:
        libraries.append( x.replace("-l","") )
"""

_RASER_LIBRARY_PARSE = """\
    vals = lib_output.split()

    libraries = []
    for x in vals:
        if x.startswith("-L"):
            lib_dir = x[2:]
            if _os.path.isdir(lib_dir):
                cppyy.add_library_path(_os.path.abspath(lib_dir))
        elif x.startswith("-l"):
            libraries.append(x[2:])
        elif _os.path.isabs(x) and _os.path.exists(x):
            libraries.append(x)
"""

_warned_versions = set()


def _installed_g4ppyy_version():
    try:
        return importlib.metadata.version("g4ppyy")
    except importlib.metadata.PackageNotFoundError:
        return None


class _G4PpyyLazyLoaderPonytail(importlib.abc.Loader):
    def __init__(self, base_spec):
        self._base_loader = base_spec.loader
        self._origin = base_spec.origin

    def create_module(self, spec):
        create_module = getattr(self._base_loader, "create_module", None)
        if create_module is None:
            return None
        return create_module(spec)

    def exec_module(self, module):
        get_source = getattr(self._base_loader, "get_source", None)
        if get_source is None:
            raise ImportError(
                "RASER g4ppyy ponytail needs a source loader; review "
                "env/ponytail/sitecustomize.py for this g4ppyy build"
            )

        source = get_source(module.__name__)
        if _G4PPYY_010_LIBRARY_PARSE not in source:
            raise ImportError(
                "RASER g4ppyy ponytail did not find the expected g4ppyy 0.1.0 "
                "library parser; g4ppyy likely changed, so review "
                "env/ponytail/sitecustomize.py before continuing"
            )

        source = source.replace(_G4PPYY_010_LIBRARY_PARSE, _RASER_LIBRARY_PARSE, 1)
        code = compile(source, self._origin or module.__name__, "exec")
        exec(code, module.__dict__)


class _G4PpyyLazyLoaderFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname != _G4PPYY_MODULE:
            return None

        version = _installed_g4ppyy_version()
        if version not in _SUPPORTED_G4PPYY_VERSIONS:
            if version not in _warned_versions:
                print(
                    "RASER warning: g4ppyy version "
                    f"{version or '<not installed>'} is outside the verified "
                    "ponytail set; review env/ponytail/sitecustomize.py",
                    file=sys.stderr,
                )
                _warned_versions.add(version)
            return None

        base_spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if base_spec is None or base_spec.loader is None:
            return None

        base_spec.loader = _G4PpyyLazyLoaderPonytail(base_spec)
        return base_spec


if not any(isinstance(finder, _G4PpyyLazyLoaderFinder) for finder in sys.meta_path):
    sys.meta_path.insert(0, _G4PpyyLazyLoaderFinder())
