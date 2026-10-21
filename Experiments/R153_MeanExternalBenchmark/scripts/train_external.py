"""Formal ordinary-training entry. Epochs and synthetic-validation stopping are recorded."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
if (Path(__file__).resolve().parents[1]/'config/TIME_BUDGET_OVERRIDE.json').exists():
    from short_budget import main
else:
    from normal_training import main
if __name__=='__main__':main()
