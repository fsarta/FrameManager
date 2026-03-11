"""
observer.py
-----------
Pattern Observer generico tramite la classe Signal.

Esempio d'uso
-------------
>>> sig = Signal()
>>> sig.connect(lambda name: print(f"added: {name}"))
>>> sig.emit("frame_A")
added: frame_A
"""

from __future__ import annotations

from typing import Any, Callable, List


class Signal:
    """
    Segnale osservabile: callback registrate con `connect`, invocate con `emit`.

    Thread-safety: NON è thread-safe — da usare nel thread GUI.
    """

    def __init__(self) -> None:
        self._callbacks: List[Callable[..., Any]] = []

    def connect(self, callback: Callable[..., Any]) -> None:
        """Registra una callback. Evita duplicati."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def disconnect(self, callback: Callable[..., Any]) -> None:
        """Rimuove una callback. Ignora se non presente."""
        try:
            self._callbacks.remove(callback)
        except ValueError:
            pass

    def emit(self, *args: Any, **kwargs: Any) -> None:
        """Invoca tutte le callback registrate con gli argomenti forniti."""
        for cb in self._callbacks:
            cb(*args, **kwargs)

    def clear(self) -> None:
        """Rimuove tutte le callback."""
        self._callbacks.clear()

    @property
    def count(self) -> int:
        """Numero di callback registrate."""
        return len(self._callbacks)
