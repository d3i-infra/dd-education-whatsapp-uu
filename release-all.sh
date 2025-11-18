#!/bin/bash

# build release all individual platforms

script_location='./src/framework/processing/py/port/script.py'
single_platform='flows = \[ '
single_platform_commented_out='#flows = \[ '

platforms=("whatsapp_chat_flow" "whatsapp_account_info_flow" )

for platform in "${platforms[@]}"; do
    sed -i "s/$single_platform_commented_out$platform/$single_platform$platform/g" $script_location
    npm run build && ./release.sh $platform
    git restore $script_location
done
