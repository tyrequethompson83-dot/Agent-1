from __future__ import annotations

from abc import ABC, abstractmethod


class ChatAdapter(ABC):
    @abstractmethod
    def run(self) -> None:
        raise NotImplementedError

