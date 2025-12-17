"""
Генерация PNG иконок для расширения Movie Lottery.
Запустите этот скрипт для создания иконок:
    python generate_icons.py

Требует: pip install pillow cairosvg
"""

import os
import sys

def generate_from_svg():
    """Генерирует PNG из SVG с помощью cairosvg."""
    try:
        import cairosvg
        from PIL import Image
        import io
    except ImportError:
        print("Установите зависимости: pip install pillow cairosvg")
        return False
    
    icons_dir = os.path.dirname(os.path.abspath(__file__))
    icons_subdir = os.path.join(icons_dir, 'icons')
    svg_path = os.path.join(icons_subdir, 'icon.svg')
    
    if not os.path.exists(svg_path):
        print(f"SVG файл не найден: {svg_path}")
        return False
    
    sizes = [16, 32, 48, 128]
    
    for size in sizes:
        png_data = cairosvg.svg2png(
            url=svg_path,
            output_width=size,
            output_height=size
        )
        
        filename = f'icon{size}.png'
        filepath = os.path.join(icons_subdir, filename)
        
        with open(filepath, 'wb') as f:
            f.write(png_data)
        
        print(f'✓ Создан {filename}')
    
    print(f'\nВсе иконки сохранены в {icons_subdir}')
    return True


def generate_fallback():
    """Создаёт иконки программно с помощью PIL (fallback если нет cairosvg)."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("Установите Pillow: pip install pillow")
        return False
    
    def create_icon(size):
        """Создаёт иконку заданного размера в новом стиле."""
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        scale = size / 128
        
        # Цвета нового дизайна
        purple_start = (99, 102, 241)  # #6366f1
        purple_mid = (168, 85, 247)    # #a855f7
        pink_end = (236, 72, 153)      # #ec4899
        gold = (252, 211, 77)          # #fcd34d
        dark = (30, 27, 75)            # #1e1b4b
        
        # Скругленный фон с градиентом (имитация)
        margin = int(4 * scale)
        corner_radius = int(28 * scale)
        
        # Создаём градиент вручную
        for y in range(size):
            for x in range(size):
                # Проверяем, находится ли точка внутри скруглённого прямоугольника
                if margin <= x < size - margin and margin <= y < size - margin:
                    # Проверка углов
                    in_rect = True
                    
                    # Верхний левый угол
                    if x < margin + corner_radius and y < margin + corner_radius:
                        dx = x - (margin + corner_radius)
                        dy = y - (margin + corner_radius)
                        if dx * dx + dy * dy > corner_radius * corner_radius:
                            in_rect = False
                    
                    # Верхний правый угол
                    if x >= size - margin - corner_radius and y < margin + corner_radius:
                        dx = x - (size - margin - corner_radius)
                        dy = y - (margin + corner_radius)
                        if dx * dx + dy * dy > corner_radius * corner_radius:
                            in_rect = False
                    
                    # Нижний левый угол
                    if x < margin + corner_radius and y >= size - margin - corner_radius:
                        dx = x - (margin + corner_radius)
                        dy = y - (size - margin - corner_radius)
                        if dx * dx + dy * dy > corner_radius * corner_radius:
                            in_rect = False
                    
                    # Нижний правый угол
                    if x >= size - margin - corner_radius and y >= size - margin - corner_radius:
                        dx = x - (size - margin - corner_radius)
                        dy = y - (size - margin - corner_radius)
                        if dx * dx + dy * dy > corner_radius * corner_radius:
                            in_rect = False
                    
                    if in_rect:
                        # Градиент по диагонали
                        t = (x + y) / (2 * size)
                        
                        if t < 0.5:
                            t2 = t * 2
                            r = int(purple_start[0] * (1 - t2) + purple_mid[0] * t2)
                            g = int(purple_start[1] * (1 - t2) + purple_mid[1] * t2)
                            b = int(purple_start[2] * (1 - t2) + purple_mid[2] * t2)
                        else:
                            t2 = (t - 0.5) * 2
                            r = int(purple_mid[0] * (1 - t2) + pink_end[0] * t2)
                            g = int(purple_mid[1] * (1 - t2) + pink_end[1] * t2)
                            b = int(purple_mid[2] * (1 - t2) + pink_end[2] * t2)
                        
                        img.putpixel((x, y), (r, g, b, 255))
        
        # Рисуем хлопушку (clapperboard)
        # Основная часть
        clap_y = int(52 * scale)
        clap_h = int(52 * scale)
        clap_x = int(24 * scale)
        clap_w = int(80 * scale)
        
        draw.rounded_rectangle(
            [clap_x, clap_y, clap_x + clap_w, clap_y + clap_h],
            radius=int(6 * scale),
            fill=(*dark, 230)
        )
        
        # Верхняя золотая часть хлопушки
        top_y = int(36 * scale)
        top_h = int(16 * scale)
        draw.rounded_rectangle(
            [clap_x - int(2 * scale), top_y, clap_x + clap_w + int(2 * scale), top_y + top_h],
            radius=int(4 * scale),
            fill=gold
        )
        
        # Полоски на хлопушке
        stripe_w = int(16 * scale)
        for i in range(5):
            sx = clap_x + i * int(20 * scale)
            if sx + stripe_w < clap_x + clap_w:
                # Диагональная полоска
                points = [
                    (sx, top_y),
                    (sx + stripe_w, top_y),
                    (sx + stripe_w - int(8 * scale), top_y + top_h),
                    (sx - int(8 * scale), top_y + top_h)
                ]
                draw.polygon(points, fill=dark)
        
        # Золотой игральный кубик в центре
        dice_size = int(28 * scale)
        dice_x = int(50 * scale)
        dice_y = int(64 * scale)
        
        draw.rounded_rectangle(
            [dice_x, dice_y, dice_x + dice_size, dice_y + dice_size],
            radius=int(5 * scale),
            fill=gold
        )
        
        # Точки на кубике
        dot_r = max(1, int(2.5 * scale))
        dot_positions = [
            (0.25, 0.25), (0.75, 0.25),
            (0.5, 0.5),
            (0.25, 0.75), (0.75, 0.75)
        ]
        
        for px, py in dot_positions:
            cx = dice_x + int(dice_size * px)
            cy = dice_y + int(dice_size * py)
            draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=dark)
        
        # Блестки
        if size >= 32:
            sparkle_color = (255, 255, 255, 230)
            
            # Большая звёздочка
            sx, sy = int(100 * scale), int(28 * scale)
            sparkle_size = int(6 * scale)
            draw.polygon([
                (sx, sy - sparkle_size),
                (sx + int(2 * scale), sy - int(2 * scale)),
                (sx + sparkle_size, sy),
                (sx + int(2 * scale), sy + int(2 * scale)),
                (sx, sy + sparkle_size),
                (sx - int(2 * scale), sy + int(2 * scale)),
                (sx - sparkle_size, sy),
                (sx - int(2 * scale), sy - int(2 * scale))
            ], fill=sparkle_color)
            
            # Маленькие точки
            draw.ellipse([int(90 * scale) - 2, int(100 * scale) - 2, 
                         int(90 * scale) + 2, int(100 * scale) + 2], 
                        fill=(255, 255, 255, 150))
        
        return img
    
    sizes = [16, 32, 48, 128]
    icons_dir = os.path.dirname(os.path.abspath(__file__))
    icons_subdir = os.path.join(icons_dir, 'icons')
    
    os.makedirs(icons_subdir, exist_ok=True)
    
    for size in sizes:
        icon = create_icon(size)
        filename = f'icon{size}.png'
        filepath = os.path.join(icons_subdir, filename)
        icon.save(filepath, 'PNG')
        print(f'✓ Создан {filename}')
    
    print(f'\nВсе иконки сохранены в {icons_subdir}')
    return True


def main():
    """Генерирует все необходимые размеры иконок."""
    print("Movie Lottery - Генерация иконок\n")
    
    # Пробуем сначала из SVG (лучшее качество)
    try:
        import cairosvg
        print("Используем cairosvg для конвертации SVG...")
        if generate_from_svg():
            return
    except ImportError:
        print("cairosvg не установлен, используем PIL fallback...")
    
    # Fallback на PIL
    generate_fallback()


if __name__ == '__main__':
    main()
