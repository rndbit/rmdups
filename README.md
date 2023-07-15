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
