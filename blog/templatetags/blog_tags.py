import re
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter(name='link_barcodes')
def link_barcodes(text):
    # Matches exactly 13-digit barcode strings
    pattern = r'\b(\d{13})\b'
    # Wraps the barcode in a link pointing to the product URL
    replacement = r'<a href="/product/\1/" class="link">\1</a>'
    return mark_safe(re.sub(pattern, replacement, str(text)))