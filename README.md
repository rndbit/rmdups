# rmdups
Remove duplicate files that already exist in other directories

The program must be given one or more sets of files "to keep"
and one or more sets of files to consider "to delete".

In order to be flagged for deletion a file must satisfy ALL following:
 * must be present in any "to delete" set;
 * must NOT be SAME file as ANY file in the "to keep" sets, where "SAME" is
   determined by comparing the file-system AND inode but NOT the path.
   This protects cases where "to keep" and "to delete" sets intersect;
 * there must exist another DIFFERENT (different filesystem and/or inode)
   file in any "to keep" set with identical content.

In less strict terms, the goal is that:
 * ALL files in the "to keep" sets are kept.
   Duplicates within the "to keep" sets are not even searched for;
 * Files in the "to delete" sets that have a copy in any "to keep" set are
   flagged for deletion.
   The file names are ignored, only the content is compared;
 * Files in the "to delete" sets that do NOT have a copy in any "to keep" sets
   are kept.

Example usage

Consider there are two directories both containing all files dumped from phone at different points in time.
This finds files in "phone-dump-prevoius" that are also in "phone-dump-latest" even if they got renamed.

    python3 rmdups.py --del-dir "phone-dump-prevoius" --keep-dir "phone-dump-latest"
    # To actually delete the duplicates also add "--unlink" parameter.

Consider old backup was extracted into directory "old-backup" and user wants to focus only on files
in the "old-backup" directory that no longer appear or changed compared to "current-good-work" directory.
Any files that are the same to be deleted, except any files that contain "project1" in the path to be kept anyway.

    # Make a list of files to delete
    find old-backup -type f | grep -v -e "project1" > delete-set1
    # Make a list of all files to keep
    find current-good-work -type f > keep-set1
    # Generate a report of files eligible for deletion
    python3 rmdups.py --del-index delete-set1 --keep-index keep-set1
    # Or can feed list of files to STDIN
    python3 rmdups.py --del-index delete-set1 --keep-index - < keep-set1
    # Or can specify keep set via --keep-dir and NOT have to create a list of files
    python3 rmdups.py \
        --del-index delete-set1 \
        --keep-dir current-good-work

Alternatively if all "project1" content is confined to a single subdirectory inside "old-backup/subdir/project1"
then can achive similar result by telling the program to "keep" that subdir even though it is inside delete dir:

    python3 rmdups.py \
        --del-dir old-backup \
        --keep-dir old-backup/subdir/project1 \
        --keep-dir current-good-work

The parameters "--keep-dir", "--keep-index", "--del-dir", "--del-index" can be mixed and appear many times.
