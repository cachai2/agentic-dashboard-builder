targetScope = 'resourceGroup'

@description('The location of this resource group')
param location string

@description('Environment name used for deriving resource names')
param environmentName string

@description('A suffix to provide resource naming uniqueness')
param resourceToken string


@description('Username for nginx auth proxy basic authentication')
param proxyAuthUser string = 'admin'

@description('Password for nginx auth proxy basic authentication')
@secure()
param proxyAuthPassword string

@description('Flag indicating whether diagnostic logging should be enabled')
param enableDebugging bool = false

@description('Enable VNet integration for the Container Apps Environment')
param enableVnetIntegration bool = false

@description('Enable persistent volume mount for the Ollama GPU service')
param enableOllamaModelVolume bool = true

@description('Optional override for the frontend API base URL; defaults to the deployed agent FQDN when omitted')
param agentApiBaseUrl string = ''

@description('Public URL for the frontend used for CORS allowance')
param frontendPublicUrl string = 'https://frontend-ignite-demo-evdeo.salmondune-d5fce79f.westus.azurecontainerapps.io'

@description('Comma-delimited list of allowed origins for the orchestrator API')
param agentAllowedOrigins string = frontendPublicUrl

var baseName = toLower('${environmentName}-${resourceToken}')
var sanitized = toLower(replace(replace(environmentName, '-', ''), '_', ''))
var sanitizedBase = empty(sanitized) ? 'env' : sanitized
var containerRegistryName = take('acr${sanitizedBase}${resourceToken}00', 50)
var storageAccountName = take('st${sanitizedBase}${resourceToken}000', 24)
var storageAccountSmbName = take('st${sanitizedBase}${resourceToken}100', 24)
var artifactStorageAccountName = take('st${sanitizedBase}${resourceToken}200', 24)
var agentArtifactsContainerName = 'agent-artifacts'
var agentArtifactsShareName = 'agent-artifacts'
var agentArtifactsVolumeName = 'agent-artifacts'
var agentArtifactsMountPath = '/app/agent-service/artifacts'
var identityName = 'id-${baseName}'
var containerAppsEnvironmentName = 'cae-${baseName}'
var ollamaAppName = 'ollama-${baseName}'
var agentAppName = 'agent-${baseName}'
var frontendAppName = 'frontend-${baseName}'
var plannerGatewayAppName = 'planner-${baseName}'
var nginxAuthProxyAppName = 'proxy-${baseName}'
var logAnalyticsWorkspaceName = 'log-${baseName}'
var storagePrivateLinkFqdn = '${storageAccountName}.privatelink.file.${environment().suffixes.storage}'
var seedScriptLines = [
  '#!/bin/bash'
  'set -euo pipefail'
  ''
  format('az account set --subscription {0}', subscription().subscriptionId)
  ''
  'echo "[seed-acr-images] importing agent-agent:latest"'
  format('az acr import --resource-group {0} --name {1} --source mcr.microsoft.com/azuredocs/containerapps-helloworld:latest --image agent-agent:latest --force --only-show-errors --output none', resourceGroup().name, containerRegistryName)
  ''
  'echo "[seed-acr-images] importing ollama:latest"'
  format('az acr import --resource-group {0} --name {1} --source mcr.microsoft.com/azuredocs/containerapps-helloworld:latest --image ollama:latest --force --only-show-errors --output none', resourceGroup().name, containerRegistryName)
  ''
  'echo "[seed-acr-images] importing planner-planner:latest"'
  format('az acr import --resource-group {0} --name {1} --source mcr.microsoft.com/azuredocs/containerapps-helloworld:latest --image planner-planner:latest --force --only-show-errors --output none', resourceGroup().name, containerRegistryName)
  ''
  'echo "[seed-acr-images] importing nginx-auth-proxy:latest"'
  format('az acr import --resource-group {0} --name {1} --source mcr.microsoft.com/azuredocs/containerapps-helloworld:latest --image nginx-auth-proxy:latest --force --only-show-errors --output none', resourceGroup().name, containerRegistryName)
  ''
  'echo "[seed-acr-images] complete"'
]
var seedScript = join(seedScriptLines, '\n')
var artifactStorageConnectionString = 'DefaultEndpointsProtocol=https;AccountName=${artifactStorageAccount.name};AccountKey=${artifactStorageAccount.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'
var logAnalyticsWorkspaceId = resourceId('Microsoft.OperationalInsights/workspaces', logAnalyticsWorkspaceName)
var containerAppsEnvironmentBaseProperties = {
  workloadProfiles: [
    {
      name: 'Consumption'
      workloadProfileType: 'Consumption'
    }
    {
      name: 'GPU'
      workloadProfileType: 'Consumption-GPU-NC8as-T4'
    }
    {
      name: 'GPU-A100'
      workloadProfileType: 'Consumption-GPU-NC24-A100'
    }
  ]
}
var containerAppsEnvironmentProperties = union(containerAppsEnvironmentBaseProperties, enableVnetIntegration ? {
  vnetConfiguration: {
    infrastructureSubnetId: '${virtualNetwork.id}/subnets/aca-subnet'
  }
} : {})
var agentVolumeMounts = enableVnetIntegration ? [
  {
    volumeName: 'agent-local'
    mountPath: '/root/.local'
  }
  {
    volumeName: 'agent-config'
    mountPath: '/root/.config'
  }
  {
    volumeName: 'agent-workspace'
    mountPath: '/workspace'
  }
] : []
var agentVolumes = enableVnetIntegration ? [
  {
    name: 'agent-local'
    storageType: 'NfsAzureFile'
    storageName: agentLocalStorage.name
    mountOptions: 'vers=4.1'
  }
  {
    name: 'agent-config'
    storageType: 'NfsAzureFile'
    storageName: agentConfigStorage.name
    mountOptions: 'vers=4.1'
  }
  {
    name: 'agent-workspace'
    storageType: 'NfsAzureFile'
    storageName: agentWorkspaceStorage.name
    mountOptions: 'vers=4.1'
  }
] : []

