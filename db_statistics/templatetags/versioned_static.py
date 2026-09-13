import os

from django import template
from django.conf import settings
from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import staticfiles_storage

register = template.Library()


@register.simple_tag
def static_versioned(path):
    """Возвращает URL статического файла с автоматическим сбросом кэша.

    В продакшене whitenoise уже добавляет хэш содержимого в имя файла (см.
    STORAGES в db/settings.py), так что там достаточно обычного {% static %}.
    В разработке (DEBUG=True) хранилище файлы не хэширует, поэтому вместо
    того чтобы вручную поднимать ?v=NN в шаблоне при каждой правке кода,
    добавляем время последнего изменения файла на диске — оно меняется само.
    """
    url = staticfiles_storage.url(path)
    if not settings.DEBUG:
        return url
    absolute_path = finders.find(path)
    if not absolute_path:
        return url
    version = int(os.path.getmtime(absolute_path))
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}v={version}"
