from abc import ABC, abstractmethod
from pymodrev.network.model import Model

class NetworkParser(ABC):
    """
    Abstract base class for reading and writing network models.
    Subclasses must implement 'read' and 'write' for specific file formats.
    """
    @abstractmethod
    def read(self, network: Model, filepath: str) -> int:
        """
        Populate the provided Model object from the given filepath.
        
        Args:
            network: The Model object to populate.
            filepath: The path to the model file.
            
        Returns:
            int: 1 on success, -1 or -2 on failure/errors.
        """
        pass

    @abstractmethod
    def write(self, network: Model, filename: str) -> None:
        """
        Write the provided Model object to a file.
        
        Args:
            network: The Model object to write.
            filename: The path to the output file.
        """
        pass
