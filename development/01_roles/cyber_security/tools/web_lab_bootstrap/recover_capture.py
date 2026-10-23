"""Teacher recovery: read-only mount of the explicitly selected stopped disk."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


def upload(url, source, config_path):
    # Keep scoped URLs out of argv and console/error output.
    config_path.write_text("url = "+json.dumps(url)+"\nupload-file = "+json.dumps(str(source))+
        "\nrequest = \"PUT\"\nfail\nsilent\nshow-error\nconnect-timeout = 30\nmax-time = 1800\n")
    config_path.chmod(0o600)
    result=subprocess.run(["curl","--config",str(config_path),"-w","%{http_code}"],capture_output=True,text=True)
    config_path.unlink()
    print("RECOVERY_PUT_HTTP="+result.stdout[-3:]+" CURL_EXIT="+str(result.returncode),flush=True)
    if result.returncode:
        raise ValueError("Recovery upload failed")


def main():
    os.umask(0o077)
    root=Path("/var/lib/jdu-capture-recovery")
    config=json.loads((root/"config.json").read_text())
    wanted=config["volume_id"].replace("-","")
    device=None
    for _ in range(120):
        info=json.loads(subprocess.check_output(["lsblk","-J","--tree","-o","PATH,SERIAL,TYPE,FSTYPE,LABEL"],text=True))
        disk=next((d for d in info["blockdevices"] if (d.get("serial") or "").replace("-","")==wanted),None)
        if disk:
            # NAME is not requested, so --tree is essential for children.
            # This AMI has a separate ext4 /boot as well as the root partition.
            # Select the explicitly recorded root partition, never any ext4.
            partitions=[]
            for part in disk.get("children",[]):
                if part["path"]!=disk["path"]+"p"+str(config["root_partition"]):
                    continue
                probe=subprocess.run(["blkid","-p","-s","TYPE","-o","value",part["path"]],capture_output=True,text=True)
                if probe.returncode==0 and probe.stdout.strip()=="ext4":
                    partitions.append(part)
            if len(partitions)==1:
                device=partitions[0]["path"]; break
            if len(partitions)>1:
                raise ValueError("Recovery target contains multiple ext4 partitions")
        time.sleep(2)
    if not device:
        print("RECOVERY_DEVICE_DIAGNOSTIC="+json.dumps(info),flush=True)
        raise ValueError("Explicit recovery volume or ext4 partition not ready")
    mount=Path("/mnt/jdu-capture-recovery"); mount.mkdir(exist_ok=True)
    subprocess.run(["mount","-o","ro,noload",device,str(mount)],check=True)
    if 'VERSION_ID="24.04"' not in (mount/"etc/os-release").read_text():
        raise ValueError("Recovery filesystem is not the fixed Ubuntu release")
    print("JDU_RECOVERY_STAGE=READ_ONLY_ROOT_MOUNTED",flush=True)
    archive=mount/"srv/jdu-capture.tar.gz"
    payload=mount/"srv/jdu-capture"
    summary_path=payload/"capture-summary.json"
    diagnostic={"archive_exists":archive.is_file(),"summary_exists":summary_path.is_file(),
                "deb_count":len(list((payload/"apt/pool").glob("*.deb"))),
                "wheel_count":len(list((payload/"artifacts/python/wheelhouse").glob("*.whl")))}
    if summary_path.is_file():
        diagnostic["capture_summary"]=json.loads(summary_path.read_text())
    # Include only the final diagnostic lines, never upload user-data or URL files.
    log=mount/"var/log/jdu-web-collector.log"
    if log.is_file():
        diagnostic["log_tail"]=log.read_text(errors="replace")[-3000:]
    diagnostic_path=root/"diagnostic.json"; diagnostic_path.write_text(json.dumps(diagnostic,indent=2))
    upload(config["diagnostic_put_url"],diagnostic_path,root/"curl-diagnostic.conf")
    print("JDU_RECOVERY_DIAGNOSTIC="+json.dumps({k:v for k,v in diagnostic.items() if k!="log_tail"}),flush=True)
    if not archive.is_file():
        raise ValueError("Capture archive was not created; diagnostic preserved")
    with archive.open("rb") as stream:
        sha=hashlib.file_digest(stream,"sha256").hexdigest()
    upload(config["archive_put_url"],archive,root/"curl-archive.conf")
    print("JDU_RECOVERY_RESULT="+json.dumps({"archive_sha256":sha,"archive_size_bytes":archive.stat().st_size,"uploaded":True}),flush=True)
    subprocess.run(["umount",str(mount)],check=True)


if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        print("JDU_RECOVERY_FAILED="+type(exc).__name__,flush=True)
        if isinstance(exc,ValueError):
            print("RECOVERY_VALIDATION="+str(exc),flush=True)
        raise SystemExit(1)