resource virtualNetwork 'Microsoft.Network/virtualNetworks@2023-06-01' = {
  name: 'vnet-${baseName}'
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        '10.0.0.0/16'
      ]
    }
    subnets: [
      {
        name: 'aca-subnet'
        properties: {
          addressPrefix: '10.0.0.0/23'
          delegations: [
            {
              name: 'aca-delegation'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }
      }
      {
        name: 'pe-subnet'
        properties: {
          addressPrefix: '10.0.2.0/24'
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
    ]
  }
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: containerRegistryName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    zoneRedundancy: 'Disabled'
  }
}
resource userAssignedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2018-11-30' = {
  name: identityName
  location: location
}



resource seedImages 'Microsoft.Resources/deploymentScripts@2020-10-01' = {
  name: 'seed-acr-images'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${userAssignedIdentity.id}': {}
    }
  }
  kind: 'AzureCLI'
  properties: {
    azCliVersion: '2.61.0'
    retentionInterval: 'P1D'
    timeout: 'PT30M'
    cleanupPreference: 'OnSuccess'
    scriptContent: seedScript
  }
  dependsOn: [
    containerRegistry
    acrPushAssignment
    acrReaderAssignment
    acrContributorAssignment
  ]
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Premium_LRS'
  }
  kind: 'FileStorage'
  properties: {
    publicNetworkAccess: 'Disabled'
    supportsHttpsTrafficOnly: false
    allowSharedKeyAccess: true
    allowBlobPublicAccess: false
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'None'
    }
  }
}

resource storageAccountSmb 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountSmbName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    publicNetworkAccess: 'Enabled'
    supportsHttpsTrafficOnly: false
    allowSharedKeyAccess: true
    allowBlobPublicAccess: false
  }
}

resource artifactStorageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: artifactStorageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    publicNetworkAccess: 'Enabled'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
  }
}

resource artifactBlobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: artifactStorageAccount
  name: 'default'
}

resource artifactContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: artifactBlobService
  name: agentArtifactsContainerName
  properties: {
    publicAccess: 'None'
  }
}

resource artifactFileService 'Microsoft.Storage/storageAccounts/fileServices@2023-01-01' = {
  parent: artifactStorageAccount
  name: 'default'
}

resource agentArtifactsShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-01-01' = {
  parent: artifactFileService
  name: agentArtifactsShareName
  properties: {
    enabledProtocols: 'SMB'
    shareQuota: 100
  }
}

resource fileService 'Microsoft.Storage/storageAccounts/fileServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
}

resource fileServiceSmb 'Microsoft.Storage/storageAccounts/fileServices@2023-01-01' = {
  parent: storageAccountSmb
  name: 'default'
}

resource agentLocalShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-01-01' = {
  parent: fileService
  name: 'agent-local'
  properties: {
    enabledProtocols: 'NFS'
    shareQuota: 100 
    rootSquash: 'NoRootSquash'
  }
}

resource agentConfigShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-01-01' = {
  parent: fileService
  name: 'agent-config'
  properties: {
    enabledProtocols: 'NFS'
    shareQuota: 100
    rootSquash: 'NoRootSquash'
  }
}

