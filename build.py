import PyInstaller.__main__
from pathlib import Path
import os
import sys
import json
import site
from importlib.metadata import version

APP_NAME = 'CIGA-GUI'
ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
if sys.platform == 'win32':
    # Do not collect incompatible DLLs from Conda, Poppler or other PATH tools.
    windows_root = Path(os.environ['SystemRoot'])
    os.environ['PATH'] = os.pathsep.join(map(str, (
        Path(sys.executable).parent, Path(sys.base_prefix),
        windows_root / 'System32', windows_root,
    )))
sys.path.insert(0, str(ROOT))
if (ROOT.parent / 'ciga' / '__init__.py').exists():
    sys.path.insert(0, str(ROOT.parent))
import ciga

DIST_DIR = ROOT / 'dist'
EXE_PATH = DIST_DIR / APP_NAME / f'{APP_NAME}.exe'
APP_DIR = DIST_DIR / APP_NAME

# Refuse output paths redirected outside this application checkout.
for directory in ('build', 'dist'):
    if (ROOT / directory).resolve().parent != ROOT:
        raise RuntimeError(f'Build directory must stay inside {ROOT}: {directory}')
os.environ['PYINSTALLER_CONFIG_DIR'] = str(ROOT / 'build' / 'pyinstaller-cache')
# PyInstaller probes the user site even when a venv disables it. Keep that
# irrelevant probe inside the checkout (including in child hook processes).
if not site.ENABLE_USER_SITE and sys.prefix != sys.base_prefix:
    os.environ.setdefault('PYTHONUSERBASE', str(ROOT / 'build' / 'python-user'))
    site.USER_BASE = os.environ['PYTHONUSERBASE']
    site.USER_SITE = None

# `ciga` is bundled from the environment (pip install -r requirements.txt);
# --paths=.. additionally finds it when this repo sits inside a CIGA checkout.
PyInstaller.__main__.run([
    str(ROOT / 'src' / 'main.py'),
    f'--name={APP_NAME}',
    '--windowed',
    '--onedir',
    '--clean',
    '--noconfirm',
    f'--specpath={ROOT}',
    f'--workpath={ROOT / "build"}',
    f'--distpath={DIST_DIR}',
    f'--paths={ROOT}',
    f'--paths={ROOT.parent}',
    f'--icon={ROOT / "assets" / "logo_black.png"}',
    f'--add-data={ROOT / "assets" / "logo_black.png"}{os.pathsep}.',
    f'--add-data={ROOT / "assets" / "logo_white.png"}{os.pathsep}.',
    # Qt hooks collect the modules, plugins and WebEngine resources imported by
    # the app; collecting every Qt module also pulls in unrelated 3D/QML tools.
    '--collect-all=shiboken6',
    '--collect-all=ciga',
    '--exclude-module=PyQt5',
    '--exclude-module=PyQt6',
    '--exclude-module=PySide2',
    '--exclude-module=torch',
    '--exclude-module=torchvision',
    '--exclude-module=torchaudio',
    '--exclude-module=botocore',
    '--exclude-module=boto3',
    '--exclude-module=bitsandbytes',
    '--exclude-module=nltk',
    '--exclude-module=jax',
    '--exclude-module=jaxlib',
    '--exclude-module=cv2',
    '--exclude-module=panel',
    '--exclude-module=playwright',
    '--exclude-module=llvmlite',
    '--exclude-module=pyarrow',
    '--exclude-module=av',
    '--exclude-module=faiss',
    '--exclude-module=transformers',
    '--exclude-module=jieba',
])

if not EXE_PATH.exists():
    raise FileNotFoundError(f'Expected PyInstaller output file not found: {EXE_PATH}')

(APP_DIR / 'build-info.json').write_text(json.dumps({
    'application': APP_NAME,
    'ciga_version': ciga.__version__,
    'python_version': sys.version.split()[0],
    'pyside6_version': version('PySide6'),
}, indent=2), encoding='utf-8')
import shutil
archive = shutil.make_archive(str(DIST_DIR / APP_NAME), 'zip', root_dir=DIST_DIR, base_dir=APP_NAME)

print(f'Packaged application directory: {APP_DIR}')
print(f'Portable ZIP: {archive}')
print('Send this entire directory (or zip it) to users. They just need to run the exe inside it.')
