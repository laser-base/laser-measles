try:
    from ._core import compute
except ImportError:

    def compute(args):
        """Pure-Python fallback: return the longest element from *args*."""
        return max(args, key=len)
