"""A program or a package that a command needs and this environment lacks."""


class MissingDependency(Exception):
    """What is missing and how to get it; the command line says both in one
    sentence and stops, without a traceback.

    what : what is missing, as "devsim is not installed"
    how  : how to get it, as "Install it with pip install devsim"
    """

    def __init__(self, what: str, how: str):
        super().__init__(f"{what}. {how}")
        self.what, self.how = what, how


# The packages of ROOT's Python bindings; the files that need ROOT import it
# themselves, and the command line says the one sentence for all of them.
ROOT_MODULES = {"ROOT", "cppyy"}
ROOT_MISSING = MissingDependency(
    "ROOT's Python bindings are not available in this Python",
    "Install them with conda install -c conda-forge root_base",
)