resource agentWorkspaceShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-01-01' = {
  parent: fileService
  name: 'agent-workspace'
  properties: {
    enabledProtocols: 'NFS'
    shareQuota: 100
    rootSquash: 'NoRootSquash'
  }
}


resource ollamaModelShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-01-01' = {
  parent: fileService
  name: 'ollama-model'
  properties: {
    enabledProtocols: 'NFS'
    shareQuota: 1024
    rootSquash: 'NoRootSquash'
  }
}

resource ollamaModelSmbShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-01-01' = {
  parent: fileServiceSmb
  name: 'ollama-model-smb'
  properties: {
    enabledProtocols: 'SMB'
    shareQuota: 1024
  }
}

resource storagePrivateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.file.${environment().suffixes.storage}'
  location: 'global'
}

resource storagePrivateDnsZoneLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: storagePrivateDnsZone
  name: '${virtualNetwork.name}-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: virtualNetwork.id
    }
  }
}

resource storagePrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-06-01' = {
  name: '${storageAccount.name}-pe'
  location: location
  properties: {
    subnet: {
      id: '${virtualNetwork.id}/subnets/pe-subnet'
    }
    privateLinkServiceConnections: [
      {
        name: '${storageAccount.name}-connection'
        properties: {
          privateLinkServiceId: storageAccount.id
          groupIds: [
            'file'
          ]
        }
      }
    ]
  }
}

resource storagePrivateEndpointDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-06-01' = {
  parent: storagePrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'file'
        properties: {
          privateDnsZoneId: storagePrivateDnsZone.id
        }
      }
    ]
  }
}

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' = if (enableDebugging) {
  name: logAnalyticsWorkspaceName
  location: location
  properties: {
    retentionInDays: 30
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerAppsEnvironmentName
  location: location
  properties: union(containerAppsEnvironmentProperties, enableDebugging ? {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: reference(logAnalyticsWorkspaceId, '2022-10-01').customerId
        sharedKey: listKeys(logAnalyticsWorkspaceId, '2020-08-01').primarySharedKey
      }
    }
  } : {})
}


resource agentLocalStorage 'Microsoft.App/managedEnvironments/storages@2025-02-02-preview' = if (enableVnetIntegration) {
  parent: containerAppsEnvironment
  name: 'agent-local-storage'
  properties: {
    nfsAzureFile: {
      server: storagePrivateLinkFqdn
      shareName: '/${storageAccount.name}/${agentLocalShare.name}'
      accessMode: 'ReadWrite'
    }
  }
}

resource agentConfigStorage 'Microsoft.App/managedEnvironments/storages@2025-02-02-preview' = if (enableVnetIntegration) {
  parent: containerAppsEnvironment
  name: 'agent-config-storage'
  properties: {
    nfsAzureFile: {
      server: storagePrivateLinkFqdn
      shareName: '/${storageAccount.name}/${agentConfigShare.name}'
      accessMode: 'ReadWrite'
    }
  }
}

resource agentWorkspaceStorage 'Microsoft.App/managedEnvironments/storages@2025-02-02-preview' = if (enableVnetIntegration) {
  parent: containerAppsEnvironment
  name: 'agent-workspace-storage'
  properties: {
    nfsAzureFile: {
      server: storagePrivateLinkFqdn
      shareName: '/${storageAccount.name}/${agentWorkspaceShare.name}'
      accessMode: 'ReadWrite'
    }
  }
}

resource ollamaModelStorage 'Microsoft.App/managedEnvironments/storages@2025-02-02-preview' = if (enableVnetIntegration) {
  parent: containerAppsEnvironment
  name: 'ollama-model-storage'
  properties: {
    nfsAzureFile: {
      server: storagePrivateLinkFqdn
      shareName: '/${storageAccount.name}/${ollamaModelShare.name}'
      accessMode: 'ReadWrite'
    }
  }
}

resource ollamaModelSmbStorage 'Microsoft.App/managedEnvironments/storages@2025-02-02-preview' = {
  parent: containerAppsEnvironment
  name: 'ollama-model-storage-smb-public'
  properties: {
    azureFile: {
      accountName: storageAccountSmb.name
      accountKey: listKeys(storageAccountSmb.id, '2022-09-01').keys[0].value
      shareName: ollamaModelSmbShare.name
      accessMode: 'ReadWrite'
    }
  }
}

resource agentArtifactsStorage 'Microsoft.App/managedEnvironments/storages@2025-02-02-preview' = {
  parent: containerAppsEnvironment
  name: 'agent-artifacts-storage'
  properties: {
    azureFile: {
      accountName: artifactStorageAccount.name
      accountKey: listKeys(artifactStorageAccount.id, '2022-09-01').keys[0].value
      shareName: agentArtifactsShare.name
      accessMode: 'ReadWrite'
    }
  }
}

