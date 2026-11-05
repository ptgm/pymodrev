"""
Lazy sequence of the optimal inconsistency solutions produced by the ASP solver.

Enumerating all the optimal models of a (large) problem can be much more
expensive than finding the optimum, and several modes only need the first few
solutions. ``SolutionStream`` wraps a generator of ``(solution, optimum)``
pairs and behaves like a list that pulls items from the generator only when
they are needed.
"""

from __future__ import annotations

from typing import Iterator, List, Tuple

from pymodrev.network.inconsistency_solution import InconsistencySolution


class SolutionStream:
    """List-like, lazily filled sequence of InconsistencySolution."""

    def __init__(self, generator: Iterator[Tuple[InconsistencySolution, int]]):
        self._generator = generator
        self._items: List[InconsistencySolution] = []
        # number of nodes to repair: -1 when there is no solution
        self.optimization: int = -1
        self._first_optimum: int = -1
        if self._pull():
            self.optimization = self._first_optimum

    def _pull(self) -> bool:
        if self._generator is None:
            return False
        try:
            solution, optimum = next(self._generator)
        except StopIteration:
            self.close()
            return False
        if not self._items:
            self._first_optimum = optimum
        self._items.append(solution)
        return True

    def close(self) -> None:
        """Stops the solver (releases the clingo solve handle)."""
        generator, self._generator = self._generator, None
        if generator is not None:
            generator.close()

    def drain(self) -> None:
        """Pulls every remaining solution."""
        while self._pull():
            pass

    def __iter__(self) -> Iterator[InconsistencySolution]:
        index = 0
        while True:
            if index < len(self._items):
                yield self._items[index]
                index += 1
            elif not self._pull():
                return

    def __getitem__(self, index):
        if isinstance(index, slice) or index < 0:
            self.drain()
        else:
            while len(self._items) <= index and self._pull():
                pass
        return self._items[index]

    def __len__(self) -> int:
        self.drain()
        return len(self._items)

    def __bool__(self) -> bool:
        return bool(self._items)

    def __deepcopy__(self, memo):
        import copy
        self.drain()
        return copy.deepcopy(self._items, memo)

    def __del__(self):
        try:
            self.close()
        except Exception:  # pragma: no cover - interpreter shutdown
            pass
