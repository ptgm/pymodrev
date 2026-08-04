import os
import re
import csv
from abc import ABC, abstractmethod
from typing import List
from pymodrev.network.observation import Observation
from pymodrev.updaters.updater import Updater

class ObservationParser(ABC):
    """
    Abstract base class for observation parsers.
    """
    @abstractmethod
    def read(self, filepath: str, updater: Updater) -> Observation:
        """
        Parses an observation file and returns an Observation object.
        """
        pass

    def read_table(self, table: List, obs: Observation) -> Observation:
        header = table[0]
        
        # Detect type:
        # Steady State: ,node1,node2,... (header[0] is empty)
        # Time Series: ,,node1,node2,... (header[0] and header[1] are empty)
        is_ts = len(header) > 2 and header[0] in ('', None) and header[1] in ('', None)
        nodes = header[2:] if is_ts else header[1:]
        
        for row in table[1:]:
            if not row or not any(row):
                continue
            exp_id = row[0]
            if is_ts:
                time = str(row[1])
                values = row[2:]
                if obs.updater.get_type() in ('reachasync', 'reachsync') and time not in ('init','final') \
                    or (obs.updater.get_type() in ('async', 'sync', 'complete') and not time.isdigit()):
                    raise ValueError(f"Updater '{obs.updater.get_type()}' with invalid time value.")
            else:
                time = None
                values = row[1:]
            
            for i, val in enumerate(values):
                if i >= len(nodes): break

                val = str(val).strip()
                if val == "" or val.lower() in ("n/a", "na", "nan", "*", "-"):
                    continue

                try:
                    obs.add_data(exp_id, time, nodes[i], int(float(val)))
                except ValueError:
                    # Skip non-numeric values
                    continue
        return obs
        

class LPObservationParser(ObservationParser):
    """
    Parses observations in Answer Set Programming (.lp) format.
    """
    def read(self, filepath: str, updater: Updater) -> Observation:
        obs = Observation(updater)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('%'):
                        continue
                    # Match predicates like exp(p1). or obs_vlabel(p1, node, 0).
                    for match in re.finditer(r'([a-z_]+)\(([^)]+)\)', line):
                        pred = match.group(1)
                        args = [a.strip() for a in match.group(2).split(',')]
                        if pred == 'exp' and len(args) == 1:
                            obs.experiments.add(args[0])
                        elif pred == 'obs_vlabel':
                            if len(args) == 3:  # Steady State: obs_vlabel(P, V, S)
                                obs.add_data(args[0], None, args[1], int(args[2]))
                            elif len(args) == 4:  # Time Series: obs_vlabel(P, T, V, S)
                                obs.add_data(args[0], args[1], args[2], int(args[3]))
        except Exception as e:
            raise ValueError(f"Error parsing LP observation file {filepath}: {e}")
        return obs

class CSVObservationParser(ObservationParser):
    """
    Parses observations in CSV format.
    Supports both steady-state and time-series patterns.
    """
    def read(self, filepath: str, updater: Updater) -> Observation:
        obs = Observation(updater)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)

                return self.read_table(list(reader), obs)
        except Exception as e:
            raise ValueError(f"Error parsing CSV observation file {filepath}: {e}")
        return obs

class ExcelObservationParser(ObservationParser):
    """
    Parses observations in Excel (.xls, .xlsx) format.
    Supports both steady-state and time-series patterns.
    """
    def read(self, filepath: str, updater: Updater) -> Observation:
        obs = Observation(updater)
        ext = os.path.splitext(filepath)[1].lower()
        try:
            rows = []
            if ext == '.xlsx':
                import openpyxl
                wb = openpyxl.load_workbook(filepath, data_only=True)
                ws = wb[wb.sheetnames[0]] # Read the first sheet
                for row in ws.iter_rows(values_only=True):
                    rows.append(list(row))
            elif ext == '.xls':
                import xlrd
                wb = xlrd.open_workbook(filepath)
                ws = wb.sheet_by_index(0)
                for i in range(ws.nrows):
                    rows.append(ws.row_values(i))
            
            return self.read_table(rows, obs)
        except Exception as e:
            raise ValueError(f"Error parsing Excel observation file {filepath}: {e}")
        return obs

def get_observation_parser(filepath: str) -> ObservationParser:
    """
    Factory function to return the appropriate ObservationParser based on file extension.
    """
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.lp':
        return LPObservationParser()
    elif ext == '.csv':
        return CSVObservationParser()
    elif ext in ('.xls', '.xlsx'):
        return ExcelObservationParser()
    else:
        raise ValueError(f"Unsupported observation format: '{ext}'. Supported formats are: .lp, .csv, .xls, .xlsx")
