#!/bin/bash
# https://stackoverflow.com/questions/5014632/how-can-i-parse-a-yaml-file-from-a-linux-shell-script
function parse_yaml {
   local prefix=$2
   local s='[[:space:]]*' w='[a-zA-Z0-9_]*' fs=$(echo @|tr @ '\034')
   sed -ne "s|^\($s\):|\1|" \
        -e "s|^\($s\)\($w\)$s:$s[\"']\(.*\)[\"']$s\$|\1$fs\2$fs\3|p" \
        -e "s|^\($s\)\($w\)$s:$s\(.*\)$s\$|\1$fs\2$fs\3|p"  $1 |
   awk -F$fs '{
      indent = length($1)/2;
      vname[indent] = $2;
      for (i in vname) {if (i > indent) {delete vname[i]}}
      if (length($3) > 0) {
         vn=""; for (i=0; i<indent; i++) {vn=(vn)(vname[i])("_")}
         printf("%s%s%s=\"%s\"\n", "'$prefix'",vn, $2, $3);
      }
   }'
}

# Create a unique deployment name
deployment='iot_deployment_'
deployment+=$(date +%s)

echo "Beginning deployment: $deployment"

# Fetch settings from yaml file
eval $(parse_yaml settings.yaml)

# Login to Azure
az login --service-principal -u $user_name -p $password --tenant $tenant

# Set default subscription
az account set --subscription $subscription_id

# Create resource group
az group create --name $rg_name --location $location

# Deploy the ARM template with parameters. You still have to renew authorization to PowerBI from the Azure portal.
az group deployment create --name $deployment --resource-group $rg_name --template-file azureDeployment.json --parameters @deploymentParameters.json

# Add IoT cli extension
az extension add --name azure-cli-iot-ext

# Register simulator and sensor devices in IoT Hub.
az iot hub device-identity update -n $iotHubName -d $simulator_id -g $rg_name
az iot hub device-identity update -n $iotHubName -d $sensor_id -g $rg_name

#Manually update yaml file with connection strings
az iot hub device-identity show-connection-string --hub-name $iotHubName --device-id $simulator_id --output table
az iot hub device-identity show-connection-string --hub-name $iotHubName --device-id $sensor_id --output table
