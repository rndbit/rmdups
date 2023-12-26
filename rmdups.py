#!/usr/bin/env python3

import os
import sys
import argparse
import functools
import subprocess

CACHE_SIZE = 1024
FREAD_SIZE = 1024 * 64


def trace(msg):
    label = "TRACE: "
#    print(label + msg, file=sys.stderr)


def debug(msg):
    label = "DEBUG: "
#    print(label + msg, file=sys.stderr)


def info(msg):
    label = "INFO: "
    print(label + msg, file=sys.stderr)


def warning(msg):
    label = "WARNING: "
    print(label + msg, file=sys.stderr)


class IndexedFile(object):

    def __init__(self, path, name, stat):
        self.path = path
        self.name = name
        self.stat = stat
        self.cache = None


class Index(object):
    def __init__(self, label):
        self.label = label
        self.files_by_size = { }

    def add_file(self, file):
        if file.stat.st_size in self.files_by_size.keys():
            # add the new file to the list of files with same size
            # TODO change to insert in order of file_name, mtime
            self.files_by_size[file.stat.st_size].append(file)
        else:
            # create a new mapping from file size to one sized array containing the file
            self.files_by_size[file.stat.st_size] = [ file ]

        trace("added to {label} index, size={file_size:,} size_count={count}, path={path}".format(
            label = self.label,
            file_size = file.stat.st_size,
            count = len(self.files_by_size[file.stat.st_size]),
            path = file.path,
            ))

    # Always returns a list, possibly empty list
    def get_by_size(self, file):
        if file.stat.st_size in self.files_by_size.keys():
            return self.files_by_size[file.stat.st_size].copy()
        else:
            return []


def compare_for_file(test_file, f1, f2):
    # If test_file is same as f1
    if (
        test_file.stat.st_dev == f1.stat.st_dev
        and test_file.stat.st_ino == f1.stat.st_ino
    ):
        # if test_file is NOT same as f2
        if not (
            test_file.stat.st_dev == f2.stat.st_dev
            and test_file.stat.st_ino == f2.stat.st_ino
        ):
            trace("sort comparison: test_file(%s) same file as f1(%s) but not same as f2(%s)" % (test_file.path, f1.path, f2.path))
            # f1 comes 1st as same to test_file
            return -1
        else:
            trace("sort comparison: test_file(%s) same file as f1(%s) AND same as f2(%s)" % (test_file.path, f1.path, f2.path))
    # test_file is NOT same as f1
    # if test_file is same as f2
    elif (
        test_file.stat.st_dev == f2.stat.st_dev
        and test_file.stat.st_ino == f2.stat.st_ino
    ):
        trace("sort comparison: test_file(%s) NOT same file as f1(%s) but same as f2(%s)" % (test_file.path, f1.path, f2.path))
        # f2 comes 1st as same to test_file
        return 1

    # order by name sameness
    if test_file.name == f1.name:
        if not test_file.name == f2.name:
            return -1
    elif test_file.name == f2.name:
        return 1

    # If test_file has mtime sameness
    if test_file.stat.st_mtime == f1.stat.st_mtime:
        if not test_file.stat.st_mtime == f2.stat.st_mtime:
            return -1
    elif test_file.stat.st_mtime == f2.stat.st_mtime:
        return 1

    if f1.path < f2.path:
        return -1
    elif f1.path > f2.path:
        return 1

    return 0


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--keep-index', dest='keep_index', action='append', help='index of files to keep')
    parser.add_argument('--keep-dir', dest='keep_dir', action='append', help='directory to keep')
    parser.add_argument('--del-index', dest='del_index', action='append', help='index of files to consider for deletion')
    parser.add_argument('--del-dir', dest='del_dir', action='append', help='directory whos content to consider for deletion')
    parser.add_argument('--dup-print', dest='dup_print', action='store_true', help='Print the duplicate file names to stdout terminated with LF')
    parser.add_argument('--dup-print0', dest='dup_print0', action='store_true', help='Print the duplicate file names to stdout terminated by \\000 zero char')
    parser.add_argument('--dup-cmd', dest='dup_cmd', action='append', help='Provide command(s) to run for the duplicate files, command is split on space, any {} is replaced by filename, if not found filename is appended')
    parser.add_argument('--dup-delete', dest='dup_delete', action='store_true', help='Delete duplicate files')
    parser.add_argument('--dup-wipe', dest='dup_wipe', action='store_true', help='Write zeros to whole length of duplicate files before deleting')
    args = parser.parse_args()
    return args


def read_index_file_name(file_name, update_index, predicate):
    with open(file_name, "r") as file_handle:
        read_index_file_handle(file_handle, update_index, predicate)


def read_index_file_handle(file_handle, update_index, predicate):
    for line in file_handle:
        file_path = line.rstrip()

        if not os.path.isfile(file_path):
            warning("ignore not-a-file: %s" % file_path)
            continue

        file_name = os.path.split(file_path)[1]
        if len(file_name) == 0:
            warning("Empty file name for path, skippign: %s" % file_path)
            continue

        try:
            stat = os.stat(file_path)
        except Exception as ex:
            warning("Error getting file info, skipping: %s" % file_path)
            continue

        index_file = IndexedFile(file_path, file_name, stat)
        if not predicate is None:
            if not predicate(index_file):
                debug("not allowed by predicate: %s" % file_path)
                continue
        update_index.add_file(index_file)


