import click
import os
from pathlib import Path
import gzip
import shutil
import datetime


@click.command()
@click.option("--accesslog", help="Path of access log")
@click.option("--target", help="Target directory, its format is yyyy/mm/dd/hh.log.gz")
def rotate(accesslog, target):
    prev_hour = datetime.datetime.now() - datetime.timedelta(minutes=60)
    directory = Path(target) / Path(prev_hour.strftime("%Y/%m/%d"))
    if directory.exists() is False:
        directory.mkdir(parents=True)
    dst = directory / prev_hour.strftime("%H.log")
    idx = 1
    while True:
        if dst.exists():
            dst = directory / (prev_hour.strftime("%H.log") +  ".{}".format(idx))
            idx += 1
        else:
            break
    shutil.move(accesslog, dst)
    os.system("kill -USR1 `cat /var/run/nginx.pid`")
    # merge all logs
    dst_gz = directory / prev_hour.strftime("%H.log.gz")
    if dst_gz.exists():
        mode = "ab"
    else:
        mode = "wb"

    gzip_f = gzip.open(dst_gz, mode)
    with open(dst, "rb") as f:
        data = f.read()
        gzip_f.write(data)
    gzip_f.close()
    
    os.unlink(dst)

    print("Write to {}".format(dst_gz))


@click.group()
def main():
    pass


main.add_command(rotate)


if __name__ == "__main__":
    main()
