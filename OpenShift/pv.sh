#!/bin/bash

SERVER=`hostname`
COUNT=70

sudo mkdir -p /exports
sudo chmod 777 /exports
sudo chown nfsnobody:nfsnobody /exports
oc project default

for i in $(seq 1 $COUNT); do
    PV=$(cat <<EOF
apiVersion: v1
kind: PersistentVolume
metadata:
  name: pv$(printf %04d $i)
spec:
  capacity:
    storage: 5Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Recycle
  nfs:
    server: $SERVER
    path: /exports/pv$(printf %04d $i)
EOF
)
    echo "$PV" | oc create -f -
    sudo mkdir -p /exports/pv$(printf %04d $i)
    sudo chown nfsnobody:nfsnobody /exports/pv$(printf %04d $i)
done
