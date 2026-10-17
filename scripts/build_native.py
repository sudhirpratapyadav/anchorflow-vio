#!/usr/bin/env python3
"""Build the frozen estimator from pinned public source; never copy old binaries."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-repo',type=Path,required=True,help='Clone of public upstream Basalt; worktree changes are ignored')
    p.add_argument('--work',type=Path,required=True,help='New owned build directory')
    p.add_argument('--vcpkg',type=Path,help='Pinned vcpkg checkout; defaults to source-repo/thirdparty/vcpkg')
    p.add_argument('--deps-prefix',type=Path,help='Existing read-only vcpkg_installed prefix; disables dependency installation')
    p.add_argument('--cmake',default='cmake')
    p.add_argument('--ninja',default='ninja')
    p.add_argument('--resume',action='store_true')
    a=p.parse_args()
    manifest=json.loads((ROOT/'native/source_manifest.json').read_text())
    repo=a.source_repo.resolve();work=a.work.resolve();source=work/'source';build=work/'build';runtime=work/'runtime'
    vcpkg=(a.vcpkg or repo/'thirdparty/vcpkg').resolve()
    if subprocess.check_output(['git','-C',str(vcpkg),'rev-parse','HEAD'],text=True).strip()!=manifest['vcpkg_commit']:
        raise ValueError('Wrong vcpkg commit')
    if digest(ROOT/manifest['patch'])!=manifest['patch_sha256']:raise ValueError('Historical patch changed')
    for name,sha in manifest['mono_reader_sha256'].items():
        if digest(ROOT/name)!=sha:raise ValueError('Frozen reader changed')
    if not a.resume:
        work.mkdir(parents=True,exist_ok=False);source.mkdir()
        archive=work/'upstream.tar'
        subprocess.run(['git','-C',str(repo),'archive','--format=tar','--output='+str(archive),manifest['basalt_commit']],check=True)
        subprocess.run(['tar','-xf',str(archive),'-C',str(source)],check=True)
        subprocess.run(['git','-C',str(source),'apply',str(ROOT/manifest['patch'])],check=True)
        (work/'source_pins.json').write_text(json.dumps({str(f.relative_to(source)):digest(f) for f in source.rglob('*') if f.is_file()},indent=2)+'\n')
    pins=json.loads((work/'source_pins.json').read_text())
    for name,sha in pins.items():
        if digest(source/name)!=sha:raise ValueError('Build source changed: '+name)
    deps=a.deps_prefix.resolve() if a.deps_prefix else work/'dependencies'
    command=[a.cmake,'-S',str(source),'-B',str(build),'-G','Ninja',
             '-DCMAKE_MAKE_PROGRAM='+str(Path(shutil.which(a.ninja) or a.ninja).resolve()),
             '-DCMAKE_BUILD_TYPE=Release','-DCMAKE_CXX_FLAGS=-ffp-contract=off',
             '-DCMAKE_TOOLCHAIN_FILE='+str(vcpkg/'scripts/buildsystems/vcpkg.cmake'),
             '-DVCPKG_INSTALLED_DIR='+str(deps),
             '-DVCPKG_MANIFEST_INSTALL='+('OFF' if a.deps_prefix else 'ON')]
    subprocess.run(command,check=True)
    subprocess.run([a.cmake,'--build',str(build),'--target','basalt_vio','-j1'],check=True)
    runtime.mkdir(exist_ok=True)
    for name in ('basalt_vio','libbasalt.so'):shutil.copy2(build/name,runtime/name)
    for name in ('reader.cpp','mono_euroc.h'):shutil.copy2(ROOT/'native'/name,runtime/name)
    include=deps/'x64-linux/include'
    flags=subprocess.check_output(['pkg-config','--cflags','--libs','opencv4'],text=True).split()
    cmd=['c++','-std=c++17','-O2','-ffp-contract=off','-fPIC','-shared','-DEIGEN_DONT_PARALLELIZE',
         '-I'+str(source/'include'),'-I'+str(include),'-I'+str(include/'eigen3'),str(runtime/'reader.cpp'),
         '-L'+str(runtime),'-lbasalt',*flags,'-lstdc++fs','-Wl,-z,defs','-Wl,-rpath,$ORIGIN','-o',str(runtime/'libmono_reader.so')]
    subprocess.run(cmd,check=True)
    result=dict(schema_version=1,sha256={name:digest(runtime/name) for name in ('basalt_vio','libbasalt.so','libmono_reader.so')},
                source_manifest_sha256=digest(ROOT/'native/source_manifest.json'),source_pins_sha256=digest(work/'source_pins.json'),
                historical_binary_identity={name:digest(runtime/name)==sha for name,sha in manifest['reference_binary_sha256'].items()},
                dependency_mode='existing prefix, offline' if a.deps_prefix else 'pinned vcpkg source build',
                commands=[command,cmd],note='Scientific pose parity must be checked separately; compiler/path differences can change binary hashes.')
    (runtime/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print('NATIVE_BUILD_COMPLETE '+str(runtime),flush=True)

if __name__=='__main__':main()
