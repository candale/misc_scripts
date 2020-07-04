#!/bin/bash

# Little CLI to upload files to a Nextcloud instance
# TODO: Upload multiple files are once
# TODO: Show proper progress on files


upload_dir_files() {
    src_dir=$1
    target_remote_url=$2
    read -p "Username: " username
    read -p "Password: " pass

    num_files="$(find "$src_dir" -type f | wc -l)"
    read -p "Trying to upload $num_files files from path $src_dir.[y/n]" consent
    if [ "$consent" != "y" ]; then
        echo "Abort by user"
        exit 1
    fi

    index=0
    for file in $src_dir/*; do
	name=$(basename "$file")
        curl --progress-bar -u "$username:$pass" -T "$file" "$target_remote_url/$name"
	index=$((index+1))
	echo "File $index out of $num_files"
    done
}


case $1 in
    upload-dir)
        shift
	src_dir=$1
	shift
	dest_url=$1
	if [ -z "$src_dir" ]; then
	    echo "You must provide a target dir to upload files from"
	    exit 1
	fi
	if [ -z "$dest_url" ]; then
            echo "You must provide the target WEBDV ULR with destination dir"
	    exit 1
	fi

        upload_dir_files "$(realpath "$src_dir")" "$dest_url"
	;;
    *)
	echo "Upload files though WEBDV"
	echo "Usage: upload-dir target-dir"
	;;
esac

