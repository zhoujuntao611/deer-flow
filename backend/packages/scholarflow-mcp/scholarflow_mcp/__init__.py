"""ScholarFlow's deterministic multi-source scholarly search components."""

from scholarflow_mcp.dedup import deduplicate_records
from scholarflow_mcp.models import PaperRecord
from scholarflow_mcp.service import LiteratureSearchService

__all__ = ["LiteratureSearchService", "PaperRecord", "deduplicate_records"]
