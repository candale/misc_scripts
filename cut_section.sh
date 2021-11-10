file_name=$1
from=$2
to=$3
finish=$4
ext=$5

# to copy everything: -vcodec copy -acodec copy -scodec copy
copy='-acodec copy -scodec copy'

# when you get some out of sync stuff when you use -vcoded copy it's because
# the movie is split into segments. when this happens, you need to reencode
# i.e. remove -vcoded copy


echo "======= Making first part ==========="
echo "ffmpeg -fflags +igndts -y -ss 00:00:00 -i $file_name  -t $from file1.${ext}"
ffmpeg -y -ss 00:00:00 -i $file_name -t $from  file1.${ext}

echo "======= Making second part ========="
echo "ffmpeg -fflags +igndts -y -ss $to -avoid_negative_ts 1 -i $file_name ${copy} -t $finish file2.${ext}"
ffmpeg -y -ss $to -avoid_negative_ts 1 -i $file_name -t $finish file2.${ext}

echo "file 'file1.${ext}'" > files.txt
echo "file 'file2.${ext}'" >> files.txt

echo "======== Concatenating ============"
ffmpeg -fflags +igndts -y -f concat -avoid_negative_ts 1 -i files.txt -vcodec copy -acodec copy -scodec copy "out_$(cat /dev/urandom | head -c 4 | base64).${ext}"

# rm file1.${ext} file2.${ext}