def read_dir_recursive_into_index(dir_name, update_index, predicate):
    for path, dirs, files in os.walk(dir_name):
        for file_name in files:
            file_path = os.path.join(path, file_name)

            try:
                stat = os.stat(file_path)
            except Exception as ex:
                warning("Error getting file info, skipping: %s" % file_path)
                continue

            index_file = IndexedFile(file_path, file_name, stat)
            if not predicate is None:
                if not predicate(index_file):
                    debug("not allowed by predicate: %s" % file_path)
                    continue
            update_index.add_file(index_file)

#    if not os.path.isdir(dir_name):
#        print("when scanning dir ignore not a dir: %s" % dir_name)
#        continue


cache_hit_same = 0
cache_hit_diff = 0
cache_hit_same_but_short = 0


def compare_files(f1, f2):
    global cache_hit_same
    global cache_hit_diff
    global cache_same_but_short
    global cache_hit_same_but_short

    debug("comparing '%s' and '%s'" % (f1.path, f2.path))
    # If cache is set for both files
    if (not f1.cache is None) and (not f2.cache is None):
        # If the caches differ
        if not f1.cache == f2.cache:
            cache_hit_diff += 1
            return False
        # If both files are entirely in the cache
        if (len(f1.cache) == f1.stat.st_size and len(f2.cache) == f2.stat.st_size):
            cache_hit_same += 1
            return True
        cache_hit_same_but_short += 1

    with open(f1.path, "rb") as fh1:
        with open(f2.path, "rb") as fh2:
            cache1 = b''
            cache2 = b''

            if not f1.cache is None:
                cache1 = None
            if not f2.cache is None:
                cache2 = None

            eof1 = False
            eof2 = False

#            trace("comparing '%s' and '%s': entring looop" % (f1.path, f2.path))
            while True:
                buf1 = fh1.read(FREAD_SIZE)
                if len(buf1) == 0:
                    eof1 = True
                    # do a read on fh2 to ensure it also ended
                    temp = fh2.read(1)
                    if len(temp) > 0:
                        # 1st file ended but 2nd produced a blob, not equal length!!!
                        warning("when comparing file '%s' ended but file '%s' produced more data, not same length, BUG! File Changed?" % (f1.path, f2.path))
                        return False
                    # Both files ended, at the same time
                    return True

                # If interested in cache for f1
                if f1.cache is None:
                    cache1 += buf1
                    if len(cache1) >= CACHE_SIZE:
                        # store the cache, this also prevents caching more
                        f1.cache = cache1[0:CACHE_SIZE]
                        # discard cache
                        cache1 = None

                # Read form fh2 just enough bytes to match size buffered from fh1
                buf2 = b''
                while (not eof2) and (len(buf2) < len(buf1)):
                    temp = fh2.read(len(buf1) - len(buf2))
                    if len(temp) == 0:
                        warning("when comparing file '%s' produced more data but file '%s' ended, not same length, BUG! File Changed?" % (f1.path, f2.path))
                        return False
                    else:
                        buf2 += temp

                # If interested in cache for f2
                if f2.cache is None:
                    cache2 += buf2
                    if len(cache2) >= CACHE_SIZE:
                        # store the cache, this also prevents caching more
                        f2.cache = cache2[0:CACHE_SIZE]
                        # discard cache
                        cache2 = None

                if buf1 != buf2:
                    return False


def is_keep_file_of_interest(keep_file, delete_index):
    if keep_file.stat.st_size in delete_index.files_by_size:
        return True
    trace("inside-predicate: keep file of no interest, no delete files of same size: %s" % keep_file.path)
    return False


