import os

current_directory = os.path.dirname(os.path.abspath(__file__))
compilersDir = os.path.join(current_directory, 'compilers')
llvmbugsFile = os.path.join(current_directory, 'benchmark', 'llvmbugs_summary.txt')


def getBugInfo(llvmbug):
    items = llvmbug.strip().split(',')
    bugId, rev, passOptLevel, failOptLevel, buggyFiles = items[0], items[1], items[2].replace('+', ' '), items[3].replace('+', ' '), items[4].split('+')
    return bugId, rev, passOptLevel, failOptLevel, buggyFiles


def install(rev):
    os.chdir(compilersDir)
    revpath = os.path.join(compilersDir, rev)
    if os.path.exists(revpath):
        os.system('rm -rf ' + revpath)
    print('\033[1;35m git cloning..\033[0m')
    os.system('git clone https://github.com/llvm/llvm-project.git ' + rev)
    os.chdir(revpath)
    os.system('rm -rf ./*')
    os.system('git reset --hard ' + rev)
    os.system('mv clang llvm/tools')
    os.system('mkdir build')
    os.chdir(revpath + '/build')
    print('\033[1;35m cmake..\033[0m')
    os.system('cmake -DCMAKE_EXPORT_COMPILER_COMMANDS=ON -DCMAKE_INSTALL_PREFIX=' + revpath + '/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=/usr/bin/gcc -DCMAKE_CXX_COMPILER=/usr/bin/g++ -DCMAKE_C_FLAGS="-g -O0 -fprofile-arcs -ftest-coverage" -DCMAKE_CXX_FLAGS="-g -O0 -fprofile-arcs -ftest-coverage" -DCMAKE_EXE_LINKER_FLAGS="-g -fprofile-arcs -ftest-coverage -lgcov" -DPYTHON_EXECUTABLE:FILEPATH=/usr/bin/python ../llvm')
    print('\033[1;35m make..\033[0m')
    os.system('make -j48')
    os.system('make install')


if __name__ == '__main__':
    with open(llvmbugsFile, 'r') as f:
        llvmbugs = [item.strip() for item in f.readlines()]
    for item in llvmbugs:
        _, rev, _, _, _ = getBugInfo(item)
        install(rev)
        
