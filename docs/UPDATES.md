# FDGCast update feed: website handoff

The 0.6.0 Preview Companion checks its saved HTTPS Hub address at startup,
when pairing changes, daily after success, and hourly after a failed check.
Connections → Updates also offers a manual check. No account token is sent.
The OBS Control dock shows a notice when a newer release is available.
View changes, Download installer and Later are provided. Later remembers the
release version; a subsequent newer version appears again. Nothing installs,
stops a stream or restarts automatically.

## Website work needed

Serve public JSON at **/fdgcast/releases/latest.json**, returning HTTP 200 with
Content-Type application/json. No authentication, OAuth or redirect is needed.
Upload the reviewed Windows installer to the public downloads location first,
then publish the manifest. Use docs/latest-release.example.json as the template.

Required fields: schema_version (1), version (e.g. 0.6.0-preview), platform
(windows-x64), download_url (HTTPS or a relative Hub path). Optional: notes
(plain text, at most 16,000 characters), changes_url (HTTPS or relative Hub path).
Total JSON must be under 64 KiB. Versions use major.minor.patch and optional
-preview, -beta or -rc suffixes (optionally .number). Preview versions are
older than the stable release of the same number. Use a new version for each
shipped build; replacing files under the same version does not trigger notices.

Download/changelog links must stay on the saved Hub hostname or under the
https://github.com/Dakotalamb/ForgeCast/releases/ path. The repository is private,
so host the installer publicly on the Hub for ordinary users. Signed storage/CDN
URLs on a different hostname are not supported by this release; use a public
same-host download endpoint instead. The Hub itself must use HTTPS port 443.
Keep the feed fresh (Cache-Control: no-cache is recommended). CORS is unnecessary:
Companion fetches it server-side.

The update notice is informational. Download opens the approved link using the
user's browser; the installer remains a manual action. Close OBS and Companion
before running it over an existing install. Existing local configuration and
Windows-protected secrets are preserved by the installer. The feed must only
point to an installer you have reviewed and published. This preview does not
provide in-app binary downloading, signature verification or silent installation.

## End-to-end acceptance check

Install 0.6.0 Preview and pair the Hub. Publish a deliberately newer test version
with a valid test download. Check that Companion and OBS Control show it, release
notes open, Later persists after restarting Companion, and a further newer
version is shown. Check that the old/current version gives no banner. Unavailable,
malformed or oversized feeds must produce an unobtrusive update status, leaving
streaming and chats running. Do not publish a fictitious newer version to users.
