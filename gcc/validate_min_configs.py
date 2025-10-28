import os
import argparse
import random
import subprocess


current_directory = os.path.dirname(os.path.abspath(__file__))
compilersDir = os.path.join(current_directory, 'compilers')
collectDir = os.path.join(current_directory, 'cov')
testDir = os.path.join(current_directory, 'benchmark', 'gccbugs')
gccbugsFile = os.path.join(current_directory, 'benchmark', 'gccbugs_summary.txt')


# Keep consistent with gcc-run.py default behavior
CRASH_BUG_IDS = ['58343', '56478', '58068', '58451', '58539']


def read_bug_info(bug_id):
    with open(gccbugsFile, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            items = line.split(',')
            if items[0] != bug_id:
                continue
            rev = items[1]
            pass_opt_level = items[2].replace('+', ' ')
            fail_opt_level = items[3].replace('+', ' ')
            return rev, pass_opt_level, fail_opt_level
    raise ValueError('bugId {} not found in gccbugs_summary.txt'.format(bug_id))


def get_conf_result(bug_id, rev, conf, timeout_seconds):
    cwd = os.path.join(testDir, bug_id)
    gcc_path = os.path.join(compilersDir, rev, 'build/bin/gcc')

    compile_cmd = [gcc_path, '-w'] + conf.split() + ['fail.c']
    try:
        cpl = subprocess.run(
            compile_cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds + 1,
            universal_newlines=True,
        )
        if bug_id in CRASH_BUG_IDS:
            return str(cpl.returncode)
        if cpl.returncode != 0:
            return '{}:{}:{}'.format(cpl.returncode, (cpl.stdout or '').strip(), (cpl.stderr or '').strip())

        # run a.out
        exec_path = os.path.join(cwd, 'a.out')
        try:
            exe = subprocess.run(
                [exec_path],
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_seconds + 1,
                universal_newlines=True,
            )
            return '{}:{}:{}'.format(exe.returncode, (exe.stdout or '').strip(), (exe.stderr or '').strip())
        except subprocess.TimeoutExpired:
            return 'EXETimeoutExpired'
    except subprocess.TimeoutExpired:
        return 'CPLTimeoutExpired'


def load_fail_configs(bug_id):
    confs_path = os.path.join(collectDir, bug_id, 'confs.txt')
    if not os.path.exists(confs_path):
        raise FileNotFoundError('confs.txt not found at {}. Please run gcc-run.py first.'.format(confs_path))

    fail_configs = []
    with open(confs_path, 'r', encoding='utf-8') as f:
        lines = [line.rstrip('\n') for line in f]

    mode = None
    for line in lines:
        if not line:
            continue
        if line.strip().startswith('PASS CONFIGS:'):
            mode = 'PASS'
            continue
        if line.strip().startswith('FAIL CONFIGS:'):
            mode = 'FAIL'
            continue
        if mode == 'FAIL':
            fail_configs.append(line.strip())

    return [c for c in fail_configs if c]


def flip_flag(token):
    if token.startswith('-fno-'):
        return '-f' + token[len('-fno-'):]
    if token.startswith('-f'):
        return '-fno-' + token[len('-f'):]
    return token


def random_flip_conf(conf, rng, max_flips):
    tokens = conf.split()
    flag_indices = [i for i, t in enumerate(tokens) if t.startswith('-f')]
    if not flag_indices:
        return conf  # nothing to flip
    flips = rng.randint(1, min(max_flips, len(flag_indices)))
    chosen = rng.sample(flag_indices, flips)
    tokens2 = list(tokens)
    for idx in chosen:
        tokens2[idx] = flip_flag(tokens2[idx])
    return ' '.join(tokens2)


def get_enabled_fopts(bug_id, rev, conf):
    cwd = os.path.join(testDir, bug_id)
    gcc_path = os.path.join(compilersDir, rev, 'build/bin/gcc')
    # Query optimizer switches under the provided configuration
    try:
        out = subprocess.run(
            [gcc_path, '-Q', '--help=optimizers'] + conf.split(),
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
    except Exception as e:
        return []

    enabled = []
    for line in (out.stdout or '').splitlines():
        line = line.strip()
        if not line.startswith('-'):
            continue
        parts = line.split()
        if len(parts) == 2 and parts[1] == '[enabled]':
            enabled.append(parts[0])
    enabled.sort()
    return enabled


def main():
    parser = argparse.ArgumentParser(description='Validate minimality of FAIL CONFIGS by random flag flips.')
    parser.add_argument('--bug-id', required=True, help='Bug ID, e.g., 56478')
    parser.add_argument('--samples', type=int, default=20, help='Number of random trials')
    parser.add_argument('--max-flips', type=int, default=3, help='Max flags flipped per trial')
    parser.add_argument('--timeout', type=int, default=15, help='Seconds for compile/run timeouts')
    parser.add_argument('--seed', type=int, default=0, help='Random seed for reproducibility')
    parser.add_argument('--list-enabled', action='store_true', help='List actually enabled -f* options for FAIL CONFIGS')
    parser.add_argument('--enabled-limit', type=int, default=0, help='If >0, only process this many FAIL CONFIGS when listing enabled')
    parser.add_argument('--show-summary', action='store_true', help='Show enabled options summary for original vs minimized configs')
    args = parser.parse_args()

    rng = random.Random(args.seed)

    bug_id = args.bug_id
    rev, pass_opt_level, fail_opt_level = read_bug_info(bug_id)
    pass_result = get_conf_result(bug_id, rev, pass_opt_level, args.timeout)

    fail_configs = load_fail_configs(bug_id)
    if not fail_configs:
        raise ValueError('No FAIL CONFIGS found to test.')

    out_dir = os.path.join(collectDir, bug_id)
    os.makedirs(out_dir, exist_ok=True)
    report_path = os.path.join(out_dir, 'validate_report.txt')

    # Show summary of enabled options: original vs minimized
    if args.show_summary:
        summary_path = os.path.join(out_dir, 'options_summary.txt')
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write('=== ENABLED OPTIONS SUMMARY ===\n')
            f.write('Bug ID: {}\n'.format(bug_id))
            f.write('\n')
            
            # Original failOptLevel enabled options
            original_enabled = get_enabled_fopts(bug_id, rev, fail_opt_level)
            f.write('ORIGINAL FAIL CONFIG: {}\n'.format(fail_opt_level))
            f.write('ENABLED COUNT: {}\n'.format(len(original_enabled)))
            if original_enabled:
                f.write('ENABLED OPTIONS:\n')
                for opt in original_enabled:
                    f.write('  {}\n'.format(opt))
            f.write('\n')
            
            # Minimized FAIL CONFIGS enabled options (show first one as example)
            if fail_configs:
                minimized_enabled = get_enabled_fopts(bug_id, rev, fail_configs[0])
                f.write('MINIMIZED FAIL CONFIG (example): {}\n'.format(fail_configs[0]))
                f.write('ENABLED COUNT: {}\n'.format(len(minimized_enabled)))
                if minimized_enabled:
                    f.write('ENABLED OPTIONS:\n')
                    for opt in minimized_enabled:
                        f.write('  {}\n'.format(opt))
                f.write('\n')
                
                # Show reduction
                reduction = len(original_enabled) - len(minimized_enabled)
                f.write('REDUCTION: {} options disabled ({} -> {})\n'.format(
                    reduction, len(original_enabled), len(minimized_enabled)))
                if reduction > 0:
                    disabled_opts = set(original_enabled) - set(minimized_enabled)
                    f.write('DISABLED OPTIONS:\n')
                    for opt in sorted(disabled_opts):
                        f.write('  {}\n'.format(opt))
            f.write('\n')
        
        print('Wrote options summary to {}'.format(summary_path))

    # Optional: list enabled fine-grained opts for FAIL CONFIGS
    if args.list_enabled:
        enabled_report = os.path.join(out_dir, 'enabled_options.txt')
        limit = args.enabled_limit if args.enabled_limit and args.enabled_limit > 0 else len(fail_configs)
        with open(enabled_report, 'w', encoding='utf-8') as f:
            f.write('Bug {} enabled options report ({} configs)\n\n'.format(bug_id, limit))
            count = 0
            for conf in fail_configs:
                if count >= limit:
                    break
                enabled = get_enabled_fopts(bug_id, rev, conf)
                f.write('CONF: {}\n'.format(conf))
                f.write('ENABLED COUNT: {}\n'.format(len(enabled)))
                if enabled:
                    f.write('ENABLED OPTIONS:\n')
                    for opt in enabled:
                        f.write('  {}\n'.format(opt))
                f.write('\n')
                count += 1
        print('Wrote enabled options report to {}'.format(enabled_report))

    successes = []
    trials = []
    for i in range(1, args.samples + 1):
        base_conf = rng.choice(fail_configs)
        flipped_conf = random_flip_conf(base_conf, rng, args.max_flips)
        res = get_conf_result(bug_id, rev, flipped_conf, args.timeout)
        passed = (res == pass_result)
        trials.append((base_conf, flipped_conf, res, passed))
        if passed:
            successes.append((base_conf, flipped_conf, res))

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('Bug {} validation trials: {}\n'.format(bug_id, len(trials)))
        f.write('Pass baseline: {} -> {}\n'.format(pass_opt_level, pass_result))
        f.write('\n')
        for idx, (base_conf, flipped_conf, res, passed) in enumerate(trials, 1):
            f.write('[{}] BASE FAIL CONF: {}\n'.format(idx, base_conf))
            f.write('    FLIPPED CONF   : {}\n'.format(flipped_conf))
            f.write('    RESULT         : {}\n'.format(res))
            f.write('    BECAME PASS    : {}\n'.format(passed))
            f.write('\n')

        f.write('=== SUMMARY ===\n')
        f.write('Flipped configs that became PASS: {}/{}\n'.format(len(successes), len(trials)))
        if successes:
            f.write('Examples (up to 5):\n')
            for base_conf, flipped_conf, res in successes[:5]:
                f.write('- BASE: {}\n  FLIP: {}\n  RES : {}\n'.format(base_conf, flipped_conf, res))

    print('Wrote validation report to {}'.format(report_path))
    if successes:
        print('Found {} flipped configurations that PASS. FAIL CONFIGS may not be globally minimal.'.format(len(successes)))
    else:
        print('No flipped configurations became PASS in sampled trials.')


if __name__ == '__main__':
    main()


