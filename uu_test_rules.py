"""
Official Norwegian WCAG Test Rules from UU-tilsynet
https://www.uutilsynet.no/regelverk/oversikt-over-testregler-nettsteder/709

These are the exact test criteria used by the Norwegian Authority for Universal Design of ICT.
"""

UU_TEST_RULES = {
    # ===========================================
    # 1. MULIG Å OPPFATTE (Perceivable)
    # ===========================================
    
    # 1.1.1 Ikke-tekstlig innhold (Non-text Content)
    "1.1.1a": {
        "id": "1.1.1a",
        "name": "Ikke-lenkede bilder har tekstalternativ",
        "name_en": "Non-linked images have text alternative",
        "criterion": "1.1.1",
        "criterion_name": "Ikke-tekstlig innhold",
        "level": "A",
        "test_object": "Bilder og grafikk",
        "auto": True,
    },
    "1.1.1b": {
        "id": "1.1.1b",
        "name": "Formål med lenkede bilder går frem av lenketekst eller tekstalternativ",
        "name_en": "Purpose of linked images clear from link text or alt",
        "criterion": "1.1.1",
        "criterion_name": "Ikke-tekstlig innhold",
        "level": "A",
        "test_object": "Bilder og grafikk",
        "auto": True,
    },
    "1.1.1c": {
        "id": "1.1.1c",
        "name": "Formål med klikkbare områder i bilder går frem av tekstalternativ",
        "name_en": "Purpose of clickable image areas clear from alt",
        "criterion": "1.1.1",
        "criterion_name": "Ikke-tekstlig innhold",
        "level": "A",
        "test_object": "Bilder og grafikk",
        "auto": True,
    },
    "1.1.1d": {
        "id": "1.1.1d",
        "name": "CAPTCHA har tekstalternativ og alternativ form",
        "name_en": "CAPTCHA has text alternative and alternative form",
        "criterion": "1.1.1",
        "criterion_name": "Ikke-tekstlig innhold",
        "level": "A",
        "test_object": "CAPTCHA",
        "auto": "partial",
    },
    "1.1.1f": {
        "id": "1.1.1f",
        "name": "Video eller lydklipp har tilgjengelig navn med beskrivende identifikasjon",
        "name_en": "Video or audio has accessible name with description",
        "criterion": "1.1.1",
        "criterion_name": "Ikke-tekstlig innhold",
        "level": "A",
        "test_object": "Lyd og videoer",
        "auto": True,
    },
    
    # 1.2.1 Bare lyd og bare video
    "1.2.1a": {
        "id": "1.2.1a",
        "name": "Forhåndsinnspilt lyd har alternativ i form av tekst",
        "name_en": "Pre-recorded audio has text alternative",
        "criterion": "1.2.1",
        "criterion_name": "Bare lyd og bare video",
        "level": "A",
        "test_object": "Lyd og video",
        "auto": "partial",
    },
    "1.2.1b": {
        "id": "1.2.1b",
        "name": "Forhåndsinnspilt video uten lyd har alternativ i form av tekst eller lyd",
        "name_en": "Pre-recorded video without audio has text/audio alternative",
        "criterion": "1.2.1",
        "criterion_name": "Bare lyd og bare video",
        "level": "A",
        "test_object": "Lyd og video",
        "auto": "partial",
    },
    
    # 1.2.2 Teksting (forhåndsinnspilt)
    "1.2.2a": {
        "id": "1.2.2a",
        "name": "Forhåndsinnspilt video med lyd har teksting eller tekstalternativ",
        "name_en": "Pre-recorded video with audio has captions",
        "criterion": "1.2.2",
        "criterion_name": "Teksting",
        "level": "A",
        "test_object": "Lyd og video",
        "auto": True,
    },
    
    # 1.2.5 Synstolking (forhåndsinnspilt)
    "1.2.5a": {
        "id": "1.2.5a",
        "name": "Forhåndsinnspilt video med lyd har synstolking",
        "name_en": "Pre-recorded video has audio description",
        "criterion": "1.2.5",
        "criterion_name": "Synstolking",
        "level": "AA",
        "test_object": "Lyd og video",
        "auto": "partial",
    },
    
    # 1.3.1 Informasjon og relasjoner
    "1.3.1a": {
        "id": "1.3.1a",
        "name": "Visuelle overskrifter er korrekt kodet",
        "name_en": "Visual headings are correctly coded",
        "criterion": "1.3.1",
        "criterion_name": "Informasjon og relasjoner",
        "level": "A",
        "test_object": "Overskrifter",
        "auto": True,
    },
    "1.3.1b": {
        "id": "1.3.1b",
        "name": "Visuelle tabeller er korrekt kodet",
        "name_en": "Visual tables are correctly coded",
        "criterion": "1.3.1",
        "criterion_name": "Informasjon og relasjoner",
        "level": "A",
        "test_object": "Tabeller",
        "auto": True,
    },
    "1.3.1c": {
        "id": "1.3.1c",
        "name": "Visuelle lister er korrekt kodet",
        "name_en": "Visual lists are correctly coded",
        "criterion": "1.3.1",
        "criterion_name": "Informasjon og relasjoner",
        "level": "A",
        "test_object": "Lister",
        "auto": True,
    },
    "1.3.1d": {
        "id": "1.3.1d",
        "name": "Visuell inndeling av innhold i regioner er korrekt kodet",
        "name_en": "Visual regions are correctly coded as landmarks",
        "criterion": "1.3.1",
        "criterion_name": "Informasjon og relasjoner",
        "level": "A",
        "test_object": "Alt innhold",
        "auto": True,
    },
    "1.3.1e": {
        "id": "1.3.1e",
        "name": "Visuelle skjemainstruksjoner er programmatisk koblet",
        "name_en": "Form instructions are programmatically associated",
        "criterion": "1.3.1",
        "criterion_name": "Informasjon og relasjoner",
        "level": "A",
        "test_object": "Skjemaer",
        "auto": True,
    },
    "1.3.1f": {
        "id": "1.3.1f",
        "name": "Visuell spesialtekst er korrekt kodet",
        "name_en": "Special text is correctly coded",
        "criterion": "1.3.1",
        "criterion_name": "Informasjon og relasjoner",
        "level": "A",
        "test_object": "Alt tekstinnhold",
        "auto": "partial",
    },
    
    # 1.3.2 Meningsfylt rekkefølge
    "1.3.2a": {
        "id": "1.3.2a",
        "name": "Meningsfylt leserekkefølge er programmatisk bestemt",
        "name_en": "Meaningful reading sequence is programmatically determined",
        "criterion": "1.3.2",
        "criterion_name": "Meningsfylt rekkefølge",
        "level": "A",
        "test_object": "Navigasjon",
        "auto": "partial",
    },
    
    # 1.3.3 Sensoriske egenskaper
    "1.3.3a": {
        "id": "1.3.3a",
        "name": "Instruksjoner er ikke utelukkende avhengig av sensoriske egenskaper",
        "name_en": "Instructions not solely based on sensory characteristics",
        "criterion": "1.3.3",
        "criterion_name": "Sensoriske egenskaper",
        "level": "A",
        "test_object": "Skjemaer",
        "auto": "partial",
    },
    
    # 1.4.1 Bruk av farge
    "1.4.1a": {
        "id": "1.4.1a",
        "name": "Lenket tekst skiller seg fra annen tekst med mer enn bare farge",
        "name_en": "Linked text distinguished by more than color",
        "criterion": "1.4.1",
        "criterion_name": "Bruk av farge",
        "level": "A",
        "test_object": "Lenker",
        "auto": "partial",
    },
    "1.4.1b": {
        "id": "1.4.1b",
        "name": "Informasjon i grafiske framstillinger skiller seg ut med mer enn bare farge",
        "name_en": "Information in graphics distinguished by more than color",
        "criterion": "1.4.1",
        "criterion_name": "Bruk av farge",
        "level": "A",
        "test_object": "Bilder og grafikk",
        "auto": "partial",
    },
    "1.4.1c": {
        "id": "1.4.1c",
        "name": "Skjemaelementer er merket med mer enn bare farge",
        "name_en": "Form elements marked with more than color",
        "criterion": "1.4.1",
        "criterion_name": "Bruk av farge",
        "level": "A",
        "test_object": "Skjemaelementer",
        "auto": "partial",
    },
    
    # 1.4.2 Styring av lyd
    "1.4.2a": {
        "id": "1.4.2a",
        "name": "Det er mulig å styre lyd som starter automatisk",
        "name_en": "Auto-playing audio can be controlled",
        "criterion": "1.4.2",
        "criterion_name": "Styring av lyd",
        "level": "A",
        "test_object": "Lyd og video",
        "auto": True,
    },
    
    # 1.4.3 Kontrast
    "1.4.3a": {
        "id": "1.4.3a",
        "name": "Det er tilstrekkelig kontrast mellom tekst og bakgrunn",
        "name_en": "Sufficient contrast between text and background",
        "criterion": "1.4.3",
        "criterion_name": "Kontrast",
        "level": "AA",
        "test_object": "Alt tekstinnhold",
        "auto": True,
    },
    "1.4.3b": {
        "id": "1.4.3b",
        "name": "Det er tilstrekkelig kontrast mellom tekst og bakgrunn i bilde av tekst",
        "name_en": "Sufficient contrast in images of text",
        "criterion": "1.4.3",
        "criterion_name": "Kontrast",
        "level": "AA",
        "test_object": "Bilde av tekst",
        "auto": "partial",
    },
    
    # 1.4.4 Endring av tekststørrelse
    "1.4.4a": {
        "id": "1.4.4a",
        "name": "Tekst kan forstørres til minst 200% uten tap av innhold",
        "name_en": "Text can be resized to 200% without loss",
        "criterion": "1.4.4",
        "criterion_name": "Endring av tekststørrelse",
        "level": "AA",
        "test_object": "Alt tekstinnhold",
        "auto": "partial",
    },
    
    # 1.4.5 Bilder av tekst
    "1.4.5a": {
        "id": "1.4.5a",
        "name": "Bilde av tekst er ikke brukt unødvendig",
        "name_en": "Images of text not used unnecessarily",
        "criterion": "1.4.5",
        "criterion_name": "Bilder av tekst",
        "level": "AA",
        "test_object": "Bilder og grafikk",
        "auto": "partial",
    },
    
    # 1.4.10 Dynamisk tilpasning (Reflow)
    "1.4.10a": {
        "id": "1.4.10a",
        "name": "Dynamisk tilpasning av nettsider",
        "name_en": "Content reflows at 320px width",
        "criterion": "1.4.10",
        "criterion_name": "Dynamisk tilpasning",
        "level": "AA",
        "test_object": "Alt innhold",
        "auto": "partial",
    },
    
    # 1.4.11 Kontrast for ikke-tekstlig innhold
    "1.4.11a": {
        "id": "1.4.11a",
        "name": "Tilstrekkelig kontrast for aktive brukergrensesnittkomponenter",
        "name_en": "Sufficient contrast for UI components",
        "criterion": "1.4.11",
        "criterion_name": "Kontrast for ikke-tekstlig innhold",
        "level": "AA",
        "test_object": "Betjeningskomponenter",
        "auto": "partial",
    },
    "1.4.11b": {
        "id": "1.4.11b",
        "name": "Tilstrekkelig kontrast på tilstander for brukergrensesnittkomponenter",
        "name_en": "Sufficient contrast for UI component states",
        "criterion": "1.4.11",
        "criterion_name": "Kontrast for ikke-tekstlig innhold",
        "level": "AA",
        "test_object": "Betjeningskomponenter",
        "auto": "partial",
    },
    "1.4.11c": {
        "id": "1.4.11c",
        "name": "Tilstrekkelig kontrast for grafiske objekter",
        "name_en": "Sufficient contrast for graphics",
        "criterion": "1.4.11",
        "criterion_name": "Kontrast for ikke-tekstlig innhold",
        "level": "AA",
        "test_object": "Bilder og grafikk",
        "auto": "partial",
    },
    
    # 1.4.12 Tekstavstand
    "1.4.12a": {
        "id": "1.4.12a",
        "name": "Det er tilstrekkelig tekstavstand",
        "name_en": "Text spacing can be adjusted",
        "criterion": "1.4.12",
        "criterion_name": "Tekstavstand",
        "level": "AA",
        "test_object": "Alt tekstinnhold",
        "auto": "partial",
    },
    
    # 1.4.13 Pekerfølsomt innhold
    "1.4.13a": {
        "id": "1.4.13a",
        "name": "Pekerfølsomt innhold kan betjenes",
        "name_en": "Hover content can be operated",
        "criterion": "1.4.13",
        "criterion_name": "Pekerfølsomt innhold",
        "level": "AA",
        "test_object": "Alt tekstinnhold",
        "auto": "partial",
    },
    "1.4.13b": {
        "id": "1.4.13b",
        "name": "Innhold ved tastaturfokus kan betjenes",
        "name_en": "Focus content can be operated",
        "criterion": "1.4.13",
        "criterion_name": "Pekerfølsomt innhold",
        "level": "AA",
        "test_object": "Alt tekstinnhold",
        "auto": "partial",
    },
    
    # ===========================================
    # 2. MULIG Å BETJENE (Operable)
    # ===========================================
    
    # 2.1.1 Tastatur
    "2.1.1a": {
        "id": "2.1.1a",
        "name": "Det er mulig å nå innhold og bruke funksjonalitet med tastatur",
        "name_en": "Content accessible via keyboard",
        "criterion": "2.1.1",
        "criterion_name": "Tastatur",
        "level": "A",
        "test_object": "Betjeningskomponenter",
        "auto": "partial",
    },
    
    # 2.1.2 Ingen tastaturfelle
    "2.1.2a": {
        "id": "2.1.2a",
        "name": "Det finnes ingen tastaturfeller på nettsiden",
        "name_en": "No keyboard trap",
        "criterion": "2.1.2",
        "criterion_name": "Ingen tastaturfelle",
        "level": "A",
        "test_object": "Betjeningskomponenter",
        "auto": "partial",
    },
    
    # 2.1.4 Hurtigtaster
    "2.1.4a": {
        "id": "2.1.4a",
        "name": "Hurtigtaster som består av kun ett tegn",
        "name_en": "Character key shortcuts can be disabled",
        "criterion": "2.1.4",
        "criterion_name": "Hurtigtaster",
        "level": "A",
        "test_object": "Alt innhold",
        "auto": "partial",
    },
    
    # 2.2.1 Justerbar hastighet
    "2.2.1a": {
        "id": "2.2.1a",
        "name": "Det er mulig å slå av, justere eller forlenge tidsbegrensninger",
        "name_en": "Time limits can be adjusted",
        "criterion": "2.2.1",
        "criterion_name": "Justerbar hastighet",
        "level": "A",
        "test_object": "Innhold med tidsbegrensninger",
        "auto": "partial",
    },
    
    # 2.2.2 Pause, stopp, skjul
    "2.2.2a": {
        "id": "2.2.2a",
        "name": "Det er mulig å pause, stoppe eller skjule innhold som beveger seg",
        "name_en": "Moving content can be paused",
        "criterion": "2.2.2",
        "criterion_name": "Pause, stopp, skjul",
        "level": "A",
        "test_object": "Innhold som blinker/oppdateres",
        "auto": "partial",
    },
    "2.2.2b": {
        "id": "2.2.2b",
        "name": "Det er mulig å pause, stoppe eller endre oppdateringsfrekvensen",
        "name_en": "Auto-updating content can be controlled",
        "criterion": "2.2.2",
        "criterion_name": "Pause, stopp, skjul",
        "level": "A",
        "test_object": "Innhold som blinker/oppdateres",
        "auto": "partial",
    },
    
    # 2.3.1 Glimt
    "2.3.1a": {
        "id": "2.3.1a",
        "name": "Nettsiden har ikke innhold som glimter",
        "name_en": "No content flashes more than 3 times/second",
        "criterion": "2.3.1",
        "criterion_name": "Terskelverdi på maksimalt tre glimt",
        "level": "A",
        "test_object": "Innhold som blinker/oppdateres",
        "auto": "partial",
    },
    
    # 2.4.1 Hoppe over blokker
    "2.4.1a": {
        "id": "2.4.1a",
        "name": "Det finnes en mekanisme for å omgå blokker med gjentatt innhold",
        "name_en": "Skip link or bypass mechanism exists",
        "criterion": "2.4.1",
        "criterion_name": "Hoppe over blokker",
        "level": "A",
        "test_object": "Betjeningskomponenter",
        "auto": True,
    },
    
    # 2.4.2 Sidetitler
    "2.4.2a": {
        "id": "2.4.2a",
        "name": "Nettsiden har beskrivende sidetittel",
        "name_en": "Page has descriptive title",
        "criterion": "2.4.2",
        "criterion_name": "Sidetitler",
        "level": "A",
        "test_object": "Sidetittel",
        "auto": True,
    },
    
    # 2.4.3 Fokusrekkefølge
    "2.4.3a": {
        "id": "2.4.3a",
        "name": "Tastaturrekkefølge ivaretar meningsinnhold og betjening",
        "name_en": "Focus order preserves meaning",
        "criterion": "2.4.3",
        "criterion_name": "Fokusrekkefølge",
        "level": "A",
        "test_object": "Betjeningskomponenter",
        "auto": "partial",
    },
    
    # 2.4.4 Formål med lenke
    "2.4.4a": {
        "id": "2.4.4a",
        "name": "Formål med lenker går tydelig frem av lenketeksten",
        "name_en": "Link purpose clear from link text",
        "criterion": "2.4.4",
        "criterion_name": "Formål med lenke",
        "level": "A",
        "test_object": "Lenker",
        "auto": True,
    },
    
    # 2.4.5 Flere måter
    "2.4.5a": {
        "id": "2.4.5a",
        "name": "Det er flere måter å navigere på",
        "name_en": "Multiple ways to navigate",
        "criterion": "2.4.5",
        "criterion_name": "Flere måter",
        "level": "AA",
        "test_object": "Alt innhold",
        "auto": "partial",
    },
    
    # 2.4.6 Overskrifter og ledetekster
    "2.4.6a": {
        "id": "2.4.6a",
        "name": "Overskrifter beskriver innholdet",
        "name_en": "Headings describe content",
        "criterion": "2.4.6",
        "criterion_name": "Overskrifter og ledetekster",
        "level": "AA",
        "test_object": "Overskrifter",
        "auto": "partial",
    },
    "2.4.6b": {
        "id": "2.4.6b",
        "name": "Ledetekster beskriver skjemaelement",
        "name_en": "Labels describe form elements",
        "criterion": "2.4.6",
        "criterion_name": "Overskrifter og ledetekster",
        "level": "AA",
        "test_object": "Skjemaer",
        "auto": "partial",
    },
    
    # 2.4.7 Synlig fokus
    "2.4.7a": {
        "id": "2.4.7a",
        "name": "Innhold som kan brukes med tastatur får synlig fokusmarkering",
        "name_en": "Keyboard-operable content has visible focus",
        "criterion": "2.4.7",
        "criterion_name": "Synlig fokus",
        "level": "AA",
        "test_object": "Betjeningskomponenter",
        "auto": "partial",
    },
    
    # 2.5.1 Pekerbevegelser
    "2.5.1a": {
        "id": "2.5.1a",
        "name": "Flerpunkts- eller stibaserte gester kan betjenes med enkelt pekerbevegelse",
        "name_en": "Multipoint gestures have alternatives",
        "criterion": "2.5.1",
        "criterion_name": "Pekerbevegelser",
        "level": "A",
        "test_object": "Betjeningskomponenter",
        "auto": False,
    },
    
    # 2.5.2 Pekeravbrytelse
    "2.5.2a": {
        "id": "2.5.2a",
        "name": "Enkel pekerbevegelse kan avbrytes",
        "name_en": "Pointer actions can be cancelled",
        "criterion": "2.5.2",
        "criterion_name": "Pekeravbrytelse",
        "level": "A",
        "test_object": "Betjeningskomponenter",
        "auto": False,
    },
    
    # 2.5.3 Ledetekst i navn
    "2.5.3a": {
        "id": "2.5.3a",
        "name": "Synlig ledetekst er en del av tilgjengelig navn",
        "name_en": "Visible label is part of accessible name",
        "criterion": "2.5.3",
        "criterion_name": "Ledetekst i navn",
        "level": "A",
        "test_object": "Skjemaer",
        "auto": True,
    },
    
    # 2.5.4 Bevegelsesaktivering
    "2.5.4a": {
        "id": "2.5.4a",
        "name": "Alternativer til bevegelsesaktivering",
        "name_en": "Alternatives to motion activation",
        "criterion": "2.5.4",
        "criterion_name": "Bevegelsesaktivering",
        "level": "A",
        "test_object": "Betjeningskomponenter",
        "auto": False,
    },
    
    # ===========================================
    # 3. FORSTÅELIG (Understandable)
    # ===========================================
    
    # 3.1.1 Språk på siden
    "3.1.1a": {
        "id": "3.1.1a",
        "name": "Hovedspråket på nettsiden er programmatisk bestemt",
        "name_en": "Page language is programmatically set",
        "criterion": "3.1.1",
        "criterion_name": "Språk på siden",
        "level": "A",
        "test_object": "Alt innhold",
        "auto": True,
    },
    
    # 3.1.2 Språk på deler av innhold
    "3.1.2a": {
        "id": "3.1.2a",
        "name": "Innhold på et annet språk enn hovedspråket er programmatisk bestemt",
        "name_en": "Language changes are marked",
        "criterion": "3.1.2",
        "criterion_name": "Språk på deler av innhold",
        "level": "AA",
        "test_object": "Alt innhold",
        "auto": "partial",
    },
    
    # 3.2.1 Fokus
    "3.2.1a": {
        "id": "3.2.1a",
        "name": "Fokus fører ikke til automatisk kontekstendring",
        "name_en": "Focus does not cause context change",
        "criterion": "3.2.1",
        "criterion_name": "Fokus",
        "level": "A",
        "test_object": "Betjeningskomponenter",
        "auto": "partial",
    },
    
    # 3.2.2 Inndata
    "3.2.2a": {
        "id": "3.2.2a",
        "name": "Endret innstilling fører ikke til kontekstendring",
        "name_en": "Input does not cause context change",
        "criterion": "3.2.2",
        "criterion_name": "Inndata",
        "level": "A",
        "test_object": "Skjema",
        "auto": "partial",
    },
    
    # 3.2.3 Konsekvent navigering
    "3.2.3a": {
        "id": "3.2.3a",
        "name": "Navigeringsmekanismer har konsekvent rekkefølge",
        "name_en": "Navigation is consistent",
        "criterion": "3.2.3",
        "criterion_name": "Konsekvent navigering",
        "level": "AA",
        "test_object": "Betjeningskomponenter",
        "auto": "partial",
    },
    
    # 3.2.4 Konsekvent identifikasjon
    "3.2.4a": {
        "id": "3.2.4a",
        "name": "Brukergrensesnittkomponenter med samme funksjonalitet har konsekvent identifikasjon",
        "name_en": "Components identified consistently",
        "criterion": "3.2.4",
        "criterion_name": "Konsekvent identifikasjon",
        "level": "AA",
        "test_object": "Betjeningskomponenter",
        "auto": "partial",
    },
    
    # 3.3.1 Identifikasjon av feil
    "3.3.1a": {
        "id": "3.3.1a",
        "name": "Skjema gir feilmelding hvis tomme obligatoriske felt oppdages",
        "name_en": "Empty required fields show error",
        "criterion": "3.3.1",
        "criterion_name": "Identifikasjon av feil",
        "level": "A",
        "test_object": "Skjemaer",
        "auto": "partial",
    },
    "3.3.1b": {
        "id": "3.3.1b",
        "name": "Skjema gir feilmelding hvis feil inndata oppdages",
        "name_en": "Invalid input shows error",
        "criterion": "3.3.1",
        "criterion_name": "Identifikasjon av feil",
        "level": "A",
        "test_object": "Skjemaer",
        "auto": "partial",
    },
    
    # 3.3.2 Ledetekster eller instruksjoner
    "3.3.2a": {
        "id": "3.3.2a",
        "name": "Inndataelementer har instruksjon eller ledetekst",
        "name_en": "Input elements have labels/instructions",
        "criterion": "3.3.2",
        "criterion_name": "Ledetekster eller instruksjoner",
        "level": "A",
        "test_object": "Skjemaer",
        "auto": True,
    },
    
    # 3.3.3 Forslag ved feil
    "3.3.3a": {
        "id": "3.3.3a",
        "name": "Skjema gir forslag til retting hvis feil oppdages",
        "name_en": "Error suggestions provided",
        "criterion": "3.3.3",
        "criterion_name": "Forslag ved feil",
        "level": "AA",
        "test_object": "Skjemaer",
        "auto": "partial",
    },
    
    # 3.3.4 Forhindring av feil
    "3.3.4a": {
        "id": "3.3.4a",
        "name": "Skjema med juridisk/økonomisk formål lar brukeren kontrollere og bekrefte",
        "name_en": "Legal/financial submissions can be reviewed",
        "criterion": "3.3.4",
        "criterion_name": "Forhindring av feil",
        "level": "AA",
        "test_object": "Skjemaer",
        "auto": "partial",
    },
    "3.3.4b": {
        "id": "3.3.4b",
        "name": "Brukeren kan bekrefte eller angre sletting av lagret informasjon",
        "name_en": "Deletions can be confirmed/undone",
        "criterion": "3.3.4",
        "criterion_name": "Forhindring av feil",
        "level": "AA",
        "test_object": "Skjemaer",
        "auto": "partial",
    },
    
    # ===========================================
    # 4. ROBUST
    # ===========================================
    
    # 4.1.2 Navn, rolle, verdi
    "4.1.2a": {
        "id": "4.1.2a",
        "name": "For skjemaelementer kan tilgjengelig navn, rolle og tilstand bestemmes",
        "name_en": "Form elements have name, role, value",
        "criterion": "4.1.2",
        "criterion_name": "Navn, rolle, verdi",
        "level": "A",
        "test_object": "Skjemaer",
        "auto": True,
    },
    "4.1.2b": {
        "id": "4.1.2b",
        "name": "For knapper kan tilgjengelig navn, rolle og tilstand bestemmes",
        "name_en": "Buttons have name, role, value",
        "criterion": "4.1.2",
        "criterion_name": "Navn, rolle, verdi",
        "level": "A",
        "test_object": "Betjeningskomponenter",
        "auto": True,
    },
    "4.1.2c": {
        "id": "4.1.2c",
        "name": "Iframe har et tilgjengelig navn som beskriver formålet",
        "name_en": "Iframes have accessible name",
        "criterion": "4.1.2",
        "criterion_name": "Navn, rolle, verdi",
        "level": "A",
        "test_object": "Iframe",
        "auto": True,
    },
    "4.1.2d": {
        "id": "4.1.2d",
        "name": "For menyelementer kan tilgjengelig navn, rolle og tilstand bestemmes",
        "name_en": "Menu elements have name, role, value",
        "criterion": "4.1.2",
        "criterion_name": "Navn, rolle, verdi",
        "level": "A",
        "test_object": "Betjeningskomponenter",
        "auto": True,
    },
    
    # 4.1.3 Statusbeskjeder
    "4.1.3a": {
        "id": "4.1.3a",
        "name": "Statusbeskjeder kan bestemmes programmatisk",
        "name_en": "Status messages are programmatically determinable",
        "criterion": "4.1.3",
        "criterion_name": "Statusbeskjeder",
        "level": "AA",
        "test_object": "Statusmelding",
        "auto": "partial",
    },
}

# Group test rules by criterion
def get_rules_by_criterion():
    """Group test rules by WCAG criterion."""
    by_criterion = {}
    for rule_id, rule in UU_TEST_RULES.items():
        criterion = rule["criterion"]
        if criterion not in by_criterion:
            by_criterion[criterion] = []
        by_criterion[criterion].append(rule)
    return by_criterion

# Get fully automatable rules
def get_auto_rules():
    """Get rules that can be fully automated."""
    return {k: v for k, v in UU_TEST_RULES.items() if v["auto"] == True}

# Get partially automatable rules
def get_partial_rules():
    """Get rules that can be partially automated."""
    return {k: v for k, v in UU_TEST_RULES.items() if v["auto"] == "partial"}

# Get manual-only rules
def get_manual_rules():
    """Get rules that require manual testing."""
    return {k: v for k, v in UU_TEST_RULES.items() if v["auto"] == False}
