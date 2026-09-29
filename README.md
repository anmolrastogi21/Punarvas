<p align="center">
  <img src="assets/logo.png" alt="PUNARVAS - Rehabilitation & Resettlement" width="180">
</p>

# PUNARVAS: Rehabilitation & Resettlement

Integrated red zone and relocation planning system. Decision support for identifying landslide-prone villages, prioritising them for relocation, and matching them to resettlement sites. The current build replays the 30 July 2024 landslides at Meppadi, Wayanad.

## Features

- Real basemap (OpenStreetMap / CARTO) with a Google-style Satellite view (imagery plus place labels) and a Terrain view, following light and dark mode
- Proposed village-to-site moves drawn as dashed lines, with the selected village highlighted
- Rainfall trigger slider (stands in for the IMD forecast) with alert levels
- Hazard layers: landslide, flood and cloudburst
- Adjustable priority weights: hazard, exposure, vulnerability, disaster history
- Village ranking into Immediate, Short-term, Medium and Monitor tiers
- Funding slider that matches funded villages to relocation sites and flags those needing a field survey
- Export of the relocation plan as JSON
- Light and dark mode
- **SHAP analysis tab:** shows what drives each village's priority score (SHAP charts, a heatmap of all villages, and automatic plain-language explanations)

## Project structure

```
app.py              Streamlit app: map tab + SHAP analysis tab
core.py             Scoring engine (Python port of the map logic) and SHAP values
index.html          The planning tool (React + MapLibre GL + Tailwind, loaded from CDNs)
requirements.txt    Python dependencies for Streamlit
assets/             Logo and favicon
.streamlit/         Streamlit configuration
```

## About the data

Village names, the event and the Elstone Estate township site are real. Coordinates are approximate, and household counts, susceptibility scores and Parcels B and C are indicative placeholders. Not for operational use.

## Map credits

Basemap tiles: &copy; OpenStreetMap contributors, &copy; CARTO (or Esri, HERE, Garmin when no key is set). Satellite imagery and place labels: Esri, Maxar, Earthstar Geographics. Terrain: &copy; OpenTopoMap (CC-BY-SA), SRTM. An internet connection is needed to load tiles.
