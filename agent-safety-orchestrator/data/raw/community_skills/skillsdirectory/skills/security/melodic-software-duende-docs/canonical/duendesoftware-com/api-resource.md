---
title: API Resource
source_url: https://docs.duendesoftware.com/api-resource/
source_type: llms-full-txt
content_hash: sha256:6a080c146ef3fea7276a2b9d8ec7f0e6cb140fcd7e46e1abea8a8bf2ffb04f06
doc_id: api-resource
---

> Reference documentation for the ApiResource class which models an API in Duende IdentityServer, including its properties and configuration options.

## Duende.IdentityServer.Models.ApiResource

[Section titled âDuende.IdentityServer.Models.ApiResourceâ](#duendeidentityservermodelsapiresource)

This class models an API.

* **`Enabled`**

  Indicates if this resource is enabled and can be requested. Defaults to true.

* **`Name`**

  The unique name of the API. This value is used for authentication with introspection and will be added to the audience of the outgoing access token.

* **`DisplayName`**

  This value can be used e.g. on the consent screen.

* **`Description`**

  This value can be used e.g. on the consent screen.

* **`RequireResourceIndicator`**

  Indicates if this API resource requires the resource indicator to request it, and expects access tokens issued to it will only ever contain this API resource as the audience.

* **`ApiSecrets`**

  The API secret is used for the introspection endpoint. The API can authenticate with introspection using the API name and secret.

* **`AllowedAccessTokenSigningAlgorithms`**

  List of allowed signing algorithms for access token. If empty, will use the server default signing algorithm.

* **`UserClaims`**

  List of associated user claim types that should be included in the access token.

* **`Scopes`**

  List of API scope names. You need to create those using [ApiScope](/identityserver/reference/models/api-scope/).

## Defining API resources In appsettings.json

[Section titled âDefining API resources In appsettings.jsonâ](#defining-api-resources-in-appsettingsjson)

The `AddInMemoryApiResource` extensions method also supports adding API resources from the ASP.NET Core configuration file:

```plaintext
"IdentityServer": {
    "IssuerUri": "urn:sso.company.com",
    "ApiResources": [
        {
            "Name": "resource1",
            "DisplayName": "Resource #1",


            "Scopes": [
                "resource1.scope1",
                "shared.scope"
            ]
        },
        {
            "Name": "resource2",
            "DisplayName": "Resource #2",


            "UserClaims": [
                "name",
                "email"
            ],


            "Scopes": [
                "resource2.scope1",
                "shared.scope"
            ]
        }
    ]
}
```

Then pass the configuration section to the `AddInMemoryApiResource` method:

Program.cs

```csharp
idsvrBuilder.AddInMemoryApiResources(configuration.GetSection("IdentityServer:ApiResources"))
```
