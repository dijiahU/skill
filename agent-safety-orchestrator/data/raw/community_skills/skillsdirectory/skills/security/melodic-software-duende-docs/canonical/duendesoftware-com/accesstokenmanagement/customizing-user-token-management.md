---
title: Customizing User Token Management
source_url: https://docs.duendesoftware.com/accesstokenmanagement/customizing-user-token-management/
source_type: llms-full-txt
content_hash: sha256:970d65345f8910b51ccdc509f8ca22f104e0f010b6d101080bde7903ad40c673
last_fetched: '2025-12-16T19:17:17Z'
category: accesstokenmanagement
doc_id: accesstokenmanagement/customizing-user-token-management
---

> Learn how to customize user token management options, per-request parameters, and token storage mechanisms in ASP.NET Core applications.

The most common way to use [access token management is for interactive web applications](/accesstokenmanagement/web-apps/) - however, you may want to customize certain aspects of it. Hereâs what you can do.

## General Options

[Section titled âGeneral Optionsâ](#general-options)

You can pass in some global options when registering token management in the ASP.NET Core service provider.

* `ChallengeScheme` - by default the OIDC configuration is inferred from the default challenge scheme. This is recommended approach. If for some reason your OIDC handler is not the default challenge scheme, you can set the scheme name on the options
* `UseChallengeSchemeScopedTokens` - the general assumption is that you only have one OIDC handler configured. If that is not the case, token management needs to maintain multiple sets of token artefacts simultaneously. You can opt in to that feature using this setting.
* `ClientCredentialsScope` - when requesting client credentials tokens from the OIDC provider, the scope parameter will not be set since its value cannot be inferred from the OIDC configuration. With this setting you can set the value of the scope parameter.
* `ClientCredentialsResource` - same as previous, but for the resource parameter
* `ClientCredentialStyle` - specifies how client credentials are transmitted to the OIDC provider

Program.cs

```csharp
builder.Services.AddOpenIdConnectAccessTokenManagement(options =>
{
    options.ChallengeScheme = "schemeName";
    options.UseChallengeSchemeScopedTokens = false;


    options.ClientCredentialsScope = "api1 api2";
    options.ClientCredentialsResource = "urn:resource";
    options.ClientCredentialStyle = ClientCredentialStyle.PostBody;
});
```

## Per Request Parameters

[Section titled âPer Request Parametersâ](#per-request-parameters)

You can also modify token management parameters on a per-request basis.

The `UserTokenRequestParameters` class can be used for that:

* `SignInScheme` - allows specifying a sign-in scheme. This is used by the default token store
* `ChallengeScheme` - allows specifying a challenge scheme. This is used to infer token service configuration
* `ForceRenewal` - forces token retrieval even if a cached token would be available
* `Scope` - overrides the globally configured scope parameter
* `Resource` - override the globally configured resource parameter
* `Assertion` - allows setting a client assertion for the request

The request parameters can be passed via the manual API:

```csharp
var token = await _tokenManagementService
    .GetAccessTokenAsync(User, new UserAccessTokenRequestParameters {
        // ...
    });
```

â¦the extension methods

```csharp
var token = await HttpContext.GetUserAccessTokenAsync(
    new UserTokenRequestParameters {
        // ...
    });
```

â¦or the HTTP client factory

Program.cs

```csharp
// registers HTTP client that uses the managed user access token
builder.Services.AddUserAccessTokenHttpClient("invoices",
    parameters: new UserTokenRequestParameters {
        // ...
    },
    configureClient: client =>
       {
         client.BaseAddress = new Uri("https://api.company.com/invoices/");
       });


// registers a typed HTTP client with token management support
builder.Services.AddHttpClient<InvoiceClient>(client =>
    {
        client.BaseAddress = new Uri("https://api.company.com/invoices/");
    })
    .AddUserAccessTokenHandler(new UserTokenRequestParameters {
        // ...
    });
```

## Token Storage

[Section titled âToken Storageâ](#token-storage)

By default, the userâs access and refresh token will be store in the ASP.NET Core authentication session (implemented by the cookie handler).

You can modify this in two ways

* the cookie handler itself has an extensible storage mechanism via the `TicketStore` mechanism
* replace the store altogether by providing an `IUserTokenStore` implementation and registering it in the service provider at application startup
