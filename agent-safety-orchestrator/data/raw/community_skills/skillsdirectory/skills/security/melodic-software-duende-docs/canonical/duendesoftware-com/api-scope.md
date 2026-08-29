---
title: API Scope
source_url: https://docs.duendesoftware.com/api-scope/
source_type: llms-full-txt
content_hash: sha256:d35a2613b34298b2702a92a08536926d9027623e3fd36d9c13b41e94071d398a
doc_id: api-scope
---

> Reference documentation for the ApiScope class which models an OAuth scope in Duende IdentityServer, including its properties and configuration options.

## Duende.IdentityServer.Models.ApiScope

[Section titled âDuende.IdentityServer.Models.ApiScopeâ](#duendeidentityservermodelsapiscope)

This class models an OAuth scope.

* **`Enabled`**

  Indicates if this resource is enabled and can be requested. Defaults to true.

* **`Name`**

  The unique name of the API. This value is used for authentication with introspection and will be added to the audience of the outgoing access token.

* **`DisplayName`**

  This value can be used e.g. on the consent screen.

* **`Description`**

  This value can be used e.g. on the consent screen.

* **`UserClaims`**

  List of associated user claim types that should be included in the access token.

## Defining API Scope In appsettings.json

[Section titled âDefining API Scope In appsettings.jsonâ](#defining-api-scope-in-appsettingsjson)

The `AddInMemoryApiResource` extension method also supports adding clients from the ASP.NET Core configuration file:

```json
{
  "IdentityServer": {
    "IssuerUri": "urn:sso.company.com",
    "ApiScopes": [
      {
        "Name": "IdentityServerApi"
      },
      {
        "Name": "resource1.scope1"
      },
      {
        "Name": "resource2.scope1"
      },
      {
        "Name": "scope3"
      },
      {
        "Name": "shared.scope"
      },
      {
        "Name": "transaction",
        "DisplayName": "Transaction",
        "Description": "A transaction"
      }
    ]
  }
}
```

Then pass the configuration section to the `AddInMemoryApiScopes` method:

Program.cs

```csharp
idsvrBuilder.AddInMemoryApiScopes(configuration.GetSection("IdentityServer:ApiScopes"))
```
