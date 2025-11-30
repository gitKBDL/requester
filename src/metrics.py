import threading
from dataclasses import dataclass, field
from typing import Dict

@dataclass
class Stats:
    total: int = 0
    success: int = 0
    failed: int = 0
    codes: Dict[int, int] = field(default_factory=dict)

class Metrics:
    def __init__(self):
        self._lock = threading.Lock()
        self.stats = Stats()

    def record_response(self, status_code: int):
        with self._lock:
            self.stats.total += 1
            if 200 <= status_code < 400:
                self.stats.success += 1
            else:
                self.stats.failed += 1
            
            self.stats.codes[status_code] = self.stats.codes.get(status_code, 0) + 1

    def record_error(self):
        with self._lock:
            self.stats.total += 1
            self.stats.failed += 1
            # -1 represents network error/exception
            self.stats.codes[-1] = self.stats.codes.get(-1, 0) + 1
