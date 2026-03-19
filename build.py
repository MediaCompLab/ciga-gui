import PyInstaller.__main__
from pathlib import Path
import shutil
import os

# Clean previous builds to avoid cache poisoning
if os.path.exists('build'): shutil.rmtree('build')
if os.path.exists('dist'): shutil.rmtree('dist')
if os.path.exists('CIGA-GUI.spec'): os.remove('CIGA-GUI.spec')

# Make sure ciga package can be found? 
# Pyinstaller might need --paths=.. to find 'ciga' correctly if it's external, or we package ciga with it.
PyInstaller.__main__.run([
    'src/main.py',
    '--name=CIGA-GUI',
    '--windowed',
    '--clean',
    '--paths=..',
    f'--add-data=../logo_black.png{os.pathsep}.',
    f'--add-data=../logo_white.png{os.pathsep}.',
    '--collect-all=PySide6',
    '--collect-all=ciga',
    '--collect-all=pandas',
    '--collect-all=igraph',
    '--collect-all=numpy',
])
