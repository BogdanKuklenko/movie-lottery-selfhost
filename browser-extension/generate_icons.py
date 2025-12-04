"""
Генерация PNG иконок для расширения Movie Lottery.
Запустите этот скрипт для создания иконок:
    python generate_icons.py
"""

from PIL import Image, ImageDraw
import os

def create_icon(size):
    """Создаёт иконку заданного размера."""
    # Создаём изображение с прозрачным фоном
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Параметры
    margin = size * 0.05
    center = size / 2
    
    # Градиент фона (имитация) - используем сплошной оранжевый
    # Рисуем круг
    circle_bbox = [margin, margin, size - margin, size - margin]
    draw.ellipse(circle_bbox, fill='#ff5500')
    
    # Добавляем более светлый оверлей в верхней части для эффекта градиента
    overlay = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    
    # Верхняя часть чуть светлее
    for i in range(int(size * 0.4)):
        alpha = int(40 * (1 - i / (size * 0.4)))
        overlay_draw.ellipse(
            [margin + i * 0.3, margin, size - margin - i * 0.3, size - margin],
            fill=(255, 149, 0, alpha)
        )
    
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)
    
    # Масштаб для элементов
    scale = size / 128
    
    # Цвет элементов
    white = '#ffffff'
    
    # Рамка плёнки
    rect_x1 = int(28 * scale)
    rect_y1 = int(36 * scale)
    rect_x2 = int(100 * scale)
    rect_y2 = int(92 * scale)
    rect_radius = int(6 * scale)
    line_width = max(1, int(5 * scale))
    
    # Рисуем скруглённый прямоугольник (рамка)
    draw.rounded_rectangle(
        [rect_x1, rect_y1, rect_x2, rect_y2],
        radius=rect_radius,
        outline=white,
        width=line_width
    )
    
    # Перфорации слева
    perf_width = max(2, int(8 * scale))
    perf_height = max(2, int(6 * scale))
    perf_x_left = int(32 * scale)
    
    for y_offset in [44, 56, 68, 80]:
        y = int(y_offset * scale)
        draw.rounded_rectangle(
            [perf_x_left, y, perf_x_left + perf_width, y + perf_height],
            radius=max(1, int(scale)),
            fill=white
        )
    
    # Перфорации справа
    perf_x_right = int(88 * scale)
    
    for y_offset in [44, 56, 68, 80]:
        y = int(y_offset * scale)
        draw.rounded_rectangle(
            [perf_x_right, y, perf_x_right + perf_width, y + perf_height],
            radius=max(1, int(scale)),
            fill=white
        )
    
    # Плюс в центре
    plus_h_width = max(3, int(40 * scale))
    plus_h_height = max(2, int(12 * scale))
    plus_v_width = max(2, int(16 * scale))
    plus_v_height = max(3, int(28 * scale))
    
    # Горизонтальная часть плюса
    h_x = int(44 * scale)
    h_y = int(58 * scale)
    draw.rounded_rectangle(
        [h_x, h_y, h_x + plus_h_width, h_y + plus_h_height],
        radius=max(1, int(2 * scale)),
        fill=white
    )
    
    # Вертикальная часть плюса
    v_x = int(56 * scale)
    v_y = int(50 * scale)
    draw.rounded_rectangle(
        [v_x, v_y, v_x + plus_v_width, v_y + plus_v_height],
        radius=max(1, int(2 * scale)),
        fill=white
    )
    
    return img


def main():
    """Генерирует все необходимые размеры иконок."""
    sizes = [16, 32, 48, 128]
    icons_dir = os.path.dirname(os.path.abspath(__file__))
    icons_subdir = os.path.join(icons_dir, 'icons')
    
    # Создаём директорию если её нет
    os.makedirs(icons_subdir, exist_ok=True)
    
    for size in sizes:
        icon = create_icon(size)
        filename = f'icon{size}.png'
        filepath = os.path.join(icons_subdir, filename)
        icon.save(filepath, 'PNG')
        print(f'✓ Создан {filename}')
    
    print(f'\nВсе иконки сохранены в {icons_subdir}')


if __name__ == '__main__':
    main()

