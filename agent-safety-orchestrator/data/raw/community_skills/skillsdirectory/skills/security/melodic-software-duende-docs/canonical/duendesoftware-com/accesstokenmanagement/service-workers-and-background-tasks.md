---
title: Service Workers and Background Tasks
source_url: https://docs.duendesoftware.com/accesstokenmanagement/service-workers-and-background-tasks/
source_type: llms-full-txt
content_hash: sha256:4c4aaa40b719572aaa3b1ab54ecb6b581e98d017d385da24a34efe8c56ef7f65
last_fetched: '2025-12-16T19:17:17Z'
category: accesstokenmanagement
doc_id: accesstokenmanagement/service-workers-and-background-tasks
---

> Learn how to manage OAuth access tokens in worker applications and background tasks using Duende.AccessTokenManagement.

A common scenario in worker applications or background tasks (or really any daemon-style applications) is to call APIs using an OAuth token obtained via the client credentials flow.

The access tokens need to be requested and [cached](/accesstokenmanagement/advanced/client-credentials/#token-caching) (either locally or shared between multiple instances) and made available to the code calling the APIs. In case of expiration (or other token invalidation reasons), a new access token needs to be requested. The actual business code should not need to be aware of this.

For more information, see the [advanced topic on client credentials](/accesstokenmanagement/advanced/client-credentials/).

Sample code

Take a look at the [`Worker` project in the samples folder](https://github.com/DuendeSoftware/foss/tree/main/access-token-management/samples/) for example code.

To get started, you will need to add the `Duende.AccessTokenManagement` package to your solution.

Next, there are two fundamental ways to interact with token management:

1. **Automatic** recommended: You request an `HttpClient` from the `IHttpClientFactory`. This HTTP client automatically requests, optionally renews and attaches the access tokens on each request.
2. **Manually** advanced: You request an access token, which you can then use to (for example) authenticate with services. You are responsible for attaching the access token to requests.

Letâs cover these steps in more detail.

## Adding Duende.AccessTokenManagement

[Section titled âAdding Duende.AccessTokenManagementâ](#adding-duendeaccesstokenmanagement)

Start by adding a reference to the `Duende.AccessTokenManagement` NuGet package to your application.

```bash
dotnet add package Duende.AccessTokenManagement
```

You can add the necessary services to the ASP.NET Core service provider by calling `AddClientCredentialsTokenManagement()`. After that you can add one or more named client definitions by calling `AddClient`.

* V4

  Program.cs

  ```csharp
  services.AddClientCredentialsTokenManagement()
    .AddClient(ClientCredentialsClientName.Parse("catalog.client"), client =>
    {
        client.TokenEndpoint = new Uri("https://demo.duendesoftware.com/connect/token");


        client.ClientId = ClientId.Parse("6f59b670-990f-4ef7-856f-0dd584ed1fac");
        client.ClientSecret = ClientSecret.Parse("d0c17c6a-ba47-4654-a874-f6d576cdf799");


        client.Scope = Scope.Parse("catalog inventory");
    })
    .AddClient(ClientCredentialsClientName.Parse("invoice.client"), client =>
    {
        client.TokenEndpoint = new Uri("https://demo.duendesoftware.com/connect/token");


        client.ClientId = ClientId.Parse("ff8ac57f-5ade-47f1-b8cd-4c2424672351");
        client.ClientSecret = ClientSecret.Parse("4dbbf8ec-d62a-4639-b0db-aa5357a0cf46");


        client.Scope = Scope.Parse("invoice customers");
    });
  ```

* V3

  Program.cs

  ```csharp
  services.AddClientCredentialsTokenManagement()
    .AddClient("catalog.client", client =>
    {
        client.TokenEndpoint = "https://demo.duendesoftware.com/connect/token";


        client.ClientId = "6f59b670-990f-4ef7-856f-0dd584ed1fac";
        client.ClientSecret = "d0c17c6a-ba47-4654-a874-f6d576cdf799";


        client.Scope = "catalog inventory";
    })
    .AddClient("invoice.client", client =>
    {
        client.TokenEndpoint = "https://demo.duendesoftware.com/connect/token";


        client.ClientId = "ff8ac57f-5ade-47f1-b8cd-4c2424672351";
        client.ClientSecret = "4dbbf8ec-d62a-4639-b0db-aa5357a0cf46";


        client.Scope = "invoice customers";
    });


  // in v3, you explicitly need to add a distributed cache implementation, such as in-memory
  services.AddDistributedMemoryCache();
  ```

## Automatic Token Management Using HTTP Factory

[Section titled âAutomatic Token Management Using HTTP Factoryâ](#automatic-token-management-using-http-factory)

You can register HTTP clients with the factory that will automatically use the above client definitions to request and use access tokens.

The following code registers an `HttpClient` called `invoices` which automatically uses the `invoice.client` definition:

* V4

  Program.cs

  ```csharp
  services.AddClientCredentialsHttpClient("invoices",
    ClientCredentialsClientName.Parse("invoice.client"),
    client =>
    {
        client.BaseAddress = new Uri("https://apis.company.com/invoice/");
    });
  ```

  You can also set up a typed HTTP client to use a token client definition, e.g.:

  Program.cs

  ```csharp
  services.AddHttpClient<CatalogClient>(client =>
  {
    client.BaseAddress = new Uri("https://apis.company.com/catalog/");
  })
  .AddClientCredentialsTokenHandler(ClientCredentialsClientName.Parse("catalog.client"));
  ```

* V3

  Program.cs

  ```csharp
  services.AddClientCredentialsHttpClient("invoices",
    "invoice.client",
    client =>
    {
        client.BaseAddress = new Uri("https://apis.company.com/invoice/");
    });
  ```

  You can also set up a typed HTTP client to use a token client definition, e.g.:

  Program.cs

  ```csharp
  services.AddHttpClient<CatalogClient>(client =>
  {
    client.BaseAddress = new Uri("https://apis.company.com/catalog/");
  })
  .AddClientCredentialsTokenHandler("catalog.client");
  ```

Once you have set up HTTP clients in the HTTP factory, no token-related code is needed at all, e.g.:

WorkerHttpClient.cs

```csharp
public class WorkerHttpClient : BackgroundService
{
    private readonly ILogger<WorkerHttpClient> _logger;
    private readonly IHttpClientFactory _clientFactory;


    public WorkerHttpClient(ILogger<WorkerHttpClient> logger, IHttpClientFactory factory)
    {
        _logger = logger;
        _clientFactory = factory;
    }


    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            var client = _clientFactory.CreateClient("invoices");
            var response = await client.GetAsync("test", stoppingToken);


            // rest omitted
        }
    }
}
```

Default resiliency handler in BFF v4

When you use `AddClientCredentialsHttpClient`, the configured HTTP client will include a resiliency message handler which automatically retries the HTTP request in case of a `401 Unauthorized` response.

This retry helps in two scenarios:

* The access token has expired. A new token is requested to retry the original HTTP request.
* Youâre using [DPoP](/accesstokenmanagement/advanced/dpop/). The DPoP request may need to be retried with a nonce value present in the HTTP response.

The retry only happens once: if it still results in `401 Unauthorized`, the response is returned to the caller.

This functionality is **not** included when you use `AddClientCredentialsTokenHandler` when registering your own HTTP clients. You can however add the resiliency message handler manually:

```csharp
services.AddHttpClient<CatalogClient>(client =>
{
    client.BaseAddress = new Uri("https://apis.company.com/catalog/");
})
.AddDefaultAccessTokenResiliency()
.AddClientCredentialsTokenHandler("catalog.client");
```

## Manually Request Access Tokens

[Section titled âManually Request Access Tokensâ](#manually-request-access-tokens)

If you want to use access tokens in a different way or have more advanced needs which the automatic option doesnât cover, then you can also manually request access tokens.

* V4

  You can retrieve the current access token for a given token client via `IClientCredentialsTokenManager.GetAccessTokenAsync`.

  WorkerManual.cs

  ```csharp
  public class WorkerManual(
    IHttpClientFactory factory,
    IClientCredentialsTokenManager tokenManagementService
    ) : BackgroundService
  {
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            var client = factory.CreateClient();
            client.BaseAddress = new Uri("https://apis.company.com/catalog/");


            // get access token for client and set on HttpClient
            var token = await tokenManagementService.GetAccessTokenAsync(
                ClientCredentialsClientName.Parse("catalog.client"), ct: stoppingToken)
                .GetToken();


            client.SetBearerToken(token.AccessToken.ToString());


            var response = await client.GetAsync("list", stoppingToken);


            // rest omitted
        }
    }
  }
  ```

  The result of the GetAccessTokenAsync method is a `TokenResult<ClientCredentialsToken>`. You can interrogate this to see if the result was successful by checking the `Succeeded` property or by calling `WasSuccessful()`. Alternatively, as you see in the example, you can call the `.GetToken()` which will throw if the token couldnât be retrieved.

  You can customize some of the per-request parameters by passing in an instance of `TokenRequestParameters`. This allows forcing a fresh token request (even if a cached token would exist) and also allows setting a per-request scope, resource and client assertion.

* V3

  You can retrieve the current access token for a given token client via `IClientCredentialsTokenManagementService.GetAccessTokenAsync`.

  WorkerManual.cs

  ```csharp
  public class WorkerManual : BackgroundService
  {
    private readonly IHttpClientFactory _clientFactory;
    private readonly IClientCredentialsTokenManagementService _tokenManagementService;


    public WorkerManual(IHttpClientFactory factory, IClientCredentialsTokenManagementService tokenManagementService)
    {
        _clientFactory = factory;
        _tokenManagementService = tokenManagementService;
    }


    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            var client = _clientFactory.CreateClient();
            client.BaseAddress = new Uri("https://apis.company.com/catalog/");


            // get access token for client and set on HttpClient
            var token = await _tokenManagementService.GetAccessTokenAsync("catalog.client");
            client.SetBearerToken(token.Value);


            var response = await client.GetAsync("list", stoppingToken);


            // rest omitted
        }
    }
  }
  ```

  You can customize some of the per-request parameters by passing in an instance of `ClientCredentialsTokenRequestParameters`. This allows forcing a fresh token request (even if a cached token would exist) and also allows setting a per-request scope, resource and client assertion.
