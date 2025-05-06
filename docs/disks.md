# Disk managment Manual

## Disk replacement procedure
1. Remove the faulted disk from the NAS. (Look up the disk_map.md for the physical location)
2. Insert the new disk into the NAS. Update the disk_map.md with the new disk.
3. Check if the disk qualifies for warranty.
4. Boot up and find the new disk (See 'List disks' section below)
5. Run conveyance, short and long tests on the new disk. (See 'Test hard drive' section below)
6. Replace the disk in the ZFS pool. (See 'Replace disk' section below)
7. Update the disk on the smartd.conf file for continuing monitoring.

## List disks
```sh
lsblk
fdisk -l
ls /dev/disk/by-label
```

## hdparm
<!-- http://howtoeverything.net/linux/hardware/why-some-hard-disks-wont-spin-down-hdparm -->
Power modes: ACTIVE, IDLE, standby
### Verify Write cache
```sh
hdparm -W /dev/sd[a-z]
```
### Check current power status
```sh
hdparm -C /dev/sd[a-z]
```
```sh
# Set time
hdparm -S 255 /dev/sd[a-z]
# Set power mode (not supported ????)
# hdparm -B 127 /dev/sd[a-z]
```
## Clean old fs
```sh
sudo wipefs -a /dev/sdx1
```

## Partition hdd
```sh
lsblk -f
parted /dev/sdX
	mklabel gpt
	mkpart primary 0% 100%
	print
mkfs.ext4 /dev/sdX1
```
## Create new label
```sh
blkid
lsblk
sudo e2label /dev/sdX1 "DataY"
```

## Test hard drive
https://www.thomas-krenn.com/en/wiki/SMART_tests_with_smartctl

### Verify time:
```sh
sudo smartctl -c /dev/sdX
```
### Manually run tests:
```sh
sudo smartctl -t <short|long|conveyance|select> /dev/sdX
```

### Verify progress:
```sh
sudo smartctl -a /dev/sdX
```



# ZFS
## Add new vdev
```sh
sudo zpool add Storage mirror /dev/disk/by-id/disk1 /dev/disk/by-id/disk2
```
## Replace disk
```sh
sudo zpool replace Storage /dev/disk/by-id/disco_bosta /dev/disk/by-id/disco_top
```