resource acrPullAssignment 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  scope: containerRegistry
  name: guid(containerRegistry.id, userAssignedIdentity.name, 'AcrPull')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: userAssignedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource acrPushAssignment 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  scope: containerRegistry
  name: guid(containerRegistry.id, userAssignedIdentity.name, 'AcrPush')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8311e382-0749-4cb8-b61a-304f252e45ec')
    principalId: userAssignedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource acrReaderAssignment 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  scope: containerRegistry
  name: guid(containerRegistry.id, userAssignedIdentity.name, 'Reader')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'acdd72a7-3385-48ef-bd42-f606fba81ae7')
    principalId: userAssignedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource acrContributorAssignment 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  scope: containerRegistry
  name: guid(containerRegistry.id, userAssignedIdentity.name, 'Contributor')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c')
    principalId: userAssignedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource artifactStorageBlobDataContributor 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  scope: artifactStorageAccount
  name: guid(artifactStorageAccount.id, userAssignedIdentity.name, 'StorageBlobDataContributor')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: userAssignedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Deploy ollama app as a separate module
module ollamaModule './ollama.bicep' = {
  name: 'ollama-deployment'
  params: {
    environmentName: containerAppsEnvironment.name
    ollamaAppName: ollamaAppName
    userAssignedIdentityId: userAssignedIdentity.id
    containerAppsEnvironmentId: containerAppsEnvironment.id
    containerRegistryEndpoint: containerRegistry.properties.loginServer
    ollamaModelStorageName: ollamaModelSmbStorage.name
    enableStorageMount: enableOllamaModelVolume
  }
}

resource agentApp 'Microsoft.App/containerApps@2025-02-02-preview' = {
  name: agentAppName
  location: location
  tags: {'azd-service-name': 'agent'}
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${userAssignedIdentity.id}': {}
    }
  }
  dependsOn: [
    seedImages
  ]
  properties: {
    environmentId: containerAppsEnvironment.id
    workloadProfileName: 'Consumption'
    configuration: {
      ingress: {
        external: true
        targetPort: 8080
        transport: 'Auto'
        allowInsecure: true
      }
      secrets: [
        {
          name: 'artifact-storage-connection-string'
          value: artifactStorageConnectionString
        }
      ]
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: userAssignedIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'agent'
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          env: [
            {
              name: 'OLLAMA_HOST'
              value: format('https://{0}', ollamaModule.outputs.OLLAMA_HOST)
            }
            {
              name: 'ORCH_PLANNER_GATEWAY_HOST'
              value: format('https://{0}', plannerGatewayApp.properties.configuration.ingress.fqdn)
            }
            {
              name: 'ORCH_ALLOWED_ORIGINS'
              value: agentAllowedOrigins
            }
            {
              name: 'AZURE_STORAGE_CONNECTION_STRING'
              secretRef: 'artifact-storage-connection-string'
            }
            {
              name: 'AGENT_STORAGE_ACCOUNT_NAME'
              value: artifactStorageAccount.name
            }
            {
              name: 'AGENT_STORAGE_CONTAINER_NAME'
              value: agentArtifactsContainerName
            }
            {
              name: 'GITHUB_PERSONAL_ACCESS_TOKEN'
              value: 'NA'
            }
            {
              name: 'MCP_EMAIL_SERVER_EMAIL_ADDRESS'
              value: 'NA'
            }
            {
              name: 'MCP_EMAIL_SERVER_USER_NAME'
              value: 'NA'
            }
            {
              name: 'MCP_EMAIL_SERVER_PASSWORD'
              value: 'NA'
            }
            {
              name: 'MCP_EMAIL_SERVER_FULL_NAME'
              value: 'NA'
            }
          ]
          resources: {
            cpu: 2
            memory: '4Gi'
          }
          volumeMounts: concat(
            agentVolumeMounts,
            [
              {
                volumeName: agentArtifactsVolumeName
                mountPath: agentArtifactsMountPath
              }
            ]
          )
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
      volumes: concat(
        agentVolumes,
        [
          {
            name: agentArtifactsVolumeName
            storageType: 'AzureFile'
            storageName: agentArtifactsStorage.name
          }
        ]
      )
    }
  }
}

