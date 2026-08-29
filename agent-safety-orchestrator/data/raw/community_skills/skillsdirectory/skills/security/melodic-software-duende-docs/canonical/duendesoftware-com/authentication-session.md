---
title: Authentication Session
source_url: https://docs.duendesoftware.com/authentication-session/
source_type: llms-full-txt
content_hash: sha256:93359029fc6f1f3f7bce84c98699d3cb2c2fbc77c7a265d2f3e50b9cc9362e3b
doc_id: authentication-session
---

> Guide to establishing and configuring authentication sessions in IdentityServer using ASP.NET Core's cookie authentication system, including required claims, session management, and cookie handler configuration options.

Regardless of how the user proves their identity on the login page, an authentication session must be established. This authentication session is based on ASP.NET Coreâs authentication system, and is tracked with a cookie managed by the [cookie authentication](https://docs.microsoft.com/en-us/aspnet/core/security/authentication/cookie) handler.

To establish the session, ASP.NET Core provides a `SignInAsync` extension method on the `HttpContext`. This API accepts a `ClaimsPrincipal` which contains claims that describe the user. IdentityServer requires a special claim called `sub` whose value uniquely identifies the user. On your login page, this would be the code to establish the authentication session and issue the cookie:

```csharp
var claims = new Claim[] {
    new Claim("sub", "unique_id_for_your_user")
};
var identity = new ClaimsIdentity(claims, "pwd");
var user = new ClaimsPrincipal(identity);


await HttpContext.SignInAsync(user);
```

Note

The `sub` claim is the [subject identifier](https://openid.net/specs/openid-connect-core-1_0.html#standardclaims) and is the most important claim your IdentityServer will issue. It will uniquely identify the user and must never change and must never be reassigned to a different user. A GUID data type is a very common choice for the `sub`.

Additional claims can be added to the cookie if desired or needed at other UI pages. For example, itâs common to also issue a `name` claim which represents the userâs display name.

The claims issued in the cookie are passed as the `Subject` on the [ProfileDataRequestContext](/identityserver/reference/services/profile-service/#duendeidentityservermodelsprofiledatarequestcontext) in the [profile service](/identityserver/fundamentals/claims/).

## Well Known Claims Issued From the Login Page

[Section titled âWell Known Claims Issued From the Login Pageâ](#well-known-claims-issued-from-the-login-page)

There are some claims beyond `sub` that can be issued by your login page to capture additional information about the userâs authentication session. Internally Duende IdentityServer will set some of these values if you do not specify them when calling `SignInAsync`. The claims are:

* **`name`**: The display name of the user.
* **`amr`**: Name of the [authentication method](https://tools.ietf.org/html/rfc8176) used for user authentication ( defaults to `pwd`).
* **`auth_time`**: Time in epoch format the user entered their credentials (defaults to the current time).
* **`idp`**: Authentication scheme name of the external identity provider used for login. When not specified then the value defaults to `local` indicating that it was a local login. This is used to determine if a user must re-authenticate when clients make [authorization requests](/identityserver/reference/endpoints/authorize/) using the acr\_values with an idp value, or the client has `IdentityProviderRestrictions`. If the userâs idp does not match the request, then they should re-authenticate.
* **`tenant`**: Tenant identifier the user is associated with (if needed). This is used to determine if a user must re-authenticate when clients make [authorization requests](/identityserver/reference/endpoints/authorize/) using the `acr_values` with a `tenant` value. If the userâs tenant does not match the request, then they should re-authenticate.

While you can create the `ClaimsPrincipal` yourself, you can alternatively use IdentityServer extension methods and the `IdentityServerUser` class to make this easier:

```csharp
var user = new IdentityServerUser("unique_id_for_your_user")
{
    DisplayName = user.Username
};


await HttpContext.SignInAsync(user);
```

## Cookie Handler Configuration

[Section titled âCookie Handler Configurationâ](#cookie-handler-configuration)

Duende IdentityServer registers a cookie authentication handler by default for the authentication session. The scheme that the handler in the authentication system is identified by is from the constant `IdentityServerConstants.DefaultCookieAuthenticationScheme`.

When configuring IdentityServer, the [AuthenticationOptions](/identityserver/reference/options/#authentication) expose some settings to control the cookie (e.g. expiration and sliding). For example:

Program.cs

```csharp
builder.Services.AddIdentityServer(options =>
{
    options.Authentication.CookieLifetime = TimeSpan.FromHours(1);
    options.Authentication.CookieSlidingExpiration = false;
});
```

Note

In addition to the authentication cookie, IdentityServer will issue an additional cookie which defaults to the name `idsrv.session`. This cookie is derived from the main authentication cookie, and it used for the check session endpoint for [browser-based JavaScript clients at signout time](/identityserver/ui/logout/notification/#browser-based-javascript-clients). It is kept in sync with the authentication cookie, and is removed when the user signs out.

If you require more control over the cookie authentication handler you can register your own cookie handler. You can then configure IdentityServer to use your cookie handler by setting the `CookieAuthenticationScheme` on the [AuthenticationOptions](/identityserver/reference/options/#authentication). For example:

Program.cs

```csharp
builder.Services.AddAuthentication()
    .AddCookie("your_cookie", options => {
        // ...
    });


builder.Services.AddIdentityServer(options =>
{
    options.Authentication.CookieAuthenticationScheme = "your_cookie";
});
```

If the `CookieAuthenticationScheme` is not set, the `DefaultAuthenticationScheme` configured for ASP.NET Core will be used instead. Note that the `AddAuthentication` call that sets the default can come after the `AddIdentityServer` call. For example:

Program.cs

```csharp
// No cookie authentication scheme is set here.
// Identity Server will use the default scheme from ASP.NET Core,
// even though it is not yet defined.
builder.Services.AddIdentityServer();


// Default scheme is registered. IdentityServer will use this scheme.
builder.Services.AddAuthentication(defaultScheme: "your_cookie")
    .AddCookie("your_cookie", options => {
        // ...
    });
```
