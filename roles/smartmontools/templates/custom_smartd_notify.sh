#! /bin/bash

# Create a file to store the message in. Give it a unique filename to avoid issues if this script runs twice simultaneously
msgFile="/root/$(uuidgen).txt"

# Clear file, set subject line and formatting
echo "Subject: $SMARTD_SUBJECT" > $msgFile
echo "Content-Type: text/html" >> $msgFile
echo "<html>" >> $msgFile
echo "<style type=\"text/css\">pre { font-family:monospace }</style>" >> $msgFile
echo "<body>" >> $msgFile
echo "<pre>" >> $msgFile

# Save the email message from STDIN:
cat >> $msgFile

# Append the output of zpool status:
/usr/sbin/zpool status >> $msgFile

# Append the output of smartctl -a to the message:
/usr/sbin/smartctl -a "$SMARTD_DEVICE" >> $msgFile

# Close HTML tags
echo "</pre></body></html>" >> $msgFile

# Now email the message to the user at address ADD:
/bin/msmtp "$SMARTD_ADDRESS" < $msgFile
