# Sign-in with Google (and phone)

Sign-in in Citewell is **optional by default** and built on Streamlit's own OpenID Connect support. Citewell never sees a password and never stores your name, email or phone number. Signed-in visitors get a higher question limit (`MAX_QUESTIONS_SIGNED_IN`, default 100, versus 30 for anonymous visitors). Set `REQUIRE_LOGIN=true` to make sign-in mandatory.

If nothing below is configured, the app simply has no sign-in and everything else works as before.

## 1. Install the two requirements

Run in Anaconda Prompt (do not re-run the whole `requirements.txt`, which could replace your working PyTorch):

```bat
conda activate citewell
python -c "import streamlit; print(streamlit.__version__)"
pip install "Authlib>=1.3.2"
```

The Streamlit version must be **1.42 or newer**. If it is older: `pip install -U streamlit`.

## 2. Create Google credentials (free)

1. Open the Google Cloud Console (console.cloud.google.com) and create a project, for example "Citewell".
2. Go to **APIs & Services**, then **OAuth consent screen**. Choose **External**, enter an app name (Citewell), your support email and developer email. Keep the default scopes (openid, email, profile).
3. While the app is in **Testing**, only the test users you list can sign in. To let anyone sign in, **publish** the app. These basic scopes do not need Google's verification process.
4. Go to **Credentials**, **Create credentials**, **OAuth client ID**, type **Web application**.
5. Under **Authorized redirect URIs** add both:
   - `http://localhost:8501/oauth2callback`
   - `https://citewell.streamlit.app/oauth2callback`
6. Copy the **Client ID** and **Client secret**.

Google changes its console layout from time to time, so follow the current wording if a label differs.

## 3. Add the secrets

Generate a cookie secret:

```bat
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Streamlit Community Cloud:** app menu, **Settings**, **Secrets**, then add (keep your existing `GROQ_API_KEY` line):

```toml
[auth]
redirect_uri = "https://citewell.streamlit.app/oauth2callback"
cookie_secret = "paste-the-generated-string"

[auth.google]
client_id = "xxxxxxxx.apps.googleusercontent.com"
client_secret = "xxxxxxxx"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

**On your computer:** create `.streamlit/secrets.toml` in the project folder with the same content, but use `redirect_uri = "http://localhost:8501/oauth2callback"`. That file is git-ignored; never commit it.

Restart the app. The sidebar now shows **Account** with **Continue with Google**.

## Phone-number sign-in

Phone sign-in means sending an SMS one-time code, which needs an identity provider with an SMS service (for example Auth0, Firebase or Clerk). SMS delivery usually costs money, and in some countries (India, for example) it needs carrier registration. Citewell does not implement its own SMS codes: that would need a paid SMS gateway and careful abuse protection.

If you set up such a provider, add it as a second provider named `phone`:

```toml
[auth.phone]
client_id = "..."
client_secret = "..."
server_metadata_url = "https://YOUR-PROVIDER/.well-known/openid-configuration"
```

A **Continue with phone number** button then appears automatically, with no code change. Check the provider's current pricing and limits before relying on it.

## Troubleshooting

| Problem | Fix |
|---|---|
| No Account section in the sidebar | Streamlit older than 1.42, Authlib not installed, or no `[auth.google]` secrets. |
| Google says "redirect_uri_mismatch" | The redirect URI in Google must match `redirect_uri` exactly, including `https` and `/oauth2callback`. |
| "Access blocked: app not verified" | The app is still in Testing: add yourself as a test user, or publish it. |
| Sign-in works locally but not on Cloud | Add the Cloud redirect URI in Google, and the `[auth]` secrets in Cloud Settings. |
