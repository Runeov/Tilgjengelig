# Hamsunsenteret.no - Accessibility Fix Guide

**Site:** https://hamsunsenteret.no
**Scan Date:** 2026-02-06
**Total Critical Issues:** 970

---

## Issue #1: Empty Links (617 instances)

### Problem
Links without accessible text. Screen readers announce "link" but cannot tell users where it goes.

### Current Code (Bad)
```html
<!-- Empty link -->
<a href="/some-page"></a>

<!-- Link with only an icon -->
<a href="/search"><i class="icon-search"></i></a>

<!-- Link wrapping empty content -->
<a href="/page">
  <span></span>
</a>
```

### Fixed Code (Good)
```html
<!-- Add visible text -->
<a href="/some-page">Les mer</a>

<!-- Add aria-label for icon-only links -->
<a href="/search" aria-label="Søk">
  <i class="icon-search" aria-hidden="true"></i>
</a>

<!-- Add screen reader text -->
<a href="/page">
  <span class="visually-hidden">Gå til side</span>
  <span>→</span>
</a>
```

### CSS for Visually Hidden Text
```css
.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
```

### JavaScript Fix (Bulk)
```javascript
// Find and fix empty links
document.querySelectorAll('a').forEach(link => {
  const text = link.textContent.trim();
  const ariaLabel = link.getAttribute('aria-label');
  const title = link.getAttribute('title');
  const img = link.querySelector('img[alt]:not([alt=""])');

  if (!text && !ariaLabel && !title && !img) {
    console.warn('Empty link found:', link.href);
    // Add aria-label based on URL or set a default
    const urlPath = new URL(link.href).pathname;
    link.setAttribute('aria-label', `Gå til ${urlPath}`);
  }
});
```

---

## Issue #2: Missing Alt Attributes (198 instances)

### Problem
Images without `alt` attribute. Screen readers cannot describe these images.

### Current Code (Bad)
```html
<img src="photo.jpg">
<img src="banner.jpg" class="hero-image">
```

### Fixed Code (Good)
```html
<!-- Informative image - describe content -->
<img src="photo.jpg" alt="Knut Hamsun foran Hamsunsenteret i 1920">

<!-- Decorative image - use empty alt -->
<img src="decorative-border.jpg" alt="">

<!-- Complex image - use longer description -->
<img src="chart.jpg" alt="Besøkstall 2024" aria-describedby="chart-desc">
<p id="chart-desc">Grafen viser økende besøkstall fra januar til august...</p>
```

### JavaScript Fix (Bulk)
```javascript
// Find images without alt
document.querySelectorAll('img:not([alt])').forEach(img => {
  console.warn('Image missing alt:', img.src);

  // For decorative images, add empty alt
  if (img.classList.contains('decorative') ||
      img.closest('.background') ||
      img.getAttribute('role') === 'presentation') {
    img.setAttribute('alt', '');
  } else {
    // For content images, add placeholder (must be manually reviewed)
    img.setAttribute('alt', '[Bilde mangler beskrivelse]');
  }
});
```

---

## Issue #3: Linked Images with Empty Alt (154 instances)

### Problem
Images used as links with `alt=""` but the link has no other text.

### Current Code (Bad)
```html
<a href="/article/123">
  <img src="thumbnail.jpg" alt="">
</a>

<a href="/event">
  <img src="event-banner.jpg" alt="">
</a>
```

### Fixed Code (Good)
```html
<!-- Add descriptive alt to linked image -->
<a href="/article/123">
  <img src="thumbnail.jpg" alt="Les artikkelen: Hamsuns barndom">
</a>

<!-- Or add visible text alongside image -->
<a href="/event">
  <img src="event-banner.jpg" alt="">
  <span>Sommerutstilling 2024</span>
</a>

<!-- Or use aria-label on the link -->
<a href="/event" aria-label="Sommerutstilling 2024 - Les mer">
  <img src="event-banner.jpg" alt="">
</a>
```

