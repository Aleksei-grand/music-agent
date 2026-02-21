"""
Фабрика для создания дистрибьюторов
"""
from typing import Optional, Dict, Type
import logging

from .base import BaseDistributor
from .routenote import RouteNoteDistributor
from .sferoom import SferoomDistributor

logger = logging.getLogger(__name__)


class DistributorFactory:
    """Фабрика для создания экземпляров дистрибьюторов"""
    
    _distributors: Dict[str, Type[BaseDistributor]] = {
        'routenote': RouteNoteDistributor,
        'sferoom': SferoomDistributor,
    }
    
    @classmethod
    def get_available(cls) -> list:
        """Получить список доступных дистрибьюторов"""
        return list(cls._distributors.keys())
    
    @classmethod
    def create(
        cls,
        name: str,
        cookie: str,
        proxy: Optional[str] = None,
        headless: bool = True
    ) -> BaseDistributor:
        """
        Создать экземпляр дистрибьютора
        
        Args:
            name: Название дистрибьютора (routenote, sferoom)
            cookie: Cookie для аутентификации
            proxy: Прокси (опционально)
            headless: Запускать браузер без GUI
            
        Returns:
            Экземпляр дистрибьютора
        """
        name_lower = name.lower()
        
        if name_lower not in cls._distributors:
            available = ", ".join(cls.get_available())
            raise ValueError(f"Unknown distributor: {name}. Available: {available}")
        
        distributor_class = cls._distributors[name_lower]
        
        logger.info(f"Creating {name} distributor")
        return distributor_class(cookie=cookie, proxy=proxy, headless=headless)
    
    @classmethod
    def register(cls, name: str, distributor_class: Type[BaseDistributor]):
        """Зарегистрировать новый дистрибьютор"""
        cls._distributors[name.lower()] = distributor_class
        logger.info(f"Registered distributor: {name}")
    
    @classmethod
    def get_info(cls, name: str) -> Optional[Dict]:
        """Получить информацию о дистрибьюторе"""
        name_lower = name.lower()
        
        if name_lower not in cls._distributors:
            return None
        
        dist_class = cls._distributors[name_lower]
        return {
            'name': name_lower,
            'display_name': dist_class.DISPLAY_NAME,
            'min_cover_size': dist_class.MIN_COVER_SIZE,
            'accepted_formats': dist_class.ACCEPTED_FORMATS
        }