def main():
    args = parse_args()
    print(args, file=sys.stderr)

    delete_index = Index("DeleteIndex")
    keep_index = Index("KeepIndex")

    # First load up all delete indexes and dirs scans
    if not args.del_index is None:
        for del_ind_file in args.del_index:
            if del_ind_file == '-':
                info("reading --del-index from STDIN'")
                read_index_file_handle(sys.stdin, delete_index, None)
            else:
                info("reading --del-index '%s'" % del_ind_file)
                read_index_file_name(del_ind_file, delete_index, None)
        info("Finished reading all --del-index")
    else:
        debug("del_index is NOT set")


    if not args.del_dir is None:
        for del_dir in args.del_dir:
            info("scanning --del-dir '%s'" % del_dir)
            read_dir_recursive_into_index(del_dir, delete_index, None)
        info("Finished scanning all --del-dir")
    else:
        debug("del_dir is NOT set")


    # When adding files to keep_index do not bother adding files whos sizes do not appear in the delete_index

    # Create lambda that test if a file's size appears in sizes in delete_index
    keep_index_predicate = lambda ifile : is_keep_file_of_interest(ifile, delete_index)

    # First load up all delete indexes and dirs scans
    if not args.keep_index is None:
        for keep_ind_file in args.keep_index:
            if keep_ind_file == '-':
                info("reading --keep-index from STDIN'")
                read_index_file_handle(sys.stdin, keep_index, keep_index_predicate)
            else:
                info("reading --keep-index '%s'" % keep_ind_file)
                read_index_file_name(keep_ind_file, keep_index, keep_index_predicate)
        info("Finished reading all --keep-index")
    else:
        debug("keep_index is NOT set")

    if not args.keep_dir is None:
        for keep_dir in args.keep_dir:
            info("scanning --keep-dir '%s'" % keep_dir)
            read_dir_recursive_into_index(keep_dir, keep_index, keep_index_predicate)
        info("Finished scanning all --keep-dir")
    else:
        debug("keep_dir is NOT set")

    delete_byte_count = 0
    delete_file_count = 0
    for size in sorted(delete_index.files_by_size.keys(), reverse=True):
        trace("comparing size: {:,}".format(size))
        delete_files = delete_index.files_by_size[size].copy()
        keep_files   = keep_index  .files_by_size.get(size, []).copy()
        for del_file in delete_files:
            comparator_for_del_file = lambda f1, f2 : compare_for_file(del_file, f1, f2)
            keep_files_sorted = sorted(keep_files, key=functools.cmp_to_key(comparator_for_del_file))
#            keep_files_sorted = keep_files
            trace("for del_file %s sorted list is %s" % (del_file.path, ",".join(map(lambda v: v.path, keep_files_sorted))))

            # Test if the del_file is SAME file (not came content) as any of the files to be kept
            skip_del_file = False
            for keep_file in keep_files_sorted:
                if ( del_file.stat.st_dev == keep_file.stat.st_dev and del_file.stat.st_ino == keep_file.stat.st_ino ):
                    warning("refuse to delete file '%s' is same file as to be kept file '%s'" % ( del_file.path, keep_file.path ))
#                    warning("refuse to delete file '%s' is same file as to be kept" % ( del_file.path ))
                    skip_del_file = True
                    break
            if skip_del_file:
                continue

            for keep_file in keep_files_sorted:
                equals = compare_files(del_file, keep_file)
                if equals:
                    delete_file_count += 1
                    delete_byte_count += del_file.stat.st_size
                    dup_handled = False
                    if args.dup_print:
                        sys.stdout.write(del_file.path + '\n')
                        dup_handled = True
                    if args.dup_print0:
                        sys.stdout.write(del_file.path + '\0')
                        dup_handled = True
                    if args.dup_cmd:
                        # There could be multiple command to run, iterate over the list of commands
                        for cmd in args.dup_cmd:
                            cmd_args = []
                            append_file_path = True
                            for cmd_arg in cmd.split():
                                cmd_arg_replaced = cmd_arg.replace('{}', del_file.path)
                                if cmd_arg_replaced != cmd_arg:
                                    append_file_path = False
                                cmd_args.append(cmd_arg_replaced)
                            if append_file_path:
                                cmd_args.append(del_file.path)
                            info("execute command: '%s'" % cmd_args)
                            # subprocess.run(check=True) causes stop with exception if subprocess exits with non-zero
                            subprocess.run(cmd_args, check=True)
                            dup_handled = True
                    if args.dup_wipe:
                        info("wiping and deleting {size:,} bytes '{del_path}' it is same as '{keep_path}'".format(
                            size = del_file.stat.st_size,
                            del_path = del_file.path,
                            keep_path = keep_file.path,
                            ))
                        with open(del_file.path, "rb+") as fh:
                            bc = del_file.stat.st_size # remaining byte count
                            buf = b'\0' * 1024 * 64 # buffer to write
                            while bc > 0:
                                if bc < len(buf):
                                    buf = b'\0' * bc
                                wc = fh.write(buf)
                                bc -= wc
                        # os.unlink() throws exception if file is gone, good
                        os.unlink(del_file.path)
                        dup_handled = True
                    if args.dup_delete:
                        info("deleting {size:,} bytes '{del_path}' it is same as '{keep_path}'".format(
                            size = del_file.stat.st_size,
                            del_path = del_file.path,
                            keep_path = keep_file.path,
                            ))
                        # os.unlink() throws exception if file is gone, good
                        os.unlink(del_file.path)
                        dup_handled = True
                    # If no other handling was done print default info about dup file
                    if not dup_handled:
                        info("can delete {size:,} bytes '{del_path}' it is same as '{keep_path}'".format(
                            size = del_file.stat.st_size,
                            del_path = del_file.path,
                            keep_path = keep_file.path,
                            ))
                    break

    info("Can delete files={del_count}, bytes={del_byte_sum:,}".format(
        del_count = delete_file_count,
        del_byte_sum = delete_byte_count,
        ))

    global cache_hit_same
    global cache_hit_diff
    global cache_hit_same_but_short

    info("cache_hit_same = %d" % cache_hit_same)
    info("cache_hit_diff = %d" % cache_hit_diff)
    info("cache_hit_same_but_short = %d" % cache_hit_same_but_short)

main()
