#!/usr/bin/env python3
"""Inventory actual Linux runtime dependencies and preserve installed distro notices."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('runtime',type=Path)
p.add_argument('out',type=Path)
p.add_argument('notices',type=Path)
a=p.parse_args()
runtime=a.runtime.resolve();env=dict(os.environ,LD_LIBRARY_PATH=str(runtime));env.pop('LD_PRELOAD',None)
libraries={}
for name in ('basalt_vio','libbasalt.so','libmono_reader.so'):
    text=subprocess.check_output(['ldd',str(runtime/name)],env=env,text=True)
    if 'not found' in text:raise ValueError('Unresolved runtime library: '+text)
    for lib,path in re.findall(r'^\s*(\S+) => (/[^ ]+)',text,re.M):
        libraries[lib]=Path(path).resolve()
packages={};rows=[];missing=[]
for lib,path in sorted(libraries.items()):
    if path.parent==runtime:
        rows.append(dict(library=lib,source='this build'));continue
    owners=[]
    for candidate in (str(path),str(path).replace('/usr/lib/','/lib/',1)):
        q=subprocess.run(['dpkg-query','-S',candidate],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
        if not q.returncode:
            owners=[line.split(': /',1)[0] for line in q.stdout.splitlines()];break
    if not owners:missing.append(lib)
    rows.append(dict(library=lib,packages=owners))
    for package in owners:
        if package in packages:continue
        version=subprocess.check_output(['dpkg-query','-W','-f=${Version}',package],text=True)
        copyright_path=Path('/usr/share/doc')/package.split(':')[0]/'copyright'
        if not copyright_path.exists():raise ValueError('Missing distro notice: '+package)
        a.notices.mkdir(parents=True,exist_ok=True)
        dest=a.notices/(package.replace(':','_')+'.txt');dest.write_bytes(copyright_path.read_bytes())
        packages[package]=dict(version=version,notice=dest.name,sha256=hashlib.sha256(dest.read_bytes()).hexdigest())
report=dict(scope='Actual ldd closure for source-built runtime on validation host; OS libraries are not redistributed by this source release.',libraries=rows,packages=packages,unidentified_libraries=missing)
a.out.write_text(json.dumps(report,indent=2)+'\n')
if missing:raise ValueError('Unidentified system libraries: '+str(missing))
print('SYSTEM_NOTICES_COMPLETE',len(rows),len(packages))
