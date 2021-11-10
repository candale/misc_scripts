"""
Run: python3 check_sub.py path_to.srt

Give the following:
- error if the first line in file is a number with no spaces around it
- error if there are two blank lines between two subtitle chunks
- error if sync info matches the standard format, with no spaces at the
  beginning or end
- error if a subtitle chunk has more than three subtitles lines
- warning if a subtitle chunk has no subtitle lines
- warning if a subtitle chunk has three subtitle lines

When an error is given, fix the error and run the script again. If the script
encounters an error, it stops processing the file.
"""

import sys
import re


def check_chunk(chunk_count, start_line, file):
    assert start_line.strip().replace('\ufeff', '').isdigit(), (
        'Something wrong at chunk on line {}. Expected number but got {}'
        .format(chunk_count, start_line.strip())
    )
    timing = next(f)
    assert re.match(
        (
            r'^\d{1,2}:\d\d{1,2}:\d\d{1,2},?\d{0,3}'
            r'\s-->'
            r'\s\d{1,2}:\d\d{1,2}:\d\d{1,2},?\d{0,3}$'
        ),
        timing
    ), 'TIming is wrong at chunk on line {}'.format(chunk_count)

    count = 0
    while True:
        try:
            sub = next(f)
        except StopIteration:
            break

        count += 1
        if sub.strip() == '':
            if count == 1:
                print('WARNING: No subtitle for chunk at line {}'.format(chunk_count))
            break

        if count == 3:
            print(
                'WARNING: Three lines of subtitle at chunk on line {}'
                .format(chunk_count)
            )

        if count > 3:
            assert False, (
                'More than 3 lines at chunk on line {}'.format(chunk_count))

    return count + 1


with open(sys.argv[1], 'r') as f:
    consumed = 0
    for line in f:
        consumed += 1
        consumed += check_chunk(consumed, line, f)