### JavaScript Fix (Bulk)
```javascript
// Find linked images with empty alt
document.querySelectorAll('a img[alt=""]').forEach(img => {
  const link = img.closest('a');
  const linkText = link.textContent.trim();
  const ariaLabel = link.getAttribute('aria-label');

  if (!linkText && !ariaLabel) {
    console.warn('Linked image needs alt:', img.src, 'Link:', link.href);

    // Try to generate alt from URL
    const urlPath = new URL(link.href).pathname;
    const pageName = urlPath.split('/').filter(Boolean).pop() || 'side';
    img.setAttribute('alt', `Gå til ${pageName.replace(/-/g, ' ')}`);
  }
});
```

---

## Issue #4: Form Input with Placeholder Only (1 instance)

### Problem
Form input uses only placeholder text, no proper label.

### Current Code (Bad)
```html
<input type="text" placeholder="Søk...">
<input type="email" placeholder="Din e-post">
```

### Fixed Code (Good)
```html
<!-- Visible label (preferred) -->
<label for="search">Søk</label>
<input type="text" id="search" placeholder="Søk...">

<!-- Hidden label for compact designs -->
<label for="search" class="visually-hidden">Søk</label>
<input type="text" id="search" placeholder="Søk...">

<!-- Or use aria-label -->
<input type="text" placeholder="Søk..." aria-label="Søk på nettstedet">
```

---

## Quick Fix Script

Run this in browser console to identify all issues:

```javascript
(function() {
  const issues = {
    emptyLinks: [],
    missingAlt: [],
    emptyAltLinked: [],
    noLabel: []
  };

  // Empty links
  document.querySelectorAll('a[href]').forEach(link => {
    const hasText = link.textContent.trim();
    const hasAriaLabel = link.getAttribute('aria-label');
    const hasTitle = link.getAttribute('title');
    const hasImgAlt = link.querySelector('img[alt]:not([alt=""])');

    if (!hasText && !hasAriaLabel && !hasTitle && !hasImgAlt) {
      issues.emptyLinks.push(link);
      link.style.outline = '3px solid red';
    }
  });

  // Missing alt
  document.querySelectorAll('img:not([alt])').forEach(img => {
    issues.missingAlt.push(img);
    img.style.outline = '3px solid orange';
  });

  // Empty alt in links
  document.querySelectorAll('a img[alt=""]').forEach(img => {
    const link = img.closest('a');
    if (!link.textContent.trim() && !link.getAttribute('aria-label')) {
      issues.emptyAltLinked.push(img);
      img.style.outline = '3px solid purple';
    }
  });

  // Inputs without labels
  document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"])').forEach(input => {
    const id = input.id;
    const hasLabel = id && document.querySelector(`label[for="${id}"]`);
    const hasAriaLabel = input.getAttribute('aria-label');
    const hasAriaLabelledby = input.getAttribute('aria-labelledby');

    if (!hasLabel && !hasAriaLabel && !hasAriaLabelledby) {
      issues.noLabel.push(input);
      input.style.outline = '3px solid blue';
    }
  });

  console.log('=== ACCESSIBILITY ISSUES ===');
  console.log('Empty links (red):', issues.emptyLinks.length);
  console.log('Missing alt (orange):', issues.missingAlt.length);
  console.log('Empty alt in links (purple):', issues.emptyAltLinked.length);
  console.log('Inputs without labels (blue):', issues.noLabel.length);

  return issues;
})();
```

---

## Priority Fix Order

1. **Empty Links** - Highest impact, 617 instances
2. **Linked Images** - Related to links, 154 instances
3. **Missing Alt** - 198 instances
4. **Form Labels** - 1 instance

## Testing After Fixes

```bash
# Re-run the WCAG checker
python checker.py https://hamsunsenteret.no/forside --browser --max-pages 50 --format html
```

---

**Generated by WCAG Checker**
Based on Norwegian UU-tilsynet test rules
