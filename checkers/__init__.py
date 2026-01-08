"""
WCAG Checkers Package
Individual check modules for WCAG 2.1 compliance testing.
"""

from .images import check_images
from .headings import check_headings
from .links import check_links
from .forms import check_forms
from .contrast import check_contrast
from .keyboard import check_keyboard
from .language import check_language
from .structure import check_structure
from .media import check_media
from .aria import check_aria
from .use_of_color import check_use_of_color
from .name_role_value import check_name_role_value
from .non_text_contrast import check_non_text_contrast

__all__ = [
    'check_images',
    'check_headings',
    'check_links',
    'check_forms',
    'check_contrast',
    'check_keyboard',
    'check_language',
    'check_structure',
    'check_media',
    'check_aria',
    'check_use_of_color',
    'check_name_role_value',
    'check_non_text_contrast',
]
