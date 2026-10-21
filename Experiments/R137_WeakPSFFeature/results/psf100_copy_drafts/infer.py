"""Retired draft entry point; the tested 100-PSF package is R142."""
from pathlib import Path

target=Path(__file__).resolve().parents[3]/'R142_PSF100_AdaptiveTop8_Standalone'
raise SystemExit('This incomplete PSF100 draft was replaced. Read '+str(target/'README.md')+
                 '. The R142 package refuses inference until a real100 bank and trained model are installed.')
