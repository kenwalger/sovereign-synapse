from abc import ABC, abstractmethod

class BaseAdapter(ABC):
    """
    Abstract base class for all LLM data adapters.
    """
    
    @abstractmethod
    def parse(self, file_path: str):
        """Must be implemented to handle provider-specific JSON/CSV logic."""
        pass

    @abstractmethod
    def write_turn(self, **kwargs):
        """Must be implemented to standardize the Markdown output."""
        pass