import os
import subprocess
import math
import multiprocessing

current_directory = os.path.dirname(os.path.abspath(__file__))
compilersDir = os.path.join(current_directory, 'compilers')
collectDir = os.path.join(current_directory, 'cov')
testDir = os.path.join(current_directory, 'benchmark', 'gccbugs')
gccbugsFile = os.path.join(current_directory, 'benchmark', 'gccbugs_summary.txt')
resultdict = {}
rankFile = os.path.join(current_directory, 'ranks.txt')

# avoid warning
skipped_fineOpt_lst = ['-fno-rtti', '-fno-handle-exceptions', '-fthreadsafe-statics']
# crash while compiling
crash_bugId_lst = ['58343', '56478', '58068', '58451', '58539']

timeout = 15
processes = 10
parallel = True

def getBugInfo(gccbug):
    items = gccbug.strip().split(',')
    bugId, rev, passOptLevel, failOptLevel, buggyFiles = items[0], items[1], items[2].replace('+', ' '), items[3].replace('+', ' '), items[4].split('+')
    return bugId, rev, passOptLevel, failOptLevel, buggyFiles
# 56478,r196310,-O1+-c,-O2+-c,gcc/predict.c 变成 56478,r196310,-O1 -c，-O2 -c，gcc/predict.c

def getConfResult(bugId, rev, conf, timeout=timeout):
    cwd = os.path.join(testDir, bugId)
    gccPath = os.path.join(compilersDir, rev, 'build/bin/gcc')

    cplcmd = gccPath + ' -w ' + conf + ' fail.c'
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
    

