from pathlib import Path
import subprocess
root=Path(__file__).resolve().parent
subprocess.run([r'C:\Users\Rio\anaconda3\python.exe',str(root/'prepare_doc_data.py')],check=True)
subprocess.run([r'C:\Users\Rio\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe',str(root/'author_docs.py')],check=True)
