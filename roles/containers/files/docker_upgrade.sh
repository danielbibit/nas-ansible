# Previous upgrade was sucesseful, no need to old images
echo 'Pruning old images...'
docker image prune -af

echo
echo 'Saving current images hash id...'
# Save current image hash for rollback
echo >> /home/nas/scripts/docker_pre_upgrade_digest.log
date >> /home/nas/scripts/docker_pre_upgrade_digest.log
docker image list --digests | awk '{print $1 "   " $3}' >> /home/nas/scripts/docker_pre_upgrade_digest.log


echo
echo 'Pulling new images...'
echo
# Pull new images
for file in $(ls -1 /home/nas/compose | grep yml);
do
    docker-compose -f /home/nas/compose/${file} pull;
done


echo
echo 'Creating zfs snapshot...'
# Create zfs snapshot
/usr/sbin/zfs snapshot Users/docker@$(date +%Y_%m_%d)


echo
echo 'Upgrading docker containers...'
echo
# Upgrade images
for file in $(ls -1 /home/nas/compose | grep yml);
do
    docker-compose --project-name ${file} -f /home/nas/compose/${file} up -d;
done


#TODO delete old snapshots
# https://serverfault.com/questions/340837/how-to-delete-all-but-last-n-zfs-snapshots
