import os
import subprocess

current_directory = os.path.dirname(os.path.abspath(__file__))
compilersDir = os.path.join(current_directory, 'compilers')
gccbugsFile = os.path.join(current_directory, 'benchmark', 'gccbugs_summary.txt')


def getBugInfo(gccbug):
    items = gccbug.strip().split(',')
    bugId, rev, passOptLevel, failOptLevel, buggyFiles = items[0], items[1], items[2].replace('+', ' '), items[3].replace('+', ' '), items[4].split('+')
    return bugId, rev, passOptLevel, failOptLevel, buggyFiles


def install(rev):
    os.chdir(compilersDir)
    revpath = os.path.join(compilersDir, rev)
    os.system('mkdir ' + revpath)
    os.chdir(revpath)
    print('\033[1;35m svn downloading..\033[0m')
    os.system('svn co svn://gcc.gnu.org/svn/gcc/trunk -' + rev)
    os.chdir(revpath + '/trunk')
    os.system('./contrib/download_prerequisites')
    os.system('mkdir ' + revpath + '/build')
    os.chdir(revpath + '/build')
    os.system('../trunk/configure --enable-languages=c,c++ --enable-checking=release --enable-coverage --prefix='+revpath+'/build')
    print('\033[1;35m make..\033[0m')
    os.system('make -j 20')
    os.system('make install')


if __name__ == '__main__':
    if not os.path.exists(compilersDir):
        subprocess.run('mkdir -p ' + compilersDir, shell=True)
    with open(gccbugsFile, 'r') as f:
        gccbugs = [item.strip() for item in f.readlines()]
    for item in gccbugs:
        _, rev, _, _, _ = getBugInfo(item)
        install(rev)
