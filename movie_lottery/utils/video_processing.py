"""Video processing utilities using FFmpeg."""
import logging
import os
import shutil
import subprocess
import tempfile

logger = logging.getLogger(__name__)

# Extensions that support/need faststart optimization
FASTSTART_EXTENSIONS = {'.mp4', '.mov', '.m4v', '.m4a'}


def is_ffmpeg_available():
    """Check if FFmpeg is available on the system."""
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def should_apply_faststart(file_path):
    """Check if faststart should be applied to this file type."""
    ext = os.path.splitext(file_path)[1].lower()
    return ext in FASTSTART_EXTENSIONS


def apply_faststart(input_path):
    """
    Apply faststart optimization to a video file.
    
    Moves the moov atom to the beginning of the file for faster web playback.
    The file is modified in-place using a temporary file.
    
    Args:
        input_path: Path to the video file to process
        
    Returns:
        dict with keys:
            - success: bool
            - message: str
            - new_size: int (file size after processing, if successful)
    """
    if not os.path.exists(input_path):
        return {
            'success': False,
            'message': f'Файл не найден: {input_path}',
            'new_size': None
        }
    
    if not should_apply_faststart(input_path):
        ext = os.path.splitext(input_path)[1].lower()
        return {
            'success': True,
            'message': f'Faststart не требуется для {ext} файлов',
            'new_size': os.path.getsize(input_path)
        }
    
    if not is_ffmpeg_available():
        logger.warning('FFmpeg не установлен, пропускаем faststart оптимизацию')
        return {
            'success': False,
            'message': 'FFmpeg не установлен на сервере',
            'new_size': None
        }
    
    # Create temporary file in the same directory to ensure same filesystem
    dir_path = os.path.dirname(input_path)
    fd, temp_path = tempfile.mkstemp(suffix='.mp4', dir=dir_path)
    os.close(fd)
    
    try:
        # Run FFmpeg with faststart flag
        # -y: overwrite output without asking
        # -i: input file
        # -c copy: copy streams without re-encoding (fast, no quality loss)
        # -movflags +faststart: move moov atom to the beginning
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-c', 'copy',
            '-movflags', '+faststart',
            temp_path
        ]
        
        logger.info('Применяем faststart к %s', input_path)
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=300  # 5 minute timeout for large files
        )
        
        if result.returncode != 0:
            stderr = result.stderr.decode('utf-8', errors='replace')
            logger.error('FFmpeg ошибка для %s: %s', input_path, stderr)
            return {
                'success': False,
                'message': f'FFmpeg ошибка: {stderr[:200]}',
                'new_size': None
            }
        
        # Replace original file with processed one
        shutil.move(temp_path, input_path)
        new_size = os.path.getsize(input_path)
        
        logger.info('Faststart успешно применён к %s (размер: %d)', input_path, new_size)
        
        return {
            'success': True,
            'message': 'Faststart успешно применён',
            'new_size': new_size
        }
        
    except subprocess.TimeoutExpired:
        logger.error('FFmpeg таймаут для %s', input_path)
        return {
            'success': False,
            'message': 'Таймаут обработки видео',
            'new_size': None
        }
    except Exception as exc:
        logger.exception('Ошибка при обработке видео %s: %s', input_path, exc)
        return {
            'success': False,
            'message': f'Ошибка обработки: {str(exc)}',
            'new_size': None
        }
    finally:
        # Clean up temp file if it still exists
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass










