# ZFS Manual
## Create pool
```sh
sudo zpool create Storage mirror /dev/sdx /dev/sdy
```

## Import zfs
```sh
zpool import -a
zpool import -f Users
```

## Create filesystem
```sh
sudo zfs create Storage/foo/bar
```

```sh
sudo zfs set compression=? Storage/foo/bar
sudo zfs set quota=XXG Storage/foo/bar
```

## ARC
```sh
arc_summary
```
