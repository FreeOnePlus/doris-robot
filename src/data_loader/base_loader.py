import logging
from abc import ABC, abstractmethod
from typing import Iterator

logger = logging.getLogger(__name__)

class BaseLoader(ABC):
    @abstractmethod
    def load_documents(self, *args, **kwargs) -> Iterator[dict]:
        """抽象方法，子类必须实现文档加载逻辑"""
        pass

    @abstractmethod
    def process_document(self, document) -> dict:
        """抽象方法，子类必须实现文档处理逻辑"""
        pass 