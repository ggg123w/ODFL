import os

current_directory = os.path.dirname(os.path.abspath(__file__))
collectDir = os.path.join(current_directory, 'cov')
gccbugsFile = os.path.join(current_directory, 'benchmark', 'gccbugs_summary.txt')
rankFile = os.path.join(current_directory, 'ranks.txt')
resultdict = {}


def getBugInfo(gccbug):
    items = gccbug.strip().split(',')
    bugId, rev, passOptLevel, failOptLevel, buggyFiles = items[0], items[1], items[2].replace('+', ' '), items[3].replace('+', ' '), items[4].split('+')
    return bugId, rev, passOptLevel, failOptLevel, buggyFiles


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


if __name__ == '__main__':
    # Rank
    with open(gccbugsFile, 'r') as f:
        gccbugs = [item.strip() for item in f.readlines()]

    for gccbug in gccbugs:
        bugId, _, _, _, buggyFiles = getBugInfo(gccbug)

        with open(os.path.join(collectDir, bugId, 'Ochiai_scoredict.txt'), 'r') as f:
            scoredict = eval(f.read())

        tmpresultlist = []
        flag = False
        for buggyfile in buggyFiles:
            if buggyfile not in scoredict:
                continue
            else:
                flag = True
                score = scoredict[buggyfile]
                cnt = 1
                for v in scoredict.values():
                    if v > score:
                        cnt += 1
                tmpresultlist.append(cnt)
        if flag == True:
            with open(rankFile, 'a') as f:
                f.write('%s,%s\n' % (bugId, tmpresultlist))

    with open(rankFile, 'r') as f:
        lines = f.readlines()
        for line in lines:
            bugId, tmpresultlist = line.strip().split(',', 1)
            resultdict[bugId] = [int(item) for item in tmpresultlist.strip('][').split(', ')]
    
    # Result
    print('\033[1;35m===================================================\033[0m')
    for key in sorted(resultdict):
        print('%s,%s' % (key, resultdict[key]))
    print('\033[1;35m===================================================\033[0m')

    # Metric calculation
    print('\033[1;35m[metric]:\033[0m')
    result = calculate_metrics(resultdict.values())
    for key, value in result.items():
        print(f"{key}: {value}")
    print('\033[1;35m===================================================\033[0m')

