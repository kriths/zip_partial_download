#!/usr/bin/env python3
import sys
import requests

def find_cdf_offset(url, total_size):
    idx_start = total_size - 65557
    if idx_start < 0:
        idx_start = 0
    req = requests.get(url, headers={'Range': 'bytes={}-{}'.format(idx_start, total_size)})
    oecd_record = req.content

    oecd_startidx = 3
    oecd_backfind = int.from_bytes(oecd_record[-4:], byteorder='big')
    while oecd_backfind != 0x504b0506:
        oecd_backfind >>= 8
        oecd_startidx += 1
        oecd_backfind |= (oecd_record[-oecd_startidx] << 24)

    oecd_record = oecd_record[-oecd_startidx:]
    cdf_count = get_num(oecd_record, 10, 2)
    cdf_size = get_num(oecd_record, 12, 2)
    cdf_offset = get_num(oecd_record, 16, 4)
    return cdf_offset, cdf_size, cdf_count


def get_file_list(url, cdf_offset, cdf_size, cdf_count):
    req = requests.get(url, headers={'Range': 'bytes={}-{}'.format(cdf_offset, cdf_offset+cdf_size)})
    cdf = req.content

    file_list = []
    for _ in range(cdf_count):
        if get_num(cdf, 0, 4, byteorder='big') != 0x504b0102:
            print("Found invalid file descriptor in CDF")
            exit(1)

        file_compression = get_num(cdf, 10, 2)
        file_size_c = get_num(cdf, 20, 4)
        file_size_u = get_num(cdf, 24, 4)
        len_file_name = get_num(cdf, 28, 2)
        len_extra_field = get_num(cdf, 30, 2)
        len_comments = get_num(cdf, 32, 2)
        file_offset = get_num(cdf, 42, 4)
        file_name = cdf[46:46+len_file_name].decode('utf-8')

        next_offset = 46 + len_file_name + len_extra_field + len_comments
        cdf = cdf[next_offset:]
        new_file = {
            'name': file_name,
            'offset': file_offset,
            'compression': file_compression,
            'size_c': file_size_c,
            'size_u': file_size_u
        }
        file_list.append(new_file)

    return file_list


def download_file(url, dl_file):
    print("Starting download of file '{}'".format(dl_file['name']))

    req_fh = requests.get(url, headers={'Range': 'bytes={}-{}'.format(dl_file['offset'], dl_file['offset'] + 29)})
    lfh = req_fh.content
    del req_fh
    if get_num(lfh, 0, 4, byteorder='big') != 0x504b0304:
        print("File header could not be found")
        exit(1)

    size_c = get_num(lfh, 18, 4)
    size_u = get_num(lfh, 22, 4)
    if (dl_file['size_c'] != size_c) or (dl_file['size_u'] != size_u):
        print("File header size does not match")
        exit(1)

    size_file_name = get_num(lfh, 26, 2)
    size_extra_field = get_num(lfh, 28, 2)
    del lfh

    offset = dl_file['offset'] + 30 + size_file_name + size_extra_field
    req_data = requests.get(url, headers={'Range': 'bytes={}-{}'.format(offset, offset+size_c-1)})
    data_c = req_data.content
    del req_data

    file_name = dl_file['name'].split('/')[-1]
    with open(file_name, 'wb') as out_file:
        out_file.write(data_c)


def get_num(btarr, offset, count, byteorder='little'):
    return int.from_bytes(btarr[offset:offset+count], byteorder)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input("Please enter URL of file to download: ")

    file_size = int(requests.head(url).headers['Content-Length'])

    # Find offset of directory
    gcdf_offset, gcdf_size, gcdf_count = find_cdf_offset(url, file_size)
    if gcdf_count <= 0:
        print("No elements to fetch")
        exit(1)

    # Get list of all available files
    files = get_file_list(url, gcdf_offset, gcdf_size, gcdf_count)
    if len(files) == 0:
        print("No files retreived")
        exit(1)

    # Decide which file do download
    for idx, file in enumerate(files):
        print("{idx}: {name} {size}".format(idx=idx+1, name=file['name'], size=file['size_u']))
    dl_index_input = input("Please enter number of file to download: ")
    dl_index = int(dl_index_input) - 1
    if dl_index < 0 or dl_index >= len(files):
        print("Invalid input")
        exit(1)

    download_file(url, files[dl_index])
