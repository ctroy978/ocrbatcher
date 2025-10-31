from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("grader")
except PackageNotFoundError:
    from .version import __version__ as __version__

__all__ = ["__version__"]

