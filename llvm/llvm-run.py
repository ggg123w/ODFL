import os
import math
import subprocess
import multiprocessing
import re

current_directory = os.path.dirname(os.path.abspath(__file__))
compilersDir = os.path.join(current_directory, 'compilers')
collectDir = os.path.join(current_directory, 'cov')
testDir = os.path.join(current_directory, 'benchmark', 'llvmbugs')
llvmbugsFile = os.path.join(current_directory, 'benchmark', 'llvmbugs_summary.txt')
rankFile = os.path.join(current_directory, 'ranks.txt')

# crash while compiling
crash_bugId_lst = []

timeout = 15
processes = 10
parallel = True


def getBugInfo(llvmbug):
    items = llvmbug.strip().split(',')
    bugId, rev, passOptLevel, failOptLevel, buggyFiles = items[0], items[1], items[2].replace('+', ' '), items[3].replace('+', ' '), items[4].split('+')
    return bugId, rev, passOptLevel, failOptLevel, buggyFiles


def getConfResult(bugId, rev, conf, timeout=timeout):
    cwd = os.path.join(testDir, bugId)
    clangPath = os.path.join(compilersDir, rev, 'build/bin/clang')

    cplcmd = clangPath + ' -w ' + conf + ' fail.c'
    cplcmd = 'timeout --signal=SIGKILL ' + str(timeout) + ' ' + cplcmd
    try:
        cplout = subprocess.run(cplcmd, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout+1)
        if bugId in crash_bugId_lst:
            return str(cplout.returncode)
        else:
            if cplout.returncode != 0:
                return str(cplout.returncode) + ':' + cplout.stdout.decode().strip() + ':' + cplout.stderr.decode().strip()

            execmd = 'timeout --signal=SIGKILL ' + str(timeout) + ' ./a.out'
            try:
                exeout = subprocess.run(execmd, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout+1)
                return str(exeout.returncode) + ':' + exeout.stdout.decode().strip() + ':' + exeout.stderr.decode().strip()
            except subprocess.TimeoutExpired:
                return 'EXETimeoutExpired'
    except subprocess.TimeoutExpired:
        return 'CPLTimeoutExpired'
    

def getOptBisectLimit(bugId, rev, failOptLevel, passOptLevel):
    passResult = getConfResult(bugId, rev, passOptLevel)
    passConfs = []
    failConfs = []
    os.chdir(os.path.join(testDir, bugId))
    clangPath = os.path.join(compilersDir, rev, 'build/bin/clang')
    os.system(clangPath + ' ' + failOptLevel + ' -mllvm -opt-bisect-limit=-1 fail.c > failLimit.txt 2>&1')
    with open('failLimit.txt', 'r') as f:
        maxfailLimit = len(f.readlines())
    failLimit = maxfailLimit
    passLimit = 0
    while True:
        print('\033[1;35m passLimit = %d, failLimit = %d\033[0m' % (passLimit, failLimit))
        if failLimit - passLimit == 1:
            break
        tmpLimit = (failLimit + passLimit) // 2
        tmpConf = failOptLevel + ' -mllvm -opt-bisect-limit=' + str(tmpLimit)
        tmpResult = getConfResult(bugId, rev, tmpConf)
        if tmpResult == passResult:  # pass
            passLimit = tmpLimit
        else:  # fail
            failLimit = tmpLimit
    
    passConfs.append(failOptLevel + ' -mllvm -opt-bisect-limit=' + str(passLimit))
    failConfs.append(failOptLevel + ' -mllvm -opt-bisect-limit=' + str(failLimit))

    for i in range(2):
        if failLimit + i + 1 > maxfailLimit:
            break
        else: 
            failConfs.append(failOptLevel + ' -mllvm -opt-bisect-limit=' + str(failLimit + i + 1))

    for i in range(2):
        if passLimit - i - 1 < 0:
            break
        else:
            passConfs.append(failOptLevel + ' -mllvm -opt-bisect-limit=' + str(passLimit - i - 1))

    return passConfs, failConfs


