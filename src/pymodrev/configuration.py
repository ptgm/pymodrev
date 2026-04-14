"""
This module defines enumerations and configuration settings for handling 
inconsistencies and update types in a network analysis system.
"""

from enum import Enum
from dataclasses import dataclass

class Inconsistencies(Enum):
    """
    Enumeration representing different levels of inconsistencies in the system.

    Attributes:
        CONSISTENT (int): No inconsistency detected.
        SINGLE_INC_GEN (int): A general single inconsistency.
        SINGLE_INC_PART (int): A partial single inconsistency.
        DOUBLE_INC (int): A double inconsistency.
    """
    CONSISTENT = (0, "No inconsistency detected")
    SINGLE_INC_GEN = (1, "General single inconsistency")
    SINGLE_INC_PART = (2, "Partial single inconsistency")
    DOUBLE_INC = (3, "Double inconsistency")

    def __init__(self, int_val, description):
        self._value_ = int_val
        self.description = description
    def __str__(self):
        return f"{self.name} ({self.value}): {self.description}"


class UpdateType(Enum):
    """
    Enumeration representing the types of update strategies that can be used.

    Attributes:
        ASYNC (int): Asynchronous update strategy.
        SYNC (int): Synchronous update strategy.
        MASYNC (int): Mixed asynchronous update strategy.
    """
    ASYNC = (0, "Asynchronous update strategy")
    SYNC = (1, "Synchronous update strategy")
    MASYNC = (2, "Mixed asynchronous update strategy")

    def __init__(self, int_val, description):
        self._value_ = int_val
        self.description = description
    def __str__(self):
        return f"{self.name} ({self.value}): {self.description}"


import importlib.metadata

try:
    _package_version = importlib.metadata.version('pymodrev')
except Exception:
    _package_version = '1.0.0-dev'

@dataclass
class Configuration:
    """Class representing the configuration settings for the system"""
    name: str = 'pyModRev'
    version: str = _package_version
    task: str = 'r' # default is show the repairs
    format: str = 'h' # default is human-readable format
    update: UpdateType = UpdateType.ASYNC  # Setting the update type to ASYNC
    debug: bool = False
    check_asp: bool = True  # Use ASP consistency check program
    function_asp: bool = True # Use ASP function program
    solutions: int = 3 # Number/Type of solutions presented (default=3)
    labelling: bool = False
    multiple_profiles: bool = True
    compare_level_function: bool = True
    exact_middle_function_determination: bool = True
    ignore_warnings: bool = False
    force_optimum: bool = False
    show_all_functions: bool = True # Show all function repairs for a given node
    check_consistency: bool = False  # Just check the consistency of the model and return

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        setattr(self, key, value)


config = Configuration()
