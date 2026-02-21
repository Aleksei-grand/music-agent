"""
Обработка изображений для музыкальных обложек
- Resize до требований дистрибьюторов (3000x3000)
- Конвертация форматов
- Проверка требований
"""
import logging
from pathlib import Path
from typing import Tuple, Optional
from PIL import Image, ImageEnhance
import io

logger = logging.getLogger(__name__)


class CoverRequirements:
    """Требования дистрибьюторов к обложкам"""
    
    # Стандартные требования
    MIN_SIZE = 3000  # pixels
    MAX_SIZE = 6000
    RECOMMENDED_SIZE = 3000
    ASPECT_RATIO = 1.0  # 1:1 (квадрат)
    FORMATS = ['JPEG', 'PNG']
    MIN_DPI = 72
    MAX_FILE_SIZE_MB = 30  # Мб
    COLOR_MODE = 'RGB'


class ImageProcessor:
    """Процессор изображений для обложек альбомов"""
    
    def __init__(self):
        self.requirements = CoverRequirements()
    
    def process_for_distribution(
        self,
        input_path: Path,
        output_path: Path,
        target_size: int = 3000,
        quality: int = 95
    ) -> dict:
        """
        Обработать изображение для дистрибьютора
        
        Args:
            input_path: Путь к исходному изображению
            output_path: Куда сохранить результат
            target_size: Целевой размер (обычно 3000x3000)
            quality: Качество JPEG (0-100)
            
        Returns:
            dict с информацией о результате
        """
        logger.info(f"Processing image: {input_path} -> {output_path}")
        
        # Открываем
        with Image.open(input_path) as img:
            original_size = img.size
            original_mode = img.mode
            
            logger.info(f"Original: {original_size}, mode: {original_mode}")
            
            # Конвертируем в RGB если нужно
            if img.mode not in ('RGB', 'L'):
                if img.mode == 'RGBA':
                    # Создаём белый фон для прозрачности
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1])
                    img = background
                else:
                    img = img.convert('RGB')
            
            # Resize с сохранением пропорций
            img = self._resize_to_square(img, target_size)
            
            # Улучшение качества
            img = self._enhance_image(img)
            
            # Сохраняем
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path, 'JPEG', quality=quality, optimize=True)
            
            # Проверяем результат
            result = self.validate_cover(output_path)
            result['original_size'] = original_size
            result['processed_size'] = img.size
            result['output_path'] = str(output_path)
            
            logger.info(f"Saved processed image: {output_path} ({img.size})")
            
        return result
    
    def _resize_to_square(self, img: Image.Image, target_size: int) -> Image.Image:
        """Изменить размер до квадрата"""
        # Если изображение не квадратное - обрезаем центр
        width, height = img.size
        
        if width != height:
            # Обрезаем до квадрата (центрируем)
            min_dim = min(width, height)
            left = (width - min_dim) // 2
            top = (height - min_dim) // 2
            right = left + min_dim
            bottom = top + min_dim
            img = img.crop((left, top, right, bottom))
            logger.debug(f"Cropped to square: {img.size}")
        
        # Resize до целевого размера
        if img.size[0] != target_size:
            img = img.resize((target_size, target_size), Image.Resampling.LANCZOS)
            logger.debug(f"Resized to: {img.size}")
        
        return img
    
    def _enhance_image(self, img: Image.Image) -> Image.Image:
        """Улучшить качество изображения"""
        # Немного повышаем резкость
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(1.1)  # +10% резкости
        
        # Немного контраста
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.05)  # +5% контраста
        
        return img
    
    def validate_cover(self, image_path: Path) -> dict:
        """
        Проверить соответствие требованиям дистрибьюторов
        
        Returns:
            dict: {'valid': bool, 'errors': [], 'warnings': []}
        """
        errors = []
        warnings = []
        
        try:
            with Image.open(image_path) as img:
                width, height = img.size
                
                # Проверка размера
                if width < self.requirements.MIN_SIZE or height < self.requirements.MIN_SIZE:
                    errors.append(f"Size too small: {width}x{height}, minimum {self.requirements.MIN_SIZE}x{self.requirements.MIN_SIZE}")
                
                if width > self.requirements.MAX_SIZE or height > self.requirements.MAX_SIZE:
                    warnings.append(f"Size very large: {width}x{height}")
                
                # Проверка пропорций
                aspect = width / height
                if abs(aspect - self.requirements.ASPECT_RATIO) > 0.01:
                    errors.append(f"Not square: aspect ratio {aspect:.2f}")
                
                # Проверка формата
                if img.format not in self.requirements.FORMATS:
                    warnings.append(f"Format {img.format} may not be accepted, use JPEG or PNG")
                
                # Проверка цветового режима
                if img.mode != self.requirements.COLOR_MODE:
                    warnings.append(f"Color mode {img.mode}, recommended {self.requirements.COLOR_MODE}")
                
                # Проверка размера файла
                file_size_mb = image_path.stat().st_size / (1024 * 1024)
                if file_size_mb > self.requirements.MAX_FILE_SIZE_MB:
                    errors.append(f"File too large: {file_size_mb:.1f}MB, max {self.requirements.MAX_FILE_SIZE_MB}MB")
                
        except Exception as e:
            errors.append(f"Cannot read image: {e}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'path': str(image_path)
        }
    
    def create_variations(
        self,
        input_path: Path,
        output_dir: Path,
        sizes: list = None
    ) -> list:
        """
        Создать варианты обложек разных размеров
        (для разных платформ)
        """
        if sizes is None:
            sizes = [3000, 1500, 600, 300]  # Полный, превью, мини, иконка
        
        results = []
        
        with Image.open(input_path) as img:
            base_name = input_path.stem
            
            for size in sizes:
                output_path = output_dir / f"{base_name}_{size}.jpg"
                
                # Resize
                resized = img.resize((size, size), Image.Resampling.LANCZOS)
                
                # Сохраняем
                output_path.parent.mkdir(parents=True, exist_ok=True)
                resized.save(output_path, 'JPEG', quality=90, optimize=True)
                
                results.append({
                    'size': size,
                    'path': str(output_path)
                })
                
                logger.debug(f"Created variation: {size}x{size}")
        
        return results
    
    def add_text_overlay(
        self,
        image_path: Path,
        text: str,
        output_path: Path,
        position: str = 'bottom',
        font_size: int = 100
    ) -> Path:
        """
        Добавить текст на обложку (название альбома)
        Внимание: Для дистрибьюторов текст НЕ рекомендуется!
        Использовать только для превью/соцсетей.
        """
        from PIL import ImageDraw, ImageFont
        
        with Image.open(image_path) as img:
            draw = ImageDraw.Draw(img)
            
            # Загружаем шрифт (используем дефолтный если нет файла)
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                font = ImageFont.load_default()
            
            # Получаем размер текста
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Позиция
            img_width, img_height = img.size
            if position == 'bottom':
                x = (img_width - text_width) // 2
                y = img_height - text_height - 100
            elif position == 'center':
                x = (img_width - text_width) // 2
                y = (img_height - text_height) // 2
            else:
                x = 50
                y = 50
            
            # Тень
            draw.text((x+2, y+2), text, fill='black', font=font)
            # Текст
            draw.text((x, y), text, fill='white', font=font)
            
            img.save(output_path)
            logger.info(f"Added text overlay: {output_path}")
            
        return output_path


def check_cover_requirements(image_path: Path) -> bool:
    """Быстрая проверка обложки"""
    processor = ImageProcessor()
    result = processor.validate_cover(image_path)
    
    if not result['valid']:
        logger.error(f"Cover validation failed: {result['errors']}")
        return False
    
    if result['warnings']:
        logger.warning(f"Cover warnings: {result['warnings']}")
    
    return True
