# medusa/src/tool_crawler/parsers/base_parser.py

from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseToolParser(ABC):
    """
    Abstract base class for all tool extraction parsers.
    Defines the interface for can_parse and parse methods.
    Parsers should be robust, extensible, and return data in a standard format.
    """
    @abstractmethod
    def can_parse(self, response: Dict[str, Any]) -> bool:
        """
        Determines if this parser can handle the given response (from fetcher).
        Implement logic for content-type, URL pattern, etc. in concrete subclasses.
        """
        pass

    @abstractmethod
    def parse(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts raw tool data from the response.
        Returns a dict with all required fields for normalization.
        Implement robust extraction logic, handle edge cases, and log extraction confidence in subclasses.
        """
        pass

    def configure(self, config: Dict[str, Any]):
        """
        Extensibility point for parser configuration.
        """
        pass

    def fallback_parse(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fallback strategy for parsing if main parse fails (stub).
        """
        return {}

    def handle_error(self, error: Exception, response: Dict[str, Any]):
        """
        Extensibility point for error handling (stub).
        """
        pass

    # TODO: Add extensibility points for parser configuration, fallback strategies, and error handling. 