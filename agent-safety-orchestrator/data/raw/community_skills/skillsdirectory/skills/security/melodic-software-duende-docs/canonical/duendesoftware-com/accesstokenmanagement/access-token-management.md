---
title: Access Token Management
source_url: https://docs.duendesoftware.com/accesstokenmanagement/access-token-management/
source_type: llms-full-txt
content_hash: sha256:0db63ee6392c83114b4d5b0af34cf3002ee6657450eb6bd956d30e910fe5f30d
last_fetched: '2025-12-16T19:17:17Z'
category: accesstokenmanagement
doc_id: accesstokenmanagement/access-token-management
---

> The Duende.AccessTokenManagement library provides automatic access token management features for .NET applications

The `Duende.AccessTokenManagement` library provides automatic access token management features for .NET worker and ASP.NET Core web applications:

* Automatic acquisition and lifetime management of client credentials based access tokens for machine-to-machine communication (using the `Duende.AccessTokenManagement` package)
* Automatic access token lifetime management using a refresh token for API calls on behalf of the currently logged-in user (using the `Duende.AccessTokenManagement.OpenIdConnect` package)
* Revocation of access tokens

## Machine-To-Machine Token Management

[Section titled âMachine-To-Machine Token Managementâ](#machine-to-machine-token-management)

To get started, install the NuGet Package:

```bash
dotnet add package Duende.AccessTokenManagement
```

See [Service Workers and Background Tasks](/accesstokenmanagement/workers/) for more information on how to get started.

[GitHub Repository ](https://github.com/DuendeSoftware/foss/tree/main/access-token-management)View the source code for this library on GitHub.

[NuGet Package ](https://www.nuget.org/packages/Duende.AccessTokenManagement/)View the package on NuGet.org.

## User Token Management

[Section titled âUser Token Managementâ](#user-token-management)

To get started, install the NuGet Package:

```bash
dotnet add package Duende.AccessTokenManagement.OpenIdConnect
```

See [Web Applications](/accesstokenmanagement/web-apps/) for more information on how to get started.

[GitHub Repository ](https://github.com/DuendeSoftware/foss/tree/main/access-token-management)View the source code for this library on GitHub.

[NuGet Package ](https://www.nuget.org/packages/Duende.AccessTokenManagement.OpenIdConnect/)View the package on NuGet.org.

## License And Feedback

[Section titled âLicense And Feedbackâ](#license-and-feedback)

**Duende.AccessTokenManagement** is released as open source under the Apache 2.0 license. Bug reports, feature requests and contributions are welcome via the [Duende community discussions](https://duende.link/community).
