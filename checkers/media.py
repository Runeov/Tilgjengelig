"""
WCAG Media Accessibility Checker
Covers: 1.2.1-1.2.5 Time-based Media, 1.4.2 Audio Control
"""

from dataclasses import dataclass


@dataclass
class Issue:
    rule_id: str
    criterion_id: str
    criterion_name: str
    criterion_name_en: str
    level: str
    impact: str
    element: str
    selector: str
    issue: str
    fix: str
    context: str = ""


def check_media(soup, url, html=None):
    """Check media elements for accessibility issues."""
    issues = []
    passed = []
    warnings = []
    
    # Check video elements
    videos = soup.find_all('video')
    for video in videos:
        element_str = str(video)[:200]
        src = video.get('src', '')
        
        # Check for track element (captions/subtitles)
        tracks = video.find_all('track')
        has_captions = False
        has_descriptions = False
        
        for track in tracks:
            kind = track.get('kind', '')
            if kind in ['captions', 'subtitles']:
                has_captions = True
            if kind == 'descriptions':
                has_descriptions = True
        
        if not has_captions:
            issues.append(Issue(
                rule_id="1.2.2",
                criterion_id="1.2.2",
                criterion_name="Teksting",
                criterion_name_en="Captions (Prerecorded)",
                level="A",
                impact="critical",
                element=element_str,
                selector="video",
                issue="Video has no captions track",
                fix="Add <track kind='captions' src='captions.vtt' srclang='nb' label='Norsk'>"
            ))
        else:
            passed.append("1.2.2: Video has captions track")
        
        if not has_descriptions:
            warnings.append("1.2.5: Video has no audio descriptions - may be needed for visual content")
        
        # Check for autoplay
        if video.get('autoplay') is not None:
            muted = video.get('muted') is not None
            if not muted:
                issues.append(Issue(
                    rule_id="1.4.2",
                    criterion_id="1.4.2",
                    criterion_name="Styring av lyd",
                    criterion_name_en="Audio Control",
                    level="A",
                    impact="critical",
                    element=element_str,
                    selector="video[autoplay]",
                    issue="Video autoplays with sound",
                    fix="Either remove autoplay, add muted attribute, or provide controls to stop/mute"
                ))
            else:
                passed.append("1.4.2: Autoplay video is muted")
        
        # Check for controls
        if video.get('controls') is None:
            issues.append(Issue(
                rule_id="1.4.2",
                criterion_id="1.4.2",
                criterion_name="Styring av lyd",
                criterion_name_en="Audio Control",
                level="A",
                impact="serious",
                element=element_str,
                selector="video",
                issue="Video has no native controls",
                fix="Add controls attribute or provide custom accessible controls"
            ))
    
    # Check audio elements
    audios = soup.find_all('audio')
    for audio in audios:
        element_str = str(audio)[:200]
        
        # Check for autoplay
        if audio.get('autoplay') is not None:
            issues.append(Issue(
                rule_id="1.4.2",
                criterion_id="1.4.2",
                criterion_name="Styring av lyd",
                criterion_name_en="Audio Control",
                level="A",
                impact="critical",
                element=element_str,
                selector="audio[autoplay]",
                issue="Audio autoplays - may interfere with screen readers",
                fix="Remove autoplay or ensure audio stops within 3 seconds"
            ))
        
        # Check for controls
        if audio.get('controls') is None:
            issues.append(Issue(
                rule_id="1.4.2",
                criterion_id="1.4.2",
                criterion_name="Styring av lyd",
                criterion_name_en="Audio Control",
                level="A",
                impact="serious",
                element=element_str,
                selector="audio",
                issue="Audio has no native controls",
                fix="Add controls attribute or provide custom accessible controls"
            ))
        
        # Audio should have transcript
        warnings.append("1.2.1: Audio content should have text transcript available")
    
    # Check for iframes (may contain video)
    iframes = soup.find_all('iframe')
    for iframe in iframes:
        src = iframe.get('src', '').lower()
        element_str = str(iframe)[:200]
        
        # Check for common video platforms
        video_platforms = ['youtube', 'vimeo', 'dailymotion', 'wistia', 'brightcove']
        is_video = any(platform in src for platform in video_platforms)
        
        if is_video:
            warnings.append(f"1.2.2: Embedded video found - verify captions are available: {src[:50]}")
        
        # Check iframe has title
        if not iframe.get('title'):
            issues.append(Issue(
                rule_id="4.1.2",
                criterion_id="4.1.2",
                criterion_name="Navn, rolle, verdi",
                criterion_name_en="Name, Role, Value",
                level="A",
                impact="serious",
                element=element_str,
                selector="iframe",
                issue="iframe is missing title attribute",
                fix="Add descriptive title attribute to iframe"
            ))
        else:
            passed.append(f"4.1.2: iframe has title: {iframe.get('title')[:30]}")
    
    # Check for object/embed elements
    objects = soup.find_all(['object', 'embed'])
    for obj in objects:
        element_str = str(obj)[:200]
        
        issues.append(Issue(
            rule_id="1.1.1f",
            criterion_id="1.1.1",
            criterion_name="Ikke-tekstlig innhold",
            criterion_name_en="Non-text Content",
            level="A",
            impact="serious",
            element=element_str,
            selector=obj.name,
            issue=f"{obj.name} element found - ensure accessible alternative exists",
            fix="Provide text alternative or accessible fallback content"
        ))
    
    # Check for bgsound (very old, but still seen)
    bgsounds = soup.find_all('bgsound')
    for bg in bgsounds:
        issues.append(Issue(
            rule_id="1.4.2",
            criterion_id="1.4.2",
            criterion_name="Styring av lyd",
            criterion_name_en="Audio Control",
            level="A",
            impact="critical",
            element=str(bg)[:200],
            selector="bgsound",
            issue="Background sound autoplays with no controls",
            fix="Remove bgsound element - use audio with controls instead"
        ))
    
    return issues, passed, warnings
