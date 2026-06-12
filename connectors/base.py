from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class DataSourceConfig:
    """Configuration d'une source de donnees"""
    source_type: str
    identifier: str
    url: Optional[str] = None
    api_key: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    rate_limit: int = 1


@dataclass
class RawDocument:
    """Document brut recupere"""
    id: str
    source: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    collected_at: datetime = field(default_factory=datetime.now)


class BaseSourceConnector(ABC):
    """Classe de base pour TOUS les connecteurs"""
    
    def __init__(self, config: DataSourceConfig):
        self.config = config
    
    @abstractmethod
    def connect(self) -> bool:
        """Verifie que la source fonctionne"""
        pass
    
    @abstractmethod
    def fetch(self, keywords: List[str]) -> List[RawDocument]:
        """Recupere les documents selon les mots-cles"""
        pass