def collectCov(bugId, rev, conf, testname, collectDir):
    clangPath = os.path.join(compilersDir, rev, 'build/bin/clang')
    gcovPath = os.path.join('gcov-5')
    covDir = os.path.join(compilersDir, rev, 'build')
    clangbuildPath = os.path.join(compilersDir, rev, 'build')
    cwd = os.path.join(testDir, bugId)
    covline_set = set()

    subprocess.run('find ' + covDir + ' -name "*.gcda" | xargs rm -f', shell=True, cwd=cwd)  # delete all .gcda files
    subprocess.run(clangPath + ' -w ' + conf + ' fail.c > /dev/null 2>&1', shell=True, cwd=cwd)  # compile test program

    file_gcdalist = os.path.join(cwd, 'gcdalist')
    if os.path.exists(file_gcdalist):
        subprocess.run('rm ' + file_gcdalist, shell=True, cwd=cwd)

    subprocess.run('find ' + covDir + ' -name "*.gcda" > ' + file_gcdalist, shell=True, cwd=cwd)

    tempdir = os.path.join(collectDir, bugId, testname)
    if os.path.exists(tempdir):
        subprocess.run('rm -rf ' + tempdir, shell=True, cwd=cwd)

    subprocess.run('mkdir -p ' + tempdir, shell=True, cwd=cwd)

    with open(file_gcdalist, 'r') as f:
        gcdafilelines = f.readlines()

        subprocess.run('find ' + covDir + ' -name "*.cpp.gcov" | xargs rm -f', shell=True, cwd=cwd)
        for gcdafile in sorted(gcdafilelines):
            gcdafile = gcdafile.strip()
            if '/build/lib/' not in gcdafile:
                continue
            subprocess.run(gcovPath + ' ' + gcdafile + ' > /dev/null 2>&1', shell=True, cwd=clangbuildPath)
            gcovfile = os.path.join(clangbuildPath, gcdafile.strip().split('/')[-1].split('.gcda')[0] + '.gcov')
            if not os.path.exists(gcovfile):
                continue
            tmpfilename = os.path.relpath(gcdafile, covDir).replace('.cpp.gcda', '.cpp')
            tmpfilename = tmpfilename.split('/CMakeFiles/')[0] + tmpfilename.split('.dir')[1]
            with open(gcovfile, 'r', encoding='utf-8') as f:
                stmtlines = f.readlines()
                tmp = []
                for stmtline in stmtlines:
                    stmtline = stmtline.strip()
                    if ':' in stmtline:
                        lineCov = stmtline.split(':')[0].strip()
                        lineNum = stmtline.split(':')[1].strip()
                        if lineCov != '-' and lineCov != '#####' and lineCov != '=====':
                            tmp.append(lineNum)
                if len(tmp) == 0: continue                
                covline = tmpfilename + '$' + ','.join(tmp)
                covline_set.add(covline)

    file_stmtinfo = os.path.join(tempdir, 'stmt_info.txt')
    with open(file_stmtinfo, 'w') as stmtfile:
        stmtfile.write('\n'.join(sorted(covline_set)))
    
    return covline_set


def getStmtInfo(covFile):
    stmtInfoSet = set()
    with open(covFile, 'r') as f:
        for line in f:
            filename, stmts = line.strip().split('$')
            for stmt in stmts.split(','):
                stmtInfoSet.add(filename + ',' + stmt)
    return stmtInfoSet


