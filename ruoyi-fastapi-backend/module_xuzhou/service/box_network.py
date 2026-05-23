from urllib.parse import urlparse


def build_box_base_urls(box: dict) -> list[str]:
    urls: list[str] = []
    port = box.get('port') or 9100

    for value in (box.get('ip'), box.get('host')):
        if not value:
            continue
        target = str(value).strip()
        if not target:
            continue

        parsed = urlparse(target if '://' in target else f'http://{target}')
        if not parsed.hostname:
            continue

        parsed_port = parsed.port or port
        base_url = f'{parsed.scheme or "http"}://{parsed.hostname}:{parsed_port}'
        if base_url not in urls:
            urls.append(base_url)

    return urls
