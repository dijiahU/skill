---
title: Accepting Local Credentials
source_url: https://docs.duendesoftware.com/accepting-local-credentials/
source_type: llms-full-txt
content_hash: sha256:435a33539e7976e53eb96bf411581a90cd431ba1b45587beee6747eb679bfa7b
doc_id: accepting-local-credentials
---

> Guide to implementing a local login page in IdentityServer that validates username/password credentials, issues authentication cookies, and includes a sample Razor Page implementation.

The steps for implementing a local login page are:

* Validate the userâs credentials
* Issue the authentication cookie
* Redirect the user to the return URL

The code below shows a sample Razor Page that could act as a login page. This sample hard codes the logic for the credentials. In production code, use your custom user database or identity management library here.

If you are using ASP.NET Identity for user management, our Identity Server ASP.NET Identity (`isaspid`) [template](/identityserver/overview/packaging/#templates) includes a login page that shows how you might use the abstractions of that library on your login page. Notably, it uses the `SignInManager` to start the session, rather than `HttpContext.SignInAsync`.

This is the cshtml for the login Razor Page:

```html
@page
@model Sample.Pages.Account.LoginModel
@addTagHelper *, Microsoft.AspNetCore.Mvc.TagHelpers


<div asp-validation-summary="All"></div>


<form method="post">
    <input type="hidden" asp-for="ReturnUrl" />


    <div>
        <label asp-for="Username">Username</label>
        <input asp-for="Username" autofocus>
    </div>
    <div>
        <label asp-for="Password">Password</label>
        <input type="password" asp-for="Password" autocomplete="off">
    </div>


    <button type="submit">Login</button>
</form>
```

And this is the code behind for the login Razor Page:

```csharp
namespace Sample.Pages.Account
{
    public class LoginModel : PageModel
    {
        [BindProperty(SupportsGet = true)]
        public string ReturnUrl { get; set; }
        [BindProperty]
        public string Username { get; set; }
        [BindProperty]
        public string Password { get; set; }


        public async Task<IActionResult> OnPost()
        {
            if (Username == "alice" && Password == "password")
            {
                var claims = new Claim[] {
                    new Claim("sub", "unique_id_for_alice")
                };
                var identity = new ClaimsIdentity(claims, "pwd");
                var user = new ClaimsPrincipal(identity);


                await HttpContext.SignInAsync(user);


                if (Url.IsLocalUrl(ReturnUrl))
                {
                    return Redirect(ReturnUrl);
                }
            }


            ModelState.AddModelError("", "Invalid username or password");


            return Page();
        }
    }
}
```

When IdentityServer redirects to the [LoginUrl](/identityserver/ui/login), the user should arrive at this page. If youâre using the default urls, then this page should be created at the path: \~/Pages/Account/Login.cshtml, which allows it to be loaded from the browser at the â/Account/Loginâ path.

Note

While you can use any custom user database or identity management library for your users, we provide first class [integration support](/identityserver/aspnet-identity/) for ASP.NET Identity.
