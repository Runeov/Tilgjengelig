"""
WCAG 1.2.x Media Checker
Checks video and audio elements for accessibility.
"""

from bs4 import BeautifulSoup

RULE_INFO = {
    "1.2.2a": {
        "criterion": "1.2.2",
        "criterion_name": "Teksting",
        "criterion_name_en": "Captions (Prerecorded)",
        "level": "A",
    },
    "1.4.2a": {
        "criterion": "1.4.2",
        "criterion_name": "Styring av lyd",
        "criterion_name_en": "Audio Control",
        "level": "A",
    }
}


def check_media(soup, url, **kwargs):
    """
    Check video and audio elements for accessibility.
    
    Returns tuple of (issues, passed, warnings).
    """
    issues = []
    passed = []
    warnings = []
    
    # Check video elements
    videos = soup.find_all('video')
    
    for video in videos:
        # Check for captions/subtitles
        tracks = video.find_all('track')
        caption_tracks = [t for t in tracks if t.get('kind') in ('captions', 'subtitles')]
        
        if not caption_tracks:
            rule = RULE_INFO["1.2.2a"]
            element_str = str(video)[:200]
            warnings.append({
                "rule_id": "1.2.2a",
                "criterion_id": rule["criterion"],
                "criterion_name": rule["criterion_name"],
                "criterion_name_en": rule["criterion_name_en"],
                "level": rule["level"],
                "impact": "serious",
                "element": element_str,
                "selector": _get_selector(video),
                "issue": "Video mangler tekstspor (captions/subtitles)",
                "fix": "Legg til <track kind='captions'> eller <track kind='subtitles'> element"
            })
        else:
            passed.append({
                "rule_id": "1.2.2a",
                "criterion_id": "1.2.2",
                "criterion_name": "Teksting",
                "message": "Video har tekstspor"
            })
        
        # Check for autoplay with audio
        if video.has_attr('autoplay') and not video.has_attr('muted'):
            rule = RULE_INFO["1.4.2a"]
            element_str = str(video)[:200]
            issues.append({
                "rule_id": "1.4.2a",
                "criterion_id": rule["criterion"],
                "criterion_name": rule["criterion_name"],
                "criterion_name_en": rule["criterion_name_en"],
                "level": rule["level"],
                "impact": "serious",
                "element": element_str,
                "selector": _get_selector(video),
                "issue": "Video har autoplay uten å være dempet",
                "fix": "Legg til 'muted' attributt eller fjern 'autoplay'"
            })
    
    # Check audio elements
    audios = soup.find_all('audio')
    
    for audio in audios:
        if audio.has_attr('autoplay'):
            rule = RULE_INFO["1.4.2a"]
            element_str = str(audio)[:200]
            issues.append({
                "rule_id": "1.4.2a",
                "criterion_id": rule["criterion"],
                "criterion_name": rule["criterion_name"],
                "criterion_name_en": rule["criterion_name_en"],
                "level": rule["level"],
                "impact": "serious",
                "element": element_str,
                "selector": _get_selector(audio),
                "issue": "Lyd starter automatisk",
                "fix": "Fjern autoplay eller gi bruker kontroll over lyden"
            })
    
    # Check for iframes with video content (YouTube, Vimeo, etc.)
    iframes = soup.find_all('iframe')
    video_iframes = []
    
    for iframe in iframes:
        src = iframe.get('src', '').lower()
        if any(platform in src for platform in ['youtube', 'vimeo', 'dailymotion', 'wistia']):
            video_iframes.append(iframe)
    
    for iframe in video_iframes[:3]:
        src = iframe.get('src', '')[:100]
        element_str = str(iframe)[:200]
        warnings.append({
            "rule_id": "1.2.2a",
            "criterion_id": "1.2.2",
            "criterion_name": "Teksting",
            "criterion_name_en": "Captions (Prerecorded)",
            "level": "A",
            "impact": "moderate",
            "element": element_str,
            "selector": _get_selector(iframe),
            "issue": f"Video fra ekstern tjeneste - verifiser at teksting er tilgjengelig: {src}",
            "fix": "Sørg for at innebygd video har teksting aktivert"
        })
    
    # Summary
    total_media = len(videos) + len(audios) + len(video_iframes)
    if total_media == 0:
        passed.append({
            "rule_id": "1.2.2a",
            "criterion_id": "1.2.2",
            "criterion_name": "Teksting",
            "message": "Ingen video- eller lydelementer funnet på siden"
        })
    
    return issues, passed, warnings


def _get_selector(element):
    """Generate a CSS-like selector for an element."""
    parts = []
    for parent in element.parents:
        if parent.name is None:
            break
        if parent.name == '[document]':
            break
        parts.append(parent.name)
    parts.reverse()
    parts.append(element.name)
    
    if element.get('id'):
        parts[-1] += f"#{element['id']}"
    elif element.get('class'):
        classes = element['class']
        if isinstance(classes, str):
            classes = classes.split()
        parts[-1] += f".{'.'.join(classes[:2])}"
    
    return ' > '.join(parts[-4:])
