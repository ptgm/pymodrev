import os
from parsers.network_reader import NetworkReader
from parsers.asp_reader import ASPReader
from parsers.bnet_reader import BnetReader
from parsers.ginml_reader import GINMLReader

def get_reader(filepath: str) -> NetworkReader:
    """
    Factory function to return the appropriate NetworkReader based on the
    file extension of the given filepath.
    
    Args:
        filepath: The path to the network model file.
        
    Returns:
        An instance of a subclass of NetworkReader.
        
    Raises:
        ValueError: If the file extension is unsupported.
    """
    _, ext = os.path.splitext(filepath)
    ext = ext.lower()
    
    if ext == '.lp':
        return ASPReader()
    elif ext == '.bnet':
        return BnetReader()
    elif ext in ('.ginml', '.zginml'):
        return GINMLReader()
    else:
        raise ValueError(f"Unsupported model file extension: '{ext}'. Supported extensions are: .lp, .bnet, .ginml, .zginml")
