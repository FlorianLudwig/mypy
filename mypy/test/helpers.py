import sys
import re
import os

from typing import List

from mypy.myunit import AssertionFailure
from mypy.test import config


# AssertStringArraysEqual displays special line alignment helper messages if
# the first different line has at least this many characters,
MIN_LINE_LENGTH_FOR_ALIGNMENT = 5


def assert_string_arrays_equal(expected: List[str], actual: List[str],
                               msg: str) -> None:
    """Assert that two string arrays are equal.

    Display any differences in a human-readable form.
    """
    
    actual = clean_up(actual)
    
    if actual != expected:
        num_skip_start = num_skipped_prefix_lines(expected, actual)
        num_skip_end = num_skipped_suffix_lines(expected, actual)
        
        sys.stderr.write('Expected:\n')
        
        # If omit some lines at the beginning, indicate it by displaying a line
        # with '...'.
        if num_skip_start > 0:
            sys.stderr.write('  ...\n')
        
        # Keep track of the first different line.
        first_diff = -1
        
        # Display only this many first characers of identical lines.
        width = 75
        
        for i in range(num_skip_start, len(expected) - num_skip_end):
            if i >= len(actual) or expected[i] != actual[i]:
                if first_diff < 0:
                    first_diff = i
                sys.stderr.write('  {:<45} (diff)'.format(expected[i]))
            else:
                e = expected[i]
                sys.stderr.write('  ' + e[:width])
                if len(e) > width:
                    sys.stderr.write('...')
            sys.stderr.write('\n')
        if num_skip_end > 0:
            sys.stderr.write('  ...\n')
        
        sys.stderr.write('Actual:\n')
        
        if num_skip_start > 0:
            sys.stderr.write('  ...\n')
        
        for j in range(num_skip_start, len(actual) - num_skip_end):
            if j >= len(expected) or expected[j] != actual[j]:
                sys.stderr.write('  {:<45} (diff)'.format(actual[j]))
            else:
                a = actual[j]
                sys.stderr.write('  ' + a[:width])
                if len(a) > width:
                    sys.stderr.write('...')
            sys.stderr.write('\n')
        if actual == []:
            sys.stderr.write('  (empty)\n')
        if num_skip_end > 0:
            sys.stderr.write('  ...\n')
        
        sys.stderr.write('\n')
        
        if first_diff >= 0 and first_diff < len(actual) and (
                len(expected[first_diff]) >= MIN_LINE_LENGTH_FOR_ALIGNMENT
                or len(actual[first_diff]) >= MIN_LINE_LENGTH_FOR_ALIGNMENT):
            # Display message that helps visualize the differences between two
            # long lines.
            show_align_message(expected[first_diff], actual[first_diff])
        
        raise AssertionFailure(msg)


def show_align_message(s1: str, s2: str) -> None:
    """Align s1 and s2 so that the their first difference is highlighted.

    For example, if s1 is 'foobar' and s2 is 'fobar', display the
    following lines:
    
      E: foobar
      A: fobar
           ^
    
    If s1 and s2 are long, only display a fragment of the strings around the
    first difference. If s1 is very short, do nothing.
    """
    
    # Seeing what went wrong is trivial even without alignment if the expected
    # string is very short. In this case do nothing to simplify output.
    if len(s1) < 4:
        return 
    
    maxw = 72 # Maximum number of characters shown
    
    sys.stderr.write('Alignment of first line difference:\n')
    
    trunc = False
    while s1[:30] == s2[:30]:
        s1 = s1[10:]
        s2 = s2[10:]
        trunc = True
    
    if trunc:
        s1 = '...' + s1
        s2 = '...' + s2
    
    max_len = max(len(s1), len(s2))
    extra = ''
    if max_len > maxw:
        extra = '...'
    
    # Write a chunk of both lines, aligned.
    sys.stderr.write('  E: {}{}\n'.format(s1[:maxw], extra))
    sys.stderr.write('  A: {}{}\n'.format(s2[:maxw], extra))
    # Write an indicator character under the different columns.
    sys.stderr.write('     ')
    for j in range(min(maxw, max(len(s1), len(s2)))):
        if s1[j:j + 1] != s2[j:j + 1]:
            sys.stderr.write('^') # Difference
            break
        else:
            sys.stderr.write(' ') # Equal
    sys.stderr.write('\n')


def assert_string_arrays_equal_wildcards(expected: List[str],
                                         actual: List[str],
                                         msg: str) -> None:
    # Like above, but let a line with only '...' in expected match any number
    # of lines in actual.
    actual = clean_up(actual)
    
    while actual != [] and actual[-1] == '':
        actual = actual[:-1]
    
    # Expand "..." wildcards away.
    expected = match_array(expected, actual)
    assert_string_arrays_equal(expected, actual, msg)


def clean_up(a):
    """Remove common directory prefix from all strings in a.

    This uses a naive string replace; it seems to work well enough. Also
    remove trailing carriage returns.
    """
    res = []
    for s in a:
        prefix = config.PREFIX + os.sep
        ss = s
        for p in prefix, prefix.replace(os.sep, '/'):
            if p != '/' and p != '//' and p != '\\' and p != '\\\\':
                ss = ss.replace(p, '')
        # Ignore spaces at end of line.
        ss = re.sub(' +$', '', ss)
        res.append(re.sub('\\r$', '', ss))
    return res


def match_array(pattern: List[str], target: List[str]) -> List[str]:
    """Expand '...' wildcards in pattern by matching against target."""
    
    res = [] # type: List[str]
    i = 0
    j = 0
    
    while i < len(pattern):
        if pattern[i] == '...':
            # Wildcard in pattern.
            if i + 1 == len(pattern):
                # Wildcard at end of pattern; match the rest of target.
                res.extend(target[j:])
                # Finished.
                break
            else:
                # Must find the instance of the next pattern line in target.
                jj = j
                while jj < len(target):
                    if target[jj] == pattern[i + 1]:
                        break
                    jj += 1
                if jj == len(target):
                    # No match. Get out.
                    res.extend(pattern[i:])
                    break
                res.extend(target[j:jj])
                i += 1
                j = jj
        elif (j < len(target) and (pattern[i] == target[j]
                                   or (i + 1 < len(pattern)
                                       and j + 1 < len(target)
                                       and pattern[i + 1] == target[j + 1]))):
            # In sync; advance one line. The above condition keeps sync also if
            # only a single line is different, but loses it if two consecutive
            # lines fail to match.
            res.append(pattern[i])
            i += 1
            j += 1
        else:
            # Out of sync. Get out.
            res.extend(pattern[i:])
            break
    return res


def num_skipped_prefix_lines(a1: List[str], a2: List[str]) -> int:
    num_eq = 0
    while num_eq < min(len(a1), len(a2)) and a1[num_eq] == a2[num_eq]:
        num_eq += 1
    return max(0, num_eq - 4)


def num_skipped_suffix_lines(a1: List[str], a2: List[str]) -> int:
    num_eq = 0
    while (num_eq < min(len(a1), len(a2))
           and a1[-num_eq - 1] == a2[-num_eq - 1]):
        num_eq += 1
    return max(0, num_eq - 4)


def testfile_pyversion(path: str) -> int:
    if path.endswith('python2.test'):
        return 2
    else:
        return 3