resource plannerGatewayApp 'Microsoft.App/containerApps@2025-02-02-preview' = {
  name: plannerGatewayAppName
  location: location
  tags: {'azd-service-name': 'planner'}
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${userAssignedIdentity.id}': {}
    }
  }
  dependsOn: [
    seedImages
  ]
  properties: {
    environmentId: containerAppsEnvironment.id
    workloadProfileName: 'Consumption'
    configuration: {
      ingress: {
        external: true
        targetPort: 8080
        transport: 'Auto'
        allowInsecure: true
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: userAssignedIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'planner'
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          env: [
            {
              name: 'OLLAMA_HOST'
              value: format('https://{0}', ollamaModule.outputs.OLLAMA_HOST)
            }
            {
              name: 'OLLAMA_MODE'
              value: 'remote'
            }
            {
              name: 'OLLAMA_API_PATH'
              value: '/api/chat'
            }
            {
              name: 'PLAN_SCHEMA_PATH'
              value: '/app/schemas/dashboard_plan.schema.json'
            }
            {
              name: 'PORT'
              value: '8080'
            }
          ]
          resources: {
            cpu: 2
            memory: '4Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

resource frontendApp 'Microsoft.App/containerApps@2025-02-02-preview' = {
  name: frontendAppName
  location: location
  tags: {'azd-service-name': 'frontend'}
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${userAssignedIdentity.id}': {}
    }
  }
  dependsOn: [
    seedImages
  ]
  properties: {
    environmentId: containerAppsEnvironment.id
    workloadProfileName: 'Consumption'
    configuration: {
      ingress: {
        external: true
        targetPort: 80
        transport: 'Auto'
        allowInsecure: false
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: userAssignedIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'frontend'
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          env: [
            {
              name: 'VITE_API_BASE_URL'
              value: empty(agentApiBaseUrl) ? format('https://{0}', agentApp.properties.configuration.ingress.fqdn) : agentApiBaseUrl
            }
            {
              name: 'VITE_USE_MOCK'
              value: 'false'
            }
          ]
          resources: {
            cpu: 1
            memory: '2Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}


resource nginxAuthProxyApp 'Microsoft.App/containerApps@2025-02-02-preview' = {
  name: nginxAuthProxyAppName
  location: location
  tags: {'azd-service-name': 'nginx-auth-proxy'}
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${userAssignedIdentity.id}': {}
    }
  }
  dependsOn: [
    seedImages
  ]
  properties: {
    environmentId: containerAppsEnvironment.id
    workloadProfileName: 'Consumption'
    configuration: {
      ingress: {
        external: true
        targetPort: 80
        transport: 'Auto'
        allowInsecure: false
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: userAssignedIdentity.id
        }
      ]
      secrets: [
        {
          name: 'basic-auth-password'
          value: proxyAuthPassword
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'nginx-auth-proxy'
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          env: [
            {
              name: 'BACKEND_URL'
              value: format('{0}', agentApp.properties.configuration.ingress.fqdn)
            }
            {
              name: 'BASIC_AUTH_USER'
              value: proxyAuthUser
            }
            {
              name: 'BASIC_AUTH_PASSWORD'
              secretRef: 'basic-auth-password'
            }
            {
              name: 'BACKEND_TIMEOUT'
              value: '600'
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}


output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.properties.loginServer
output AZURE_CONTAINER_REGISTRY_NAME string = containerRegistry.name
output AZURE_CONTAINER_APPS_ENVIRONMENT_ID string = containerAppsEnvironment.id
output AZURE_CONTAINER_APPS_ENVIRONMENT_NAME string = containerAppsEnvironment.name
output ACA_ENVIRONMENT_IDENTITY_ID string = userAssignedIdentity.id
output agent_APP_NAME string = agentApp.name
output FRONTEND_APP_NAME string = frontendApp.name
output OLLAMA_APP_NAME string = ollamaAppName
output PLANNER_APP_NAME string = plannerGatewayApp.name
output PLANNER_GATEWAY_FQDN string = plannerGatewayApp.properties.configuration.ingress.fqdn
output NGINX_AUTH_PROXY_APP_NAME string = nginxAuthProxyApp.name
output LOG_ANALYTICS_WORKSPACE_ID string = enableDebugging ? logAnalyticsWorkspace.id : ''
output LOCATION string = location
output USER_ASSIGNED_IDENTITY object = userAssignedIdentity
output CONTAINER_REGISTRY object = containerRegistry
output CONTAINER_APPS_ENVIRONMENT object = containerAppsEnvironment
output OLLAMA_MODEL_STORAGE object = enableVnetIntegration ? ollamaModelStorage : {}
output OLLAMA_MODEL_STORAGE_NAME string = ollamaModelSmbStorage.name
output SEED_IMAGES object = seedImages
output AGENT_STORAGE_ACCOUNT_NAME string = artifactStorageAccount.name
output AGENT_STORAGE_CONTAINER_NAME string = agentArtifactsContainerName
