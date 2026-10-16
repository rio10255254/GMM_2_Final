"""Retired draft exporter; do not relabel old 25-PSF weights as trained 100-PSF weights."""
from pathlib import Path

target=Path(__file__).resolve().parents[3]/'R142_PSF100_AdaptiveTop8_Standalone'
raise SystemExit('The old PSF100 export draft was replaced. Read '+str(target/'README.md')+
                 '. R142 requires a real100 bank and new training before operational inference.')
