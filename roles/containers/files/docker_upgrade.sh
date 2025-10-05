# Previous upgrade was sucesseful, no need to old images
echo 'Pruning old images...'
docker image prune -af

# Save current image hash for rollback
echo -e '\nSaving current images hash id...'
echo >> /home/nas/scripts/docker_pre_upgrade_digest.log
date >> /home/nas/scripts/docker_pre_upgrade_digest.log
docker image list --digests | awk '{print $1 "   " $3}' >> /home/nas/scripts/docker_pre_upgrade_digest.log

# Compute project list using docker compose ls (without jq)
PROJECTS=$(docker compose ls | tail -n +2)

# Pull new images using docker compose v2 and specifying file path
echo -e '\nPulling new images...\n'
while read -r project status compose_path; do
    echo "Pulling images for project $project from $compose_path"
    docker compose -p $project -f $compose_path pull
done <<< "$PROJECTS"

# Create zfs snapshot
echo -e '\nCreating zfs snapshot...'
/usr/sbin/zfs snapshot Storage/System@$(date +%Y_%m_%d)

# Upgrade docker containers using docker compose v2
echo -e '\nUpgrading docker containers...\n'
while read -r project status compose_path; do
    echo "Upgrading containers for project $project from $compose_path"
    docker compose -p $project -f $compose_path up -d
done <<< "$PROJECTS"

# Delete old snapshots
FS="Storage/System"

# List snapshots sorted by creation date (oldest first)
SNAPSHOTS=($(zfs list -t snapshot -o name -s creation | grep "^$FS@"))

# Count snapshots
NUM_SNAPSHOTS=${#SNAPSHOTS[@]}

# Keep only the 4 most recent ones
if [ "$NUM_SNAPSHOTS" -gt 4 ]; then
    TO_DELETE=$((NUM_SNAPSHOTS - 4))
    echo "Deleting $TO_DELETE old snapshots..."
    for ((i=0; i<$TO_DELETE; i++)); do
        echo "Destroying ${SNAPSHOTS[$i]}"
        zfs destroy "${SNAPSHOTS[$i]}"
    done
else
    echo "No snapshots to delete. Keeping all $NUM_SNAPSHOTS snapshots."
fi