def get_fineOpt_dict(rev, bugId, conf):
    gccPath = os.path.join(compilersDir, rev, 'build/bin/gcc')
    cwd = os.path.join(testDir, bugId)
    out = subprocess.run(gccPath + ' -Q --help=optimizers ' + conf, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    fineOpt_dict = {}
    for line in out.stdout.decode().splitlines():
        line = line.strip()
        if line.startswith('-'):
            items = line.split()
            if len(items) == 2:
                fineOpt_dict[items[0]] = items[1]
    return fineOpt_dict


def collect_option(rev, bugId, failOptLevel, passOptLevel):
    fail_fineOpt_dict = get_fineOpt_dict(rev, bugId, failOptLevel)
    passResult = getConfResult(bugId, rev, passOptLevel)

    bugtrigger_fineOpt = set()
    all_fineOpt = set()
    
    for fineOpt, optStatus in sorted(fail_fineOpt_dict.items()):
        if optStatus != '[enabled]':
            continue
        if fineOpt.startswith('-fno-'):
            flipped_fineOpt = fineOpt.replace('-fno-', '-f', 1)
        else:
            flipped_fineOpt = fineOpt.replace('-f', '-fno-', 1)
        if flipped_fineOpt in skipped_fineOpt_lst:
            continue
        tmpConf = failOptLevel + ' ' + flipped_fineOpt
        tmpResult = getConfResult(bugId, rev, tmpConf)
        if tmpResult == passResult:  # fail -> pass
            bugtrigger_fineOpt.add(flipped_fineOpt)
        all_fineOpt.add(flipped_fineOpt)
        
    baseConf = failOptLevel + ' ' + ' '.join(sorted(all_fineOpt - bugtrigger_fineOpt))
    if getConfResult(bugId, rev, baseConf) == passResult:  # pass
        bugfree_fineOpt = set()
        for fineOpt in sorted(all_fineOpt-bugtrigger_fineOpt):
            tmpConf = failOptLevel + ' ' + ' '.join(sorted(bugfree_fineOpt)) + ' ' + fineOpt
            if getConfResult(bugId, rev, tmpConf) != passResult:  # fail
                bugfree_fineOpt.add(fineOpt)
        baseConf = failOptLevel + ' ' + ' '.join(sorted(bugfree_fineOpt))

    passConfs = []
    failConfs = []

    failConfs.append(baseConf) 
    for f in sorted(bugtrigger_fineOpt):
        tmpConf = baseConf + ' ' + f
        if getConfResult(bugId, rev, tmpConf) == passResult:  # pass
            passConfs.append(tmpConf)
        else:
            failConfs.append(tmpConf)

    if len(passConfs) == 0:
        passConfs.append(passOptLevel)

    return passConfs, failConfs


def collectCov(bugId, rev, option, testname, collectDir):
    gccPath = os.path.join(compilersDir, rev, 'build/bin/gcc')
    gcovPath = os.path.join(compilersDir, rev, 'build/bin/gcov')
    covDir = os.path.join(compilersDir, rev, 'build')
    gccbuildPath = os.path.join(compilersDir, rev, 'build/gcc')

    cwd = os.path.join(testDir, bugId)

    subprocess.run('find ' + covDir + ' -name "*.gcda" | xargs rm -f', shell=True, cwd=cwd)  # delete all .gcda files
    subprocess.run(gccPath + ' -w ' + option + ' fail.c > /dev/null 2>&1', shell=True, cwd=cwd)  # compile test program

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

        subprocess.run('find ' + covDir + ' -name "*.c.gcov" | xargs rm -f', shell=True, cwd=cwd)
        for gcdafile in sorted(gcdafilelines):
            gcdafile = gcdafile.strip()
            if '/gcc/testsuite/' in gcdafile:
                continue

            subprocess.run(gcovPath + ' ' + gcdafile + ' > /dev/null 2>&1', shell=True, cwd=gccbuildPath)

    file_gcovlist = os.path.join(cwd, 'gcovlist')
    if os.path.exists(file_gcovlist):
        subprocess.run('rm ' + file_gcovlist, shell=True, cwd=cwd)

    subprocess.run('find ' + covDir + ' -name "*.c.gcov" > ' + file_gcovlist, shell=True, cwd=cwd)

    covline_set = set()
    with open(file_gcovlist, 'r') as f:
        gcovfilelines = f.readlines()
        for gcovfile in sorted(gcovfilelines):
            gcovfile = gcovfile.strip()
            tmpfilename = os.path.relpath(gcovfile, covDir).replace('.c.gcov', '.c')
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


def topk(resultlist, k):
    cnt = sum(1 for gcc in resultlist if min(gcc) <= k)
    return cnt


def calculate_metrics(resultlist):
    result = {}
    result['Top-1'] = topk(resultlist, 1)
    result['Top-5'] = topk(resultlist, 5)
    result['Top-10'] = topk(resultlist, 10)
    result['Top-20'] = topk(resultlist, 20)

    mfr_sum = sum(min(gcc) for gcc in resultlist)
    result['MFR'] = round(mfr_sum / len(resultlist), 2)

    mar_sum = sum(sum(gcc) / len(gcc) for gcc in resultlist)
    result['MAR'] = round(mar_sum / len(resultlist), 2)

    return result


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


def task(gccbug):
    bugId, rev, passOptLevel, failOptLevel, buggyFiles = getBugInfo(gccbug)

    # generate configurations
    passConfs, failConfs = collect_option(rev, bugId, failOptLevel, passOptLevel)

    # SBFL rank
    scoredict = getRank(bugId, rev, passConfs, failConfs, collectDir)
        

if __name__ == '__main__':
    if not os.path.exists(collectDir):
        subprocess.run('mkdir -p ' + collectDir, shell=True)

    with open(gccbugsFile, 'r') as f:
        gccbugs = [item.strip() for item in f.readlines()]
    
    if not parallel:
        for gccbug in gccbugs:
            _, rev, _, _, _ = getBugInfo(gccbug)
            if os.path.exists(os.path.join(compilersDir, rev, 'build')):
                task(gccbug)
    else:
        bugs = []
        for item in gccbugs:
            bugId, rev, _, _, _ = getBugInfo(item)
            if not os.path.exists(os.path.join(compilersDir, rev, 'build')):
                continue
            if bugId == '61518':  # same gcc version as 61517
                continue
            bugs.append(item)
        pool = multiprocessing.Pool(processes)
        result = pool.map_async(task, bugs)
        result.wait()

        for gccbug in gccbugs:
            bugId, _, _, _, _ = getBugInfo(gccbug)
            if bugId == '61518':
                task(gccbug)
    
    
