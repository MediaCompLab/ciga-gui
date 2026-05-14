import PyInstaller.__main__
from pathlib import Path
import shutil
import os

APP_NAME = 'CIGA-GUI'
DIST_DIR = Path('dist')
EXE_PATH = DIST_DIR / APP_NAME / f'{APP_NAME}.exe'
APP_DIR = DIST_DIR / APP_NAME

# Clean previous builds to avoid cache poisoning
if os.path.exists('build'): shutil.rmtree('build')
if os.path.exists('dist'): shutil.rmtree('dist')
if os.path.exists(f'{APP_NAME}.spec'): os.remove(f'{APP_NAME}.spec')

# Make sure ciga package can be found? 
# Pyinstaller might need --paths=.. to find 'ciga' correctly if it's external, or we package ciga with it.
PyInstaller.__main__.run([
    'src/main.py',
    f'--name={APP_NAME}',
    '--windowed',
    '--onedir',
    '--clean',
    '--paths=..',
    '--icon=../logo_black.png',
    f'--add-data=../logo_black.png{os.pathsep}.',
    f'--add-data=../logo_white.png{os.pathsep}.',
    '--collect-all=PySide6',
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

print(f'Packaged application directory: {APP_DIR}')
print('Send this entire directory (or zip it) to users. They just need to run the exe inside it.')
