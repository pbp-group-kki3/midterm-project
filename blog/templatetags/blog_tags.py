import re

from django import template
from django.urls import reverse
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe

register = template.Library()


# Escape article text before inserting links for recognized barcodes.
@register.filter(name="link_barcodes")
def link_barcodes(text):
    text = str(text)
    parts = []
    position = 0

    for match in re.finditer(r"\b([0-9]{13})\b", text):
        parts.append(str(escape(text[position:match.start()])))
        barcode = match.group(1)
        parts.append(str(format_html(
            '<a href="{}" class="link">{}</a>',
            reverse("main:product_detail", args=[barcode]),
            barcode,
        )))
        position = match.end()

    parts.append(str(escape(text[position:])))
    return mark_safe("".join(parts))