def rank(failStmtInfoDir, passStmtInfoDir, formula = 'Ochiai'):
    failstmt = {}  # the stmt cov information of failing test program
    passstmt = {}
    nfstmt = {}
    npstmt = {}

    failstmtset = set()  # all failstmt
    passstmtset = set()  # all passstmt

    # efs
    # the statements that the falling test program executed
    for failStmtInfo in failStmtInfoDir:
        tmpfailstmtset = getStmtInfo(failStmtInfo)
        failstmtset.update(tmpfailstmtset)
        for stmt in tmpfailstmtset:
            failstmt[stmt] = failstmt.get(stmt, 0) + 1

    # init nfstmt and passstmt
    for stmt in failstmtset:
        nfstmt[stmt] = 0
        passstmt[stmt] = 0
        npstmt[stmt] = 0

    # nfs
    for failStmtInfo in failStmtInfoDir:
        nfset = failstmtset - getStmtInfo(failStmtInfo)
        for nf in nfset:
            nfstmt[nf] += 1

    # eps and nps
    for passStmtInfo in passStmtInfoDir:
        tmppassstmtset = getStmtInfo(passStmtInfo)
        passstmtset.update(failstmtset - tmppassstmtset)
        for stmt in tmppassstmtset:
            if stmt in failstmtset:
                passstmt[stmt] += 1
        npset = failstmtset - tmppassstmtset
        for np in npset:
            npstmt[np] += 1

    # compute statement score based on SBFL
    score = {}  # the buggy value of each statement and its line number in each file
    filescore = {}  # the buggy value of each file, and we can get the corresponding statement values
    for key in failstmt:
        if formula == 'Ochiai':
            score[key] = failstmt[key] / math.sqrt((failstmt[key] + nfstmt[key]) * (failstmt[key] + passstmt[key]))

        elif formula == 'Tarantula': 
            score[key] = (failstmt[key]/(failstmt[key]+nfstmt[key])) / ((failstmt[key]/(failstmt[key] + nfstmt[key])) + (passstmt[key]/(npstmt[key] + passstmt[key])))
        
        elif formula == 'DStar':
            if passstmt[key] + nfstmt[key] != 0:
                score[key] = failstmt[key] * failstmt[key] / (passstmt[key] + nfstmt[key])
            else:
                score[key] = 1

        elif formula == 'Dice':
            score[key] = 2 * failstmt[key] / (failstmt[key] + nfstmt[key] + passstmt[key])

        elif formula == 'Barinel':
            score[key] = 1 - passstmt[key] / (passstmt[key] + failstmt[key])

        elif formula == 'Op2':
            score[key] = failstmt[key] - passstmt[key] / (1 + npstmt[key] + passstmt[key])

        filename = key.rsplit(',', 1)[0]
        filescore.setdefault(filename, []).append(score[key])

    # compute the buggy values of each file based on average aggregation
    scoredict = {key: sum(values) / len(values) for key, values in filescore.items()}

    return scoredict


def getRank(bugId, rev, passConfs, failConfs, collectDir):
    # collect cov
    cwd = os.path.join(testDir, bugId)
    tempdir = os.path.join(collectDir, bugId)
    if os.path.exists(tempdir):
        subprocess.run('rm -rf ' + tempdir, shell=True, cwd=cwd)
    subprocess.run('mkdir ' + tempdir, shell=True, cwd=cwd)

    passStmtInfoDir = []
    passcnt = 0
    for passConf in passConfs:
        passcnt += 1
        testname = 'pass'+str(passcnt)
        collectCov(bugId, rev, passConf, testname, collectDir)
        passStmtInfoDir.append(os.path.join(collectDir, bugId, testname, 'stmt_info.txt'))
    
    failStmtInfoDir = []
    failcnt = 0
    for failConf in failConfs:
        failcnt += 1
        testname = 'fail'+str(failcnt)
        collectCov(bugId, rev, failConf, testname, collectDir)
        failStmtInfoDir.append(os.path.join(collectDir, bugId, testname, 'stmt_info.txt'))

    # rank file by score
    scoredict = rank(failStmtInfoDir, passStmtInfoDir, formula = 'Ochiai')
    with open(os.path.join(collectDir, bugId, 'Ochiai_scoredict.txt'), 'w') as f:
        f.write(str(scoredict))
    return scoredict


def task(llvmbug):
    print('\033[1;35m%s\033[0m' % llvmbug)
    bugId, rev, passOptLevel, failOptLevel, buggyFiles = getBugInfo(llvmbug)

    # generate configurations
    passConfs, failConfs = getOptBisectLimit(bugId, rev, failOptLevel, passOptLevel)

    # SBFL rank
    scoredict = getRank(bugId, rev, passConfs, failConfs, collectDir)


if __name__ == '__main__':
    if not os.path.exists(collectDir):
                subprocess.run('mkdir -p ' + collectDir, shell=True)
    
    with open(llvmbugsFile, 'r') as f:
        llvmbugs = [item.strip() for item in f.readlines()]
    
    if not parallel:
        for llvmbug in llvmbugs:
            _, rev, _, _, _ = getBugInfo(llvmbug)
            if os.path.exists(os.path.join(compilersDir, rev, 'build')):
                task(llvmbug)
    else:
        bugs = []
        for item in llvmbugs:
            bugId, rev, _, _, _ = getBugInfo(item)
            if not os.path.exists(os.path.join(compilersDir, rev, 'build')):
                continue
            bugs.append(item)
        pool = multiprocessing.Pool(processes)
        result = pool.map_async(task, bugs)
        result.wait()

