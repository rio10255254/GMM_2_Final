from pathlib import Path
import runpy, sys
sys.dont_write_bytecode=True
package, original, output, script = map(Path, sys.argv[1:5])
blocked = [original.resolve(), original.parent/'R148v2_HybridContextNativePSF']
allowed = [package.resolve(), output.resolve()]
def guard(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes)):
        path = Path(args[0]).resolve()
        if any(path.is_relative_to(p) for p in blocked) and not any(path.is_relative_to(p) for p in allowed):
            raise PermissionError('Attempt to read original experiment: ' + str(path))
sys.addaudithook(guard)
sys.path.insert(0, str(package))
sys.argv = [str(package/script)] + sys.argv[5:]
runpy.run_path(str(package/script), run_name='__main__')
