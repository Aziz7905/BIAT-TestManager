"""
Repository tree serializers for the project workspace sidebar.

The tree intentionally stops at scenarios in the initial payload. Test cases are
loaded on demand from the scenario cases endpoint so the sidebar stays fast and
the tree contract remains stable for larger projects.
"""

from .repository import ProjectRepositoryTreeSerializer, RepositoryTreeSuiteSerializer

TreeSuiteSerializer = RepositoryTreeSuiteSerializer

__all__ = ["ProjectRepositoryTreeSerializer", "RepositoryTreeSuiteSerializer", "TreeSuiteSerializer"]
