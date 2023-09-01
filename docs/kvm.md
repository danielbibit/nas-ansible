https://ostechnix.com/export-import-kvm-virtual-machines-linux/

# KVM Manual

## Create VM (HA Example)
```sh
sudo apt install qemu-kvm libvirt-daemon-system libvirt-clients bridge-utils ovmf virtinst
```
```sh
adduser nas libvirt
adduser nas kvm
```

```sh
mkdir /srv/Users/vms/hassos
cd /srv/Users/vms/hassos
```

```sh
wget https://github.com/home-assistant/operating-system/releases/download/6.1/haos_ova-6.1.qcow2.xz
unxz *.qcow.xz
mv haos_ova-6.1.qcow2 hassos.qcow2
```

```sh
virsh pool-create-as --name hassos --type dir --target /srv/Users/vms/hassos
```

create bridge adpter using netplan called br0

```sh
virt-install --import --name hassos \
--memory 2048 --vcpus 2 --cpu host \
--disk hassos.qcow2,format=qcow2,bus=virtio \
--network bridge=br0,model=virtio \
--graphics none \
--noautoconsole \
--boot uefi
```

find the mac adress on the router, and change static lease.

## Export VM

## Import VM

## Attach device
