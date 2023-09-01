# Daniel's NAS
## About
NAS (Network Attached Storage) is a type of server that primarily serves the purpose
of serving files on the network, but in the context of home users usually has many more features.

In this context, for the last 5 years I have managed my own home server,
having a linux machine on 24/7 is really useful, not only I can share all my files across my devices,
I have Virtual machines running automation stuff and work related environments.
On top of all that, you can have a really nice media center,
having your movies, music, shows and photos being served on the network is really cool.

This project has had many prior iterations, starting with OpenMediaVault, a Linux distro specifically
tailored to NAS, to the final decision of me managing my own linux install.

This current iteration uses ansible to manage the server,
serving as a tool to deploy changes and save the server definitions as code.
Although this project is tailored made for my need, I believe it can be very useful as a boilerplate
to implement a similar server, you can check the pre requisites section to get started.


## Features
### Server setup
* Users and group creation (Ansible)
* VM management (Ansible)*
* Software management (Ansible)
* SAMBA setup (Ansible)
* Auto container upgrades (Shell Script)

### Network setup
* DDNS Cloudflare Auto Update
* Reverse Proxy NGINX

### Media and Downloads
* Jdownloader - Generic download client
* qBittorrent - Torrent client
* Jackett - Torrent source aggregator
* Sonarr - TV Shows automatic download
* Radarr - Movies automatic download
* Bazarr - Subtitle management
* Plex - Media server

### Backups
* Cloud backup
* Local services backup

### Monitoring and reports
* Smartmon disk monitoring with daily tests and monthly email report
* ZFS monitoring
* Prometheus
* Loki
* Grafana dashboard with alerts
* Glances

## Pre requisites
### OS setup - Ubuntu
This project run against a physical machine running the latest Ubuntu LTS version.
Make sure you have a clean install, and have SSH access on your local network.

### Filesystem setup - ZFS
ZFS features are used on some tasks, it will be pretty difficult to use another filesystem.
This project *DO NOT* setup nor manage it, you should take your time to setup it properly,
before attempting to use this project.

I have setup two separate pools: **Users**, where are stored transitional files and
data files for the docker containers. And **Storage**, a 14TB pool to store all the rest.

### Email
You will need a SMP service that allow using plain text password for authentication,
I recommend using AWS SES.

### Network
* Setup your server with a static IP locally, you'll avoid a bunch of headaches.
* This projects comes with a reverse proxy and DDNS updates, but **BE CAREFUL**,
it's not a good idea to expose services that you don't need online, if you want
to access the whole server online, I strongly recommend setting up a VPN (Wireguard, OpenVPN).

### Hardware

## Configuration
Make a copy of the example files, rename it and fill with your desired config
```sh
cp example.secrets.yml secrets.yml
```

## Running
### Setting up
The recommended way to run this project is using VSCode Dev Container feature,
this way you can edit your files and don't have to worry about setting up ansible.

1. Clone or Fork this repository
2. Open project with VSCode
3. Open in Container

If you don't want to use VSCode, you can build the container yourself,
or setup the project manually using Poetry.

### Running ansible
```sh
ansible-playbook server_setup.yml -i inventory.yml --diff --ask-pass --ask-become-pass --check
ansible-playbook server_setup.yml -i inventory.yml --diff --check
```

To run a tag:
```sh
ansible-playbook server_setup.yml -i inventory.yml --diff --tags docker --check
```

## TODO
* Setup local backup
* Setup cloud backup
* Implement grafana alerts

## Encryption
```sh
ansible-vault encrypt secrets.yml
ansible-vault decrypt secrets.yml
```
